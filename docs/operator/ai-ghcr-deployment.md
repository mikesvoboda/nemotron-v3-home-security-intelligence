# AI Services GHCR Deployment

> Deploy AI services using containers from GitHub Container Registry (GHCR).

**Time to read:** ~12 min
**Prerequisites:** [AI Installation](ai-installation.md), [GPU Setup](gpu-setup.md)

---

## Overview

This guide covers deploying the AI services stack from source. Currently, the CI/CD pipeline publishes the **backend** and **frontend** images to GHCR, while AI service images are built locally due to their GPU-specific requirements and large model dependencies.

### Image Availability

| Service           | GHCR Image                                                                   | Notes                               |
| ----------------- | ---------------------------------------------------------------------------- | ----------------------------------- |
| **backend**       | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest`  | Published on every merge to main    |
| **frontend**      | `ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest` | Published on every merge to main    |
| **ai-yolo26**     | Build locally                                                                | YOLO26 object detection             |
| **ai-llm**        | Build locally                                                                | Nemotron LLM (llama.cpp)            |
| **ai-florence**   | Build locally                                                                | Florence-2 vision-language          |
| **ai-clip**       | Build locally                                                                | CLIP embeddings                     |
| **ai-enrichment** | Build locally                                                                | Vehicle/pet/clothing classification |

### Why AI Services Are Built Locally

AI service containers are intentionally not published to GHCR because:

1. **Model files**: Large AI models (2-18GB) need to be mounted at runtime
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

# 2. Build AI services locally (first time only, ~10-15 min)
podman-compose -f docker-compose.prod.yml build ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment

# 3. Start the full stack
podman-compose -f docker-compose.prod.yml up -d

# 4. Verify deployment
curl http://localhost:8000/api/system/health/ready
```

### Deploy Core AI Only (No Optional Services)

```bash
# Build and start only YOLO26 and Nemotron
podman-compose -f docker-compose.prod.yml build ai-yolo26 ai-llm
podman-compose -f docker-compose.prod.yml up -d ai-yolo26 ai-llm

# Verify
curl http://localhost:8095/health  # YOLO26
curl http://localhost:8091/health  # Nemotron
```

---

## AI Service Container Reference

### ai-yolo26 (YOLO26)

Object detection service using YOLO26 transformer model.

| Property         | Value                                           |
| ---------------- | ----------------------------------------------- |
| **Port**         | 8095                                            |
| **VRAM**         | ~3-4GB                                          |
| **Base Image**   | `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` |
| **Model**        | Auto-downloads from HuggingFace on first start  |
| **Health Check** | `GET /health`                                   |

**Build:**

```bash
podman-compose -f docker-compose.prod.yml build ai-yolo26
```

**Environment Variables:**

| Variable            | Default                          | Description                              |
| ------------------- | -------------------------------- | ---------------------------------------- |
| `YOLO26_CONFIDENCE` | `0.5`                            | Detection confidence threshold (0.0-1.0) |
| `YOLO26_MODEL_PATH` | `PekingU/yolo26_r50vd_coco_o365` | HuggingFace model ID                     |

**Volume Mounts:**

```yaml
volumes:
  # :U tells Podman to recursively chown the volume to match container user
  # Docker ignores the :U flag, making this backward compatible
  - ${HF_CACHE:-~/.cache/huggingface}:/cache/huggingface:U
```

### ai-llm (Nemotron)

Large language model service for risk analysis using llama.cpp.

| Property         | Value                                    |
| ---------------- | ---------------------------------------- |
| **Port**         | 8091                                     |
| **VRAM**         | ~3GB (Mini 4B) or ~14GB (Nano 30B)       |
| **Base Image**   | `nvidia/cuda:12.4.1-runtime-ubuntu22.04` |
| **Model**        | Requires manual download (see below)     |
| **Health Check** | `GET /health`                            |

**Build:**

```bash
podman-compose -f docker-compose.prod.yml build ai-llm
```

**Environment Variables:**

| Variable     | Default  | Description                              |
| ------------ | -------- | ---------------------------------------- |
| `GPU_LAYERS` | `35`     | Number of model layers to offload to GPU |
| `CTX_SIZE`   | `131072` | Context window size (tokens)             |
| `PARALLEL`   | `1`      | Number of parallel inference slots       |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
```

**Model Download (Production - Nano 30B):**

Download from the official NVIDIA HuggingFace repository: [nvidia/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF)

```bash
mkdir -p /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
cd /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
wget https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
```

### ai-florence (Florence-2)

Vision-language model for dense captioning and visual understanding.

| Property         | Value                                           |
| ---------------- | ----------------------------------------------- |
| **Port**         | 8092                                            |
| **VRAM**         | ~1.2GB                                          |
| **Base Image**   | `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` |
| **Model**        | Requires manual download                        |
| **Health Check** | `GET /health`                                   |

**Build:**

```bash
podman-compose -f docker-compose.prod.yml build ai-florence
```

**Environment Variables:**

| Variable     | Default                    | Description              |
| ------------ | -------------------------- | ------------------------ |
| `MODEL_PATH` | `/models/florence-2-large` | Path to Florence-2 model |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/florence-2-large:/models/florence-2-large:ro
```

