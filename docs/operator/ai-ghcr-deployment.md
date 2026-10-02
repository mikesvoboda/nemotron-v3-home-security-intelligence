# AI Services GHCR Deployment

> Deploy AI services using containers from GitHub Container Registry (GHCR).

**Time to read:** ~12 min
**Prerequisites:** [AI Installation](ai-installation.md), [GPU Setup](gpu-setup.md)

---

## Read This First: What GHCR Actually Ships

The Deploy workflow (`.github/workflows/deploy.yml`, runs on every push to `main`)
publishes **two images and no more**: `backend` and `frontend`, each linux/amd64 +
linux/arm64, tagged `latest` plus the bare commit SHA.

That means `docker-compose.ghcr.yml` — the "pull everything pre-built" surface — cannot
actually run the shipped AI path as written:

| Fact                                                       | Consequence                                                                                                                                     |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `ghcr.yml` declares **19 services, none behind a profile** | A default `up -d` there starts everything it knows about                                                                                        |
| `ghcr.yml` has **no `ai-vlm` service at all**              | The GHCR surface ships **no reasoning engine**. `PIPELINE_MODE=vlm` with no VLM means every event lands `verification_failed` with a NULL score |
| `ghcr.yml` pulls `…/ai-gateway:${IMAGE_TAG:-latest}`       | Nobody publishes that tag — `deploy.yml`'s matrix is backend + frontend only                                                                    |
| `ghcr.yml` sets no `AI_VLM_URL`                            | Even a bolted-on `ai-vlm` would be dialed at the backend's `localhost:8098` default                                                             |

This is a **known, owner-adjudicated publish gap**, recorded in the header of
`deploy.yml` itself:

> _The shipped GPU services `ai-gateway` and `ai-vlm` are built by compose and were never
> matrix images here; the ghcr compose pulling `ai-gateway` (and having no `ai-vlm`
> service) is a reported publish gap, owner-adjudicated — do not "fix" it here without a
> ruling._

**Practical rule: use `docker-compose.prod.yml` for any deployment that must produce
verdicts.** Use the GHCR file only when you deliberately want the detection-only shape
and accept that events will carry no risk score. If you want GHCR to ship the VLM, that
is an owner decision first — §9 of
[AI pipeline: current state](../architecture/ai-pipeline-current-state.md) records this
as unsettled — not an edit to this page.

### Image Availability

| Service                                      | Source                                                | Notes                                                                       |
| -------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------- |
| **backend**                                  | `…/nemotron-v3-home-security-intelligence/backend`    | Published on every merge to main (multi-arch)                               |
| **frontend**                                 | `…/nemotron-v3-home-security-intelligence/frontend`   | Published on every merge to main (multi-arch)                               |
| **ai-gateway**                               | `…/nemotron-v3-home-security-intelligence/ai-gateway` | **Referenced by `ghcr.yml`; never built by CI.** Build locally              |
| **ai-vlm**                                   | not published                                         | No GHCR service exists; built locally from `ai/vlm/Dockerfile`              |
| `ai-llm-vllm` (prod compose, `vllm` profile) | not published                                         | Local build; an opt-in benchmarking harness, not the shipped reasoning path |

### Why the GPU Services Are Built Locally

1. **Model files** come from the `models.yml` manifest at runtime and are mounted, not
   baked: the download rule selects **5 of the 10 catalogue entries, 763 MB** by the
   manifest's `size_mb` estimates (the full 10-entry manifest sums to 1,483 MB). The
   VLM's GGUF pair is operator-placed and provisioned by no script at all.
2. **GPU drivers**: the CUDA version must match the host's nvidia-container-toolkit.
3. **Build customization**: `CUDA_ARCHITECTURES` is a per-host build arg — the same
   `ai/vlm/Dockerfile` builds compute `103` on one box and `86` on another.
4. **Storage costs**: multi-GB images are expensive to host and transfer.

---

## Quick Start (recommended: prod compose)

```bash
# 1. Pull the two images GHCR actually publishes
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# 2. Build the AI containers locally (first time only)
podman compose -f docker-compose.prod.yml build ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm build ai-vlm

# 3. Download models (manifest: models.yml), then place the VLM GGUF pair yourself
./ai/download_models.sh
#   ${AI_MODELS_PATH}/vlm/{Qwen3VL-8B-Instruct-Q4_K_M,mmproj-Qwen3VL-8B-Instruct-Q8_0}.gguf

# 4. Start the full stack — the profile is what starts the reasoning engine
podman compose -f docker-compose.prod.yml --profile vlm up -d

# 5. Verify
curl -s http://localhost:8000/api/system/health/ready | jq
curl -s http://localhost:8090/health | jq       # ai-gateway
curl -s http://localhost:8098/props  | jq        # ai-vlm served model + build
```

