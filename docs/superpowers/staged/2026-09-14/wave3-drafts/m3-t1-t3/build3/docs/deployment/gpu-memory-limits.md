---
title: GPU Memory Limits Configuration
description: Guide for configuring GPU memory limits per container to prevent OOM and enable multi-container GPU sharing
source_refs:
  - docker-compose.prod.yml:116-245
  - docs/development/multi-gpu.md:40-58
---

# GPU Memory Limits Configuration

This guide documents GPU memory limits per service for preventing out-of-memory (OOM) errors and enabling stable multi-container GPU sharing.

---

## Overview

GPU memory limits are configured at the Docker/Podman container level using NVIDIA Container Runtime options. Combined with PyTorch memory allocator configuration, this allows multiple containers to safely share a single GPU without causing system crashes.

### Key Benefits

- **OOM Prevention**: Hard limits prevent one container from consuming all GPU memory
- **Fair Resource Sharing**: Multiple models can run concurrently on shared GPUs
- **Predictable Performance**: Applications behave consistently under memory pressure
- **Multi-GPU Support**: Foundation for distributing workloads across multiple GPUs

---

## Configuration Methods

### 1. Docker Compose Deploy Options

GPU memory limits are set in `docker-compose.prod.yml` under `deploy.resources.reservations.devices`:

```yaml
services:
  ai-llm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
              options:
                memory: 24g # GPU memory limit for this container
```

The `options.memory` field specifies the maximum GPU memory available to the container.

### 2. PyTorch Memory Allocator Configuration

PyTorch's CUDA allocator is configured via environment variable to reduce fragmentation:

```yaml
environment:
  - PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
```

This setting:

- Limits maximum allocation block size to 512 MB
- Reduces memory fragmentation under concurrent loads
- Helps prevent "out of memory" errors when models load incrementally

---

## Service Memory Allocations

All GPU-enabled services have memory limits configured. Here are the recommended allocations based on model sizes:

| Service               | Model(s)                                | Memory Limit | GPU | Notes                                      |
| --------------------- | --------------------------------------- | ------------ | --- | ------------------------------------------ |
| `ai-llm`              | Nemotron-3-Nano-30B (Q4_K_M)            | 24G          | 0   | Large LLM requires dedicated high-VRAM GPU |
| `ai-yolo26`           | YOLO26                                  | 2G           | Any | Object detection, runs frequently          |
| `ai-yolo26`           | YOLO26 TensorRT                         | 1.5G         | 1   | Optional TensorRT-optimized variant        |
| `ai-florence`         | Florence-2-Large                        | 2G           | 1   | Vision-language dense captioning           |
| `ai-clip`             | CLIP ViT-L                              | 1.5G         | 1   | Entity re-identification embeddings        |
| `ai-enrichment-light` | Pose, Threat, ReID, Pet, Depth (~1.2GB) | 2G           | 1   | Light-weight models, efficient inference   |
| `ai-enrichment`       | Vehicle, Fashion, Demographics (~4.3GB) | 3G           | 1   | Large transformer models with lazy load    |
| `backend`             | FastAPI application                     | 2G           | Any | GPU for inference acceleration             |

---

## Memory Management Best Practices

### 1. Monitor GPU Memory Usage

Use `nvidia-smi` to monitor real-time GPU memory:

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Single snapshot
nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free \
  --format=csv,noheader,nounits
```

### 2. Troubleshooting

**Container crashes with CUDA Out of Memory**: Check current GPU memory with `nvidia-smi` and increase memory limit in `docker-compose.prod.yml`.

---

## Related Documentation

- **[Multi-GPU Support](../development/multi-gpu.md)** - User-facing GPU configuration guide
- **[Container Orchestration](./container-orchestration.md)** - Container management and health checks
