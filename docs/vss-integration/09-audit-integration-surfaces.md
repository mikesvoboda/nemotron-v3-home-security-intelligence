# 09 — Audit: VSS Integration Surfaces (What Can We Incorporate?)

> **Provenance.** Independent read-only audit by a research subagent ("Auditor B") on
> 2026-09-23, against VSS `1e94133b4` (`origin/develop`; 78 commits after the `cdad5cc0e`
> baseline that docs 00-07 cite). Scope: component contracts — RT-VLM, RT-CV, RT-Embed, agent/LLM slot, Alert Bridge, message bus, LVS, schemas. Evidence markers follow [`AGENTS.md`](AGENTS.md).
> Corrections it raises against docs 00-07 are consolidated in
> [`11-errata-2026-09-23.md`](11-errata-2026-09-23.md). The design it fed is
> [`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md).
> Line citations resolve at `1e94133b4`; VSS moves fast, so re-verify before relying on one.

**Audited:** VSS `origin/develop` = `1e94133b4` (2026-09-23). The previous research pass audited `cdad5cc0e` (2026-09-19).
**Our repo:** `feat/vss-gaming-gpu-profile` @ `4eab98e5`.
**Scope:** integration contracts, component by component. Profile anatomy, `dev-profile.sh` placement logic, GPU-architecture support and CI belong to Auditor A. This report covers them only where a component's own constraints depend on them.

## Conventions

**Evidence markers** (from `docs/vss-integration/AGENTS.md`):

| Marker  | Meaning                                |
| ------- | -------------------------------------- |
| **[V]** | Read in this session, with `path:line` |
| **[C]** | Computed; the formula is shown         |
| **[E]** | External; the command or URL is given  |
| **[?]** | Open                                   |
| **[A]** | Inferred, not verified                 |

**Paths:**

- Bare paths are relative to the VSS worktree.
- `ours:` prefixes paths in this repository.
- `llama.cpp@b7972:` means the llama.cpp tag our Nemotron container is pinned to (`ours:ai/nemotron/Dockerfile:24`, `RUN git checkout b7972`) **[V]**.

**How the audit ran:** four parallel sub-audits covered RT-VLM, RT-CV/RT-Embed, agent/LVS, and alerts/bus/nvschema. I re-read the load-bearing citations myself before writing:

- the RT-VLM substring trigger;
- `extra="forbid"`;
- the xgrammar mapping;
- the openai-compat request shape;
- `AlertSeverity`;
- the shared-GPU sizing lines;
- the NIM ≥32 GB floor;
- our `nvext.guided_json` probe.

**Registry checks** used the anonymous ghcr and nvcr v2 token APIs with `curl`. `skopeo` is not installed. No image was pulled.

---

## Headline

1. **The VSS technology most worth adopting is a pattern, not a container.** The pattern is VLM-as-verifier on CV-triggered candidates, with a constrained yes/no or JSON verdict. VSS's Alert Bridge implements it (Apache-2.0 source), and RT-VLM's xgrammar `choice`/`json_schema` supplies the constraint. We can run the same pattern on llama.cpp, which we already operate, without Kafka, Elasticsearch, DeepStream or vLLM.
2. **Our own structured-output guarantee is weaker than it looks, and VSS exposes this.**
   - Our analyzer sends NIM-only `nvext.guided_json` to llama.cpp's native `/completion` endpoint.
   - It treats any 2xx as "supported".
   - llama.cpp's `/completion` takes `json_schema`/`grammar`, not `nvext`.
   - Unparseable output falls back to **score 50 → `medium`**, which is exactly the failure mode the product must not have (§9).
3. **Every VSS model service is always-on resident, and none has an unload path.** llama.cpp@b7972 already has `--sleep-idle-seconds` and router-mode `/models/unload` **[E]**. Duty cycling therefore remains our contribution, not something we can borrow.
4. **Only RT-VLM and RT-Embed run with zero Kafka and zero Elasticsearch.**
   - Alert Bridge is fenced to Kafka + ES.
   - Every read path (the VA-API, the UI, the agent's search and incident tools) needs ES.
   - Redis 7.4 satisfies every Redis command VSS uses. VSS never needs Redis 8 or the Query Engine.
5. **One existing claim must be withdrawn: "two vLLM engines cannot share one GPU".** VSS ships LLM + RT-VLM co-resident on one H100 or RTX PRO 6000 at `0.40 + 0.40` and has measured it. The blocker on consumer cards is capacity (the ≥32 GB INT4 LLM NIM floor, the 0.7 default reservation), not topology.

---

## 1. RT-VLM (`services/rtvi/rt-vlm`)

### (a) What it does

RT-VLM is a FastAPI server (`src/server/rtvi_vlm_server.py`, 4030 lines). It wraps three parts:

- a GStreamer/DeepStream decode front end;
- an asset manager for files, URLs, RTSP and VIOS webhooks;
- an **in-process vLLM engine** selected by `VLM_MODEL_TO_USE` **[V]**.

The six backends are `openai-compat`, `vllm-compatible`, `cosmos-reason1/2/3` and `custom` (`src/vlm_pipeline/vlm_pipeline.py:228-234`) **[V]**. Media is chunked and frames are sampled. Captions come back over REST/SSE, and nvschema protobuf (`VisionLLM`, `Incident`) can be published to Kafka or Redis Streams (`src/server/rtvi_stream_handler.py:1825-1830,1992-1999,2476-2490`) **[V]**.

`src/server/alert_verification_server.py` is dormant: it has routes and a `__main__`, but nothing launches it (`:246-763,:1173`) **[V]**.

**01's claim that "BYOM is RT-Embed-only" is incomplete.** RT-VLM also has a `custom` loader: `VLM_MODEL_TO_USE=custom` + `MODEL_IMPLEMENTATION_PATH` (`src/scripts/start_rtvi_vlm.sh:236-239`; `vlm_pipeline.py:240-259`) **[V]**.

### (b) External contract

**REST** (prefix `/v1`, `rtvi_vlm_server.py:128`; it matches `api_spec/openapi.json`, 26 paths) **[V]**:

| Route                                                                                      | Line                 |
| ------------------------------------------------------------------------------------------ | -------------------- |
| `POST /v1/files` (multipart, server-side `filename`, or `url`)                             | 1718                 |
| `GET/DELETE /v1/files[/{id}]`, `/content`                                                  | 1973-2091            |
| `POST /v1/streams/add`, `DELETE /v1/streams/delete/{id}` (RTSP)                            | 2114, 2319           |
| `POST /v1/stream/add` / `remove` (VIOS webhook format)                                     | 2452, 2602           |
| `POST /v1/config` (runtime message-bus switch)                                             | 2390                 |
| `GET /v1/models`                                                                           | 2718                 |
| `POST /v1/generate_captions`, `DELETE /v1/generate_captions/{stream_id}`                   | 2756, 3089           |
| `POST /v1/chat/completions`, `POST /v1/completions`                                        | 3146, 3723           |
| health and readiness (`/v1/ready`, `/live`, `/startup`, `/metrics`, NIM-style `/health/*`) | 1585-1704, 3773-3849 |

**OpenAI-compatible surface** (`src/api_models/nim_compat.py`):

- Content parts are only `text`, `image_url` and `video_url` (`:58`). Roles are only `system`, `user` and `assistant` (`:95`) **[V]**.
- `image_url.url` accepts a URL or base64 data URI up to 10 MB of characters (`:34-37`) **[V]**.
- `response_format: Optional[dict]` is present (`:250`) **[V]**.
- **Every request model is `extra="forbid"`** (`src/api_models/common.py:140-145`) **[V]**. **A request carrying `tools` or `tool_choice` gets 422, so RT-VLM cannot be the agent's tool-calling LLM** **[C]** (no such field + forbid).
- Only the first media URL is used (`rtvi_vlm_server.py:3226`). A request with no media goes to text-only chat on the loaded VL model (`:3319`, `:580-655`) **[V]**.
- `model` must equal the advertised id, or the call returns `400 No such model` (`:3754`) **[V]**.

**`/v1/generate_captions`** (`VlmQuery`, `src/api_models/captions.py:285-690`) **[V]**:

- `id`: a UUID, or a list of up to 50.
- `url`: `http(s)`, `s3` or `file://`.
- `media_type`: `"image"` or `"video"`, default `video` (`:361`).
- `system_prompt`: defaults to env `VLM_SYSTEM_PROMPT` (`:380-381`).
- Also: `prompt`, `response_format`, `stream`, sampling parameters, `chunk_duration`, `enable_reasoning`, `alert_category`.
- The response is `chunk_responses[].content`, a **string**. The caller parses the JSON (`:150-275`).

**Input modes: a single still JPEG is first-class** **[V]**:

- `MediaType = {VIDEO, IMAGE}` (`src/api_models/file.py:32-36`).
- Images are probed (`utils/media_file_info.py:152-158`), become a single chunk (`utils/file_splitter.py:133-147`), and are never seeked (`video_file_frame_getter.py:946`).
- In `vllm-compatible` mode a still goes to vLLM as the **image** modality, `mm_data={"image": …}` (`models/vllm_compatible/vllm_compatible_model.py:3755,3813-3819,3895-3896`).
- `file://` inputs need `FILE_URL_ALLOWED_DIRS`, otherwise 403 (`rtvi_vlm_server.py:1221-1253`).
- **FTP fit [A]:** mount `/export/foscam` read-only, set `FILE_URL_ALLOWED_DIRS=/export/foscam`, and send `image_url: file:///export/foscam/<cam>/<file>.jpg`. No bytes are copied.
- **Gotcha [V]:** `RTVI_ADD_TIMESTAMP_TO_VLM_PROMPT` defaults to `true` (`start_rtvi_vlm.sh:47`). It prepends "These are images sampled from the same video at times …" to stills too. Set it to `false`.
- Short clips go through `/v1/files` + `generate_captions`, or through `video_url`.

**Structured output** **[V, re-read]**:

- `ResponseType = {choice, json_schema, json_object, text}` (`captions.py:100-106`).
- The `vllm-compatible` backend maps them to vLLM `StructuredOutputsParams(json_object=True | json=schema | choice=[…])` and forces `ignore_eos=False` (`vllm_compatible_model.py:745-770`).
- The engine uses `StructuredOutputsConfig(backend="xgrammar", disable_fallback=True, disable_any_whitespace=True)` (`:773-782`).
- A device-level "fail-closed finite-choice" contract test exists (`tests/run_choice_output_contract.py`).
- None of this is documented in `docs/real-time-vlm.mdx`, which has zero hits.
- **In `openai-compat` mode, `response_format` is silently dropped.** The upstream `chat.completions.create` passes only messages, token count, temperature, seed, `top_p` and `extra_body` (`models/openai_compat/openai_compat_model.py:1177-1214`) **[V, re-read]**.

**Prompts:**

- per request, via `system_prompt`/`prompt` or chat `system` messages (only the **last** system message is used, `rtvi_vlm_server.py:3186-3210`);
- the env default `VLM_SYSTEM_PROMPT`;
- the timestamp templates `RTVI_TIMESTAMP_PROMPT_*` (`docker/compose.yaml:114-118`) **[V]**.

**The two named commits** **[V]**:

- `56f77a896` (#2293, "locked VLM request policy") touches **only `libs/vss/cli`**: client-side `vss configure vlm … --lock` defaults. The RT-VLM wire contract is unchanged.
- `1f1a0b904` (#2325) re-enables CR3 reasoning when the prompt contains `<think>` plus format wording and `enable_reasoning` is omitted (`rtvi_vlm_server.py:167-211`). Callers should send `enable_reasoning:false` explicitly.

**EVS** **[V]**:

- Fixed-rate `VLM_VIDEO_PRUNING_RATE ∈ (0,1)` covers Nemotron Nano VL, Qwen2.5-VL, Qwen3-VL and Cosmos3.
- EVS++ (`VIA_EVS_SESSION=true`) covers Qwen3-VL only and raises for Nemotron Omni (`vllm_compatible_model.py:1667-1698`; `docs/real-time-vlm.mdx:1726-1762`).
- The benchmark is unchanged: 8193→4353 tokens, 26.7 s→14.2 s (`README.md:797-800`).
- **EVS prunes video tokens and does nothing for single stills [A].**

**Model path schemes** **[V]**:

- `ngc:` goes through `download_model` and needs `NGC_API_KEY` (`vlm_pipeline/ngc_model_downloader.py:28-61`).
- `git:` becomes `hf download` for huggingface.co, otherwise `git clone` (`:96-148`).
- A bare path is used as-is.
- The cache is `NGC_MODEL_CACHE` (`vlm_pipeline.py:68`).

**Allowlist: the env-var name is settled** **[V]**:

- The container reads **`RTVI_MODEL_PATH_ALLOWLIST`** and `RTVI_ENFORCE_MODEL_PATH_ALLOWLIST` (`src/vlm_pipeline/model_path_policy.py:12-13`).
- `RTVI_VLM_MODEL_PATH_ALLOWLIST` is only the **host-side** name in the VSS-level compose, which maps it across (`deploy/docker/services/rtvi/rtvi-vlm/rtvi-vlm-docker-compose.yml:76-77`).
- The standalone compose forwards `RTVI_MODEL_PATH_ALLOWLIST` directly (`services/rtvi/rt-vlm/docker/compose.yaml:42-43`).
- Enforcement triggers when `RTVI_ENFORCE…` is truthy, **or** the allowlist is non-empty, **or `VLM_TRUST_REMOTE_CODE` is truthy** (`model_path_policy.py:41-55`, unchanged). Patterns are fnmatch globs against the raw `MODEL_PATH`, checked before any download (`vlm_pipeline.py:1976-1979`).

**README NVFP4 recipe: still broken** **[V]**:

- The recipe moved to `services/rtvi/rt-vlm/README.md:805-810`.
- It still sets `VLM_TRUST_REMOTE_CODE=true`, never mentions an allowlist (zero `ALLOWLIST` hits in the README), and then runs `docker compose up` with the allowlist defaulting to empty (`:813-814`).
- It fails at boot with "RTVI_MODEL_PATH_ALLOWLIST must be set when allowlist enforcement is on".
- The Omni recipes share the defect (`README.md:1219-1231`).
- The `ngc:…nemotron-nano-12b-v2-vl:nvfp4-refresh` tag is still 401 anonymously **[E]** (`curl https://api.ngc.nvidia.com/v2/org/nim/team/nvidia/models/nemotron-nano-12b-v2-vl`).

**Supported architectures** **[V]** (`vllm_compatible_model.py`):

| Set                        | Members                                                    | Line              |
| -------------------------- | ---------------------------------------------------------- | ----------------- |
| `_NEMOTRON_OMNI_ARCHS`     | `NemotronH_Nano_VL_V2`, `NemotronH_Nano_Omni_Reasoning_V3` | `:632`, unchanged |
| `_QWEN35_ARCHS`            | Qwen3.5 dense and MoE                                      | `:642-647`        |
| `_QWEN3VL_ARCHS`           | Qwen3VL, Qwen3VLMoe                                        | `:648-653`        |
| `_QWEN3_OMNI_ARCHS`        | Qwen3 Omni                                                 | `:654`            |
| `_COSMOS3_DIFFUSERS_ARCHS` | Cosmos3 Diffusers                                          | `:655`            |
| `_COSMOS3_EDGE_ARCHS`      | `Cosmos3EdgeForConditionalGeneration`                      | `:656-660`        |

The Supported-Models table (`docs/real-time-vlm.mdx:66-85`) lists:

- CR2 8B (four NGC tags);
- CR3 Nano and Super (NGC plus HF "Diffuser");
- Nemotron-3-Nano-Omni 30B-A3B (BF16, FP8);
- Qwen3-VL-30B-A3B, Qwen3-Omni-30B-A3B, Qwen3.5-27B;
- **Cosmos Reason1 7B**, which is now listed. The old "CR1 unsupported in VSS 3.3" line was removed by `a76afbe73`.

Nemotron-Nano-12B-v2-VL is still absent from the table. `git grep -niE "nemotron[-_]nano[-_]12b"` returns **3 lines in 2 files**, not the 5 lines 04 reports **[V]**. There are no rows for the small Qwen3-VL sizes (2B/4B/8B), although the architecture set covers them.

**openai-compat fronting** **[V]**:

- Env: `VLM_MODEL_TO_USE=openai-compat`, `VIA_VLM_ENDPOINT`, `VIA_VLM_API_KEY`, `VIA_VLM_OPENAI_MODEL_DEPLOYMENT_NAME` (`openai_compat_model.py:45-66,833-858`). No local model is loaded (`start_rtvi_vlm.sh:309-318`).
- Frames are **re-encoded as JPEG base64**:
  - a single image, or `REMOTE_VIDEO_INPUT=false`, sends `image_url`;
  - by default, multi-frame input sends `video_url` MP4 (`:1008-1085`).
- The prompt is always wrapped as "These are images sampled from a video … correct timestamps" (`:1110-1145`).

**Could the fronted endpoint be llama.cpp?** Mechanically yes for stills, or with `REMOTE_VIDEO_INPUT=false` **[A]**: llama.cpp accepts `image_url` base64 when started with `--mmproj` **[E]** (`llama.cpp@b7972:tools/server/README.md`, image_url section). It has no `video_url`. **Doing so loses `response_format` and forces video/timestamp framing**, so calling llama.cpp directly is strictly better.

### (c) Infrastructure dragged in

- **The message bus is optional** **[V]**:
  - An empty `MESSAGE_BUS` disables output (`rtvi_stream_handler.py:881-906`).
  - Kafka init failure degrades to "disabled" (`:1025-1050`).
  - Redis Streams uses `XADD … MAXLEN ~` (`:866-874,2476-2490`).
- The shipped composes default to Kafka and pin `redis:8.10.0-alpine` / `apache/kafka:4.1.1` for convenience (`docker/compose.yaml:101-105,189-238`).
- There is no separate DeepStream service. The image is built on DeepStream 9.1 + Triton 26.03 + NVIDIA vLLM 26.03 (`docker/Dockerfile:9-13`) **[V]**.
- It starts a **CUDA MPS daemon** except on CC 12.1 (`start_rtvi_vlm.sh:182-189`) **[V]**. That affects a desktop GPU shared with other work **[A]**.
- Other runtime needs: `shm_size 16gb`, `ipc: host`, `runtime: nvidia` (`docker/compose.yaml:19-26,184`) **[V]**. `runtime: nvidia` needs a CDI rewrite for rootless Podman **[A]**.

### (d) Licensing and gating

| Item                                                                                                                   | Finding                                                                                     | Tag                                                                     |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Image `ghcr.io/nvidia-ai-blueprints/vss/vss-rt-vlm:develop-latest`                                                     | Anonymous HTTP 200; amd64 + arm64; amd64 **11.31 GB** compressed                            | **[E]**                                                                 |
| Base images `nvcr.io/nvidia/deepstream:9.1-triton-multiarch`, `nvidia/vllm:26.03-py3`, `nvidia/tritonserver:26.03-py3` | Anonymous nvcr manifests all HTTP 200, so **a rebuild from source needs no entitlement**    | **[E]** (`nvcr.io/proxy_auth` token → `GET /v2/<repo>/manifests/<tag>`) |
| Source                                                                                                                 | Apache-2.0 (SPDX headers)                                                                   | **[V]** `LICENSE:3`                                                     |
| Dockerfile                                                                                                             | `LicenseRef-NvidiaProprietary` (`docker/Dockerfile:3`)                                      | **[V]**                                                                 |
| Service directory                                                                                                      | Ships `docker/NVIDIA-Software-License-Agreement.pdf`                                        | **[V]**                                                                 |
| Microservice images                                                                                                    | "NVIDIA Software and Model Evaluation License Agreement" (`docs/License-Information.mdx:6`) | **[V]**                                                                 |
| `develop-*` images                                                                                                     | "pre-release … AS IS" (`README.md:103-105`)                                                 | **[V]**                                                                 |

Default and candidate models **[E]** (HF API `curl -s https://huggingface.co/api/models/<id>`; NGC API):

| Model                                             | Gating                                                          | Size                    | Notes       |
| ------------------------------------------------- | --------------------------------------------------------------- | ----------------------- | ----------- |
| CR3 Nano (profile default)                        | NGC 401 anonymously; HF `nvidia/Cosmos3-Nano-Reasoner` also 401 | —                       | —           |
| `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` | ungated                                                         | 10.62 GB                | —           |
| Nemotron-Nano-12B-v2-VL FP8                       | ungated                                                         | 15.40 GB                | —           |
| Qwen3-VL-2B                                       | ungated                                                         | 4.26 GB                 | Apache-2.0  |
| Qwen3-VL-4B                                       | ungated                                                         | 8.88 GB (FP8 6.02 GB)   | Apache-2.0  |
| Qwen3-VL-8B                                       | ungated                                                         | 17.53 GB (FP8 10.59 GB) | Apache-2.0  |
| Cosmos3-Edge                                      | ungated                                                         | 9.18 GB                 | openmdw-1.1 |
| Cosmos-Reason2-2B                                 | `gated: auto` (click-through)                                   | —                       | —           |

### (e) VRAM

- The default `VLLM_GPU_MEMORY_UTILIZATION` is **0.7** on cards of 50 GB or less (`start_rtvi_vlm.sh:115-120`; `vllm_compatible_model.py:1460-1462`) **[V]**.
- A blank value is read as a dedicated 0.7 even on a shared GPU (`skills/vss-build-vision-ai/references/sizing.md:183-186`) **[V]**.
- Shared starting points are 0.40 (H100, RTX PRO 6000) and 0.2 (GB300) (`sizing.md:163-171`) **[V]**.

**[C]** What 0.7 × VRAM reserves:

| Card  | Reservation | Remaining after 12B-VL NVFP4 (10.62 GB) |
| ----- | ----------- | --------------------------------------- |
| 32 GB | 22.4 GB     | —                                       |
| 24 GB | 16.8 GB     | ~6.2 GB for KV + vision encoder         |
| 16 GB | 11.2 GB     | ~0.6 GB, **not viable**                 |

Qwen3-VL-4B-FP8 (6.02 GB) fits every tier.

### (f) Duty cycling

**Always-on** **[V]**:

- The `AsyncLLMEngine` is built and warmed at boot (`vllm_compatible_model.py:1450-1533`).
- No route sleeps, unloads or idles, and `grep -rniE "sleep_mode|enable_sleep|wake_up|unload" src/` returns nothing.
- The vendored vLLM patch overlay contains vLLM sleep mode (`docker/rtvi_vlm/patches/evs_vllm_public_files/engine/arg_utils.py:577,744`; `v1/engine/async_llm.py:937`), but RT-VLM never passes `enable_sleep_mode`. The capability is one layer down and unwired.
- The healthcheck `start_period` is 300 s standalone and 1200 s in VSS, so a container restart is not a practical duty cycle **[V]/[A]**.

### (g) Mapping and verdict

| Use                                                                                                                | Maps to                      | Verdict                 | Reason                                                                             |
| ------------------------------------------------------------------------------------------------------------------ | ---------------------------- | ----------------------- | ---------------------------------------------------------------------------------- |
| RT-VLM container, 8-16 GB tiers                                                                                    | `/florence`                  | **AVOID**               | 0.7 always-on reservation, 11.3 GB image, no unload                                |
| RT-VLM container, 32 GB halo tier, as a **verifier on stills**                                                     | new stage after risk scoring | **ADAPT** (conditional) | Only if sleep mode is wired; co-residency with llama.cpp is unmeasured **[?]**     |
| RT-VLM **contract ideas**: `choice`/`json_schema` via grammar, image-modality stills, `file://` + allowlisted dirs | our analyzer and a verifier  | **ADOPT** as pattern    | Implement on llama.cpp, which has `json_schema`/`response_format` at b7972 **[E]** |
| openai-compat mode fronting llama.cpp                                                                              | —                            | **AVOID**               | Drops `response_format`, forces video framing, re-encodes images                   |
| RT-VLM as the agent LLM                                                                                            | `ai-llm`                     | **AVOID**               | `tools` gets 422                                                                   |

---

## 2. RT-CV (`services/rtvi/rt-cv`, `rt-cv-3d`)

Neither `rt-cv` nor its skill file changed since `cdad5cc0e` **[V]**.

### (a) What it does

RT-CV is a DeepStream 9.x app (`metropolis_perception_app`, derived from deepstream-test5) **[V]** (`docs/object-detection-tracking.mdx:11,626`). The pipeline, per the shipped configs **[V]**:

1. `nvmultiurisrcbin` (REST :9000, starts with zero streams)
2. `nvstreammux` (batch 4, 1920×1080)
3. `nvinfer` (RT-DETR ONNX→TRT FP16) **or** `nvinferserver` (GDINO Triton ensemble)
4. NvDCF tracker
5. optional `[visionencoder]` (RADIO-CLIP 1024-d or SigLIP2 1152-d) and `[text-embedder]`
6. `sink1` MsgConvBroker (`msg-conv-payload-type=2` protobuf, `libnvds_kafka_proto.so`)

Sources: `reference-configs/smartcities/rt-detr/run_config-api-rtdetr-protobuf.txt:34-46,75-102,158-205`; `reference-configs/warehouse-2d/ds-main-config.txt:140,217`.

### (b) Contract

- **REST** (`/api/v1`): `stream/add`, `stream/remove`, `get-stream-info`, `live`/`ready`/`startup`/`metrics`/`metadata`, `generate_text_embeddings` **[V]** (`skills/deployment/vss-deploy-detection-tracking-2d/references/api-reference.md:11-306`).
- **URL schemes:** `rtsp`, `rtmp`, `file:///` (container-local), `http(s)`, `v4l2` (`:336-344`) **[V]**.
- **Codecs:** h264/h265/vp8/vp9/av1. **JPEG is not listed** (`:347-348`) **[V]**.
- **There is no upload endpoint and no still-image path.** A `grep -iE "jpegdec|nvjpeg|multifilesrc|image/jpeg"` over rt-cv and its deploy tree returns nothing **[V]**.
- **Model selection:** `ds-start.sh` accepts exactly `rtdetr-warehouse`, `rtdetr-gdino` and `sparse4d-warehouse`, and exits 1 on anything else (`deploy/docker/services/rtvi/rtvi-cv/ds-start.sh:22,347-355,765-769`) **[V]**.
- **Output schema:** nvschema protobuf `Frame{…objects[]}` and `Object{id,bbox,type,confidence,embedding,…}` (`libs/nvschema/protobuf/schema.proto:25-168`) on Kafka `mdx-raw` **[V]**.

**Tracker:** NvDCF (`config_tracker_NvDCF_accuracy.yml`) with optional ReID `resnet50_market1501.etlt`. The warehouse config ships `reidType: 0` (`ds-nvdcf-accuracy-tracker-config.yml:80-81`) **[V]**. NvDCF needs frame continuity and **degenerates on sparse FTP stills** **[A]**. Our `track_service.py` is a DB trajectory store, not a pixel tracker (`ours:backend/services/track_service.py:1-8`) **[V]**.

**BYOM path for YOLO26: possible, with custom work.**

- The docs say to export ONNX and "potentially implement custom bounding box parsers" (`docs/object-detection-tracking.mdx:915`) **[V]**.
- The shipped parsers are prebuilt `.so` files for TAO RT-DETR/DDETR only, stored as Git LFS pointers (`ds-ppl-analytics-pgie-config.yml:59-62`) **[V]**.
- No YOLO appears anywhere in VSS **[V]**.
- Our YOLO26 Triton model is NMS-free, `output0 [1,300,6]`, batch 1 (`ours:ai/triton/model_repository/yolo26/config.pbtxt`) **[V]**.
- Recipe **[A]**:
  1. Re-export with a dynamic batch dimension.
  2. Write `NvDsInferParseCustomYolo26` (~100-200 lines of C++).
  3. Configure `cluster-mode=4`.
  4. Mount through `RTVI_CV_EXTRA_MOUNT_1` / `RTVI_CV_MOUNTED_CONFIG_DIR` (`rt-cv.md:83-88`).
  5. Masquerade as one of the three `DS_MODEL_FAMILY` values **[?]**, since no custom family exists.

**Bus:** Kafka by default. Redis is **selected only by DeepStream config file** (`libnvds_redis_proto.so`, `ds-redis-config.txt:16-24`). `STREAM_TYPE` is **only logged** by the profile-neutral `ds-start.sh` (`:23,757`) **[V]**. The reference configs ship `[sink1] enable=0`, so nothing is published (`ds-main-config.txt:70`) **[V]**.

### (c) Infrastructure

- DeepStream 9.1, Triton 26.03, TensorRT 10.16 and CUDA 13.2 in the image **[E]**.
- Kafka: the alerts config hard-codes `kafka;29092;mdx-raw` (`dev-profile-alerts/deepstream/configs/run_config-api-rtdetr-protobuf.txt:89-94`) **[V]**.
- Downstream consumers: Behavior Analytics (alerts) and Search analytics (search).

### (d) Licensing and gating

- Image `vss-rt-cv:develop-latest`: anonymous 200; amd64 + arm64; **17.83 GB** compressed **[E]**.
- Base `nvcr.io/nvidia/deepstream:rtvi_ds9.1.1-triton-dev135`: anonymous 200 **[E]**.
- App code: Apache-2.0 (`src/metropolis_perception_app.c:1-3`) **[V]**.
- Models are public NGC TAO (`isPublic: True`: trafficcamnet_transformer_lite, mask_grounding_dino, reidentificationnet, rtdetr_2d_warehouse) **[E]**.
- Sparse4D uses org `nvstaging` **[V]**, which is probably not public **[?]**.

### (e) VRAM: the prior numbers have been reclassified

The in-repo guidance is qualitative only: "size with stream count and model family" (`sizing.md:96,321-323`) **[V]**.

**Prior "≈3.0 GB (1.7-4.5)" and "95-96% SM at 2-3 streams":**

- Sources: UX **example output boxes** in skill instructions (`skills/deployment/vss-deploy-detection-tracking-2d/references/next-steps.md:212-218`; `start-app.md:273-296`; `usage-vss-detection-tracking-2d.md:386-390`) **[V]**. These are not benchmarks.
- The "95-96%" is nvidia-smi GPU utilisation on unthrottled `file://` sources (`sync=0`) **[V]/[E]**, **not SM saturation on live cameras** **[A]**.

### (f) Duty cycling

Always-on. The engine is built and warmed at start (`warmup-engine: 1`, `ds-ppl-analytics-pgie-config.yml:61`), and there is no unload route **[V]**.

### (g) Verdict

| Component          | Verdict                                                                                 | Reason                                                                                                                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RT-CV vs `/yolo26` | **REFERENCE-ONLY** for the FTP-still product; ADAPT only if RTSP ingest becomes primary | Stream-only input, continuity tracker, 17.8 GB image, three hard-coded families, Kafka default, no unload                                                                                     |
| rt-cv-3d           | **AVOID**                                                                               | Multi-view calibrated 3D tracking (MV3DT) with Kafka + MQTT. Sparse4D lives under `rt-cv/reference-configs/warehouse-3d`, not in `rt-cv-3d` (`services/rtvi/rt-cv-3d/README.md:1-13`) **[V]** |

Ideas worth borrowing from RT-CV:

- "smart embedding": skip re-embedding objects the tracker already knows (`docs/object-detection-tracking.mdx:207`);
- decode once, share with RT-Embed over IPC.

---

## 3. RT-Embed (`services/rtvi/rt-embed`)

### (a) What it does

RT-Embed produces **chunk-level** embeddings for video, RTSP, images and text. The default model is Cosmos-Embed1-448p: 8 frames at 448² → 768-d (`README.md:3,15`; `models/custom/samples/cosmos-embed1/triton_model_repo/video_embeddings/config.pbtxt:17-31`) **[V]**.

**01's mapping of CLIP → RT-Embed is wrong.** Our per-object CLIP/re-ID maps to **RT-CV's `[visionencoder]`** (SigLIP2 / RADIO-CLIP, `docs/object-detection-tracking.mdx:176-207`) **[V]**. Also, `nemotron-embed-vl-1b-v2` is not an RT-Embed model. It is the `vss_core` knowledge-adapter embedder (`libs/vss/core/src/vss_core/knowledge/adapters/langchain.py:61-65`) **[V]**.

### (b) Contract

**REST** (`/v1`) **[V]** (`src/server/rtvi_embed_server.py`):

| Route                                          | Line    |
| ---------------------------------------------- | ------- |
| `POST /v1/files` (`media_type` image or video) | `:747`  |
| `POST /v1/generate_video_embeddings`           | `:1862` |
| `POST /v1/generate_text_embeddings`            | `:1732` |
| `POST /v1/streams/add`                         | `:1067` |
| `GET /v1/models`                               | `:1692` |

- **Stills are supported** (`api_models/embeddings.py:294-297`).
- `file://` requires `FILE_URL_ALLOWED_DIRS` (`README.md:702`).
- The response is `chunk_responses[{start_time,end_time,embeddings[]}]` (`embeddings.py:458-563`).

**BYOM contract** **[V]**:

- `DynamicModelLoader` imports `<MODEL_IMPLEMENTATION_PATH>/inference.py`. It picks a class named `Model`/`VlmModel`/`CustomModel`/`Inference`, or any `BaseVlmModel` subclass, and constructs it as `cls(model_path, **kwargs)` (`src/models/dynamic_model_loader.py:40-150`).
- `BaseVlmModel` (`src/models/base_vlm_model.py:66-243`) requires these members:
  - `_initialize_model`
  - `_shutdown_model`
  - `model_name`
  - `generate(query, chunks, video_frames, video_frames_times, generation_config) -> list[VlmModelOutput]`
  - `can_enqueue_requests`
  - `get_model_info`
  - `get_input_config -> InputConfig(num_frames, use_jpeg_encoding, width, height)`
- `VlmModelOutput` carries an `embeddings: List[float]` field.
- `MODEL_REPOSITORY_SCRIPT_PATH` runs once, with `--max_batch_size <VLM_BATCH_SIZE>` (`vlm_pipeline/vlm_pipeline.py:1536-1551`).

**Triton path** **[V]**:

- Triton runs **in-process** through the Python `tritonserver.Server` API (`cosmos-embed1/inference.py:48-61`), with `platform: tensorrt_plan`.
- `create_triton_model_repo.py` exports torch→ONNX (`:88-158`), then runs `trtexec` with min/opt/max shapes (`:283-324`).
- Engines are named per GPU, batch and precision, and are skipped if present (`:261-266`). `config.pbtxt` `max_batch_size` is patched (`:378-380`).

**Shared-technology leverage with our gateway:**

- Our gateway runs `tritonserver:26.01-py3` as a separate server (`ours:ai/gateway/Dockerfile:1`; `ours:ai/gateway/entrypoint.sh:126-132`, `--model-control-mode=none`), with `onnxruntime` backends (e.g. `ours:ai/triton/model_repository/clip/config.pbtxt`) **[V]**. Same Triton lineage, same repository layout.
- **The ONNX→TensorRT-plan script with per-GPU engine naming is a direct template for our consumer-GPU optimisation** **[A]**.
- Neither side uses Triton `explicit` model control (load/unload), which is the obvious duty-cycle lever for both **[E]** (Triton model-management docs).

**Could our CLIP be a BYOM model?**

- Mechanically, yes **[A]**. Our `/clip` is SigLIP2-Base/CLIP ViT-L at 768-d (`ours:backend/services/clip_client.py:4,53-54`) **[V]**. The implementation is a ~60-line `inference.py` subclass that returns `VlmModelOutput(embeddings=<768 floats>)` with `get_input_config → num_frames=1, 224×224`.
- **The value is low.** It trades an in-gateway call for a 12 GB container with GStreamer, an asset manager and a bus, to get the same vector. Cosmos-Embed1 is also 768-d but lives in a **different embedding space**, so switching models means re-embedding all history **[A]**.

### (c) Infrastructure

Nothing is mandatory. Triton is in-process, and `MESSAGE_BUS` is empty by default in base, LVS and alerts (`rt-embed.md:31-53`) **[V]**. Redis output uses `XADD … MAXLEN ~ 10000` (`server/rtvi_stream_handler.py:2283-2302`) **[V]**.

### (d) Licensing and gating

- Image: anonymous 200; amd64 + arm64; 12.16 GB compressed **[E]**. `README.md:22` says "does not require registry authentication" **[V]**.
- `nvidia/Cosmos-Embed1-448p`: `gated: false`, nvidia-open-model-license, 2.39 GB **[E]**.

### (e) The "~10 GB reservation"

The line is a **planning reserve, not a measurement**: "Reserve about 10 GB for RT-Embed" (`sizing.md:290-291`, moved from `:236`) **[V]**.

- The only measured figure is "~6 GiB to build its TensorRT engine" on AGX Thor (`deploy/docker/scripts/dev-profile.sh:1216`) **[V]**.
- Its likely components are the FP16 TRT engines (the BF16 weights are 2.39 GB), activations at max batch × 8 × 448², one CUDA context per NVDEC decoder process, and the transient build peak **[A]**.
- **It is reducible:**
  - `VLM_BATCH_SIZE` auto-drops to **2 below 16 GB and 4 at 46 GB or less** (`start_rtvi_embed.sh:150-158`), and that becomes the engine max batch **[V]**;
  - there are precision flags (`COSMOS_EMBED1_TRT_PRECISION`);
  - a persisted engine cache avoids the build peak **[A]**;
  - `REMOTE_EMBED_ENDPOINT` offloads the model entirely (`start_rtvi_embed.sh:62-71`) **[V]**.
- `sizing.md:318-319`'s `RTVI_EMBED_NUM_VLM_PROCS` knob applies only to openai-compat, so it does nothing on the default path (`vlm_pipeline.py:2306-2310`) **[V]**.

### (f) Duty cycling

Always-on. The model loads at startup, and there is no unload route **[V]**.

### (g) Verdict

| Item                                                                 | Verdict            |
| -------------------------------------------------------------------- | ------------------ |
| Service vs our `/clip`                                               | **REFERENCE-ONLY** |
| `create_triton_model_repo.py` ONNX→TRT-plan pattern, for our gateway | **ADAPT**          |

---

## 4. The LLM slot and agent service (`services/agent`, `libs/vss`)

### (a) What it does

The agent is a **NeMo Agent Toolkit 1.8.0** app (`services/agent/packages/vss_agents/pyproject.toml:39`) on LangChain/LangGraph **[V]**.

- Its `top_agent` is a plan → execute → update router "with native tool calling" (`agents/top_agent.py:428,475-476`) **[V]**.
- Its tools are registered through NAT entry points (`pyproject.toml:52-60`) **[V]**:
  - `video_understanding`, `video_caption`;
  - `vst.*`;
  - `video_report_gen` (HITL `/generate`, `/refine`, `/default`, `/cancel`; `/default` added by `2a0cb1b8a`);
  - `search`, `embed_search`, `attribute_search`;
  - the `video_analytics` MCP group (`get_incident(s)`, `get_places`, …);
  - `lvs_*`, `rtvi_vlm_alert`, `critic_agent`.
- `libs/vss/core` (`nvidia-vss-core`) hard-depends on `elasticsearch~=8.17.0` (`libs/vss/core/pyproject.toml:40`) **[V]**.

### (b) Contract

**HTTP** **[V]**:

- NAT's `/v1/workflow[/stream]`, `/v1/chat[/stream]` and `/v1/chat/completions` (`docs/vss-agent/vss-agent-api.mdx:9-23`), plus HITL `interaction_required` SSE.
- Custom ingest routes (`api/video_ingest.py:613`; `api/rtsp_ingest.py:570`).
- `3a52e2ffb` adds `LegacyChatTerminalMiddleware` to emit `[DONE]` on the legacy SSE routes (`api/custom_fastapi_worker.py:54-110`).
- The `vss_fastapi` front end **refuses to start without VST `streaming_ingest` URLs** (`:199-203`).
- The agent's media types are `rtsp` and `video` only, with no still images (`tools/vst/video_list.py:57,76`).

**LLM configuration** **[V]**:

- Env: `LLM_MODE`, `LLM_MODEL_TYPE` (`nim` or `openai`), `LLM_NAME`, `LLM_BASE_URL` (`deploy/docker/services/agent/compose.yml:68-71,108-112`).
- Config (`dev-profile-base/vss-agent/configs/config.yml:164-193`):
  - `_type: nim` → `ChatNVIDIA`;
  - `_type: openai` → `ChatOpenAI` with `extra_body.chat_template_kwargs.enable_thinking` **[E]** (NAT wheel `nat/plugins/langchain/llm.py:176-249`).

**The LLM contract:**

| Requirement                     | Required?                                                                                                         | Evidence                                                                                                                                                                                           | llama.cpp (our pin b7972)                                                                                                                                         |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Native OpenAI `tool_calls`      | **Yes, mandatory**; there is no text-parsing fallback                                                             | `top_agent.py:526` `bind_tools`; `:1112-1114` reads only `AIMessage.tool_calls` **[V]**                                                                                                            | Supported. `--jinja` is on by default (`llama.cpp@b7972:tools/server/README.md:213`), and `common/chat.cpp@b7972:3100-3113` has a Nemotron-3-Nano handler **[E]** |
| `nemotron_toolcall_parser`      | **No.** It is a server-side **vLLM `--tool-parser-plugin`** for the Nano-9B raw-vLLM service only                 | `deploy/docker/services/nim/nvidia-nemotron-nano-9b-v2-fp8/compose.yml:17-30,56-58`; Lightning uses `--tool-call-parser qwen3_coder` (`nemotron-3.5-lightning-30b-a3b/hw-H100-shared.env`) **[V]** | Irrelevant; llama.cpp parses itself                                                                                                                               |
| Streaming tool-call deltas      | No                                                                                                                | the agent uses `ainvoke` (`top_agent.py:1098-1102`) **[V]**                                                                                                                                        | n/a                                                                                                                                                               |
| Parallel tool calls             | Desirable                                                                                                         | `top_agent.py:1510` **[V]**                                                                                                                                                                        | Needs `parallel_tool_calls: true` **[E]**                                                                                                                         |
| Structured outputs              | **No.** The only `with_structured_output` is in a validator no profile enables; search uses prompt + `json.loads` | `agents/postprocessing/validators/llm_based_rule_validator.py:131`; `tools/search.py:300-330` **[V]**                                                                                              | Supported anyway (`README.md:1183`) **[E]**                                                                                                                       |
| Thinking toggle                 | Yes, when the model name matches                                                                                  | `chat_template_kwargs.enable_thinking` for `nemotron-3-nano`/`lightning` names (`utils/reasoning_utils.py:29,50-62`) **[V]**                                                                       | Per-request `chat_template_kwargs` supported **[E]**                                                                                                              |
| **Hidden Responses-API switch** | Only for `openai` with `llm_reasoning: true` (the default)                                                        | `reasoning_utils.py:52-54` binds `reasoning={…}`, and langchain-openai 1.3.5 then routes to **`/v1/responses`** (`services/agent/uv.lock:2239-2240`; wheel `base.py:4235-4247`) **[V]/[E]**        | `/v1/responses` exists at b7972; tool support there is **[?]**. Mitigation: `llm_reasoning: false`, or `LLM_MODEL_TYPE=nim` **[A]**                               |

**Verdict on the contract:** our llama.cpp server satisfies the VSS agent's LLM contract **through configuration only** **[A]**. Recipe:

- `LLM_MODEL_TYPE=openai` with `llm_reasoning: false` (or `nim`);
- an `LLM_NAME` containing `nemotron-3-nano`;
- a matching `llama-server --alias`, which is **not set today** (`ours:ai/nemotron/Dockerfile:142-160`) **[V]**.

VSS has zero llama.cpp/GGUF references outside vendored vLLM patches, so this path is untested upstream **[V]**. VSS's default agent LLM, Nemotron-3.5-Lightning-30B-A3B, is the **same architecture family** as ours (`NemotronHForCausalLM`). It is ungated (openmdw-1.1), and ggml-org publishes a Q4_0 GGUF of 18.9 GB **[E]**. Whether b7972 loads it is **[?]**.

### (c) Infrastructure

- The agent itself is **CPU-only** (torch from the CPU index, `services/agent/pyproject.toml:39-44`) **[V]**.
- It always needs an LLM plus VST URLs.
- Per-profile additions: `search` +ES +Cosmos-Embed; `alerts` +VA-MCP over ES +alert bridge +RT-VLM; `lvs` +LVS +ES **[V]**.
- **Without ES these tools break:** search, `embed_search`, `attribute_search`, the whole `video_analytics` incident group, and LVS retrieval **[V]** (`video_analytics/tools.py:229,265`).
- Phoenix tracing is wired by default (`config.yml:36-41`).
- `all-MiniLM-L6-v2` is fetched at runtime (`video_analytics/tools.py:237-239`) **[V]/[A]**.

### (d) Licensing and gating

- Agent code: Apache-2.0. Image `vss-agent:develop-latest`: anonymous, amd64 + arm64, 0.49 GB **[E]**.
- LLM NIM `nvcr.io/nim/nvidia/nemotron-3.5-lightning-30b-a3b:2.0.9-variant`: the manifest is anonymous (200, 10.05 GB) **[E]**, but it receives `NGC_API_KEY` and downloads its profile at start. It is **runtime-gated** **[A]**, and "NVIDIA AI Enterprise developer licence required to local host NVIDIA NIM" (`README.md:99`) **[V]**.
- The Nano-9B alternative runs on raw `nvcr.io/nvidia/vllm:26.07-py3` (anonymous) with ungated HF weights **[E]**.

### (e) VRAM

- Agent: 0.
- LLM (`sizing.md:75-77`) **[V]**: Lightning BF16 ≈78 GB; **INT4 ≈45 GB observed**; Nano 9B FP8 11.7 GB.
- **The pinned INT4 NIM profile is ">=32 GB/GPU"** (`nemotron-3.5-lightning-30b-a3b/hw-OTHER.env:25-27`) **[V, re-read]**. So the VSS default LLM **cannot run on any 24 GB card and fills a 5090**.
- The "13.39 GB actual" figure for Nano-9B FP8 in 02/05 is **[C]**: the 10.30 GB HF blob × 1.3.

### (f) Duty cycling

The agent holds no GPU memory. Both LLM containers are `restart: always`, and a grep for `sleep_mode`, `unload` or `idle` returns 0 hits **[V]**. The LLM slot is always-on.

### (g) What the agent offers us

- **We have no natural-language Q&A today.** We do have Postgres full-text search (`ours:backend/services/search.py:1-9`), LLM hourly/daily summaries (`ours:backend/services/summary_generator.py:1-11`) and scheduled reports **[V]**.

| Item                                                                                                                                         | Verdict                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| NL Q&A over events: a small MCP server over our events API, plus a custom NAT config with only those tools, against our llama.cpp            | **ADAPT (post-MVP)** **[A]**                          |
| Stock profiles                                                                                                                               | **AVOID** (VST/ES/video-VLM)                          |
| LLM NIM                                                                                                                                      | **AVOID** (≥32 GB, runtime NGC, always-on)            |
| `vss_core.critic` (subject-anchored per-criterion JSON booleans, `libs/vss/core/src/vss_core/critic/critic.py:15-24,57-120`, "EXPERIMENTAL") | **REFERENCE-ONLY**; a prompt pattern for our verifier |
| HITL report-prompt UX, NAT eval judges                                                                                                       | **REFERENCE-ONLY**                                    |

Effort for the NL Q&A path is roughly 300-600 LoC for the MCP server plus ~150 lines of YAML **[A]**.

---

## 5. Alert service (`services/alert`, "Alert Bridge") and the `alerts` Foundation

There are zero commits under `services/alert` since `cdad5cc0e`. #2295 changed only the agent's `rtvi_vlm_alert` tool **[V]**.

### (a) What it does: VLM verifies CV candidates

It has three modes (`services/alert/README.md:13-24`) **[V]**.

**Mode 1: 2d_cv verification (primary)**

- Candidate path: `perception-alerts → mdx-raw → behavior-analytics → mdx-incidents → alert-bridge → ES mdx-vlm-incidents-*` (`skills/vss-build-vision-ai/references/services/alerts.md:66-74`).
- Clip: fetched from VST, 10 s, anchored (`dev-profile-alerts/vlm-as-verifier/configs/config.yml:27-37`).
- Mode 3-style direct `info.media_urls` bypasses VST (`src/handlers/direct_media/direct_media_handler.py:17-20`), but is off by default (`config.yaml:298-304`).
- VLM call: OpenAI `chat.completions` with `video_url` or `image_url` (multi-image OK) and vLLM-specific `extra_body` `mm_processor_kwargs`/`media_io_kwargs` (`src/vlm/vlm_client.py:87-187,279`).
- **It sends no `response_format`.** The format is prompt-only.
- Prompts are per alert type in JSON, A/B or yes/no, with `<think>` and `{place.name}` templating (`services/alert/alert_type_config.json:1-60`).
- Parsing: `VerdictType = Literal["A","B","yes","no",…]` (`src/schemas/vlm_responses.py:32`), with think/answer strategies (`:125-138,231-270`) and a JSON mode with `verdict_field` and `verdict_mapping` (`:310-400`).
- Mapping: yes/A → `"confirmed"`, no/B → `"rejected"`, error → `"verification-failed"` (`:27,403-419`).
- Pre-VLM suppression: dedup TTL, an end-time delta filter, and confirmed-verdict protection (`config.yaml:214-234`).
- **Rejected verdicts are also written to ES**, so consumers must filter on `info.verdict` (`sink_elastic.py:121-156`).

**Mode 2: 2d_vlm realtime**

- Alert Bridge registers rules on RT-VLM `generate_captions` (30 s chunks, 256 px, `enable_reasoning=True`) (`src/realtime/services/rtvi_client.py:175-253`) **[V]**.
- **RT-VLM decides the incident by substring.** `trigger_tokens = [t for t in ("yes","true") if t in lower_response]` (`services/rtvi/rt-vlm/src/server/rtvi_stream_handler.py:2165-2183`) **[V, re-read]**.
- The trigger is not gated to alert requests. "eyes", "yesterday" and "untrue" all fire **[C]** (substring semantics).
- There is no rejected record, so false negatives are invisible **[V]**.
- **This path is unfit for a false-positive-suppression product as shipped.**

**Mode 3: on-demand**

`POST /api/v1/verification/ondemand` takes `media_urls` + `media_type ∈ {video, image}` (images allowed) and returns 202. The result goes to the **sink, not the response** (`src/web/api/verification_routes.py:66-72`; `src/web/schemas/verification_schemas.py:27-58`) **[V]**.

### (b) Contract

Port `${ALERT_BRIDGE_PORT:-9080}` **[V]**:

| Route                                            | Purpose                                        | Source                          |
| ------------------------------------------------ | ---------------------------------------------- | ------------------------------- |
| `POST /api/v1/alerts`                            | Behavior JSON or protobuf → Kafka `mdx-alerts` | `alert_routes.py:43`            |
| `POST /api/v1/incidents`                         | → Kafka `mdx-incidents`                        | `incident_routes.py:37`         |
| `/api/v1/verification/config[/{type}]`           | prompt CRUD                                    | `alert_config_routes.py:53-306` |
| `/api/v1/realtime[/{id}]`, `/realtime/incidents` | realtime rules; ES query                       | `realtime_routes.py:72-690`     |
| `POST /api/v1/realtime/always-on`                | VIOS lifecycle webhook                         | `realtime_routes.py:729-730`    |

Env: `VLM_BASE_URL`, `VLM_NAME`, `VST_INTERNAL_URL`, `ALERT_AGENT_ALWAYS_ON` (default `false`) (`deploy/docker/services/alert/compose.yml:42-97`) **[V]**.

**`/api/v1/realtime/always-on`, re-verified.** It exists at `realtime_routes.py:729-730` **[V]**. It is a **VIOS `camera_streaming`/`camera_remove` webhook** that starts or stops one realtime rule per camera (`src/realtime/services/always_on_service.py:16-43`). It is **feature-flagged off**: `503 ALWAYS_ON_DISABLED` when `alert_agent.always_on: false` (`config.yaml:311-318`). The stock profile ships `MODE=2d_cv`, `ALERT_AGENT_ALWAYS_ON=false` (`dev-profile-alerts/overrides.env:23,195`) **[V]**.

What "always-on" means here is **continuous compute per camera**. It says nothing about model residency. **Residency is always-on in both modes, for a different reason:** RT-VLM is a boot-loaded vLLM engine with no unload path (§1f). 05's **[A]** should be retired and restated as "no unload or idle residency; stock alerting is event-triggered compute".

**Severity schema:**

- `AlertSeverity` is **uppercase** `LOW|MEDIUM|HIGH|CRITICAL` (`services/alert/src/schemas/shared/enums.py:34-39`) **[V, re-read]**.
- **It is not on the live wire.** It appears only in `AlertRequestEntity`/`AlertResponseEntity`. `EntityValidator` is constructed but never called, and its one construction site has no callers and imports a non-existent `VerificationInfo` (`enhance_alert_with_vlm.py:644,2886,2922,2945`) **[V]**.
- The live severity-like signal is the **lowercase binary `info.verdict`**, plus a free-text `category`.

**Delivery channels** **[V]**:

- ES index `mdx-vlm-incidents-*` (read by the VA-API and UI);
- optional Kafka `mdx-vlm-incidents`/`mdx-vlm-alerts` (`config.yaml:168-177,408-419`);
- the **OpenClaw webhook** (Slack), which itself **consumes Kafka** and is fire-and-forget with no retry (`config.yaml:362-372`; `src/webhook/openclaw_notifier.py:29-42,111-113`).

There is no email or push channel.

### (c) Infrastructure

- **Kafka is mandatory.** `EventBridgeFactory` builds only Kafka and raises otherwise (`src/mdx/event_bridge_factory.py:48-52,78-82`), and a test pins the refusal (`test/unit/mdx/test_event_bridge_factory.py:16-27`). Even the HTTP ingest routes produce to Kafka **[V]**.
- **ES is mandatory** for persistence, the rule store and the verdict sink (`config.yaml:381-407`) **[V]**.
- **Redis is not needed by Alert Bridge.** Its README, compose and Helm agree. The VSS skill doc says otherwise (`alerts.md:24`), but the profile's Redis belongs to VIOS **[V]**.
- 2d_cv also needs RT-CV + Behavior Analytics + VST. The full stock alerts profile runs about 25 services plus an LLM NIM (`skills/vss-build-vision-ai/references/profiles/alerts.md:19`) **[V]**.

### (d) Licensing and gating

- Source: Apache-2.0. The NGC image `vss-alert-verification` is under the NVIDIA SLA, which is `ADD`ed into `/app` (`services/alert/README.md:525-535`; `services/alert/Dockerfile:88-91`) **[V]**.
- ghcr `vss-alert-ms:develop-latest`: anonymous, amd64 + arm64, ~0.11 GB **[E]**.

### (e) VRAM

CPU-only (`README.md:512-515`) **[V]**. The GPU cost is its VLM, plus RT-CV in 2d_cv.

### (f) Duty cycling

- 2d_cv compute is **event-triggered**: only dedup survivors reach the VLM (`README.md:197-207`) **[V]**.
- 2d_vlm is continuous.
- Residency is always-on in both.

### (g) Compared with our pipeline

| VSS                                                           | Ours                                                                                      |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| CV rule candidate → VLM yes/no on a **clip** → binary verdict | YOLO26 + enrichment → 90 s batch → Nemotron **graded 0-100 risk** from detection **text** |

The designs are complementary: **VSS verifies, we grade.** The high-value graft is a VLM verification stage on our above-threshold events, using the evidence stills.

**Could our backend consume VSS alert messages?** Only through:

1. Kafka `mdx-vlm-incidents`, which drags in Kafka;
2. polling `GET /api/v1/realtime/incidents`, which drags in ES;
3. RT-VLM `MESSAGE_BUS=redis` → XREADGROUP nv.Incident protobuf (field `metadata`, `message_type=incident`, on the captions stream). **This path carries the substring-trigger defect.**

None is worth it.

**Verdicts:**

| Item                                                                                                                                                          | Verdict            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| Alert Bridge service                                                                                                                                          | **REFERENCE-ONLY** |
| `VLMResponse` parser, prompt-config conventions, dedup/confirmed-protection ideas (port into our backend, calling any OpenAI-compatible VLM with `image_url`) | **ADAPT**          |
| RT-VLM realtime trigger                                                                                                                                       | **AVOID**          |

---

## 6. Message bus

**Producer and consumer matrix at HEAD:**

| Service            | Redis Streams end to end?                                                                                                                                                                                                                                                                                                             | Still hard-requires                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| RT-VLM             | **Producer yes.** `MessageBus.KAFKA/REDIS` (`rt-vlm/src/api_models/config.py:46-50`, unchanged); XADD approx maxlen (`rtvi_stream_handler.py:2466-2490`). Quirks: incidents share the captions stream (`message_type=incident`, `:2809-2821`); payload field `metadata` (`:866`); errors via Redis **PUBLISH** (`:2727-2740`) **[V]** | nothing (the bus can be empty)                                                                                 |
| RT-Embed           | Producer yes; default disabled (`rt-embed/src/api_models/config.py:46-50`; `rtvi-embed-docker-compose.yml:75-77`) **[V]**                                                                                                                                                                                                             | nothing                                                                                                        |
| RT-CV              | Only by DeepStream config file (`libnvds_redis_proto.so`, `dev-profile-search/.../ds-main-redis-config.txt:83-86`) **[V]**                                                                                                                                                                                                            | alerts config is Kafka-only (`dev-profile-alerts/deepstream/configs/run_config-api-rtdetr-protobuf.txt:89-94`) |
| Behavior Analytics | Yes in code: XREADGROUP/XACK/XGROUP CREATE[CONSUMER] (`services/analytics/behavior-analytics/src/mdx/analytics/core/stream/source/source_factory.py:40-44`; `source_redis_stream.py:66-211`) **[V]**                                                                                                                                  | alerts config has only a `.kafka` block                                                                        |
| Alert Bridge       | **No.** Fenced by factory and test **[V]**                                                                                                                                                                                                                                                                                            | Kafka + ES                                                                                                     |
| Logstash           | Input only: one `pipelines/redis/mdx-logstash.conf` (`redis_stream` gem). No `mdx-vlm-captions` stream; `data_field => "value"` vs RT-VLM's `metadata` **[V]**                                                                                                                                                                        | **every output → `elasticsearch:9200`** (`:394-416`) **[V]**                                                   |
| VA-API             | `STREAM_TYPE=redis` only **skips** Kafka; it configures no Redis client (`services/analytics/video-analytics-api/src/app/initializers/server.js:105-153`; `video-analytics-api.md:43-45`) **[V]**                                                                                                                                     | ES always                                                                                                      |
| VIOS               | Publishes `vst.event` to Redis; consumes `mdx-raw` from Kafka (`dev-profile-alerts/vios/configs/notification_config_2d_cv.json:2-13`) **[V]**                                                                                                                                                                                         | Kafka for the overlay                                                                                          |
| LVS                | No Redis code (grep = 0) **[V]**                                                                                                                                                                                                                                                                                                      | Kafka (live) + ES                                                                                              |
| SDRC               | Redis for routing state (hashes, EVAL, XADD/XREADGROUP) **[V]**                                                                                                                                                                                                                                                                       | —                                                                                                              |

**The Redis-8 question is settled.**

- VSS pins `redis:8.10.0-alpine` (`deploy/docker/services/infra/compose.yml:247`) **[V]**.
- **No Query Engine, JSON, vector-set or Redis-8-only command is used anywhere.** The grep for `FT.*`, `JSON.SET`, `VADD`, `HEXPIRE`, `XDELEX`, `XACKDEL`, `KEEPREF` and similar hits only Helm comments, which say "Alert MS no longer uses Redis" (`deploy/helm/developer-profiles/dev-profile-alerts/values.yaml:78-92`) **[V]**.
- Commands used: `XADD MAXLEN ~` (5.0), `XREADGROUP`/`XACK`/`XGROUP CREATE MKSTREAM` (5.0), `XGROUP CREATECONSUMER` (6.2), `PUBLISH`, `EVAL`. **[C]** The maximum requirement is 6.2 < 7.4.
- **Our `redis:7.4-alpine3.21` (`ours:docker-compose.prod.yml:570`) satisfies every VSS Redis use we could adopt.** Redis 8 matters only for our own hypothetical CAR storage backend (07).

**Only RT-VLM and RT-Embed run with zero Kafka and zero ES.** Their Redis mode is **producer-only**: no in-tree consumer reads RT-VLM's Redis output, and even Logstash's Redis pipeline expects a different field name and sinks to ES.

---

## 7. Video summarization (LVS) and storage via context-aware-rag: re-verification

Since `cdad5cc0e`, only the RT-VLM image default in `services/video-summarization/docker/deploy/compose.yaml:311` changed. `deploy/docker/services/infra` is unchanged **[V]**.

| 07 claim                                                                               | At `1e94133b4`                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `via_stream_handler.py:505` literal `"elasticsearch_db"` branch, default `"vector_db"` | Unchanged (default `:504`, branch `:505`) **[V]**. **Qualifier:** the Milvus injection also requires `MILVUS_DB_HOST` or `MILVUS_DB_GRPC_PORT` (`:505-507`), and compose defaults both to empty (`deploy/docker/services/video-summarization/compose.yml:40-41`) |
| `:1861` silent no-op of `_store_event_prompt_in_db`                                    | Unchanged (`:1859-1861`). **Nuance:** it also needs `LVS_DROP_EMPTY_EVENT_FIELDS=false`, and the in-code default is `"true"` (`:1852-1853`). It is skipped by default even on ES **[V]**                                                                         |
| `KAFKA_ENABLED` defaults                                                               | `config.yaml:82,97` `${KAFKA_ENABLED:false}`; `dev-profile-lvs/.env:124` `true`. Unchanged **[V]**                                                                                                                                                               |
| Hard-400 live endpoints                                                                | Unchanged: `via_server.py:1031` (`/v1/generate_captions`) and `:1108` (`/v1/stream_summarize`), "Livestream APIs require KAFKA_ENABLED=true" **[V]**                                                                                                             |
| `/aggregate_live_stream`                                                               | **Does not exist**, and did not at `cdad5cc0e` either: "removed" (`via_server.py:1706-1709`) **[V]**. 07's lines 93 and 138 cite a phantom                                                                                                                       |
| CAR pin                                                                                | `services/video-summarization/docker/Dockerfile:67,72` → `context-aware-rag.git@3.1.0`, unchanged **[V]**. Upstream has `3.1.1rc1` **[E]**                                                                                                                       |
| Heap                                                                                   | `infra/compose.yml:181` (Kafka 6G), `:292` (Logstash 1G), `:119` (ES 1G), unchanged **[V]**                                                                                                                                                                      |
| `redis.conf:1407 appendonly no`                                                        | Unchanged, but RDB `save 60 1` is on (`:447`), so "no persistence" overstates it **[V]**                                                                                                                                                                         |
| Alert Redis bridge fenced                                                              | Still fenced (`services/alert/test/unit/mdx/test_event_bridge_factory.py:16-27`); commits `c0eb2e9f2` and `8e802d91e` resolve **[V]**                                                                                                                            |

**Still images:** LVS `MediaType` is `VIDEO` only (`services/video-summarization/src/vss_api_models.py:120-123`), even though the form help says "image / video" (`via_server.py:390`) **[V]**.

**Fit: AVOID.** It is video-only and ES-default, and it duplicates our Postgres store and `summary_generator`.

---

## 8. VIOS, UI, configurators, SDRC, analytics

**VIOS** (Video I/O Service, i.e. VST; C++):

- It "connects to cameras rtsp/onvif/milestone, VMS systems, or NVStreamer sources, manages sensor registration and recording, routes streams … serves recorded/live video" (`services/vios/README.md:3`) **[V]**.
- It does have **file upload**: `POST /api/v1/storage/file` and `PUT /api/v1/storage/file/{filename}/{timestamp}` (`services/vios/src/modules/storage_management/storage_management_apis.cpp:144-145`) **[V]**.
- **Uploads are validated as video containers and codecs only:**
  - `nv_streamer_media_container_supported: ["mp4","mkv"]` and `supported_video_codecs: ["h264","h265"]` (`services/vios/configs/vst_config.json:124,127`);
  - extension regex plus container check (`src/framework/utilities/config.cpp:150-185`);
  - `415 Format not supported` / `422` (`storage_management_utils.cpp:1792-1826`) **[V]**.
- **VIOS cannot ingest FTP JPEG stills** without transcoding them to MP4. It has still-frame _output_ (`/api/v1/storage/stream/{id}/picture`, `storage_management_apis.cpp:158-159`), not still input.
- It drags in Postgres (`deploy/docker/services/vios/foundational/docker-compose.yaml:18`), Redis (`vst.event`) and Kafka (the `mdx-raw` overlay consumer; `vios.md:155-158`) **[V]**.
- Images `vss-vios-sensor`/`-streamprocessing`/`-ingress` are anonymous on ghcr, amd64 + arm64 **[E]**.
- The one idea worth copying is its lifecycle **webhook fan-out** rule: "a service is a receiver iff it must act on every newly registered stream" (`skills/vss-build-vision-ai/references/services/vios.md:61-73`).
- **Verdict: AVOID** as ingest (our file watcher + go2rtc already cover it); **REFERENCE-ONLY** for the notification pattern.

**UI** (`services/ui`):

- A Next.js 16 / React 19 Turbo monorepo (`services/ui/package.json:22-33`) with packages alerts, chat, dashboard, map, search and video-management.
- It was relicensed to Apache-2.0 by `e6723df18` (`README.md:156`) **[V]**.
- The alerts page reads incidents from the ES-backed VA-API (`packages/nv-metropolis-bp-vss-ui/alerts/lib-src/hooks/useAlerts.ts:358-360`), sensors from VST (`:311`), and rules from `<host>/alert-bridge/api/v1` (`hooks/useRealtimeAlertRules.ts:8`) **[V]**.
- Image `vss-agent-ui` is anonymous **[E]**.
- Our frontend is React + Vite + Tailwind + Tremor with different data contracts.
- **Verdict: REFERENCE-ONLY.** The alert-rule builder and the "CV alerts verification config" tab are good UX references for a verifier-prompt editor.

**Configurators:**

- `vss-configurator` is Flask. It does sensor-config management plus a "Profile Configurator" whose README says it "Automatically detects GPU type" (`services/configurators/vss-configurator/README.md:176-184`).
- **The code reads `HARDWARE_PROFILE` env and otherwise falls back to `'default'`** (`app/profile_configurator/profile_config_manager.py:142-166`) **[V]**.
- It is warehouse-only (`bp-configurator-<mode>`, `configurator.md:5-9`).
- `vss-rt-config-adaptor` is a Flask `POST /config` that writes a DeepStream YAML/CSV (`vss-rt-config-adaptor/README.md:5`) **[V]**.
- **Verdict: AVOID.** Hardware-profile selection is Auditor A's topic.

**SDRC** (Sensor Distribution and Routing Controller):

- It spreads live streams across worker replicas, tracks ownership in Redis, routes through Envoy by stream-ID header, and migrates streams on worker failure (`services/sdrc/README.md:29-45`) **[V]**. Workloads are `vss-vios-streamprocessing` and `vss-rtvi-cv`.
- Image `sdr-mw-l` is anonymous **[E]**.
- **Verdict: AVOID.** It is multi-worker scale-out; a single box has one worker.

**Analytics:**

- `behavior-analytics` is a Python 3.13 streaming pipeline over Kafka, Redis Streams or MQTT (`services/analytics/behavior-analytics/README.md:7,30-35`). It provides trajectories, ROI/tripwire, proximity and incident generation. Its operating mode lives in mounted JSON `numWorkersFor*`, and it has no HTTP listener (`behavior-analytics.md:19-39`) **[V]**.
- Its input is the nvschema `Frame` stream from RT-CV, so **without RT-CV it has nothing to consume.** Its class filters must match RT-CV's label casing (`:28-31`).
- `video-analytics-api` is the ES-backed query API (`video-analytics-api.md:35-38`) **[V]**.
- Our equivalents are zones (`ours:backend/models/analytics_zone.py`, `zone.py`), dwell time, `zone_anomaly_service.py` and `track_service.py`.
- **Verdict: REFERENCE-ONLY.** The tripwire/ROI/proximity rule semantics could inform our zone rules; the service itself needs RT-CV + a bus + ES.

---

## 9. Schemas: VSS vs ours, field by field

### Our side (all **[V]**)

**Event row** (`ours:backend/models/event.py`):

- `risk_score` int with CHECK 0-100 (`:58,242`);
- `risk_level` str with CHECK in lowercase `low/medium/high/critical` (`:61,238-239`);
- `summary`, `reasoning` (deferred), `entities`/`flags`/`confidence_factors` JSONB, `recommended_action` (`:67-111`).

**Severity:** `Severity` StrEnum, lowercase, thresholds 29/59/84 configurable (`ours:backend/models/enums.py:66-84`).

**LLM contract:**

- `RISK_ANALYSIS_JSON_SCHEMA` requires `risk_score` (int 0-100), `risk_level` (lowercase enum), `summary` (maxLength 200) and `reasoning`. Optionally it takes `entities[{type ∈ person|vehicle|animal|object, description, threat_level ∈ low|medium|high}]` and `recommended_action ∈ none|review|alert|immediate_response` (`ours:backend/api/schemas/llm_response.py:34-88`).
- `LLMRiskResponse` adds `risk_factors`, `flags[{type, description, severity ∈ warning|alert|critical}]` and `confidence_factors{detection_quality, weather_impact, enrichment_coverage}` (`:247-318`). `risk_level` is normalised to lowercase (`:463-489`).

**Transport, the important finding:**

- Our analyzer calls **llama.cpp's native `/completion`** with a hand-built ChatML prompt (`ours:backend/services/nemotron_analyzer.py:3891-3898,3977-3981`).
- It adds **`nvext.guided_json`** (`:583-593`), enabled by default (`ours:backend/core/config.py:1279-1285`).
- "Support" is detected by probing `/completion` with `nvext` and **treating any 2xx as supported** (`nemotron_analyzer.py:452-478`).
- llama.cpp's `/completion` takes `json_schema`/`grammar` (`llama.cpp@b7972:tools/server/README.md:450`), not `nvext` **[E]**. **So the constraint is almost certainly ignored while the code believes it is enforced** **[A]**. Confirm with one request and a malformed-output test.

**Fail-open to MEDIUM:**

- When lenient validation fails, `risk_score = 50  # Default` → `medium` (`nemotron_analyzer.py:4392-4412`).
- The persistence path defaults to `risk_data.get("risk_score", 50)` / `get("risk_level", "medium")` (`:2884-2885`).
- **An unparseable answer about an empty porch becomes a MEDIUM event.**

**Internal inconsistencies:**

- The API's `EventResponse.risk_level` is **recomputed from `risk_score` with hard-coded thresholds** (`ours:backend/api/schemas/events.py:18-20,171-188`). It ignores both the stored LLM `risk_level` and the settings-driven `Event.computed_risk_level` (`event.py:368-399`).
- `recommended_action` has two enums: `llm_response.py:83` vs `ours:backend/services/guided_constraints.py:24-30`, which adds `review_later`, `review_soon` and `alert_homeowner`.

**Alert severity:** our own `AlertSeverityEnum` is a StrEnum with `auto()`, so its values are lowercase `low…critical` (`ours:backend/models/alert.py:50-69`). It shares a name with VSS's uppercase `AlertSeverity`.

### Field-by-field

| Concept             | Ours                                           | VSS (live wire)                                                                                       | Mismatch                                                                             |
| ------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Record              | `Event` row, `id` int, `batch_id`              | nvschema `Incident` protobuf; **no id field** (`libs/nvschema/protobuf/ext.proto:192-253`) **[V]**    | Identity is in ES `_id` / `info.requestId`                                           |
| Camera              | `camera_id` (normalised string)                | `sensorId`                                                                                            | Naming only                                                                          |
| Window              | `started_at` / `ended_at`                      | `timestamp` / `end`                                                                                   | Naming only                                                                          |
| **Score**           | `risk_score` int 0-100                         | **none.** Only per-object `Object.confidence` float (`schema.proto:95-168`)                           | No graded score in VSS                                                               |
| **Level**           | `risk_level` lowercase 4-level                 | `info.verdict` lowercase `confirmed`/`rejected`/`verification-failed` (`vlm_responses.py:27,403-419`) | **Binary vs graded.** Map `rejected` → suppress, `confirmed` → keep our graded level |
| Severity enum       | `Severity` / `AlertSeverityEnum` lowercase     | `AlertSeverity` UPPERCASE (`enums.py:34-39`), **dead code**                                           | Casing differs, but VSS never emits it. 06 §4's "near-identical" note is moot        |
| Category            | `object_types` text; `flags[].type`            | `category` free text (alert type or `vlm-alert`)                                                      | Different granularity                                                                |
| Summary             | `summary` (≤200)                               | `llm.queries[].response` raw VLM text                                                                 | VSS stores raw text                                                                  |
| Reasoning           | `reasoning` (`<think>` stripped)               | `info.reasoning` (`<think>` text)                                                                     | Compatible                                                                           |
| Entities            | `entities[{type, description, threat_level}]`  | `objectIds[]` → `Object{type, confidence}` in `Frame`                                                 | VSS has no per-entity threat                                                         |
| Anomaly flag        | none (threshold on score)                      | `isAnomaly` bool                                                                                      | —                                                                                    |
| Place               | zone tables                                    | `place{id,name,type,…}`                                                                               | —                                                                                    |
| Action / confidence | `recommended_action`, `confidence_factors`     | none                                                                                                  | —                                                                                    |
| Review state        | `reviewed`, `flagged`, `notes`, `snooze_until` | none (`AlertStatus` dead)                                                                             | —                                                                                    |
| `info` map          | typed columns / JSONB                          | `map<string,string>`; ints and lists stringified (`vlm_responses.py:519-527`)                         | Stringly typed                                                                       |

**RT-VLM structured output** can carry **our exact schema**: `response_format={type: json_schema, json_schema:{schema: RISK_ANALYSIS_JSON_SCHEMA}}` in integrated mode (§1b). The result is a string in `chunk_responses[].content`. VSS's own consumers never use it for alerts.

**Conclusion:** there is **no VSS schema worth adopting as ours**. Emitting nvschema is useful only for interop with VSS's UI or agent, which need ES anyway.

---

## Technologies we can incorporate

Ranked by value-to-effort for a single consumer GPU.

| #   | Technology                                                                                                                                                                                                                                                | What it gives us                                                                  | Effort                                                           | Infra it drags in                                                                                                                                                                                                                                                                            | Verdict                   |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| 1   | **Constrained decoding for the risk JSON** (RT-VLM's xgrammar `json_schema`/`choice` idea, §1b), implemented on our llama.cpp as `json_schema` on `/completion` or `response_format` on `/v1/chat/completions`; plus removing the 50 → `medium` fail-open | Guaranteed-parseable risk JSON; kills a silent false-positive source (§9)         | Hours to 1 day **[A]**                                           | None (llama.cpp@b7972 has it **[E]**)                                                                                                                                                                                                                                                        | **ADOPT** (pattern)       |
| 2   | **VLM-as-verifier stage** (Alert Bridge 2d_cv pattern + `VLMResponse` parser, Apache-2.0) on above-threshold events, fed the FTP evidence stills as `image_url`, with a `choice` `["yes","no"]` or small `json_schema` verdict                            | Direct false-positive suppression, the product requirement                        | ~1-2 weeks **[A]**                                               | A VL model resident when needed. Options: llama.cpp mtmd + Qwen3-VL-4B/8B GGUF (first-party **[E]**), or Nemotron-Nano-12B-v2-VL GGUF (community, Q4_K_M 7.5 GB + mmproj 1.69 GB **[E]**; needs llama.cpp ≥ #19547, 2026-02-14, i.e. **newer than b7972**, which has only `QWEN3VL` **[E]**) | **ADAPT**                 |
| 3   | **Verification prompt conventions**: per-type prompt JSON with `{place.name}` templating, A/B or yes/no plus `<think>`, `output_category`; `vss_core.critic` subject-anchored per-criterion booleans                                                      | Tunable, auditable verifier prompts                                               | Days                                                             | None                                                                                                                                                                                                                                                                                         | **ADOPT** (pattern)       |
| 4   | **Dedup and confirmed-verdict protection** (Alert Bridge `dedup_ttl_seconds`, end-time delta)                                                                                                                                                             | Fewer duplicate VLM calls, therefore less GPU time                                | Days                                                             | None                                                                                                                                                                                                                                                                                         | **ADAPT**                 |
| 5   | **ONNX→TensorRT-plan build script** (RT-Embed `create_triton_model_repo.py`: per-GPU engine naming, batch patching, engine cache) applied to our Triton gateway models                                                                                    | Smaller and faster engines per consumer SKU; same Triton lineage (26.01 vs 26.03) | 1-2 weeks per model family **[A]**                               | None new                                                                                                                                                                                                                                                                                     | **ADAPT**                 |
| 6   | **VSS agent LLM contract compatibility** + NAT `mcp_client`: NL Q&A over our events via a small MCP server and a custom agent config                                                                                                                      | "What happened at the front door last night?"                                     | 2-3 weeks **[A]**                                                | `vss-agent` container (CPU, 0.49 GB). No ES if we provide our own tools. Set llama-server `--alias`; `llm_reasoning:false`                                                                                                                                                                   | **ADAPT** (post-MVP)      |
| 7   | **Ungated model choices VSS wires**: Nemotron-3.5-Lightning-30B-A3B (same family as our LLM; GGUF Q4_0 18.9 GB); Qwen3-VL / Cosmos3-Edge for the VL slot                                                                                                  | On-message model choices with no NGC gate                                         | Model-swap testing                                               | llama.cpp pin bump **[?]**                                                                                                                                                                                                                                                                   | **ADOPT** (selectively)   |
| 8   | **RT-VLM container** as a halo-tier (32 GB) stills verifier with `file://` + `FILE_URL_ALLOWED_DIRS`, `MESSAGE_BUS` empty                                                                                                                                 | vLLM + xgrammar with an NVIDIA-supported engine                                   | Medium; **needs sleep mode wired** plus co-residency measurement | 11.3 GB image, always-on 0.7 reservation, CUDA MPS, `runtime: nvidia`                                                                                                                                                                                                                        | **ADAPT** (conditional)   |
| 9   | Per-object "smart embedding" (skip re-embedding tracked objects, RT-CV vision encoder)                                                                                                                                                                    | Less CLIP work per batch                                                          | Days                                                             | None                                                                                                                                                                                                                                                                                         | **REFERENCE-ONLY** (idea) |
| 10  | Behavior-analytics tripwire/ROI/proximity semantics                                                                                                                                                                                                       | Better zone rules                                                                 | Days to read                                                     | —                                                                                                                                                                                                                                                                                            | **REFERENCE-ONLY**        |
| 11  | VIOS webhook fan-out rule; UI alert-rule and verifier-config screens; HITL report-prompt editor                                                                                                                                                           | UX and architecture references                                                    | —                                                                | —                                                                                                                                                                                                                                                                                            | **REFERENCE-ONLY**        |

**What we bring that VSS lacks** (the contribution angle, not adoption):

- idle unload and residency control: llama.cpp `--sleep-idle-seconds`, router `/models/unload` (`llama.cpp@b7972:tools/server/README.md:221,1431,1650,1688`) **[E]**, plus our `model_zoo` LRU;
- event-triggered batching;
- still-image ingest;
- a graded 0-100 risk score.

---

## Looks reusable but isn't

| Item                                                                | Why not                                                                                                                                                   |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RT-VLM `openai-compat` fronting llama.cpp                           | Drops `response_format` (`openai_compat_model.py:1177-1214`), forces "sampled from a video … timestamps" framing (`:1110-1145`), re-encodes JPEGs         |
| RT-VLM realtime incidents ("always-on alerting")                    | `"yes"`/`"true"` **substring** trigger (`rtvi_stream_handler.py:2165-2183`); no rejected record; not gated to alert requests                              |
| VSS `AlertSeverity` as a severity schema to match                   | Dead code; the live wire has only binary `info.verdict`                                                                                                   |
| `MESSAGE_BUS=redis` as "VSS on Redis end to end"                    | Producer-only. No in-tree consumer reads RT-VLM's Redis output; Logstash expects field `value` not `metadata` and sinks to ES; Alert Bridge refuses Redis |
| `STREAM_TYPE=redis`                                                 | RT-CV only logs it (`ds-start.sh:23,757`); the VA-API only skips Kafka and configures no Redis client                                                     |
| Alert Bridge as a drop-in verifier service                          | Kafka + ES mandatory (`event_bridge_factory.py:48-52`; `config.yaml:381-407`); verdicts go to the sink, not the HTTP response                             |
| VIOS as FTP-still ingest                                            | Upload accepts mp4/mkv with h264/h265 only (`vst_config.json:124,127`)                                                                                    |
| RT-CV BYOM for YOLO26                                               | Three hard-coded `DS_MODEL_FAMILY` values, a custom C++ parser required, NvDCF needs continuous frames, 17.8 GB image, no stills                          |
| RT-Embed for our CLIP                                               | Chunk-temporal video embeddings, a different embedding space, a 12 GB image to produce the same 768-d vector                                              |
| LVS for our summaries                                               | `MediaType` is VIDEO only; ES-default; Kafka for live; duplicates our `summary_generator`                                                                 |
| VSS LLM NIM                                                         | ≥32 GB INT4 profile floor, runtime NGC key, always-on                                                                                                     |
| Stock agent profiles                                                | Need VST (`streaming_ingest` mandatory), ES, a video VLM                                                                                                  |
| `/api/v1/realtime/always-on` as the duty-cycle comparison           | It is a VIOS webhook and off by default; the residency problem is elsewhere (§5)                                                                          |
| vss-configurator GPU auto-detection                                 | Reads the `HARDWARE_PROFILE` env var and falls back to `default`; warehouse-only                                                                          |
| `sizing.md` RT-Embed "10 GB" and RT-CV "3.0 GB / 95-96%" as budgets | A planning reserve and UX example boxes, not measurements                                                                                                 |
| Cosmos FP8/NVFP4 variants                                           | NGC-gated, and "hallucinations may occur" (`docs/real-time-vlm.mdx:91`)                                                                                   |
| Our own `nvext.guided_json` "structured output"                     | NIM-only parameter sent to llama.cpp; the probe treats any 2xx as supported (§9)                                                                          |

---

## Contradictions with the existing docs

1. **"Two vLLM engines cannot share one GPU at all" (04 §3, 05, 07) is wrong as a general statement.**
   - The quote (`dev-profile.sh:1211-1216`) sits in the search-on-edge (Thor) block.
   - VSS ships and measured LLM + RT-VLM co-resident at `0.40 + 0.40` on H100 and RTX PRO 6000 (`sizing.md:100,106,109`), with "0.3 → 29970 MiB for the LLM and 21.9 GB still free, serving 8/8 concurrent tool calls" (`nim/nemotron-3.5-lightning-30b-a3b/hw-RTXPRO6000BW-shared.env`) **[V, re-read]**.
   - The L40S rule is a capacity check ("no hw-L40S-shared.env", `dev-profile.sh:1376-1386`).
   - Restate the advantage as **no ≥32 GB LLM floor, no always-on pre-allocation, and idle unload**. (This overlaps Auditor A.)
2. **01 maps CLIP to RT-Embed; the right analogue is RT-CV's vision encoder.** Also, `nemotron-embed-vl-1b-v2` is a `vss_core` knowledge embedder, not an RT-Embed model.
3. **01 says BYOM is RT-Embed-only.** RT-VLM has the same `custom` loader.
4. **04 §2/§6 use the wrong allowlist env name for standalone or `podman run`.** It is `RTVI_MODEL_PATH_ALLOWLIST`. `RTVI_VLM_MODEL_PATH_ALLOWLIST` works only through the VSS dev-profile compose, and the §6 block mixes the two conventions.
5. **04 §3 / 03 call RT-Embed a "fixed 10 GB, no knob".** It is a planning reserve, the batch auto-drops to 2 or 4 on consumer cards, and precision and remote-offload knobs exist.
6. **04/05 cite RT-CV "≈3.0 GB" and "95-96% SM".** Both come from UX template boxes and describe nvidia-smi util on unthrottled file sources.
7. **04 says "CR1 unsupported in VSS 3.3" (`real-time-vlm.mdx:18`).** The line is gone and CR1 7B is now in the table (`:85`).
8. **05 says the alert route is "literally always-on" [A].** It is a disabled-by-default VIOS webhook. Stock alerting is event-triggered compute; the true gap is no unload.
9. **06 §4 plans to "demand Event JSON via `response_format: json_schema`" and cites "uppercase `AlertSeverity`".** The first works only in RT-VLM integrated mode, not openai-compat, and not via Alert Bridge. The second is dead code; the live wire is a binary lowercase verdict.
10. **07 references `/aggregate_live_stream`.** The endpoint does not exist (`via_server.py:1706-1709`).
11. **07 says ":505 injects Milvus".** Only when Milvus env vars are set. ":1861 no-op" is off by default even on ES (`LVS_DROP_EMPTY_EVENT_FIELDS`).
12. **07 says "no persistence" for VSS Redis.** `appendonly no`, but RDB `save 60 1` is on.
13. **07 says "the message bus is already built".** True for producers only; no Redis consumer exists end to end.
14. **02/05 give Nano 9B FP8 as "13.39 GB actual [V]".** That is [C] = 10.30 GB blob × 1.3; VSS says 11.7 GB (`sizing.md:77`).
15. **04 counts "5 lines across 2 files" for the 12B-VL grep.** It is 3 lines across 2 files at both commits.
16. **01 says Kafka is "the current Compose default" for RT-VLM.** True, but RT-VLM runs with the bus empty and degrades gracefully when Kafka is unreachable.
17. **The task brief says "no RTSP service".** `docker-compose.prod.yml` does run `go2rtc` (RTSP→WebRTC live view, `ours:docker-compose.prod.yml:729-745`), and the backend has `IngestionMode.RTSP/ONVIF` (`ours:backend/models/enums.py:100-102`) and an RTSP `stream_manager.py`. FTP remains the default ingest (`ours:backend/models/camera.py:126,170`) **[V]**. The brief's intent holds (no RTSP feed into the AI pipeline), but the literal statement does not.

---

## Stale or moved citations in `docs/vss-integration`

Old line contents were compared between `cdad5cc0e` and `1e94133b4` with `git show`.

| Doc        | Old citation                                                                                                                              | Status at `1e94133b4`                                                                                                                                                                       |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 02         | `deploy/helm/developer-profiles/dev-profile-base/values-base.yaml:23`                                                                     | Resolves                                                                                                                                                                                    |
| 02         | `docs/real-time-vlm.mdx:1529`                                                                                                             | Moved → `:1596`                                                                                                                                                                             |
| 02         | `docs/real-time-vlm.mdx:82`, `:83`, `:85`                                                                                                 | Moved → `:80`, `:81`, `:83`                                                                                                                                                                 |
| 02         | `docs/real-time-vlm.mdx:1622`, `:1650`, `:97`                                                                                             | Moved → `:1689`, `:1721`, `:95`                                                                                                                                                             |
| 04         | `docs/real-time-vlm.mdx:77,81`                                                                                                            | Moved → `:75`, `:79`                                                                                                                                                                        |
| 04         | `docs/real-time-vlm.mdx:93` (hallucination note)                                                                                          | Moved → `:91`                                                                                                                                                                               |
| 04         | `docs/real-time-vlm.mdx:18` ("no CR1 in VSS 3.3")                                                                                         | **GONE** (removed by `a76afbe73`; CR1 now at `:85`)                                                                                                                                         |
| 04         | `docs/prerequisites.mdx:282-295`                                                                                                          | Moved → RTX PRO 6000 tab `:359-368`, RTX PRO 4500 tab `:370-381`. The 4500 alerts rows require **2 GPUs** with a remote LLM; `dev-profile.sh:1162-1167` enforces ≥2 (error text at `:1166`) |
| 04         | `.github/skill-eval/run_leg.py:58-61`                                                                                                     | Moved → `:59-63`; the RTX 4090 tables are still empty                                                                                                                                       |
| 04         | `services/rtvi/rt-vlm/src/models/vllm_compatible/vllm_compatible_model.py:632` (+`:638`, `:1692`)                                         | Resolve                                                                                                                                                                                     |
| 04         | same file `:1784`, `:2486`, `:3738`, `:3831`, `:3862`                                                                                     | Moved → `:1799`, `:2506`, `:3759`, `:3852`, `:3883`                                                                                                                                         |
| 04         | `README.md:838-843` (rt-vlm EVS numbers)                                                                                                  | Moved → `services/rtvi/rt-vlm/README.md:797-800`                                                                                                                                            |
| 04         | `README.md:845-852` (NVFP4 recipe)                                                                                                        | Moved → `:805-810`, **still broken**                                                                                                                                                        |
| 04         | `src/vlm_pipeline/model_path_policy.py:41-55`                                                                                             | Resolves                                                                                                                                                                                    |
| 04         | rt-vlm `Dockerfile:380` (vLLM pin) / `:67` (`TORCH_CUDA_ARCH_LIST`)                                                                       | Moved → `docker/Dockerfile:381` / `:73`; the list still omits 8.9                                                                                                                           |
| 04, 05     | `deploy/docker/scripts/dev-profile.sh:1161-1165`                                                                                          | Moved → `:1211-1216`; **scope is search-on-edge only**                                                                                                                                      |
| 05, 06     | `README.md:99` (AI Enterprise licence)                                                                                                    | Resolves                                                                                                                                                                                    |
| 04, 03     | `sizing.md` "Reserve about 10 GB for RT-Embed" (no line given)                                                                            | At `sizing.md:290-291` (was `:236`)                                                                                                                                                         |
| 04, 05, 03 | RT-CV "3.0 GB" / "95-96%" (uncited)                                                                                                       | Sources found: `skills/deployment/vss-deploy-detection-tracking-2d/references/next-steps.md:212-218`, `start-app.md:273-296`, `usage-…:386-390`. These are **template boxes**               |
| 07         | `rt-vlm/src/api_models/config.py:46-50`                                                                                                   | Resolves                                                                                                                                                                                    |
| 07         | `…/logstash/pipelines/kafka/mdx-lvs-logstash.conf:1-18`                                                                                   | Resolves                                                                                                                                                                                    |
| 07         | `via_stream_handler.py:505`, `:1861`                                                                                                      | Resolve (`:504-505`, `:1859-1861`); see qualifiers                                                                                                                                          |
| 07         | `via_server.py:1031,1108`                                                                                                                 | Resolve                                                                                                                                                                                     |
| 07         | `/aggregate_live_stream`                                                                                                                  | **GONE** (already gone at `cdad5cc0e`; `via_server.py:1706-1709`)                                                                                                                           |
| 07         | `services/video-summarization/docker/Dockerfile:67,72` (CAR 3.1.0)                                                                        | Resolves                                                                                                                                                                                    |
| 07         | `infra/compose.yml:181,292,119`                                                                                                           | Resolves                                                                                                                                                                                    |
| 07         | `redis.conf:1407`                                                                                                                         | Resolves                                                                                                                                                                                    |
| 07         | `test_event_bridge_factory.py:16-27`                                                                                                      | Resolves at `services/alert/test/unit/mdx/test_event_bridge_factory.py:16-27`                                                                                                               |
| 07         | `.github/scripts/check_folder_structure.py:33-42`                                                                                         | Resolves                                                                                                                                                                                    |
| 07         | `dev-profile-lvs/.env:124`                                                                                                                | Resolves                                                                                                                                                                                    |
| 07         | CAR-internal (`tool_factory.py:210-252`, `storage_tool.py:100-111`, `neo4j_db.py:320-325`, `milvus_db.py:443`, `elasticsearch_db.py:406`) | Not in the VSS repo; the CAR pin is unchanged at 3.1.0, so presumed stable (not re-read) **[A]**                                                                                            |
| 07 (ours)  | `docker-compose.prod.yml:562` (redis pin)                                                                                                 | Moved → `:570`                                                                                                                                                                              |
| 07 (ours)  | `backend/models/event.py:90,192-256`                                                                                                      | Resolves                                                                                                                                                                                    |
| 06 (ours)  | `camera.py:126`, `:170`                                                                                                                   | Resolve                                                                                                                                                                                     |

---

## Open questions

1. Does llama.cpp@b7972's `/completion` silently ignore `nvext`, confirming that our "guided JSON" is a no-op? One request settles it **[?]**.
2. Which VL model gives the best false-positive suppression on the boring-frames set: Qwen3-VL-4B/8B GGUF (runs on b7972), or Nemotron-Nano-12B-v2-VL (needs a llama.cpp bump past 2026-02-14)? And does `choice` vs `json_schema` matter? There is no in-repo evidence beyond RT-VLM's fail-closed choice test **[?]**.
3. Can RT-VLM start beside a resident llama.cpp on a 24-32 GB card? This depends on whether vLLM 0.17's free-memory check counts other processes. The two comments in `dev-profile.sh` (`:611-613` vs `:1211-1214`) describe it differently **[?]**.
4. Would upstream accept wiring vLLM `enable_sleep_mode` plus a `/sleep` route into RT-VLM as the duty-cycle contribution **[?]**?
5. Does the VSS agent run against llama.cpp end to end?
   - Does `/v1/responses` at b7972 handle `tools`?
   - Does `vss_fastapi` boot with dummy VST URLs?
   - How reliable is Q4 30B-A3B tool calling in the `top_agent` loop **[?]**?
6. Does b7972 load the Nemotron-3.5-Lightning GGUF (`nemotron_h` + MTP) **[?]**?
7. Real RT-CV and RT-Embed VRAM on a consumer card at 1-4 live streams, and RT-Embed steady-state at batch 2 or 4 **[?]**.
8. Does RT-CV `stream/add file:///x.jpg` process a single JPEG at all **[?]**?
9. **Redistribution.** The source is Apache-2.0 (`LICENSE:3`), but microservice images are under the "NVIDIA Software and Model Evaluation License Agreement" (`docs/License-Information.mdx:6`) and the NGC images under the SLA. Can a consumer product ship images we build from Apache source on anonymous nvcr base images? This is a legal question, not a technical one **[?]**.
10. Are there non-`develop` release tags on ghcr (only the first 200 tags were listed), or are releases NGC-only **[?]**?