`podman compose ... build ai-vlm` **without** `--profile vlm` resolves to nothing:
podman-compose drops a service whose profile is inactive before it resolves names on the
command line. The same rule applies to `up`, `logs`, `ps`, and `stop`.

### Deploy Core AI Only (detection, no verdicts)

```bash
podman compose -f docker-compose.prod.yml build ai-gateway
podman compose -f docker-compose.prod.yml up -d ai-gateway

curl http://localhost:8090/health   # ai-gateway (all Triton models)
```

Be deliberate about this: without `ai-vlm` the pipeline still writes Events, and their
`risk_score`/`risk_level` are NULL with `verdict = 'verification_failed'`. That is the
shape of a "successful" detection-only deploy.

---

## AI Container Reference

### ai-gateway (Triton + FastAPI)

One container, **two routers**: `/yolo26` (detection) and `/enrich-lt` (the resident
`threat` + `reid` Triton models, used today as a readiness lane).

| Property         | Value                                                                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ports**        | `${AI_GATEWAY_PORT:-8090}` (API), `${AI_GATEWAY_METRICS_PORT:-8002}` (Triton metrics)                                                          |
| **Base Image**   | Triton Inference Server (`ai/gateway/Dockerfile`)                                                                                              |
| **Model set**    | `GATEWAY_MODEL_SET=${GATEWAY_MODEL_SET:-vlm}` → the Triton repository holds `yolo26` + `reid`, plus `threat` when `GATEWAY_ENABLE_THREAT=true` |
| **VRAM**         | Triton residency for the shipped set (GPU `GPU_AI_SERVICES`, default 1)                                                                        |
| **Health check** | `GET /health` — `healthy` only when Triton and all resident models are ready (`start_period` 180s)                                             |
| **Limits**       | 20G memory, 8 CPUs                                                                                                                             |

**Build:**

```bash
podman compose -f docker-compose.prod.yml build ai-gateway
```

**Volume Mounts** (from `docker-compose.prod.yml`):

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo:/models/zoo:ro
  - ${AI_MODELS_PATH:-/export/ai_models}/triton:/models/cache
  - ${AI_MODELS_PATH:-/export/ai_models}/quantized:/models/quantized:ro
  - triton-kernel-cache:/root/.nv
  - triton-tmp-cache:/tmp
  - ${HF_CACHE_PATH:-/home/ubuntu/.cache/huggingface}:/root/.cache/huggingface
```

**Notable environment:** `GATEWAY_PORT=8090`,
`GATEWAY_MODEL_SET=${GATEWAY_MODEL_SET:-vlm}` and
`GATEWAY_ENABLE_THREAT=${GATEWAY_ENABLE_THREAT:-false}` (both hard-raise on any other
value), `CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}` (all GPUs are passed via CDI; this
selects the card — see [GPU Setup](gpu-setup.md)), and
`HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-1}`.

### ai-vlm (llama.cpp + mmproj, profile `vlm`)

| Property         | Value                                                                        |
| ---------------- | ---------------------------------------------------------------------------- |
| **Port**         | `127.0.0.1:${AI_VLM_PORT:-8098}:8098` (container port fixed at 8098)         |
| **Profile**      | `vlm` — **off unless you name it**                                           |
| **Base Image**   | llama.cpp built in-image (`ai/vlm/Dockerfile`)                               |
| **Model**        | Operator-placed GGUF pair; **no script fetches it**                          |
| **Health check** | `GET /health`, `start_period` 120s — does **not** prove the projector loaded |
| **Limits**       | 10G memory, 4 CPUs, one GPU (`GPU_LLM`, default 0)                           |

**Build and start:**

```bash
podman compose -f docker-compose.prod.yml --profile vlm build ai-vlm
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

**Environment Variables** (compose reads these from `.env`; container-side names in
parentheses):

| Variable                 | Default                                        | Compose name         |
| ------------------------ | ---------------------------------------------- | -------------------- |
| `VLM_MODEL_PATH`         | `/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf`      | `MODEL_PATH`         |
| `VLM_MMPROJ_PATH`        | `/models/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf` | `MMPROJ_PATH`        |
| `VLM_MODEL_ALIAS`        | `Qwen3VL-8B`                                   | `MODEL_ALIAS`        |
| `VLM_GPU_LAYERS`         | `auto`                                         | `GPU_LAYERS`         |
| `VLM_CTX_SIZE`           | `32768`                                        | `CTX_SIZE`           |
| `VLM_PARALLEL`           | `2`                                            | `PARALLEL`           |
| `VLM_SLEEP_IDLE_SECONDS` | `300`                                          | `SLEEP_IDLE_SECONDS` |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/vlm:/models:ro
  - llama-cache:/home/llama/.cache
  - llama-nv-cache:/home/llama/.nv
