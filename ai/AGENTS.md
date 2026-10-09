# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring. What actually
runs in production (`docker-compose.prod.yml` builds exactly two AI images):

| Compose service | Port                 | What it is                                                                                                                                                                                                     |
| --------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai-vlm`        | 8098 (container)     | The `ai-vlm` llama.cpp engine (VlmAnalyzer; risk reasoning — model identity is config, ledger D5. R8 S2 retired the Nemotron path, 2026-09-29). In the default compose set (since UR-18); build context `vlm/` |
| `ai-gateway`    | 8090 (+8002 metrics) | FastAPI facade over Triton in one container; after the R8 S3 prune (2026-09-29) it serves ONLY `/yolo26` + `/enrich-lt` through Triton (`ai/gateway/AGENTS.md`)                                                |

A third AI service, `ai-llm-vllm` (vLLM, host port 8097, `--profile vllm`),
is NEM-5441's benchmarking harness — not shipped serving, and the orchestrator
refuses to manage it (`RETIRED_LLM_SERVICES`).

The remaining capability modules are development/debugging code, not shipped
serving:

1. **YOLO26** (`yolo26/`) - pure-leaf detection contract + host-run dev server
   (`start_detector.sh`; `model.py` falls back to `PORT=8095`)
2. **Triton client + model repository** (`triton/`, NEM-3769) - the standalone
   gRPC client, plus the model repository Triton runs inside the ai-gateway
   container (residency-pruned to `yolo26` + `reid` + optional `threat`)

The backend reaches AI through HTTP clients in `backend/services/`:
`detector_client.py` and `vlm_client.py`. With `USE_AI_GATEWAY=true` +
`AI_GATEWAY_URL` (the production default), the detector client swaps to
`http://ai-gateway:8090/yolo26` (`backend/core/config.py` `use_ai_gateway` /
`ai_gateway_url`); the VLM client always dials `ai_vlm_url` (8098) directly.
The retired CLIP / Florence-2 / enrichment clients and their gateway routers
are gone (R8 S2/S3, 2026-09-29).

## Directory Structure

```
ai/
├── AGENTS.md              # This file
├── __init__.py            # Package init
├── cuda_streams.py        # CUDA streams for parallel preprocessing (NEM-3770)
├── compile_utils.py       # torch.compile() utilities (NEM-3773)
├── batch_utils.py         # Batch processing utilities (NEM-3377)
├── torch_optimizations.py # General PyTorch optimization utilities
├── cuda_graph_manager.py  # CUDA graph management
├── flash_attention_config.py # FlashAttention configuration
├── gpu_memory_pool.py     # GPU memory pool management
├── hub_cache_config.py    # HuggingFace hub cache configuration
├── quantization_config.py # Quantization configuration
├── static_kv_cache.py     # Static KV cache for inference
├── warmup_utils.py        # Model warmup utilities
├── shared/                # Shared utilities (gpu_profiler.py) - see shared/AGENTS.md
├── common/                # Shared TensorRT optimization infrastructure (NEM-3838)
│   ├── AGENTS.md          # TensorRT infrastructure documentation
│   ├── __init__.py        # Package exports
│   ├── tensorrt_utils.py  # ONNX-to-TensorRT conversion, engine management
│   ├── tensorrt_inference.py  # Base classes for TensorRT-accelerated models
│   └── tests/             # Unit tests
│       └── __init__.py    # Package init
├── vlm/                   # ai-vlm compose build context (llama.cpp llama-server + CUDA;
│                          #   container port 8098 — the shipped verdict engine)
├── yolo26/                # Pure-leaf contract for backend prompts + host-run dev server
│                          #   (GPU image retired 2026-09-23; prod: Triton /yolo26 via ai-gateway
│                          #    - see yolo26/AGENTS.md)
├── gateway/               # AI Gateway: FastAPI facade over Triton (port 8090)
│   ├── AGENTS.md          # Gateway documentation
│   ├── main.py            # Routers for yolo26 + enrich-lt only (R8 S3 prune, 2026-09-29)
│   ├── residency.py       # GATEWAY_MODEL_SET pruning (raises on unset/unknown; `full` gone)
│   ├── adapters/          # REST-to-gRPC adapter modules (yolo26.py, enrichment_light.py)
│   ├── export/            # ONNX/TensorRT model export pipeline
│   └── tests/             # Gateway unit tests (mocked Triton)
                          #   (clip/, florence/, enrichment/ and enrichment-light/ were
                          #    deleted with their gateway routers - R8 S3, 2026-09-29)
├── triton/                # Triton client + model repository (NEM-3769)
├── tests/                 # AI-level optimization tests (cuda streams, etc.)
├── download_models.sh     # Download AI models
└── start_detector.sh      # HOST-RUN YOLO26 dev stand-in (YOLO26_PORT, default 8090; the GPU image was retired 2026-09-23 — prod serves via ai-gateway)
                           #   (start_llm.sh/start_nemotron.sh were deleted with the
                           #    retired LLM path - R8 S2, 2026-09-29)
```

