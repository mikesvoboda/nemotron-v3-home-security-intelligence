# AI Services GHCR Deployment

> Deploy AI services using containers from GitHub Container Registry (GHCR).

**Time to read:** ~12 min
**Prerequisites:** [AI Installation](ai-installation.md), [GPU Setup](gpu-setup.md)

---

## Overview

The **Deploy** workflow (`.github/workflows/deploy.yml`, runs on every push to `main`)
publishes `backend` and `frontend` (linux/amd64 + linux/arm64) and `ai-llm`
(amd64 only) to GHCR, tagged `latest` plus the bare commit SHA.

The vision models no longer ship as separate images: YOLO26, Florence-2, CLIP and the
enrichment tiers were consolidated into a single **`ai-gateway`** Triton container that
`docker-compose.prod.yml` builds locally from `ai/gateway/Dockerfile`. The Deploy
workflow still pushes the legacy per-model image names (`ai-florence`,
`ai-clip`, `ai-enrichment` — their `ai/*/Dockerfile`s remain in the tree), but no
compose file references them anymore. `ai-yolo26` was removed from the Deploy
matrices entirely on 2026-09-23 (owner ruling: image retired fully; its build
recipe is at `archive/ai-yolo26-image/Dockerfile`).

### Image Availability

| Service                                   | Source                                                                  | Notes                                                     |
| ----------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------- |
| **backend**                               | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend`    | Published on every merge to main (multi-arch)             |
| **frontend**                              | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend`   | Published on every merge to main (multi-arch)             |
| **ai-llm**                                | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/ai-llm`     | Published (amd64 only); used by `docker-compose.ghcr.yml` |
| **ai-gateway**                            | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/ai-gateway` | Referenced by `ghcr.yml`; CI never builds — build locally |
| ~~ai-florence / ai-clip / ai-enrichment~~ | Legacy image names still pushed by CI                                   | No compose service uses them; merged into `ai-gateway`    |
| ~~ai-yolo26~~                             | Retired 2026-09-23 — removed from the Deploy matrices                   | Build recipe at `archive/ai-yolo26-image/Dockerfile`      |

### Why ai-gateway Is Built Locally

The Triton gateway container is intentionally not published to GHCR because:

1. **Model files**: The models come from the `models.yml` manifest — the
   `setup_lib` download rule selects 25 of the 30 entries, 33,579 MB
   (~32.8GB; the full 30-entry manifest sums to 34,112 MB), of which
   `./ai/download_models.sh` fetches 24 (~32.2GB — the `xclip-base` row was
   removed 2026-09-23, full X-CLIP removal owner ruling) — and are
   mounted at runtime
2. **GPU drivers**: CUDA version must match the host's nvidia-container-toolkit
3. **Build customization**: Operators may need different quantization levels or model versions
4. **Storage costs**: Multi-GB images would be expensive to host and transfer

---

## Quick Start

### Deploy Full Stack (Backend/Frontend from GHCR + Local AI)

```bash
# 1. Pull latest backend and frontend from GHCR
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# 2. Build the AI containers locally (first time only, ~10-15 min)
podman compose -f docker-compose.prod.yml build ai-gateway ai-llm

# 3. Download models (manifest: models.yml)
./ai/download_models.sh

# 4. Start the full stack
podman compose -f docker-compose.prod.yml up -d

# 5. Verify deployment
curl -s http://localhost:8000/api/system/health/ready | jq
curl -s http://localhost:8090/health | jq       # ai-gateway
curl -s http://localhost:8091/health | jq       # ai-llm
```

> [!NOTE] > `docker-compose.ghcr.yml` is now gateway-consolidated: it runs `ai-gateway`
> and Grafana Tempo (no Jaeger/Elasticsearch) and pulls `backend`/`frontend`/`ai-llm`/
> `ai-gateway` from GHCR. But the Deploy workflow never builds or pushes an `ai-gateway`
> image, so the tag it expects does not exist upstream — until `deploy.yml` is
> retargeted, either build `ai-gateway` locally and tag it for GHCR, or run
> `docker-compose.prod.yml` (which builds it from `ai/gateway/Dockerfile`). Its `ai-llm`
> also mounts a Q2_K_L benchmark model.

### Deploy Core AI Only

```bash
# Build and start the gateway + LLM
podman compose -f docker-compose.prod.yml build ai-gateway ai-llm
podman compose -f docker-compose.prod.yml up -d ai-gateway ai-llm

# Verify
curl http://localhost:8090/health  # ai-gateway (all Triton models)
curl http://localhost:8091/health  # Nemotron
```

---

## AI Container Reference

### ai-gateway (Triton + FastAPI)

Single container serving detection and all enrichment models behind one router per
model family: `/yolo26`, `/florence`, `/clip`, `/enrichment` (heavy), `/enrich-lt`
(light).

