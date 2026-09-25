# Lean Backend Feasibility: Can We Avoid VSS's Infrastructure?

> **Errata (2026-09-23):** E1, E19, E20, E21, E22, E23, E24 in [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md) correct claims in this document. The original text is kept as the record; read those entries before relying on it. Current design: [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).

**Investigated 2026-09-19**, 8 agents with two adversarial challengers. Verified against VSS
`cdad5cc0e` and `NVIDIA/context-aware-rag@3.1.0`.

**Question asked:** must we adopt VSS's data pipeline (Milvus, Elasticsearch, Neo4j, ArangoDB,
Kafka), or could we contribute a lightweight backend mimicking our Redis infrastructure?

## Direct answer

**No, you don't have to adopt it — but "mimic our Redis" is the wrong shape of the right
instinct**, and it is a bigger job than a config change. Three corrections, in order of
importance.

### Correction 1: the abstraction is not in the VSS repo **[V]**

It lives in **`NVIDIA/context-aware-rag` (CAR)**, a pip dependency pinned at
`services/video-summarization/docker/Dockerfile:67,72`. A fifth backend is a PR to a **second
repository**, with its own review queue and its own squashed-release cadence.

The registry itself is genuine: `@register_tool_config("<type>")` + `@register_tool(config=…)`
populate two module dicts; `ToolFactory.create_all_tools` (`src/vss_ctx_rag/tools/tool_factory.py:210-252`)
topo-sorts and importlib-resolves them. Tiers are `Tool` (1 abstract method) → `StorageTool` (8) →
`VectorStorageTool` (+4). The deployed `vlm_structured_summarization` declares no
`ALLOWED_TOOL_TYPES`, and `_validate_tool_types` treats absent as any-allowed — so a new type
needs no whitelist patch.

### Correction 2: the role maps to Postgres, not Redis **[V]**

The component being replaced is a **document store**. In this product that role is **Postgres** —
`backend/models/event.py:90,192-256` (TSVECTOR + GIN, BRIN, JSONB GIN).

Our Redis is **transport and runtime state**: 58 of 204 service modules, a 2,820-line facade,
Streams + DLQ, 44 pub/sub sites. There is no "mimic ours" — there are two separable contributions
on opposite sides of the system.

### Correction 3: the easy half and the hard half are swapped **[V]**

The message bus you assumed was hard is **already built**: `MessageBus.KAFKA/REDIS` at
`rt-vlm/src/api_models/config.py:46-50`, `XADD MAXLEN~`, `STREAM_TYPE=redis`.

But it does not buy what you want. **Every Logstash `output {}` in the tree — including the entire
`pipelines/redis/` set — sinks to `elasticsearch:9200`.** `STREAM_TYPE=redis` replaces Kafka _in
front of_ Logstash; Elasticsearch stays. There is no Logstash Redis output anywhere.

## The abstraction is shallower than it looks **[V]**

Real, but not a _behavioral_ contract:

- **Signature divergence.** The ABC's `filter_chunks` takes 7 params (`storage_tool.py:100-111`);
  Neo4j's takes 4 — and its _second positional_ is `max_end_time` where the ABC's is
  `max_start_time` (`neo4j_db.py:320-325`). Python ABCs don't check signatures; this instantiates
  and then `TypeError`s or silently mis-binds.
- **Semantic divergence.** Milvus filters `doc_type == 'caption'` (`milvus_db.py:443`);
  Elasticsearch filters `'caption_summary'` (`elasticsearch_db.py:406`) — which is what the
  writers actually emit. Same method, same call, two document universes. **No oracle exists to
  tell a new implementer which is right:** `tests/` is 7 unit files, none touching storage.
- **The live write path is outside the abstraction, and in Ruby.**
  `deploy/docker/services/infra/elk/logstash/pipelines/kafka/mdx-lvs-logstash.conf:1-18`
  hard-copies `ElasticsearchDBTool.add_summary`'s private document layout, including a hand-rolled
  null embedding.
- **VSS itself is not change-free.** `via_stream_handler.py:505` and `:1861` branch on the literal
  `"elasticsearch_db"`, and `:505`'s default is `"vector_db"` — so `LVS_DATABASE_BACKEND=redis_db`
  **takes the Milvus branch** and injects Milvus config at startup; `:1861` silently no-ops
  `_store_event_prompt_in_db`. **"One YAML block, no Python change" is false.**

## Capability table **[V]** — Redis 8 tested live

| Capability                                                                                                             | VSS today                    | Redis 8 / Postgres                                                                                                                                                    | Matters at home scale?                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Time-range + metadata filter — **the only storage capability the shipped path exercises** (6 live `self.db.*` methods) | ES terms+range+max+sort      | **Yes.** Verified on `redis:8.10-alpine`: `FT.SEARCH '@doc_type:{…} @start_ntp_float:[110 140]' SORTBY chunkIdx` and `FT.AGGREGATE … REDUCE MAX` give exact semantics | **Yes — and fully covered**                                                                                         |
| Full-text / BM25                                                                                                       | ES only                      | Redis `SCORER BM25STD` verified. PG `ts_rank` ≠ BM25 (no IDF)                                                                                                         | Partly; ranking differs                                                                                             |
| Vector ANN                                                                                                             | Milvus, ES dense_vector      | Redis 8 ships RediSearch HNSW auto-loaded                                                                                                                             | **No** — shipped VSS sets `LVS_EMB_ENABLE=false` → `NullEmbedding`. At 3k-15k docs a flat numpy scan beats an index |
| Graph traversal                                                                                                        | Neo4j 1729 LoC / Arango 1359 | **Neither.** `GRAPH.QUERY` → `ERR unknown command`; RedisGraph is EOL                                                                                                 | No — no shipped profile enables it                                                                                  |
| Message bus                                                                                                            | Kafka default                | Redis Streams already first-class; XGROUP/XREADGROUP/XAUTOCLAIM verified                                                                                              | Largely built — but see above                                                                                       |
| Durable replay                                                                                                         | Kafka                        | Sufficient. Zero `cleanup.policy`/`transactional_id`/`isolation_level` in VSS; 4h retention; `auto_offset_reset=latest`                                               | No                                                                                                                  |