## Model Zoo Overview

The on-demand **Model Zoo** now lives in the backend, not in `ai/`:
`backend/services/model_zoo.py` builds its registry from the repo-root
`models.yml` rows whose `service` is `backend`/`both` AND that have an entry in
`_LOADER_MAP`, and `ModelManager` loads a model only when a caller asks for it
and releases the VRAM afterwards. R8 S2 (2026-09-29) retired the attribute /
classification zoo (SigLIP 2, Florence-2-large, YOLO-World, ViTPose,
Depth-Anything, violence, weather, SegFormer, ST-GCN++, FashionCLIP, BRISQUE,
vehicle segment/damage, pet, age, gender, zero-DCE++) with the enrichment tier:
that zoo re-perceived what the shipped VLM already sees from the same key
frames, so what is left is lookups against stores the pixels cannot reach —
plates, faces, registered-person embeddings.

### Available Models (8 registry entries, 7 enabled)

| Model                  | VRAM   | Priority | Category  | Notes                      |
| ---------------------- | ------ | -------- | --------- | -------------------------- |
| `osnet-ain-x1-0`       | 100 MB | medium   | embedding | `preload: true`            |
| `face-detector-scrfd`  | 0 MB   | low      | detection | `preload: true`            |
| `face-recognizer`      | 0 MB   | low      | embedding | `preload: true`            |
| `yolo11-face`          | 200 MB | medium   | detection | on person crops            |
| `yolo11-license-plate` | 300 MB | medium   | detection | on vehicle crops           |
| `fast-alpr`            | 28 MB  | medium   | alpr      | plate detect + OCR         |
| `paddleocr`            | 100 MB | medium   | ocr       | superseded by `fast-alpr`  |
| `yolo26-general`       | 400 MB | medium   | detection | `enabled: false` (TBD row) |

Two `models.yml` rows are NOT zoo entries: `yolo26` (no `_LOADER_MAP` entry —
it is Triton `yolo26` behind the gateway `/yolo26` router) and
`threat-detection-yolov8n` (no `_LOADER_MAP` entry — Triton `threat`, reached
over `/enrich-lt/threat-detect` when `GATEWAY_ENABLE_THREAT=true`).

The X-CLIP `action_recognizer` slot was retired with the NEM-5563 move to Triton
`stgcn_action` (code in `archive/ai-enrichment/`), and the whole action chain
went next: the backend reader is archived in
`archive/xclip-backend-chain/`, there is no `/action-classify` adapter after
the R8 S3 prune (`ai/gateway/adapters/` holds `yolo26.py` and
`enrichment_light.py` only), and `models.yml` has no `xclip-base` row. Action
recognition is not a shipped capability.

### Model Priority System

`models.yml` carries a `priority` per row (`critical`/`high`/`medium`/`low`) and
a `never_evict` flag, both read into `ModelConfig`. After the R8 S2/S3 prune the
only values present are `medium` (8 rows) and `low` (3 rows) — the CRITICAL/HIGH
tiers belonged to the retired attribute zoo.

