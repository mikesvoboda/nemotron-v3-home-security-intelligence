# AI Services Containerization Design

Date: 2025-12-30

## Overview

Containerize both AI services (Nemotron LLM and RT-DETRv2) to ensure consistent dependencies, reproducible builds, and easier deployment.

## Problem

- System llama-server was built for AMD ROCm, not NVIDIA CUDA
- `nemotron_h_moe` architecture requires recent llama.cpp version
- Dependency mismatches between host and required libraries
- Manual LD_LIBRARY_PATH configuration needed

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker/Podman Network                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  ai-detector     │         │  ai-llm          │          │
│  │  (RT-DETRv2)     │         │  (Nemotron 30B)  │          │
│  │                  │         │                  │          │
│  │  Port: 8090      │         │  Port: 8091      │          │
│  │  VRAM: ~4GB      │         │  VRAM: ~16GB     │          │
│  │  PyTorch 2.4     │         │  llama.cpp       │          │
│  └────────┬─────────┘         └────────┬─────────┘          │
│           │                            │                     │
│           ▼                            ▼                     │
│  /export/ai_models/rt-detrv2   /export/ai_models/nemotron   │
│  ~/.cache/huggingface          (volume mounts)              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Decisions

| Decision           | Choice                                        | Rationale                                     |
| ------------------ | --------------------------------------------- | --------------------------------------------- |
| Container approach | Separate containers                           | Independent scaling, different resource needs |
| Build strategy     | Multi-stage                                   | Reproducible build, smaller runtime image     |
| Model handling     | Volume mount                                  | Models already on host, avoid duplication     |
| llama.cpp version  | Pin to `9496bbb80`                            | Known working version for nemotron_h_moe      |
| RT-DETRv2 base     | pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime | Pre-built CUDA PyTorch                        |
| Nemotron base      | nvidia/cuda:12.4-runtime-ubuntu22.04          | Minimal runtime with CUDA                     |

## Implementation

### Nemotron LLM Dockerfile

Location: `ai/nemotron/Dockerfile`

```dockerfile
# Multi-stage build: compile llama.cpp, copy to slim runtime

# Stage 1: Build llama.cpp with CUDA
FROM nvidia/cuda:12.4-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Clone and build llama.cpp at pinned commit
RUN git clone https://github.com/ggerganov/llama.cpp && \
    cd llama.cpp && \
    git checkout 9496bbb80 && \
    cmake -B build -DGGML_CUDA=ON && \
    cmake --build build --config Release -j$(nproc)

# Stage 2: Runtime image
FROM nvidia/cuda:12.4-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy llama-server binary
COPY --from=builder /build/llama.cpp/build/bin/llama-server /usr/local/bin/

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8091
ENV GPU_LAYERS=45
ENV CONTEXT_SIZE=12288

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s \
    CMD curl -f http://localhost:8091/health || exit 1

ENTRYPOINT ["llama-server"]
CMD ["--model", "/models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf", \
     "--host", "0.0.0.0", \
     "--port", "8091", \
     "-ngl", "45", \
     "-c", "12288", \
     "--parallel", "2", \
     "--cont-batching"]
```

### RT-DETRv2 Dockerfile

Location: `ai/rtdetr/Dockerfile`

```dockerfile
# PyTorch base with HuggingFace Transformers for RT-DETRv2

FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY model.py .
COPY example_client.py .

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8090
ENV RTDETR_CONFIDENCE=0.5
ENV HF_HOME=/cache/huggingface

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8090/health'); exit(0 if r.status_code==200 else 1)"

CMD ["python", "model.py"]
```

### Docker Compose Integration

Add to `docker-compose.prod.yml`:

```yaml
ai-detector:
  build:
    context: ./ai/rtdetr
    dockerfile: Dockerfile
  ports:
    - "8090:8090"
  volumes:
    - ${HF_CACHE:-~/.cache/huggingface}:/cache/huggingface
  environment:
    - RTDETR_CONFIDENCE=${RTDETR_CONFIDENCE:-0.5}
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  healthcheck:
    test:
      [
        "CMD",
        "python",
        "-c",
        "import httpx; exit(0 if httpx.get('http://localhost:8090/health').status_code==200 else 1)",
      ]
    interval: 30s
    timeout: 10s
    start_period: 60s
  restart: unless-stopped
  networks:
    - security-net

ai-llm:
  build:
    context: ./ai/nemotron
    dockerfile: Dockerfile
  ports:
    - "8091:8091"
  volumes:
    - /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km:/models:ro
  environment:
    - GPU_LAYERS=${NEMOTRON_GPU_LAYERS:-45}
    - CONTEXT_SIZE=${NEMOTRON_CONTEXT_SIZE:-12288}
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8091/health"]
    interval: 30s
    timeout: 10s
    start_period: 120s
  restart: unless-stopped
  networks:
    - security-net
```

Update backend environment:

```yaml
backend:
  environment:
    - RTDETR_URL=http://ai-detector:8090
    - NEMOTRON_URL=http://ai-llm:8091
```

## File Changes

| File                      | Action                                    |
| ------------------------- | ----------------------------------------- |
| `ai/nemotron/Dockerfile`  | Create                                    |
| `ai/rtdetr/Dockerfile`    | Create                                    |
| `docker-compose.prod.yml` | Modify - add ai-detector, ai-llm services |
| `docker-compose.yml`      | Modify - add for dev consistency          |

## Usage

```bash
# Build and start all services including AI
podman-compose -f docker-compose.prod.yml up -d --build

# Or just AI services
podman-compose -f docker-compose.prod.yml up -d ai-detector ai-llm

# Check logs
podman-compose -f docker-compose.prod.yml logs -f ai-llm
podman-compose -f docker-compose.prod.yml logs -f ai-detector

# Verify health
curl http://localhost:8090/health
curl http://localhost:8091/health
```

## Prerequisites

- NVIDIA Container Toolkit installed
- GPU with CUDA support
- Models available at `/export/ai_models/`

## Testing

1. Build containers: `podman-compose build ai-detector ai-llm`
2. Start services: `podman-compose up -d ai-detector ai-llm`
3. Verify health endpoints respond
4. Test detection: `curl -X POST -F "image=@test.jpg" http://localhost:8090/detect`
5. Test LLM: `curl -X POST -H "Content-Type: application/json" -d '{"prompt":"Hello"}' http://localhost:8091/completion`