| Property         | Value                                                                                                                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ports**        | `${AI_GATEWAY_PORT:-8090}` (API), `${AI_GATEWAY_METRICS_PORT:-8002}` (Triton metrics)                                                                                                                |
| **Base Image**   | `nvcr.io/nvidia/tritonserver:26.01-py3`                                                                                                                                                              |
| **VRAM**         | ~4GB base resident, ~6GB peak (GPU `GPU_AI_SERVICES`, default 1)                                                                                                                                     |
| **Models**       | `models.yml` manifest via `./ai/download_models.sh` (rule selects 25 of 30 entries, ~32.8GB; script fetches 24, ~32.2GB — xclip row removed 2026-09-23; see the `ai/download_models.sh` header rule) |
| **Health Check** | `GET /health` — `healthy` only when Triton and all models are ready (`start_period` 180s)                                                                                                            |
| **Limits**       | 20G memory, 8 CPUs                                                                                                                                                                                   |

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

**Notable environment:** `GATEWAY_PORT=8090`, `CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}` (all GPUs are
passed via CDI; this selects the card — see [GPU Setup](gpu-setup.md)),
`HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-1}` (models must be pre-downloaded), and
`VEHICLE_QUANTIZED` / `DEMOGRAPHICS_QUANTIZED` toggles that swap in files from
`/models/quantized`.

### ai-llm (Nemotron, llama.cpp)

| Property         | Value                                                               |
| ---------------- | ------------------------------------------------------------------- |
| **Port**         | `${LLM_PORT:-8091}`                                                 |
| **VRAM**         | ~3GB (Mini 4B) or ~14.7GB (Nano 30B Q4_K_M)                         |
| **Base Image**   | `nvidia/cuda:13.3.1-runtime-ubuntu22.04` (llama.cpp built in-image) |
| **Model**        | Downloaded by `./ai/download_models.sh` or manually (see below)     |
| **Health Check** | `GET /health` (`start_period` 300s)                                 |
| **Limits**       | 12G memory, 4 CPUs                                                  |

**Build:**

```bash
podman compose -f docker-compose.prod.yml build ai-llm
```

**Environment Variables** (defaults from `.env.example` / compose):

| Variable         | Default                                       | Description                                        |
| ---------------- | --------------------------------------------- | -------------------------------------------------- |
| `LLM_MODEL_PATH` | `/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | GGUF file exposed as `MODEL_PATH` in the container |
| `GPU_LAYERS`     | `auto`                                        | Layers offloaded to GPU (`auto` = all)             |
| `CTX_SIZE`       | `262144`                                      | Context window, split across `PARALLEL` slots      |
| `PARALLEL`       | `8`                                           | Parallel inference slots (8 × 32,768 tokens)       |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
  - llama-cache:/home/llama/.cache
  - llama-nv-cache:/home/llama/.nv
```

**Model Download (Production - Nano 30B):**

`./ai/download_models.sh` fetches this from `models.yml` (hf_repo
`unsloth/Nemotron-3-Nano-30B-A3B-GGUF`). Manual alternative — the NVIDIA repository is
at [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF):

```bash
mkdir -p /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
cd /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
wget https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
```

### Florence-2 / CLIP / Enrichment — consolidated

The old `ai-florence` (8092), `ai-clip` (8093), `ai-enrichment` (8094) and
`ai-enrichment-light` (8096) containers no longer exist. Their models are Triton
models inside `ai-gateway`, reachable at `http://<gateway>:8090/florence`, `/clip`,
`/enrichment` and `/enrich-lt`. Model weights land under
`${AI_MODELS_PATH:-/export/ai_models}/model-zoo/` (mounted read-only at
`/models/zoo`) when you run `./ai/download_models.sh` against the `models.yml`
manifest — no per-repo `git clone` steps are needed anymore.

---

## GPU Configuration

### GPU Passthrough (Podman / compose)

`docker-compose.prod.yml` gives both AI containers all GPUs via the Podman CDI spec and
then restricts each with `CUDA_VISIBLE_DEVICES` (using `nvidia.com/gpu=N` alone creates
only `/dev/nvidiaN`, which CUDA cannot initialize):

```yaml
# ai-gateway
devices:
  - nvidia.com/gpu=all
environment:
  - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
# ai-llm
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

| Deployment Scenario   | Services                                | Total VRAM |
| --------------------- | --------------------------------------- | ---------- |
| **Core only**         | ai-gateway (YOLO26) + ai-llm (Mini 4B)  | ~7GB       |
| **Core (production)** | ai-gateway + ai-llm (Nano 30B, ~14.7GB) | ~18-20GB   |
| **Full stack**        | All gateway models + Nemotron 30B       | ~22-24GB   |

With the default two-GPU split (`GPU_LLM=0`, `GPU_AI_SERVICES=1`) the load is ~16GB on
GPU 0 and ~6GB on GPU 1.

---

## Deployment Patterns

### Pattern 1: Full Production Stack

```bash
# Clone the repository
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# Run setup script (creates .env, installs deps)
python setup.py

# Pull backend/frontend from GHCR
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Build AI containers locally
podman compose -f docker-compose.prod.yml build ai-gateway ai-llm

# Download models (see Model Downloads above)
./ai/download_models.sh