### VRAM Budget

- `ModelManager` has no fixed GB budget: it loads lazily, tracks
  `total_loaded_vram_mb`, and unloads when the caller's context manager exits.
- `BACKEND_MODEL_PRELOAD` + the rows' `preload: true` drive `main.py`'s boot
  sweep (the face and re-ID legs never trigger a load, so they must be resident).
- `VRAM_BUDGET_GB` survives only as a string `gpu_config_service.py` writes into
  a generated override for an `ai-enrichment` service that no longer exists.

For backend-side documentation, see
[`backend/services/model_zoo.py`](../backend/services/model_zoo.py) and
[`docs/ai/model-zoo.md`](../docs/ai/model-zoo.md).

## Quick Start

### Production (Docker/Podman Containers)

```bash
# Start everything, including the shipped verdict engine ai-vlm:8098 (UR-18:
# ai-vlm is in the default compose set, so a plain up starts it)
podman compose -f docker-compose.prod.yml up -d

# Verify AI containers are running
podman ps --filter name=ai-
```

### Development (Native)

One shell script for native execution remains — `ls ai/start_*.sh` returns
`start_detector.sh` only, because `start_llm.sh` and `start_nemotron.sh` were
deleted with the retired LLM path (R8 S2, 2026-09-29):

```bash
# 1. Download models (first time only)
./ai/download_models.sh

# 2. Start the host-run YOLO26 dev stand-in
./ai/start_detector.sh     # PORT from YOLO26_PORT:-8090 (matches the gateway's
                           #   port for a stand-in; model.py alone falls back
                           #    to PORT=8095)
```

For the VLM natively there is no script: `vlm/Dockerfile` builds llama-server
and the compose service sets `PORT=8098` — run the container, or point
`AI_VLM_URL` at your own llama-server on 8098.

## Architecture

```
Camera Images
      |
      v
+------------------------------------------------------------------+
|  ai-gateway container (8090)                                     |
|  FastAPI routers (/yolo26 + /enrich-lt only, since the R8 S3     |
|  prune) -> Triton (gRPC 8001, same container, GPU)               |
|  Triton repository is residency-pruned to yolo26 + reid          |
|  (+ threat when GATEWAY_ENABLE_THREAT=true)                      |
+------------------------------------------------------------------+
      |   Detections (+ specialist lookups: face / plate / re-ID)
      v
+-----------------------------------------------------+
|              ai-vlm container (8098)                |
|        the ai-vlm llama.cpp engine (VlmAnalyzer;    |
|   risk reasoning — model identity is config, D5)    |
+-----------------------------------------------------+
                        |
                        v
                   Risk Events
```

Native development runs the same flow with the host-run stand-in:
`start_detector.sh` on `YOLO26_PORT:-8090` (`model.py` alone defaults to
`PORT=8095`), plus a llama-server you point `AI_VLM_URL` at. There are no
standalone CLIP / Florence-2 / enrichment / enrichment-light dev servers left —
those servers, their ports (8093 / 8092 / 8094 / 8096) and their routers were
deleted in R8 S2/S3 (2026-09-29).

## Backend Integration

AI clients live in `backend/services/`:

| Backend Service                       | Talks to                                       | Purpose                                               |
| ------------------------------------- | ---------------------------------------------- | ----------------------------------------------------- |
| `backend/services/detector_client.py` | YOLO26 API (gateway `/yolo26` or :8095)        | Send images, get detections                           |
| `backend/services/vlm_client.py`      | ai-vlm directly (`settings.ai_vlm_url`, :8098) | Analyze batches, get the verdict                      |
| `backend/services/reid_matcher.py`    | nothing over HTTP                              | Matches re-ID embeddings already stored on detections |

The gateway swap is `use_ai_gateway` + `ai_gateway_url` in
`backend/core/config.py` (env `USE_AI_GATEWAY`, `AI_GATEWAY_URL`), and
`detector_client.py` is the only client that applies it; `reid_matcher.py` is
DB-side matching, not an AI service client. The four clients this table used to
list alongside them — `nemotron_analyzer.py`, `enrichment_client.py`,
`florence_client.py`, `clip_client.py` — were deleted with the tiers they
talked to (R8 S2/S3, 2026-09-29).

