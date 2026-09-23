---
title: GPU Memory Limits Configuration
description: How GPU assignment and memory limits are configured per container
source_refs:
  - docker-compose.prod.yml:120-204
  - docker-compose.prod.yml:288-353
  - docker-compose.prod.yml:367-536
  - docs/developer/multi-gpu.md:40-58
  - setup_lib/linux_optimizer.py:185
---

# GPU Memory Limits Configuration

This guide documents how GPU access and memory are bounded per service, and what to do when a GPU runs out of memory.

---

## Overview

This deployment does **not** set hard per-container GPU memory caps — the compose file has no per-device `memory` limit fields, and the NVIDIA container runtime does not enforce them in this configuration. What it does instead is three things:

1. **Whole-GPU assignment.** Each GPU consumer is pinned to a specific GPU via `deploy.resources.reservations.devices.device_ids` plus a matching `CUDA_VISIBLE_DEVICES`, so containers cannot drift onto each other's card.
2. **Host RAM limits.** `deploy.resources.limits.memory` / `reservations.memory` cap **system memory** (not VRAM) per container — measured values below.
3. **Managed sharing inside the gateway.** All vision models share one process (`ai-gateway`'s Triton), where the on-demand model manager enforces a VRAM budget with priority-ordered LRU eviction instead of per-container caps.

### Key Properties

- **No cross-container contention:** the LLM and the gateway sit on separate cards by default (`GPU_LLM=0`, `GPU_AI_SERVICES=1`).
- **Predictable eviction:** under VRAM pressure inside the gateway, models evict by priority (`CRITICAL` models carry `never_evict: true` — today only smoke/fire detection).
- **Graceful degradation:** the LLM offloads layers to system RAM via `GPU_LAYERS` when its card is smaller than ~24GB.

---

## Configuration Mechanisms

### 1. GPU Assignment (compose)

```yaml
# docker-compose.prod.yml (measured)
services:
  ai-llm:
    environment:
      - CUDA_VISIBLE_DEVICES=${GPU_LLM:-0}
    deploy:
      resources:
        limits: { cpus: '4', memory: 12G }
        reservations:
          memory: 8G
          devices:
            - driver: nvidia
              device_ids: ['${GPU_LLM:-0}']
              capabilities: [gpu]

  ai-gateway:
    environment:
      - CUDA_VISIBLE_DEVICES=${GPU_AI_SERVICES:-1}
    deploy:
      resources:
        limits: { cpus: '8', memory: 20G }
        reservations:
          memory: 10G
          devices:
            - driver: nvidia
              device_ids: ['${GPU_AI_SERVICES:-1}']
              capabilities: [gpu]
```

Set `GPU_LLM` and `GPU_AI_SERVICES` in `.env`. On a single-GPU box, set both to the same index and size the LLM down with `GPU_LAYERS` (see below).

> **Note:** the `memory:` values above are host RAM, not VRAM. There is no `options.memory` GPU-memory field in this project's compose file despite what older versions of this guide claimed.

### 2. LLM VRAM Sizing (GPU_LAYERS)

The production LLM is Nemotron-3-Nano-30B Q4_K_M (~14.7GB GGUF, ~21GB resident fully offloaded to GPU). `GPU_LAYERS` (in `.env`, default `auto`) controls how many transformer layers live in VRAM; the rest run from system RAM. `auto` fits the available card. This — not a container cap — is the knob for small-VRAM hosts.

### 3. PyTorch Memory Allocator

Where PyTorch runs on the host (AI dev scripts), the environment written by `setup_lib/linux_optimizer.py` sets:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

`expandable_segments` reduces fragmentation as models load incrementally. (The older `max_split_size_mb:512` recipe that this guide used to document does not appear anywhere in the current tree.)

---

## Measured Resource Limits

From `docker-compose.prod.yml` (host RAM/CPU caps + GPU assignment):

| Service                        | CPU limit | RAM limit / reservation           | GPU assignment                                         |
| ------------------------------ | --------- | --------------------------------- | ------------------------------------------------------ |
| `ai-llm`                       | 4         | 12G / 8G                          | `device_ids: GPU_LLM` (default 0)                      |
| `ai-gateway`                   | 8         | 20G / 10G                         | `device_ids: GPU_AI_SERVICES` (default 1)              |
| `backend`                      | 2         | 10G (raised from 6G for NEM-3890) | GPU reservation, no device_ids (any GPU)               |
| `ai-llm-vllm` (profile `vllm`) | 4         | 24G / 16G                         | all GPUs visible; selection via `CUDA_VISIBLE_DEVICES` |

VRAM demand per model lives in the gateway/backend model registry, not in compose. Estimates per service: [Multi-GPU guide, VRAM Requirements by Service](../developer/multi-gpu.md#vram-requirements-by-service) — roughly ~14-18GB for the 30B LLM and ~10GB summed across the gateway's models. With the full stack on one 24GB card the measured steady state is ~23GB used.

---

## Memory Management Best Practices

### 1. Monitor GPU Memory Usage

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Single snapshot
nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free \
  --format=csv,noheader,nounits

# Which models the gateway has resident
curl -s http://localhost:8090/health | jq '.models, .models_loaded, .models_total'

# Backend view of model VRAM
curl -s http://localhost:8000/api/system/models/vram-summary
```

### 2. Troubleshooting CUDA OOM

- **LLM OOM at load:** lower `GPU_LAYERS` (or set it explicitly) so the GGUF fits, or give `GPU_LLM` its own card.
- **Gateway OOM as enrichment models accumulate:** expected behavior is LRU eviction; if eviction can't keep up, trim the loaded model set or move heavy enrichment to `GPU_AI_SERVICES` on a larger card.
- **Two containers on one card:** the most common cause is `GPU_LLM` and `GPU_AI_SERVICES` pointing at the same index while the LLM runs at full offload. Split the cards or shrink the LLM.

---

## Related Documentation

- **[Multi-GPU Support](../developer/multi-gpu.md)** - User-facing GPU configuration guide
- **[Container Orchestration](./container-orchestration.md)** - Container management and health checks