**Model Download:**

```bash
mkdir -p /export/ai_models/model-zoo/florence-2-large
cd /export/ai_models/model-zoo/florence-2-large
git lfs install
git clone https://huggingface.co/microsoft/Florence-2-large .
```

### ai-clip (CLIP ViT-L)

CLIP embedding service for entity re-identification.

| Property         | Value                                           |
| ---------------- | ----------------------------------------------- |
| **Port**         | 8093                                            |
| **VRAM**         | ~800MB                                          |
| **Base Image**   | `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` |
| **Model**        | Requires manual download                        |
| **Health Check** | `GET /health`                                   |

**Build:**

```bash
podman-compose -f docker-compose.prod.yml build ai-clip
```

**Environment Variables:**

| Variable          | Default              | Description        |
| ----------------- | -------------------- | ------------------ |
| `CLIP_MODEL_PATH` | `/models/clip-vit-l` | Path to CLIP model |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/clip-vit-l:/models/clip-vit-l:ro
```

**Model Download:**

```bash
mkdir -p /export/ai_models/model-zoo/clip-vit-l
cd /export/ai_models/model-zoo/clip-vit-l
git lfs install
git clone https://huggingface.co/openai/clip-vit-large-patch14 .
```

### ai-enrichment (Combined Classification)

Combined service for vehicle, pet, and clothing classification.

| Property         | Value                                           |
| ---------------- | ----------------------------------------------- |
| **Port**         | 8094                                            |
| **VRAM**         | ~2.5GB (all models loaded)                      |
| **Base Image**   | `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` |
| **Models**       | Requires manual download (4 models)             |
| **Health Check** | `GET /health`                                   |

**Build:**

```bash
podman-compose -f docker-compose.prod.yml build ai-enrichment
```

**Environment Variables:**

| Variable              | Default                                  | Description              |
| --------------------- | ---------------------------------------- | ------------------------ |
| `VEHICLE_MODEL_PATH`  | `/models/vehicle-segment-classification` | Vehicle classifier model |
| `PET_MODEL_PATH`      | `/models/pet-classifier`                 | Pet classifier model     |
| `CLOTHING_MODEL_PATH` | `/models/fashion-clip`                   | FashionCLIP model        |
| `DEPTH_MODEL_PATH`    | `/models/depth-anything-v2-small`        | Depth estimation model   |

**Volume Mounts:**

```yaml
volumes:
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/vehicle-segment-classification:/models/vehicle-segment-classification:ro
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/pet-classifier:/models/pet-classifier:ro
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/fashion-clip:/models/fashion-clip:ro
  - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/depth-anything-v2-small:/models/depth-anything-v2-small:ro
```

**Model Downloads:**

```bash
# Create directories
mkdir -p /export/ai_models/model-zoo/{vehicle-segment-classification,pet-classifier,fashion-clip,depth-anything-v2-small}

# Vehicle classification
cd /export/ai_models/model-zoo/vehicle-segment-classification
git lfs install
git clone https://huggingface.co/lxyuan/vit-base-patch16-224-vehicle-segment-classification .

# Pet classifier
cd /export/ai_models/model-zoo/pet-classifier
git clone https://huggingface.co/microsoft/resnet-18 .

# FashionCLIP
cd /export/ai_models/model-zoo/fashion-clip
git clone https://huggingface.co/patrickjohncyh/fashion-clip .

# Depth estimation
cd /export/ai_models/model-zoo/depth-anything-v2-small
git clone https://huggingface.co/depth-anything/Depth-Anything-V2-Small .
```

---

## GPU Configuration

### GPU Passthrough (Docker Compose)

All AI services require GPU access. The `docker-compose.prod.yml` includes this configuration:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### Verify GPU Access

```bash
# Test GPU access from container
podman run --rm --device nvidia.com/gpu=all \
  nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi

# Or for Docker
docker run --rm --gpus all \
  nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### VRAM Requirements

| Deployment Scenario   | Services                      | Total VRAM |
| --------------------- | ----------------------------- | ---------- |
| **Core only**         | ai-yolo26 + ai-llm (Mini 4B)  | ~7GB       |
| **Core (production)** | ai-yolo26 + ai-llm (Nano 30B) | ~18GB      |
| **Full stack**        | All 5 AI services             | ~22-24GB   |