## Environment Variables

### YOLO26

| Variable            | Default                                      | Description              |
| ------------------- | -------------------------------------------- | ------------------------ |
| `YOLO26_MODEL_PATH` | `/models/yolo26/exports/yolo26m_fp16.engine` | TensorRT engine path     |
| `YOLO26_CONFIDENCE` | `0.5`                                        | Min confidence threshold |
| `HOST`              | `0.0.0.0`                                    | Bind address             |
| `PORT`              | `8095`                                       | Server port              |

### ai-vlm (in the default compose set)

The `ai-vlm` llama.cpp engine (VlmAnalyzer; risk reasoning — model identity is
config, ledger D5. R8 S2 retired the Nemotron path, 2026-09-29). The compose
defaults carry the shipped identity, `Qwen3VL-8B-Instruct-Q4_K_M` (owner pick,
ledger item 35, provisional); the mmproj file is what makes llama-server
multimodal. `.env` is the source of truth; compose maps it onto the container
env:

| `.env` variable   | Default (compose)                               | Description                                        |
| ----------------- | ----------------------------------------------- | -------------------------------------------------- |
| `VLM_MODEL_PATH`  | `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`       | Passed to container as `MODEL_PATH`                |
| `VLM_MMPROJ_PATH` | `/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`  | Passed as `MMPROJ_PATH` (multimodal projector)     |
| `VLM_MODEL_ALIAS` | `Qwen3VL-8B`                                    | Passed as `MODEL_ALIAS`                            |
| `AI_VLM_PORT`     | `8098`                                          | Host port (binds 127.0.0.1; container `PORT=8098`) |
| `VLM_GPU_LAYERS`  | `auto` (llama.cpp `--fit` decides by free VRAM) | Passed as `GPU_LAYERS`                             |
| `VLM_CTX_SIZE`    | `32768`                                         | Total llama.cpp context pool (`CTX_SIZE`)          |
| `VLM_PARALLEL`    | `2` (so 16384 tokens per slot)                  | llama.cpp slots (`PARALLEL`)                       |
| `GPU_LLM`         | `0` (from `.env.example`)                       | Which physical GPU the VLM gets                    |

Residency: see `.env.example` / the bring-up record — no measured 24 GB-class
figure exists yet. `LLM_MODEL_PATH` no longer appears in `docker-compose.prod.yml`
at all (the `ai-llm` service was deleted in R8 S2; `.env.example` still declares
`LLM_PORT=8091`, which nothing in compose reads now). `.env.example` also still
carries `CTX_SIZE=262144` / `PARALLEL=8`; those feed only `config.py`'s
`nemotron_context_window` slot-derivation (the shipped engine's own budget is
`vlm_context_window` from `VLM_CTX_SIZE // VLM_PARALLEL`), not a running server.

### AI Gateway

| Variable                                       | Default                  | Description                                                                                                               |
| ---------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `AI_GATEWAY_PORT`                              | `8090`                   | Host port (binds 127.0.0.1)                                                                                               |
| `AI_GATEWAY_METRICS_PORT`                      | `8002`                   | Triton metrics port on host                                                                                               |
| `AI_GATEWAY_URL`                               | `http://ai-gateway:8090` | Backend clients' gateway base URL                                                                                         |
| `USE_AI_GATEWAY`                               | `true`                   | Toggle gateway vs direct-URL clients                                                                                      |
| `GPU_AI_SERVICES`                              | `1`                      | GPU CUDA_VISIBLE_DEVICES for the gateway                                                                                  |
| `VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` | `false`                  | Compose leftover (NEM-5533): the INT8 switch lived in the deleted ai/enrichment/ service, so no live code reads these now |