**Weigh the infrastructure:** `KAFKA_HEAP_OPTS -Xmx6G` + Logstash 1G + ES 1G ≈ **8 GB of heap**
(`infra/compose.yml:181,292,119`) against a 24 GB budget. The Redis test instance: **32.5 MB RSS**.

## What a lean profile costs **[A]**

Minimum honest slice — file summarization only, `kafka_enabled: false`, single box, no
ES/Kafka/Logstash/Milvus:

- ~500 LoC backend in CAR (no new dependency — `redis==5.2.1` is already at `pyproject.toml:43`)
- The project's **first storage conformance harness** (~400 LoC; none exists today)
- The two VSS literal-branch fixes
- A `dev-profile-*` directory (name enforced by `.github/scripts/check_folder_structure.py:33-42`)

**4-5 engineer-weeks across two repos, plus 4-8 weeks of review calendar.**

Unavailable in that profile: `/aggregate_live_stream` and the two live-stream endpoints that
hard-400 at `KAFKA_ENABLED=false` (`via_server.py:1031,1108`); `_store_event_prompt_in_db`; the 5
graph functions; the 2 Milvus-coupled foundation functions. Note `dev-profile-lvs/.env:124` sets
`KAFKA_ENABLED=true` — so the lean profile covers the path the shipped profile _doesn't_ use.

## Recommendation: overlay, don't contribute — yet

Both challengers agreed on **sequencing** and split on the **artifact**. The sequencing agreement
is the one that matters: **do not open an upstream PR first.**

1. **Ship the lean profile as a downstream package plus config in our own tree.** VSS prunes
   unreferenced tools, so nothing forces a fork.
2. **Send a conformance-test PR as the relationship opener.** `test_storage_conformance.py` needs
   no new dependency (their `license-diff.yaml` hard-fails dependency changes) and runs in their
   existing docker-less `unit-tests` job. Writing it surfaces the `caption`/`caption_summary` bug
   and the Neo4j signature as **real defects with patches attached.** _If they won't merge a test
   file, they won't maintain a backend._
3. **If a storage backend ever goes upstream, make it SQLite, not Redis** — same 13 methods,
   stdlib, zero containers, durable across power loss (VSS's own `redis.conf:1407` ships
   `appendonly no`), and it answers open security issue #2127 by deleting the attack surface.
4. **Lead with GPU topology, not storage.** The contribution nobody else can make is llama.cpp/GGUF
   co-resident with perception on one card — sidestepping the two-vLLM-engines-per-GPU hard error
   VSS documents as unsolvable — plus event-triggered duty-cycling against VSS's `always-on`.
   Pitch it as "the profile below `dev-profile-base`," with storage as the footnote. See
   [`05-hardware-profiles.md`](05-hardware-profiles.md).

### Caveat against Redis specifically **[V]**

`docker-compose.prod.yml:562` pins `redis:7.4-alpine3.21` — **no Query Engine, no vector type.**
VSS's Redis is currently more capable than ours. The "reuse our existing infrastructure" benefit is
**illusory until we bump to 8.x.**

## Governance finding **[A]**

Zero third-party merges. #1248 open since July. **#1345 closed with "we are considering adding
Redis Stream support in a future update"** — a maintainer saying they intend to build this
themselves. The alert Redis bridge was deliberately fenced (commits `c0eb2e9f2`, `8e802d91e`, with
`test_event_bridge_factory.py:16-27` pinning the refusal).

That record describes what happens to _outsiders_. **You are `@nvidia.com`** — which is why the
organizational check below outranks the technical one.

## Verify first — two cheap checks, in parallel

**Technical (one afternoon).** On the shipped LVS profile, set `LVS_DATABASE_BACKEND` to any
non-`elasticsearch_db` value and run a file summarization plus `/aggregate_live_stream`. You will
hit the `:505` Milvus injection, the `:1861` silent no-op, and an empty live aggregate. Whatever
breaks is the true VSS-side cost, and it is currently undocumented.

**Organizational (one message — highest expected value in the program).** Ask the VSS team: is a
consumer/GeForce profile on the roadmap; is Redis Streams theirs or ours; why was the alert Redis
bridge fenced; and can you borrow a 5090. **Every downstream option is priced differently by those
answers.**

## Unverified **[?]**

`retrieve_docs` was reportedly added as a new `@abstractmethod` between CAR 3.0.0 and 3.1.0 (from
the GitHub API, not re-checked). If true, **any out-of-tree `StorageTool` was broken inside one
seven-week window** — the strongest argument for in-core placement, or for not shipping a backend
at all.

## Related

- [`05-hardware-profiles.md`](05-hardware-profiles.md) — the GPU-topology contribution
- [`03-open-questions.md`](03-open-questions.md) — Q4 and Q5 answered here
