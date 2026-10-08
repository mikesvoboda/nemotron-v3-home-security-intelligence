# AI Services Configuration

> Configure environment variables for AI inference services.

**Time to read:** ~12 min
**Prerequisites:** [AI Installation](ai-installation.md)

---

## The Two AI Services

Every knob below belongs to one of two containers:

| Service      | Port          | Configured by                                                   |
| ------------ | ------------- | --------------------------------------------------------------- |
| `ai-gateway` | 8090 (m 8002) | `GATEWAY_MODEL_SET`, `GATEWAY_ENABLE_THREAT`, `GPU_AI_SERVICES` |
| `ai-vlm`     | 8098          | the `VLM_*` group and `GPU_LLM`                                 |

The backend's own routing to them is `USE_AI_GATEWAY` / `AI_GATEWAY_URL` /
`AI_VLM_URL`. The face, plate and person-re-ID lookup legs run in-process in the
backend and are governed by `BACKEND_MODEL_PRELOAD` — not by a service URL.

### Startup Script Variables

The only host-run AI script in the tree is `ai/start_detector.sh` (a development
stand-in for the gateway's detection router). It reads:

| Variable      | Used by                | Default                                                                         |
| ------------- | ---------------------- | ------------------------------------------------------------------------------- |
| `YOLO26_PORT` | `ai/start_detector.sh` | `8090` (the script's default; `.env.example` ships `8095` for the dev stand-in) |
| `PORT`        | `ai/yolo26/model.py`   | inherited from `YOLO26_PORT`                                                    |
| `HOST`        | `ai/yolo26/model.py`   | `0.0.0.0`                                                                       |

In compose, read logs with
`podman compose -f docker-compose.prod.yml logs ai-gateway` and
`podman compose -f docker-compose.prod.yml logs ai-vlm`.

### Pipeline and Residency Selectors

These three decide what the stack even loads. Two of them are **pinned by tests** to
agree with each other and with `.env.example`, so changing a shipped default there is a
gate edit, not a config edit.

| Variable                | Shipped | Meaning                                                                                                                   |
| ----------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| `PIPELINE_MODE`         | `vlm`   | The only accepted value. Any other value, `legacy` included, **raises at boot** (`backend/core/config.py`)                |
| `GATEWAY_MODEL_SET`     | `vlm`   | Triton residency set: `yolo26` + `reid`. `vlm` is the only accepted name; `full` gets a named refusal                     |
| `GATEWAY_ENABLE_THREAT` | `false` | Opt-in lane: adds the `threat` Triton model. It does not add a specialist to the prompt — see §4 of the current-state doc |
| `BACKEND_MODEL_PRELOAD` | `false` | `true` makes the boot sweep load the face and re-ID lookup weights. `setup.py` writes `true` only at **>= 24 GB** VRAM    |

With `BACKEND_MODEL_PRELOAD=false` the `faces` and `person_reid` lines read
`unavailable` on every event and nothing errors. The query that answers whether a leg
has ever run is `curl -s http://localhost:8000/metrics | grep hsi_specialist_unavailable_total`.

---

## ai-vlm (the Reasoning Engine)

llama.cpp serving a Qwen3-VL GGUF plus its mmproj projector, OpenAI-compatible on
`POST /v1/chat/completions`. **It is in the default compose set** — a plain
`up -d` starts it (until UR-18 it sat behind a `vlm` profile that had to be named
explicitly).

### Served Model (operator-placed weights)

| Variable          | Default                                        | Notes                                                                              |
| ----------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| `VLM_MODEL_PATH`  | `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`      | **container** path; host dir `${AI_MODELS_PATH}/vlm` mounts read-only at `/models` |
| `VLM_MMPROJ_PATH` | `/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` | The projector. Empty ⇒ a text-only serve that still passes `/health`               |
| `VLM_MODEL_ID`    | `Qwen3VL-8B-Instruct-Q4_K_M`                   | Provenance label on a degraded verification row; move it with the paths            |
| `VLM_MODEL_ALIAS` | `Qwen3VL-8B`                                   | The name `/v1/models` and `/props` report                                          |

The four — `VLM_MODEL_ID`, `VLM_MODEL_PATH`, `VLM_MMPROJ_PATH`, `MODEL_ALIAS` — are one
identity in four spellings and are pinned together by `test_ai_vlm_compose_service.py`.
Change them as a set.

### Slot Sizing

| Variable                 | Default | Notes                                                                                                   |
| ------------------------ | ------- | ------------------------------------------------------------------------------------------------------- |
| `VLM_CTX_SIZE`           | `32768` | Total llama.cpp pool. Read by **two** processes: the server, and the backend's prompt budget            |
| `VLM_PARALLEL`           | `2`     | Slots the pool is split across. One request occupies one slot ⇒ per-request budget is 16,384            |
| `VLM_THREADS`            | `4`     | Match to the container CPU limit (compose sets `cpus: 4`)                                               |
| `VLM_BATCH_SIZE`         | `2048`  | Prompt-processing batch                                                                                 |
| `VLM_UBATCH_SIZE`        | `512`   | Sequence-parallel batch                                                                                 |
| `VLM_CACHE_TYPE_K`       | `q8_0`  | KV quantization — halves the f16 pool                                                                   |
| `VLM_CACHE_TYPE_V`       | `q8_0`  | Needs flash attention, which the next line enables                                                      |
| `VLM_FLASH_ATTENTION`    | `true`  |                                                                                                         |
| `VLM_GPU_LAYERS`         | `auto`  | `auto` lets llama.cpp's `--fit` decide by free VRAM                                                     |
| `VLM_SLEEP_IDLE_SECONDS` | `300`   | Residency: after this idle time the weights go to CPU RAM and the VRAM is released. Empty = never sleep |

`VLM_CTX_SIZE // VLM_PARALLEL` is also the backend's `vlm_context_window`: the client
**fits** the prompt to that slot before sending it (dropping the weakest detection rows
and saying so in the prompt). Raise the pool and the client follows; shrink the pair and
a full batch is fitted, not truncated mid-token.

### Client Timeouts and Guards

| Variable                        | Default                                                 | Notes                                                                                                        |
| ------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `AI_VLM_URL`                    | `http://localhost:8098` (compose: `http://ai-vlm:8098`) | The URL the backend dials for `vlm_assess`                                                                   |
| `AI_VLM_PORT`                   | `8098`                                                  | Host loopback mapping only. The **container** port is fixed at 8098, so the internal URL never depends on it |
| `AI_VLM_READ_TIMEOUT`           | `25.0`                                                  | Per-read idle budget for an attempt (read or write phase); a timeout is a budget — not retried, no breaker charge            |
| `AI_VLM_WAKE_TIMEOUT_SECONDS`   | `90.0`                                                  | Budget for a wake-from-sleep ping. A failed wake is swallowed, not retried                                   |
| `VLM_MAX_IMAGE_BYTES`           | `8388608`                                               | Largest single key frame to embed. An oversized capture is a slot overflow that reads as an outage           |
| `VLM_ENFORCEMENT_PROBE_ENABLED` | `true`                                                  | One JSON-schema probe per endpoint+build before the first verdict is trusted                                 |
| `VLM_REQUIRED_BUILD`            | `b7972`                                                 | `build_info` substring the probe asserts against `/props`. Empty skips the assertion                         |

---

## YOLO26 Detection Server (standalone, host-run)

Configuration for `ai/yolo26/model.py` when you run it directly on the host.
**Production detection does not use this server** — YOLO26 runs as an ONNX Runtime model
inside the `ai-gateway` Triton container (`/yolo26` router); the TensorRT and
`torch.compile` variables below apply only to the standalone host-run server.

#### Core Configuration

| Variable                       | Description                                        | Default                                      |
| ------------------------------ | -------------------------------------------------- | -------------------------------------------- |
| `YOLO26_MODEL_PATH`            | Path to TensorRT engine (.engine) or PyTorch model | `/models/yolo26/exports/yolo26m_fp16.engine` |
| `YOLO26_CONFIDENCE`            | Detection confidence threshold (0.0-1.0)           | `0.5`                                        |
| `YOLO26_CACHE_CLEAR_FREQUENCY` | Clear CUDA cache every N detections (0 to disable) | `1`                                          |
| `PORT`                         | Server port (direct execution)                     | `8095`                                       |
| `HOST`                         | Bind address                                       | `0.0.0.0`                                    |

#### TensorRT Engine Paths

TensorRT engines are GPU-architecture specific. Use the appropriate engine for your deployment:

| Precision | Engine Path                                  | VRAM   | Latency | Use Case                      |
| --------- | -------------------------------------------- | ------ | ------- | ----------------------------- |
| **FP16**  | `/models/yolo26/exports/yolo26m_fp16.engine` | ~2 GB  | 10-20ms | Default, highest accuracy     |
| **INT8**  | `/models/yolo26/exports/yolo26m_int8.engine` | ~1.5GB | 5-10ms  | High throughput, multi-camera |
| **PT**    | `/models/yolo26/yolo26m.pt` (fallback)       | ~3 GB  | 30-50ms | Development, TensorRT unavail |

Host-run engines are conventionally stored under
`${AI_MODELS_PATH:-/export/ai_models}/model-zoo/yolo26/exports/`. The gateway path is
different: `ai/triton/model_repository/yolo26` runs an FP32 **ONNX** model on the ONNX
Runtime CUDA execution provider (NEM-5551 — INT8 ONNX was incompatible with the CUDA
provider), so no TensorRT engine is involved in the compose stack.

#### TensorRT Version Compatibility

| Variable               | Description                                               | Default   |
| ---------------------- | --------------------------------------------------------- | --------- |
| `YOLO26_AUTO_REBUILD`  | Auto-rebuild engine on TensorRT version mismatch          | `true`    |
| `YOLO26_PT_MODEL_PATH` | Path to source .pt model for rebuilding (if auto-rebuild) | (derived) |

When the TensorRT runtime version differs from the engine version:

1. The server detects the version mismatch error
2. If `YOLO26_AUTO_REBUILD=true`, it rebuilds the engine from the .pt model
3. If rebuild fails or is disabled, it falls back to PyTorch inference

#### torch.compile Optimization (PyTorch fallback only)

When using PyTorch models (not TensorRT engines), torch.compile provides 15-30% speedup:

| Variable                  | Description                           | Default           |
| ------------------------- | ------------------------------------- | ----------------- |
| `TORCH_COMPILE_ENABLED`   | Enable PyTorch 2.0+ graph compilation | `true`            |
| `TORCH_COMPILE_MODE`      | Compilation mode                      | `reduce-overhead` |
| `TORCH_COMPILE_BACKEND`   | Compilation backend                   | `inductor`        |
| `TORCH_COMPILE_CACHE_DIR` | Cache directory for compiled graphs   | (system default)  |

**Compilation modes:**

- `default` - Balanced optimization
- `reduce-overhead` - Faster compilation, good speedup (recommended)
- `max-autotune` - Best performance, slower compilation

> **Note:** torch.compile is automatically skipped for TensorRT engines since they are already graph-optimized.

#### Exporting TensorRT Engines

Host-side engine building runs through the prebuild script (the gateway's Triton export
pipeline `ai/gateway/export/export_all.sh` produces the ONNX path Triton serves):

```bash
# Build the FP16 engine for the local GPU (ultralytics .pt -> TensorRT .engine)
./scripts/prebuild-tensorrt-engines.sh yolo26
```

**INT8 calibration requirements** (for the archived INT8 export CLI, kept at
`archive/ai-yolo26-image/export_tensorrt.py`):

- 100-500 representative images from your deployment environment
- Cover various lighting conditions and camera angles
- Include all security-relevant object classes

For the full export-option reference, see
`archive/ai-yolo26-image/README.md`.

---

## Backend Configuration

These configure how the backend connects to AI services (`backend/core/config.py`):

| Variable               | Description                                    | Default                                                          |
| ---------------------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| `USE_AI_GATEWAY`       | Route the detection client through the gateway | `false` in code, `true` in compose/`.env`                        |
| `AI_GATEWAY_URL`       | Gateway base URL when `USE_AI_GATEWAY=true`    | none in code, `http://ai-gateway:8090` in compose                |
| `YOLO26_URL`           | Full URL to the detection router               | `http://ai-gateway:8090/yolo26`                                  |
| `AI_VLM_URL`           | The `vlm_assess` engine                        | `http://localhost:8098` in code, `http://ai-vlm:8098` in compose |
| `ENRICHMENT_LIGHT_URL` | `/enrich-lt` readiness probe target            | `http://localhost:8090/enrich-lt`                                |
| `YOLO26_API_KEY`       | API key for YOLO26 authentication              | (none)                                                           |

`ENRICHMENT_LIGHT_URL` is a **readiness** target: `api/routes/model_management.py`
probes it to report gateway health. Nothing calls it for inference — the live re-ID leg
is `osnet_loader`, in-process.

---

## Setting Up Environment Variables

The backend reads settings from the process environment first, then `data/runtime.env`,
then the `.env` file at the project root (`backend/core/config.py` via pydantic-settings).
Copy the template once and edit it:

```bash
cp .env.example .env
chmod 600 .env
# edit values with your editor
```

`ai/start_detector.sh` inherits variables from your shell, so export them there if you
run the detection server outside compose.

---

## Container Networking

When AI services run in containers, use appropriate host resolution:

> For a decision table and copy/paste `.env` snippets for every deployment mode, use: **[Deployment Modes & AI Networking](deployment-modes.md)**.

| Platform | Runtime        | AI Service URLs                        |
| -------- | -------------- | -------------------------------------- |
| macOS    | Docker Desktop | `http://host.docker.internal:8090`     |
| macOS    | Podman         | `http://host.containers.internal:8090` |
| Linux    | Docker/Podman  | `http://192.168.1.100:8090` (host IP)  |

Both AI host ports are published as `127.0.0.1:${PORT}` by default — expose them via a
reverse proxy or SSH tunnel before pointing a remote backend at a host IP.

### Production compose DNS (recommended)

When running `docker-compose.prod.yml`, the backend reaches the AI services by compose
DNS — compose sets these itself, no `.env` entries needed:

```bash
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
YOLO26_URL=http://ai-gateway:8090/yolo26
AI_VLM_URL=http://ai-vlm:8098
```

**Example .env for macOS with Docker (backend on the host):**

```bash
YOLO26_URL=http://host.docker.internal:8090/yolo26
AI_VLM_URL=http://host.docker.internal:8098
```

**Example .env for macOS with Podman:**

```bash
export AI_HOST=host.containers.internal
YOLO26_URL=http://${AI_HOST}:8090/yolo26
AI_VLM_URL=http://${AI_HOST}:8098
```

**Example .env for Linux:**

```bash
export AI_HOST=$(hostname -I | awk '{print $1}')
YOLO26_URL=http://${AI_HOST}:8090/yolo26
AI_VLM_URL=http://${AI_HOST}:8098
```

---

## Detection Settings

| Variable                         | Description                  | Default                                          |
| -------------------------------- | ---------------------------- | ------------------------------------------------ |
| `DETECTION_CONFIDENCE_THRESHOLD` | Minimum confidence to store  | `0.40` in `config.py`; `.env.example` sets `0.5` |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | Threshold for fast-path      | `2.0` in code — disabled                         |
| `FAST_PATH_OBJECT_TYPES`         | Types eligible for fast-path | `[]` in code                                     |

> [!WARNING]
> **The fast path is disabled by design.** `config.py` ships
> `fast_path_confidence_threshold = 2.0` (an impossible value) and an empty
> `FAST_PATH_OBJECT_TYPES`, because the fast path bypasses the specialist legs and the
> VLM then scores on partial data. Do not lower these unless the specialists are added
> to the fast path.

**Confidence threshold trade-offs:**

- **Lower (0.3-0.5):** More detections, more false positives
- **Higher (0.6-0.8):** Fewer detections, fewer false positives

---

## Timeout Settings

| Variable                      | Description                  | Default              |
| ----------------------------- | ---------------------------- | -------------------- |
| `AI_CONNECT_TIMEOUT`          | Connection timeout (seconds) | `10.0`               |
| `AI_HEALTH_TIMEOUT`           | Health-check timeout         | `5.0`                |
| `YOLO26_READ_TIMEOUT`         | Detection read timeout       | `30.0` (range 5–120) |
| `AI_VLM_READ_TIMEOUT`         | `vlm_assess` read timeout    | `25.0` (range 5–300) |
| `AI_VLM_WAKE_TIMEOUT_SECONDS` | Wake-from-sleep ping budget  | `90.0` (range 5–300) |

> [!NOTE]
> Older docs said `YOLO26_READ_TIMEOUT` defaults to `60.0`; `backend/core/config.py`
> currently defaults to `30.0`.

---

## Systemd Services

There are no systemd units for the AI services in this repository — the supported
production path is `docker-compose.prod.yml` (Podman). The only systemd units that ship are
monitoring extras (`monitoring/cadvisor/cadvisor.service`,
`monitoring/dcgm/dcgm-exporter.service`, both rootful).

---

## Complete Example .env

```bash
# --- AI service routing (production compose sets these itself — needed only when
#     the backend runs on the host against AI on the host) ---
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://localhost:8090
YOLO26_URL=http://localhost:8090/yolo26
AI_VLM_URL=http://localhost:8098

# --- Pipeline + residency selectors (pinned to agree; see .env.example) ---
PIPELINE_MODE=vlm
GATEWAY_MODEL_SET=vlm
GATEWAY_ENABLE_THREAT=false
BACKEND_MODEL_PRELOAD=false

# --- ai-vlm: served model (container paths; host dir is ${AI_MODELS_PATH}/vlm) ---
VLM_MODEL_PATH=/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf
VLM_MMPROJ_PATH=/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf
VLM_MODEL_ID=Qwen3VL-8B-Instruct-Q4_K_M

# --- ai-vlm: slot sizing (read by the server AND by the backend's prompt budget) ---
VLM_CTX_SIZE=32768
VLM_PARALLEL=2

# --- Standalone host-run YOLO26 server only (not used by the compose gateway) ---
# YOLO26_MODEL_PATH=${AI_MODELS_PATH:-/export/ai_models}/model-zoo/yolo26/exports/yolo26m_fp16.engine
# TORCH_COMPILE_ENABLED=true

# --- Detection tuning ---
DETECTION_CONFIDENCE_THRESHOLD=0.5

# --- Timeouts ---
AI_CONNECT_TIMEOUT=10.0
YOLO26_READ_TIMEOUT=30.0
AI_VLM_READ_TIMEOUT=25.0
```

---

## Next Steps

- [AI Services](ai-services.md) - Start and verify services
- [AI Troubleshooting](ai-troubleshooting.md) - Common issues and solutions
- [AI Performance](ai-performance.md) - Performance tuning

---

## See Also

- [Environment Variable Reference](../reference/config/env-reference.md) - Complete configuration reference
- [Risk Levels Reference](../reference/config/risk-levels.md) - Severity threshold configuration
- [AI TLS](ai-tls.md) - Secure communications setup

---

[Back to Operator Hub](README.md)