Two gateway vars the table above used to omit are load-bearing since R8 S3:
`GATEWAY_MODEL_SET` (compose default `vlm`) selects the Triton residency set and
**hard-raises** on an unset or unknown value — `full` is retired, and the pruned
set is `{yolo26, reid, threat}` (`ai/gateway/residency.py`); and
`GATEWAY_ENABLE_THREAT` (default `false`) adds `threat` to the `vlm` set.

Full env table in `ai/gateway/AGENTS.md`.

### Enrichment (Model Zoo)

Retired: R8 S3 (2026-09-29) deleted the ai/enrichment/ and
ai/enrichment-light/ directories, and R8 S2 (2026-09-29) had deleted their
backend clients. The env vars that table documented (`VRAM_BUDGET_GB`,
`VEHICLE_MODEL_PATH`, `PET_MODEL_PATH`/`PET_DEVICE`, `DEPTH_MODEL_PATH`,
`POSE_MODEL_PATH`, `THREAT_MODEL_PATH`, `AGE_MODEL_PATH`, `GENDER_MODEL_PATH`,
`REID_MODEL_PATH`/`REID_DEVICE`, `ACTION_MODEL_PATH`,
`YOLO26_ENRICHMENT_MODEL_PATH`) have no serving-code reader left: outside docs
and `archive/`, `git grep` finds them only in this file, plus the
`gpu_config_service.py` line that still writes `VRAM_BUDGET_GB` into a generated
override for the deleted `ai-enrichment` service. The two survivors worth
knowing:

| Variable                 | Where it lives                                                     |
| ------------------------ | ------------------------------------------------------------------ |
| `CLOTHING_MODEL_PATH`    | read by `ai/gateway/export/export_fashion_clip.py` only            |
| `YOLO26_POSE_MODEL_PATH` | read by `ai/yolo26/pose_estimation.py` (default `yolo11n-pose.pt`) |

Model paths for the surviving zoo are `models.yml` `local_path` rows resolved
against `MODEL_ZOO_PATH` (default `/models/model-zoo`); the Triton side is
`ai/triton/model_repository/` (pruned to `yolo26`, `reid`, `threat`).

## Security-Relevant Classes

The host-run native server filters detections to these nine classes
(`ai/yolo26/model.py`):

```python
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
```

The DEPLOYED path does not: the gateway's Triton adapter returns all 80 COCO
names unfiltered (`ai/gateway/adapters/yolo26.py`), so this filter is a property
of the dev stand-in only. `backend/ai_contract/fake/app.py` keeps both tables as
data — its default profile is `gateway` (unfiltered) and the `security` profile
switches to the nine.

## Risk Scoring

| Score Range | Level    | Description                 |
| ----------- | -------- | --------------------------- |
| 0-29        | Low      | Normal activity             |
| 30-59       | Medium   | Unusual but not threatening |
| 60-84       | High     | Suspicious activity         |
| 85-100      | Critical | Potential security threat   |

The band ends are `SeverityService` config (`SEVERITY_LOW_MAX`/`_MEDIUM_MAX`/
`_HIGH_MAX`, defaults 29/59/84), and the level is always derived from the score
there — the model never emits one.

### Specialist Context for the VLM

`backend/services/vlm_specialists.py` writes one short line per specialist into
the assess prompt. What ships today is the lookup set — the pixels cannot reach
these stores:

- **Face**: `collect_face_text` — matched identity from the face gallery
- **Plate**: `collect_plate_text` — plate reads from the frame's detections
- **Re-ID**: `collect_reid_text` — `Same person seen on front_door camera 5
minutes ago`, or `unavailable (space_mismatch)` / `(no_gallery)`
- **Threat**: `collect_threat_text` is a Rev-7 slot with no consumer, so the
  key is not emitted by default (the F12 ruling keeps Triton threat off)

The lines this section used to list — pose posture, demographics, clothing,
vehicle type, action — came from the enrichment zoo that R8 S2 retired: the VLM
re-perceives those from the same key frames, so they are no longer injected as
context.

## Hardware Requirements

- **GPU**: NVIDIA with CUDA support (tested on RTX A5500 24GB + RTX A400 4GB)
- **Container Runtime**: Podman (project standard; see AGENTS.md) or Docker
  with NVIDIA Container Toolkit