# Start all services
podman compose -f docker-compose.prod.yml up -d
```

### Pattern 2: Core Services Only

Skip Florence/CLIP/enrichment by simply not needing them — they load on demand inside
the gateway; the baseline is YOLO26 + Florence-2 + SigLIP (~4GB). Start only the
essential services:

```bash
# Build core AI containers
podman compose -f docker-compose.prod.yml build ai-gateway ai-llm

# Download Nemotron model (or run ./ai/download_models.sh)
mkdir -p /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
wget -O /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf \
  https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf

# Start core services only
podman compose -f docker-compose.prod.yml up -d \
  postgres redis backend frontend ai-gateway ai-llm
```

### Pattern 3: AI Services on Separate GPU Host

Run AI on a dedicated GPU machine:

**On GPU host:**

```bash
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence
podman compose -f docker-compose.prod.yml build ai-gateway ai-llm
podman compose -f docker-compose.prod.yml up -d ai-gateway ai-llm
```

**On application host:**

Point `.env` at the GPU host (the gateway binds `127.0.0.1` by default — expose it via
a reverse proxy or SSH tunnel, see [AI TLS](ai-tls.md) and
[Deployment Modes](deployment-modes.md) Mode 4):

```bash
GPU_HOST=10.0.0.50  # Your GPU host IP
AI_GATEWAY_URL=http://${GPU_HOST}:8090
NEMOTRON_URL=http://${GPU_HOST}:8091
```

Start non-AI services:

```bash
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

podman compose -f docker-compose.prod.yml up -d postgres redis backend frontend
```

---

## Updating Containers

### Update Backend/Frontend from GHCR

```bash
# Pull latest images
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Recreate containers with new images
podman compose -f docker-compose.prod.yml up -d backend frontend
```

### Update AI Services (Rebuild)

```bash
# Pull latest source code
git pull origin main

# Rebuild AI containers (--no-cache: cached layers hold stale code)
podman compose -f docker-compose.prod.yml build --no-cache ai-gateway ai-llm

# Recreate containers
podman compose -f docker-compose.prod.yml up -d ai-gateway ai-llm
```

### Use Specific Version (SHA Tag)

```bash
# Deploy specific commit version
SHA=abc123
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:${SHA}
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:${SHA}
IMAGE_TAG=${SHA} podman compose -f docker-compose.ghcr.yml up -d   # ghcr stack only
```

---

## Health Verification

### Quick Health Check

```bash
curl http://localhost:8000/api/system/health/ready   # Backend

# AI services
curl http://localhost:8090/health                    # ai-gateway (aggregate)
curl http://localhost:8090/yolo26/health             # per-router
curl http://localhost:8091/health                    # Nemotron
```

### Comprehensive Check Script

```bash
#!/bin/bash
echo "=== Health Check ==="

services=(
  "backend:http://localhost:8000/api/system/health/ready"
  "ai-gateway:http://localhost:8090/health"
  "ai-gateway-yolo26:http://localhost:8090/yolo26/health"
  "ai-gateway-florence:http://localhost:8090/florence/health"
  "ai-gateway-clip:http://localhost:8090/clip/health"
  "ai-gateway-enrichment:http://localhost:8090/enrichment/health"
  "ai-gateway-enrich-lt:http://localhost:8090/enrich-lt/health"
  "ai-llm:http://localhost:8091/health"
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
```

### GPU Utilization Check

```bash
# Watch GPU memory and utilization
watch -n 1 nvidia-smi

# Per-process VRAM usage
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

---

## Troubleshooting

### Container Fails to Start

```bash
# Check container logs
podman compose -f docker-compose.prod.yml logs ai-gateway
podman compose -f docker-compose.prod.yml logs ai-llm

# Triton model-load failures show up first in the gateway log
podman logs ai-gateway 2>&1 | grep -iE "error|failed|model"

# Check if model files exist
ls -la /export/ai_models/nemotron/
ls -la /export/ai_models/model-zoo/
```

### GPU Not Available in Container

```bash
# Verify nvidia-container-toolkit is installed
nvidia-ctk --version

# Regenerate CDI spec (Podman)
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Test GPU access
podman run --rm --device nvidia.com/gpu=all \
  docker.io/nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### CUDA Out of Memory

```bash
# Check current VRAM usage
nvidia-smi

# Reduce GPU layers for Nemotron (in .env)
GPU_LAYERS=25  # default is `auto` (all layers on GPU)

# Move the gateway to a second GPU instead of shrinking the LLM
GPU_AI_SERVICES=1   # already the default two-GPU split
```

### Service Timeout on Startup

AI containers have long startup times due to model loading:

| Container    | Healthcheck `start_period` | What happens during startup        |
| ------------ | -------------------------- | ---------------------------------- |
| `ai-gateway` | 180s                       | Triton initialises all models      |
| `ai-llm`     | 300s                       | 30B GGUF tensors load onto the GPU |

Wait for health checks to pass before testing:

```bash
podman compose -f docker-compose.prod.yml logs -f ai-llm
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

---

[Back to Operator Hub](README.md)