```

**Model placement:** nothing in this repository downloads these weights — their identity
is operator config. Place both files (5,027,784,800 B main + 752,289,728 B projector for
the shipped 8B) under `${AI_MODELS_PATH}/vlm/` and `chmod 644` them; the service runs as
uid 1000 and a mode-640 fetch reads as `Permission denied`. Take the **Q8_0** projector,
not the F16 one the same repo ships.

### The Lookup Legs Are Not Containers

Faces, plates and person re-ID run **in-process in the backend**
(`face_recognizer_loader`, `fast_alpr_loader`, `osnet_loader`) and are governed by
`BACKEND_MODEL_PRELOAD`, which ships `false`; `setup.py` sets it `true` only at >= 24 GB
VRAM. There is no image to pull and no port to probe for them — read
`hsi_specialist_unavailable_total` on `:8000/metrics` instead.

---

## GPU Configuration

`docker-compose.prod.yml` gives each AI container its GPU through the Podman CDI spec
(`nvidia.com/gpu=N` alone creates only `/dev/nvidiaN`, which CUDA cannot initialize):

```yaml
# ai-gateway — passes ALL GPUs so /dev/nvidia0 exists, then restricts inside
devices:
  - nvidia.com/gpu=all
environment:
  - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}

# ai-vlm — single device
devices:
  - nvidia.com/gpu=${GPU_LLM:-0}
environment:
  - CUDA_VISIBLE_DEVICES=${GPU_LLM:-0}
```

See [GPU Setup](gpu-setup.md) for the CDI setup (`sudo nvidia-ctk cdi generate
--output=/etc/cdi/nvidia.yaml`) and the multi-GPU variables.

### Verify GPU Access

```bash
podman run --rm --device nvidia.com/gpu=all \
  docker.io/nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### VRAM Requirements

Sizing is dominated by the VLM identity you configure, because
`VLM_GPU_LAYERS=auto` fits as many layers as the card allows. On top of that budget the
gateway's Triton process and roughly 1.0 GB of lookup-model headroom. There is no
measured residency figure for the shipped identity yet — the bring-up record owns the
per-card numbers, so treat the row below as a shape, not a promise:

| Scenario            | Services                                | Expect                               |
| ------------------- | --------------------------------------- | ------------------------------------ |
| Detection only      | `ai-gateway`                            | Small; Triton's shipped model set    |
| Full shipped path   | `ai-gateway` + `ai-vlm` (8B pair)       | 24 GB card is the comfortable target |
| Everything resident | as above + `BACKEND_MODEL_PRELOAD=true` | ~1.0 GB more, on the gateway's card  |

---

## Deployment Patterns

### Pattern 1: Full Production Stack

```bash
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence
python setup.py                       # creates .env, sets BACKEND_MODEL_PRELOAD by VRAM

podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

podman compose -f docker-compose.prod.yml build ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm build ai-vlm

./ai/download_models.sh               # then place the VLM GGUF pair by hand

podman compose -f docker-compose.prod.yml --profile vlm up -d
```

### Pattern 2: Backend/Frontend from GHCR, AI From Local Build

This is Pattern 1 with the two `podman pull` lines doing the real work: the GHCR images
supply the application tier, and the GPU tier is always a local build. There is no
"detection-only shortcut" variant of this pattern worth naming — skipping `ai-vlm` is a
product decision, not a deployment shape.

### Pattern 3: AI Services on a Separate GPU Host

**On the GPU host:**

```bash
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence
podman compose -f docker-compose.prod.yml build ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm build ai-vlm
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-gateway ai-vlm
```

**On the application host:** point `.env` at the GPU host. Both services publish
`127.0.0.1` only, so a remote box needs a reverse proxy or SSH tunnel first — see
[AI TLS](ai-tls.md) and [Deployment Modes](deployment-modes.md) Mode 4:

```bash
AI_GATEWAY_URL=http://10.0.0.50:8090
AI_VLM_URL=http://10.0.0.50:8098
```

---

## Updating Containers

### Update Backend/Frontend from GHCR

```bash
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest
podman compose -f docker-compose.prod.yml up -d backend frontend
```