- **Total VRAM**: no measured 24 GB-class figure exists yet for the shipped
  pair — see `.env.example` / the bring-up record. The "~22 GB" this bullet used
  to give belonged to the 30B LLM (~14.7 GB model file) plus the enrichment /
  CLIP / Florence weights, and all three of those are retired, so the number
  describes nothing that runs here.
  - `ai-vlm`: the shipped llama.cpp engine, sized by `VLM_CTX_SIZE=32768` /
    `VLM_PARALLEL=2` (model identity is config, ledger D5)
  - `ai-gateway` / Triton: the residency-pruned repository (yolo26 + reid
    - optional threat), not the 14-model `full` repo the old figure assumed

### Multi-GPU Support

The system supports distributing AI workloads across multiple GPUs. See
**[Multi-GPU Support Guide](../docs/developer/multi-gpu.md)** for
configuration instructions. Production selection is two env vars:
`GPU_LLM` (ai-vlm) and `GPU_AI_SERVICES` (ai-gateway).

**Reference Multi-GPU Configuration (dual GPU A5500 + A400):**

| GPU   | Model     | VRAM  | What runs there (production)              |
| ----- | --------- | ----- | ----------------------------------------- |
| GPU 0 | RTX A5500 | 24 GB | ai-vlm (`GPU_LLM=0`)                      |
| GPU 1 | RTX A400  | 4 GB  | ai-gateway / Triton (`GPU_AI_SERVICES=1`) |

### GPU Configuration Files (Auto-Generated)

The following files are auto-generated by the GPU Configuration Service when you apply changes via the UI:

- Docker Compose override for GPU assignments (in config directory)
- Human-readable GPU assignment reference (in config directory)

**Do not edit manually.** These files may not exist until GPU configuration is applied via the UI.

### Override File Format

Generated shape (service names as they exist in your compose file(s)):

```yaml
# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY
services:
  ai-vlm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
  ai-gateway:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]
```

The generator emits whichever service names the assignments carry, and the two
AI services `docker-compose.prod.yml` actually has are `ai-vlm` and
`ai-gateway`. The service names in `gpu_config_service.py`'s own examples
(`ai-llm`, `ai-enrichment`, `ai-yolo26`) are stale — those services were deleted
in R8 S2/S3, and the VRAM-override branch still writes `VRAM_BUDGET_GB` for an
`ai-enrichment` that no longer exists. For the shipped two-container layout,
prefer the `GPU_LLM` / `GPU_AI_SERVICES` env vars.

### Using the Override File

```bash
# Start with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml up -d

# Restart specific service with GPU override
podman-compose -f docker-compose.prod.yml \
               -f config/docker-compose.gpu-override.yml \
               up -d --force-recreate --no-deps ai-gateway
```

## Startup Scripts

Two scripts exist: `download_models.sh` and `start_detector.sh`.

### `download_models.sh`

The script fetches the **models.yml download set** — the rows
`setup_lib/models_config.py::get_downloadable_models` selects
(`download_method != skip AND (hf_repo OR download_method)`) — which on the
current 10-row `models.yml` is **5 entries / 763 MB by `size_mb`**: `yolo26`,
`osnet-ain-x1-0`, `threat-detection-yolov8n`, `yolo11-face`,
`yolo11-license-plate`. The 5 `download_method: skip` rows
(`face-detector-scrfd`, `face-recognizer`, `fast-alpr`, `paddleocr`,
`yolo26-general`) are fetched by their libraries at runtime. The "25 of 30
entries / 32.79 GiB" figures this file used to quote described the pre-R8
catalogue: those rows left `models.yml` in R8 S2/S3 (2026-09-29) and the fetch
list went with them. The pair is pinned by
`backend/tests/unit/setup_lib/test_download_models_script_vlm_retirement.py`,
which re-derives the rule and asserts the script's fetch list against it.

