# VSS Architecture and How It Maps to Ours

> **Errata (2026-09-23):** E11, E12, E18, E19, E28 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

All **[V]** claims were verified by reading the VSS repo on 2026-09-18. VSS is actively
developed — re-verify citations before relying on them.

## Repository shape **[V]**

```
video-search-and-summarization/
├── services/
│   ├── agent/                # Agentic / offline processing
│   ├── alert/                # Alert verification and delivery
│   ├── analytics/            # Downstream metadata enrichment
│   ├── configurators/        # vss-configurator, vss-rt-config-adaptor
│   ├── rtvi/                 # Real-time video intelligence tier
│   │   ├── rt-cv/            # Detection and tracking (2D)
│   │   ├── rt-cv-3d/         # Detection and tracking (3D)
│   │   ├── rt-embed/         # Video/text embeddings
│   │   └── rt-vlm/           # Streaming and file VLM inference
│   ├── sdrc/
│   ├── ui/
│   ├── video-summarization/  # The summarization pipeline + config graph
│   └── vios/
├── libs/
│   ├── analytics/
│   ├── nvschema/
│   └── vss/                  # core/ (vss_core) and cli/ (vss_cli)
├── deploy/{docker,helm}/
├── docs/                     # .mdx documentation
├── skills/                   # Agent-facing reference docs (very useful)
└── tools/
```

**`skills/` is the highest-value documentation in the repo.** It is written for agents and is more
concrete than `docs/`. Start with `skills/vss-build-vision-ai/references/`.

## The pipeline mapping

VSS did **not** replace small specialized models with one monolithic VLM. Its `services/rtvi/`
tier is a perception pipeline with the same decomposition as ours **[V]**:

| Our pipeline (`ai/`)              | VSS equivalent                              | VSS model families **[V]**                                    |
| --------------------------------- | ------------------------------------------- | ------------------------------------------------------------- |
| YOLO26 — object detection         | **RT-CV**                                   | RT-DETR, GDINO, Sparse4D (3D), selected via `DS_MODEL_FAMILY` |
| CLIP — embeddings / re-ID         | **RT-Embed**                                | Cosmos-Embed1 (default), `nemotron-embed-vl-1b-v2`            |
| Florence-2 — attribute extraction | **RT-VLM**                                  | Cosmos Reason, Nemotron VL, Qwen3-VL                          |
| Nemotron v3 Nano — risk reasoning | **LLM slot**                                | Nemotron 3.5 Lightning 30B-A3B, Nemotron Nano 9B v2 FP8       |
| `ai/enrichment/model_registry.py` | `COMPOSE_PROFILES` keys + `DS_MODEL_FAMILY` | —                                                             |

RT-CV capability keys **[V]** (`skills/vss-build-vision-ai/references/services/rt-cv.md`):

| Capability                  | Profile key                           | Foundation             | Model family          |
| --------------------------- | ------------------------------------- | ---------------------- | --------------------- |
| Detection and tracking      | `rtvi-cv`                             | Foundation-independent | via `DS_MODEL_FAMILY` |
| Alerts perception           | `perception-alerts`                   | `alerts`               | GDINO                 |
| Search detection + tracking | `perception-2d-fusion`                | `search`               | RT-DETR               |
| Warehouse 2D perception     | `perception-2d`                       | `warehouse`            | RT-DETR               |
| Warehouse 3D perception     | `perception-3d`, `ds-configurator-3d` | `warehouse`            | Sparse4D              |

`rtvi-cv` is profile-neutral — it can join the graph without adopting a Foundation's model family.

## The composition model **[V]**

`services/video-summarization/config/config.yaml` is a declarative `tools` / `functions` graph:

```yaml
tools:
  vector_db: { type: milvus, params: { host, port }, tools: { embedding: nvidia_embedding } }
  elasticsearch_db: { type: elasticsearch, params: { host, port, collection_name: lvs-events } }
  graph_db_arango: { type: arango, params: { host, port, username, password } }
  graph_db: { type: neo4j, params: { host, port, username, password } }
  nvidia_llm: { type: llm, params: { model, base_url, max_tokens, temperature, top_p, api_key } }
  nvidia_embedding: { type: embedding, params: { enable, model, base_url, api_key } }

functions:
  summarization:
    type: vlm_structured_summarization
    params: { time_overlap_threshold, max_events_per_batch, kafka_enabled, enable_llm_merging }
    tools:
      db: !ENV ${LVS_DATABASE_BACKEND:elasticsearch_db}
      llm: nvidia_llm
```