---

## Deployment Patterns

### Pattern 1: Full Production Stack

Deploy everything from GHCR + locally built AI:

```bash
# Clone the repository
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# Run setup script
./setup.sh

# Pull backend/frontend from GHCR
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Build AI services
podman-compose -f docker-compose.prod.yml build ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment

# Download models (see Model Downloads section above)

# Start all services
podman-compose -f docker-compose.prod.yml up -d
```

### Pattern 2: Core Services Only

Deploy without optional AI services (Florence, CLIP, Enrichment):

```bash
# Build only core AI
podman-compose -f docker-compose.prod.yml build ai-yolo26 ai-llm

# Download Nemotron model from official NVIDIA repository
mkdir -p /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km
wget -O /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf \
  https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF/resolve/main/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf

# Start core services only
podman-compose -f docker-compose.prod.yml up -d \
  postgres redis backend frontend ai-yolo26 ai-llm
```

### Pattern 3: AI Services on Separate GPU Host

Run AI services on a dedicated GPU machine:

**On GPU host:**

```bash
# Clone repo on GPU host
git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# Build and start AI services only
podman-compose -f docker-compose.prod.yml build ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment
podman-compose -f docker-compose.prod.yml up -d ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment
```

**On application host:**

Configure `.env` to point to the GPU host:

```bash
GPU_HOST=10.0.0.50  # Your GPU host IP
YOLO26_URL=http://${GPU_HOST}:8095
NEMOTRON_URL=http://${GPU_HOST}:8091
FLORENCE_URL=http://${GPU_HOST}:8092
CLIP_URL=http://${GPU_HOST}:8093
ENRICHMENT_URL=http://${GPU_HOST}:8094
```

Start non-AI services:

```bash
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

podman-compose -f docker-compose.prod.yml up -d postgres redis backend frontend
```

---

## Updating Containers

### Update Backend/Frontend from GHCR

```bash
# Pull latest images
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:latest

# Recreate containers with new images
podman-compose -f docker-compose.prod.yml up -d backend frontend
```

### Update AI Services (Rebuild)

```bash
# Pull latest source code
git pull origin main

# Rebuild AI containers
podman-compose -f docker-compose.prod.yml build --no-cache ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment

# Recreate containers
podman-compose -f docker-compose.prod.yml up -d ai-yolo26 ai-llm ai-florence ai-clip ai-enrichment
```

### Use Specific Version (SHA Tag)

```bash
# Deploy specific commit version
SHA=abc123
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:${SHA}
podman pull ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/frontend:${SHA}
```

---

## Health Verification

### Quick Health Check

```bash
# All services
curl http://localhost:8000/api/system/health/ready  # Backend

# AI services individually
curl http://localhost:8095/health  # YOLO26
curl http://localhost:8091/health  # Nemotron
curl http://localhost:8092/health  # Florence-2
curl http://localhost:8093/health  # CLIP
curl http://localhost:8094/health  # Enrichment
```

### Comprehensive Check Script

```bash
#!/bin/bash
echo "=== Health Check ==="

services=(
  "backend:8000/api/system/health/ready"
  "ai-yolo26:8095/health"
  "ai-llm:8091/health"
  "ai-florence:8092/health"
  "ai-clip:8093/health"
  "ai-enrichment:8094/health"
)

for svc in "${services[@]}"; do
  name="${svc%%:*}"
  url="http://localhost:${svc#*:}"
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
podman-compose -f docker-compose.prod.yml logs ai-yolo26
podman-compose -f docker-compose.prod.yml logs ai-llm

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
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### CUDA Out of Memory

```bash
# Check current VRAM usage
nvidia-smi

# Reduce GPU layers for Nemotron (in .env or docker-compose.override.yml)
GPU_LAYERS=25  # Default is 35

# Stop optional AI services to free VRAM
podman-compose -f docker-compose.prod.yml stop ai-florence ai-clip ai-enrichment
```

### Service Timeout on Startup

AI services have long startup times due to model loading:

| Service       | Expected Startup Time |
| ------------- | --------------------- |
| ai-yolo26     | 60-90 seconds         |
| ai-llm        | 120-180 seconds       |
| ai-florence   | 60-120 seconds        |
| ai-clip       | 30-60 seconds         |
| ai-enrichment | 120-180 seconds       |

Wait for health checks to pass before testing:

```bash
# Watch service logs during startup
podman-compose -f docker-compose.prod.yml logs -f ai-llm
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

[Back to Operator Hub](./)