The shipped VLM weights are deliberately NOT provisioned here (`grep -c -i qwen`
→ 0): identity is operator config (ledger D5), so `VLM_MODEL_PATH` /
`VLM_MMPROJ_PATH` are read from `${AI_MODELS_PATH}/vlm`, which compose mounts
read-only into ai-vlm at `/models`.

`enabled` in models.yml governs backend model_zoo VRAM slots, NOT disk
provisioning. The two `enabled: false` rows today are `yolo26` (n/s/m `.pt` from
ultralytics/assets — `ai/gateway/export/` `export_yolo26.py` +
`scripts/prebuild-tensorrt-engines.sh` need `model-zoo/yolo26/yolo26m.pt` on
disk) and `yolo26-general` (a `_LOADER_MAP` row, so it is a zoo entry, but
disabled and `download_method: skip`).

### `start_detector.sh`

Runs YOLO26 server (`python model.py`) on port 8090 by default: the script sets `PORT` from `YOLO26_PORT:-8090`, so it matches the gateway's port for a host-run stand-in; `model.py` itself falls back to `PORT=8095` when the script does not set it.

## CUDA Streams for Parallel Preprocessing (NEM-3770)

The `cuda_streams.py` module provides CUDA stream management for overlapping preprocessing, inference, and postprocessing operations. This can provide 20-40% throughput improvement for batch processing workloads.

### Key Components

| Component                   | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `CUDAStreamPool`            | Manages a pool of CUDA streams                 |
| `StreamedInferencePipeline` | Three-stage pipeline with overlapped execution |
| `StreamConfig`              | Configuration for stream management            |
| `PipelineStats`             | Statistics from pipeline execution             |

### Environment Variables

| Variable                 | Default | Description                          |
| ------------------------ | ------- | ------------------------------------ |
| `CUDA_STREAMS_ENABLED`   | `true`  | Enable/disable CUDA streams          |
| `CUDA_STREAMS_POOL_SIZE` | `3`     | Number of streams in the pool        |
| `CUDA_STREAMS_PRIORITY`  | `0`     | Stream priority (-1=high, 0=default) |

### Usage Example

```python
from cuda_streams import CUDAStreamPool, StreamedInferencePipeline

# Simple stream pool usage
pool = CUDAStreamPool(num_streams=3)
with pool.get_stream() as stream:
    with torch.cuda.stream(stream):
        tensor = preprocess(image)


# Full pipeline with overlapped execution
def preprocess(images):
    return processor(images, return_tensors="pt").to("cuda")


def postprocess(outputs, inputs):
    return outputs.logits.argmax(dim=-1).tolist()


pipeline = StreamedInferencePipeline(
    model=model,
    preprocess_fn=preprocess,
    postprocess_fn=postprocess,
    batch_size=8,
)
results, stats = pipeline.process_batch(images, return_stats=True)
print(f"Throughput: {stats.throughput_items_per_sec:.1f} items/sec")
```

### Pipeline Architecture

```
   Batch N-1         Batch N          Batch N+1
      │                 │                 │
      │                 │                 │
┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐
│ Postproc  │    │  Preprocess │   │   (waiting) │
│ (Stream 1)│    │  (Stream 0) │   │             │
└───────────┘    └─────────────┘   └─────────────┘
                       │
                 ┌─────▼─────┐
                 │ Inference │
                 │ (Stream 1)│ (waits for preprocess event)
                 └───────────┘
```

### Benefits

- **Overlapped Execution**: Preprocessing of the next batch while current batch is inferring
- **20-40% Throughput Improvement**: Measured on batch processing workloads
- **Automatic Synchronization**: Events ensure proper ordering between stages
- **Graceful Fallback**: Falls back to sequential processing when CUDA unavailable

### Testing

```bash
# Run CUDA streams unit tests
uv run pytest ai/tests/test_cuda_streams.py -v

# Run with CUDA (if available)
uv run pytest ai/tests/test_cuda_streams.py -v -k "cuda"
```

## NVIDIA Triton Inference Server (NEM-3769)

Triton provides production-grade model serving with automatic dynamic batching, model versioning, and multi-model serving.