Two structural observations:

- **Four database backends coexist behind a `type:` discriminator.** That is an adapter pattern
  proven by repetition, which implies an interface a fifth implementation could satisfy. Whether
  that interface is _clean_ — versus four divergent contracts with function-specific coupling — is
  **[?]** and under investigation.
- **`LVS_DATABASE_BACKEND` is an env-selectable backend chooser with a default.** The seam is
  already exposed as configuration, not just as code structure.

## RT-VLM deployment modes **[V]**

From `skills/vss-build-vision-ai/references/services/rt-vlm.md`:

- **Integrated mode** — needs model credentials and cache access, but no standalone VLM NIM.
- **OpenAI-compatible mode** — needs a reachable endpoint and matching `VLM_NAME`.
- **Kafka** is required when `RTVI_VLM_MESSAGE_BUS=kafka`, described as "the current Compose
  default."

`VLM_MODEL_TO_USE` values seen in-tree **[V]**: `cosmos-reason2`, `cosmos-reason3`,
`openai-compat`, `vllm-compatible`, `custom`.

## Bring-your-own-model **[V]**

`skills/deployment/vss-deploy-video-embedding/references/byom-custom-model.md` documents a real
BYOM contract — but it is **scoped to RT-Embed**, not to arbitrary pipeline stages:

- Reference implementation: `services/rtvi/rt-embed/src/models/custom/samples/cosmos-embed1/`
- Loader env vars: `MODEL_PATH`, `MODEL_IMPLEMENTATION_PATH`, `MODEL_REPOSITORY_SCRIPT_PATH`
- The implementation path must contain `inference.py`; the dynamic loader imports it and
  instantiates a `BaseVlmModel` subclass.
- Optional Triton optimization via `create_triton_model_repo.py` + `config.pbtxt`.

## Infrastructure weight

Stateful dependencies referenced in the config graph **[V]**: Milvus, Elasticsearch, Neo4j,
ArangoDB, and Kafka. For a single-box consumer deployment this is the heaviest part of VSS —
heavier, arguably, than the GPU requirement.

Mitigating signal **[V]**: in `config.yaml`, the summarization function carries
`kafka_enabled: !ENV ${KAFKA_ENABLED:false}` — **the default is false**. Meanwhile
`RTVI_VLM_MESSAGE_BUS=kafka` is the Compose default. Two defaults pointing opposite directions
suggests Kafka is decoupling rather than durability in at least some paths. Not yet resolved:
**[?]**.

## Credentials **[V]**

`skills/vss-build-vision-ai/references/edge.md` requires `NGC_API_KEY` or `NGC_CLI_API_KEY` plus
`docker login nvcr.io` to pull **private** NIM images, and `NVIDIA_API_KEY` for agent-side NVIDIA
API calls when a profile uses them.

Whether these are needed at pull time only (acceptable — the developer pulls once) or at runtime
per user (fatal for a consumer product) is **[?]** and under investigation. This is one of the
highest-stakes open questions in the whole evaluation.

## Doctrine worth borrowing **[V]**

From `skills/vss-build-vision-ai/references/sizing.md`:

> Never silently substitute a smaller model, lower precision, or remote endpoint. [...] If the
> requested shape does not fit, show the measured capacity and required budget, then ask the user
> to choose a different placement.

This is the same discipline the test-platform program enforces ("never widen a gate to pass",
"floors never lowered"). The two codebases already agree about what honesty means.

## Related

- [`02-model-inventory.md`](02-model-inventory.md) — the models and their VRAM budgets
- [`03-open-questions.md`](03-open-questions.md) — unresolved questions
- [`ai/AGENTS.md`](../../ai/AGENTS.md) — the pipeline this would replace