### Update AI Services (Rebuild)

```bash
git pull origin main

# --no-cache: cached layers hold stale code
podman compose -f docker-compose.prod.yml build --no-cache ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm build --no-cache ai-vlm

podman compose -f docker-compose.prod.yml up -d ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

### Use a Specific Version (SHA Tag)

```bash
SHA=abc123
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:${SHA}
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:${SHA}
IMAGE_TAG=${SHA} podman compose -f docker-compose.ghcr.yml up -d   # see Read This First
```

---

## Health Verification

```bash
curl http://localhost:8000/api/system/health/ready   # Backend

# AI services
curl http://localhost:8090/health                    # ai-gateway (aggregate)
curl http://localhost:8090/yolo26/health             # per-router
curl http://localhost:8090/enrich-lt/health          # readiness lane
curl http://localhost:8098/health                    # ai-vlm up (NOT: multimodal)
curl http://localhost:8098/props                     # served model + build
```

### Comprehensive Check Script

```bash
#!/bin/bash
echo "=== Health Check ==="

services=(
  "backend:http://localhost:8000/api/system/health/ready"
  "ai-gateway:http://localhost:8090/health"
  "ai-gateway-yolo26:http://localhost:8090/yolo26/health"
  "ai-gateway-enrich-lt:http://localhost:8090/enrich-lt/health"
  "ai-vlm:http://localhost:8098/health"
)

for svc in "${services[@]}"; do
  name="${svc%%:*}"
  url="${svc#*:}"
  if curl -sf "$url" > /dev/null 2>&1; then
    echo "[OK] $name"
  else
    echo "[FAIL] $name ($url)"
  fi
done

# Green above is NOT sufficient: a projector-less llama-server answers /health.
echo "=== Multimodal proof ==="
podman logs ai-vlm 2>&1 | grep -i mmproj || echo "[FAIL] no mmproj line in the serve log"
```

### GPU Utilization Check

```bash
watch -n 1 nvidia-smi
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

---

## Troubleshooting

### Container Fails to Start

```bash
podman compose -f docker-compose.prod.yml logs ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm logs ai-vlm

# Triton model-load failures show up first in the gateway log
podman logs ai-gateway 2>&1 | grep -iE "error|failed|model"

# Check model files exist (the vlm dir is created by the script and filled by YOU)
ls -la "${AI_MODELS_PATH:-/export/ai_models}/vlm/"
ls -la "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/"
```

An `ai-vlm` that is **absent** from `podman ps -a` rather than stopped is a profile
problem, not a crash — see [AI Troubleshooting](ai-troubleshooting.md#ai-vlm-is-not-running).

### GPU Not Available in Container

```bash
nvidia-ctk --version
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
podman run --rm --device nvidia.com/gpu=all \
  docker.io/nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### CUDA Out of Memory

```bash
nvidia-smi
```

Prefer releasing VRAM over shrinking the model: lower `VLM_SLEEP_IDLE_SECONDS` so the
weights return to CPU RAM between bursts, or move the gateway to a second GPU
(`GPU_AI_SERVICES=1`, already the default split). `VLM_GPU_LAYERS=auto` already fits what
the card allows.

### Service Timeout on Startup

| Container    | Healthcheck `start_period` | What happens during startup                 |
| ------------ | -------------------------- | ------------------------------------------- |
| `ai-gateway` | 180s                       | Triton initialises the resident model set   |
| `ai-vlm`     | 120s                       | llama.cpp copies the GGUF pair onto the GPU |

`ai-vlm`'s 120s mirrors the image's own `HEALTHCHECK --start-period=120s` so the two
never disagree about when a cold serve may answer. Whether the shipped 8B pair clears it
is **unmeasured** — if it does not, move both numbers together rather than tearing the
server down for being early.

```bash
podman compose -f docker-compose.prod.yml --profile vlm logs -f ai-vlm
```

---

## Next Steps

- [AI Services](ai-services.md) - Day-to-day service management
- [AI Troubleshooting](ai-troubleshooting.md) - Common issues and solutions
- [AI Performance](ai-performance.md) - Performance tuning
- [Deployment Modes](deployment-modes.md) - Network configuration options

---

## See Also

- [GPU Setup](gpu-setup.md) - GPU driver and container configuration
- [AI Configuration](ai-configuration.md) - Environment variables
- [AI Installation](ai-installation.md) - Prerequisites and model downloads
- [AI pipeline: current state](../architecture/ai-pipeline-current-state.md) - §9 records the GHCR publish gap

---

[Back to Operator Hub](README.md)