### Benefits Over Direct Inference

The "Current" column is the pre-migration standalone FastAPI servers — those
servers are deleted (R8 S2/S3, 2026-09-29), so the left side is history, not a
choice still on the table.

| Feature          | Current (FastAPI)      | With Triton                 |
| ---------------- | ---------------------- | --------------------------- |
| Batching         | Manual, single request | Automatic dynamic batching  |
| GPU Utilization  | Suboptimal             | Optimized scheduler         |
| Model Versioning | File-based             | Built-in A/B testing        |
| Monitoring       | Custom metrics         | Native Prometheus           |
| Throughput       | ~25 req/s (concurrent) | ~115 req/s (5x improvement) |

### Quick Start

Triton already runs **inside the ai-gateway container** in production
(`entrypoint.sh` boots Triton, waits for readiness, then uvicorn - see
`ai/gateway/AGENTS.md`). There is no separate `triton` compose profile in
`docker-compose.prod.yml`:

```bash
podman compose -f docker-compose.prod.yml up -d ai-gateway

# Gateway health (proxies readiness of the in-container Triton)
curl http://localhost:8090/health
```

The `TRITON_*` env vars below configure the **standalone client** in
`ai/triton/client.py` (native/dev use, e.g. pointing at a Triton you run
manually). Set `TRITON_ENABLED=true` there only when running that path.

### Environment Variables

| Variable             | Default          | Description               |
| -------------------- | ---------------- | ------------------------- |
| `TRITON_ENABLED`     | `false`          | Enable Triton client      |
| `TRITON_URL`         | `localhost:8001` | gRPC endpoint             |
| `TRITON_HTTP_URL`    | `localhost:8000` | HTTP endpoint             |
| `TRITON_PROTOCOL`    | `grpc`           | Protocol (grpc/http)      |
| `TRITON_MODEL`       | `yolo26`         | Default model             |
| `TRITON_TIMEOUT`     | `60`             | Request timeout (seconds) |
| `TRITON_MAX_RETRIES` | `3`              | Retry attempts            |

### Client Usage

```python
from ai.triton import TritonClient, TritonConfig

config = TritonConfig.from_env()
client = TritonClient(config)

if await client.is_healthy():
    result = await client.detect(image_bytes)
    for det in result.detections:
        print(f"{det.class_name}: {det.confidence:.2f}")

await client.close()
```

For detailed documentation, see `triton/AGENTS.md` and `docs/plans/triton-migration.md`.

## Entry Points

1. **Pipeline overview**: This file
2. **Detection server**: `yolo26/AGENTS.md` and `yolo26/model.py`
3. **Gateway**: `gateway/AGENTS.md` (routers `/yolo26` + `/enrich-lt`)
4. **VLM serving**: `vlm/Dockerfile` (the ai-vlm build context — it carries no
   AGENTS.md) and, on the backend side, `../backend/services/vlm_client.py` /
   `../backend/services/vlm_analyzer.py`
5. **Model Zoo (backend-side)**: `../backend/services/model_zoo.py` + repo-root
   `models.yml`
6. **Triton Inference Server**: `triton/AGENTS.md` (NEM-3769)
   - Client wrapper: `triton/client.py`
   - Model configs: `triton/model_repository/*/config.pbtxt`
   - Migration plan: `docs/plans/triton-migration.md`
7. **Backend integration**: `backend/services/` directory
8. **Optimization utilities**:
   - CUDA streams: `cuda_streams.py` (NEM-3770)
   - torch.compile: `compile_utils.py` (NEM-3773)
   - Batch processing: `batch_utils.py` (NEM-3377)
   - General optimizations: `torch_optimizations.py`
   - CUDA graphs: `cuda_graph_manager.py`
   - FlashAttention: `flash_attention_config.py`
   - GPU memory pool: `gpu_memory_pool.py`
   - Hub cache: `hub_cache_config.py`
   - Quantization: `quantization_config.py`
   - Static KV cache: `static_kv_cache.py`
   - Warmup utilities: `warmup_utils.py`
