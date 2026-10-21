# AI Pipeline Directory

## Purpose

Contains AI inference services for home security monitoring. What actually
runs in production (`docker-compose.prod.yml` builds exactly two AI images):

| Compose service | Port                 | What it is                                                                                                                                                                                                     |
| --------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ai-vlm`        | 8098 (container)     | The `ai-vlm` llama.cpp engine (VlmAnalyzer; risk reasoning — model identity is config, ledger D5. R8 S2 retired the Nemotron path, 2026-09-29). In the default compose set (since UR-18); build context `vlm/` |
| `ai-gateway`    | 8090 (+8002 metrics) | FastAPI facade over Triton in one container; after the R8 S3 prune (2026-09-29) it serves ONLY `/yolo26` + `/enrich-lt` through Triton (`ai/gateway/AGENTS.md`)                                                |

O3.1 (ruling 210, OD-17 / ruling 89) removed `ai-llm-vllm` and pruned non-shipping
Python modules under `ai/`, leaving:

1. **YOLO26 engine builder** (`yolo26/build_engine.py`) - TensorRT engine builder
   invoked by `scripts/prebuild-tensorrt-engines.sh`
2. **Triton model repository** (`triton/model_repository/`) - model configs
   Triton runs inside the ai-gateway container (`yolo26`, `reid`, `threat`)

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
├── conftest.py            # Pytest configuration for the ai/ tier
├── vlm/                   # ai-vlm compose build context (llama.cpp llama-server + CUDA;
│                          #   container port 8098 — the shipped verdict engine)
├── yolo26/                # YOLO26 TensorRT engine builder (build_engine.py)
├── gateway/               # AI Gateway: FastAPI facade over Triton (port 8090)
│   ├── AGENTS.md          # Gateway documentation
│   ├── main.py            # Routers for yolo26 + enrich-lt only (R8 S3 prune, 2026-09-29)
│   ├── residency.py       # GATEWAY_MODEL_SET pruning (raises on unset/unknown; `full` gone)
│   ├── adapters/          # REST-to-gRPC adapter modules (yolo26.py, enrichment_light.py)
│   ├── export/            # ONNX/TensorRT model export pipeline (yolo26, reid, threat)
│   └── tests/             # Gateway unit tests (mocked Triton)
├── triton/                # Triton model repository (yolo26, reid, threat)
├── tests/                 # Module-hygiene probes (test_module_hygiene.py)
├── download_models.sh     # Download AI models
└── start_detector.sh      # Legacy host-run launcher script
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

### Available Models (4 backend registry entries, 4 enabled; 8 total `models.yml` rows)

| Model                 | VRAM   | Priority | Category  | Notes              |
| --------------------- | ------ | -------- | --------- | ------------------ |
| `osnet-ain-x1-0`      | 100 MB | medium   | embedding | `preload: true`    |
| `face-detector-scrfd` | 0 MB   | low      | detection | `preload: true`    |
| `face-recognizer`     | 0 MB   | low      | embedding | `preload: true`    |
| `fast-alpr`           | 28 MB  | medium   | alpr      | plate detect + OCR |

Four `models.yml` rows are NOT backend in-process zoo entries: `yolo26` (`service: ai-gateway` — Triton `yolo26` behind the gateway `/yolo26` router), `threat-detection-yolov8n` (`service: ai-gateway` — Triton `threat`, reached over `/enrich-lt/threat-detect` when `GATEWAY_ENABLE_THREAT=true`), and the shipped VLM pair `qwen3-vl-8b-instruct` + `qwen3-vl-8b-instruct-mmproj` (`service: ai-vlm`). O3.3 deleted the four dead backend rows (`yolo11-face`, `yolo11-license-plate`, `paddleocr`, `yolo26-general`).

The X-CLIP `action_recognizer` slot was retired with the NEM-5563 move to Triton
`stgcn_action`, and the whole action chain went next: there is no
`/action-classify` adapter after the R8 S3 prune (`ai/gateway/adapters/` holds
`yolo26.py` and `enrichment_light.py` only), and `models.yml` has no
`xclip-base` row. Action recognition is not a shipped capability. (The retired
code sat in the deleted archive tree under ai-enrichment/ and xclip-backend-chain/;
UR-19 deleted the archive tree — recover it from git history.)

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

| Backend Service                       | Talks to                                       | Purpose                          |
| ------------------------------------- | ---------------------------------------------- | -------------------------------- |
| `backend/services/detector_client.py` | YOLO26 API (gateway `/yolo26` or :8095)        | Send images, get detections      |
| `backend/services/vlm_client.py`      | ai-vlm directly (`settings.ai_vlm_url`, :8098) | Analyze batches, get the verdict |

The gateway swap is `use_ai_gateway` + `ai_gateway_url` in
`backend/core/config.py` (env `USE_AI_GATEWAY`, `AI_GATEWAY_URL`), and
`detector_client.py` is the only client that applies it. The four clients this table used to
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
at all (the `ai-llm` service was deleted in R8 S2, and `LLM_PORT` was removed
from `.env.example` in O3.3). `.env.example` also still
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
`YOLO26_ENRICHMENT_MODEL_PATH`) have no serving-code reader left: `git grep`
finds them only in docs and this file, plus the `gpu_config_service.py` line
that still writes `VRAM_BUDGET_GB` into a generated override for the deleted
`ai-enrichment` service. (The archive copies UR-19 deleted are recoverable from
git history.) The two survivors worth knowing:

O3.1 (ruling 210) also pruned the uncalled export scripts and host-run YOLO26
server modules, so model paths for the surviving zoo are `models.yml`
`local_path` rows resolved against `MODEL_ZOO_PATH` (default `/models/model-zoo`);
the Triton side is `ai/triton/model_repository/` (pruned to `yolo26`, `reid`,
`threat`).

## Security-Relevant Classes

The deployed gateway Triton adapter returns all 80 COCO names unfiltered
(`ai/gateway/adapters/yolo26.py`). `backend/ai_contract/fake/app.py` keeps both
tables as data — its default profile is `gateway` (unfiltered) and the
`security` profile switches to the nine security classes (`person`, `car`,
`truck`, `dog`, `cat`, `bird`, `bicycle`, `motorcycle`, `bus`).

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
current 8-row `models.yml` is **3 entries / 102 MB by `size_mb`**: `yolo26`,
`osnet-ain-x1-0`, and `threat-detection-yolov8n`. The 5 `download_method: skip`
rows (`qwen3-vl-8b-instruct`, `qwen3-vl-8b-instruct-mmproj`,
`face-detector-scrfd`, `face-recognizer`, `fast-alpr`) are operator-mounted or
fetched by their libraries at runtime. O3.3 deleted `yolo11-face`,
`yolo11-license-plate`, `paddleocr`, and `yolo26-general` from `models.yml`.
The pair is pinned by
`backend/tests/unit/setup_lib/test_download_models_script_vlm_retirement.py`,
which re-derives the rule and asserts the script's fetch list against it.

The shipped VLM weights are deliberately NOT provisioned here (`grep -c -i qwen`
→ 0): identity is operator config (ledger D5), so `VLM_MODEL_PATH` /
`VLM_MMPROJ_PATH` are read from `${AI_MODELS_PATH}/vlm`, which compose mounts
read-only into ai-vlm at `/models`.

### `start_detector.sh`

Runs YOLO26 server (`python model.py`) on port 8090 by default: the script sets `PORT` from `YOLO26_PORT:-8090`, so it matches the gateway's port for a host-run stand-in; `model.py` itself falls back to `PORT=8095` when the script does not set it.

## NVIDIA Triton Inference Server (NEM-3769)

Triton runs **inside the ai-gateway container** in production
(`entrypoint.sh` boots Triton, waits for readiness, then starts uvicorn - see
`ai/gateway/AGENTS.md`).

```bash
podman compose -f docker-compose.prod.yml up -d ai-gateway

# Gateway health (proxies readiness of the in-container Triton)
curl http://localhost:8090/health
```

For detailed documentation, see `triton/AGENTS.md` and `docs/plans/triton-migration.md`.

## Entry Points

1. **Pipeline overview**: This file
2. **YOLO26 engine builder**: `yolo26/AGENTS.md` and `yolo26/build_engine.py`
3. **Gateway**: `gateway/AGENTS.md` (routers `/yolo26` + `/enrich-lt`)
4. **VLM serving**: `vlm/Dockerfile` (the ai-vlm build context) and, on the
   backend side, `../backend/services/vlm_client.py` /
   `../backend/services/vlm_analyzer.py`
5. **Model Zoo (backend-side)**: `../backend/services/model_zoo.py` + repo-root
   `models.yml`
6. **Triton model repository**: `triton/AGENTS.md` and
   `triton/model_repository/*/config.pbtxt`
7. **Backend integration**: `backend/services/` directory
