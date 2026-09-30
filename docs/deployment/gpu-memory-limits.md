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
3. **Resident sharing inside the gateway.** All vision models share one process (`ai-gateway`'s Triton) started with `--model-control-mode=none`, so its models are resident — sized at container start, not budgeted or evicted at runtime. The backend `ModelManager` likewise has no eviction pass (see `backend/main.py`'s preload note).

### Key Properties

- **No cross-container contention:** the VLM engine and the gateway sit on separate cards by default (`GPU_LLM=0`, `GPU_AI_SERVICES=1`).
- **No runtime eviction anywhere:** gateway models are Triton-resident and the backend zoo has no eviction pass — `priority`/`never_evict` rows in `models.yml` are parsed but unread. VRAM headroom is a sizing decision made before boot, not a runtime safety net.
- **Graceful degradation:** the VLM engine offloads layers to system RAM via `VLM_GPU_LAYERS` (default `auto`) when its card is smaller than the GGUF pair it was configured with.

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

Set `GPU_LLM` and `GPU_AI_SERVICES` in `.env`. On a single-GPU box, set both to the same index and size the VLM down with `VLM_GPU_LAYERS` (see below).

> **Note:** the `memory:` values above are host RAM, not VRAM. There is no `options.memory` GPU-memory field in this project's compose file despite what older versions of this guide claimed.

### 2. VLM VRAM Sizing (VLM_GPU_LAYERS)

The shipped reasoning engine is `ai-vlm` (llama.cpp, compose profile `vlm`); which GGUF pair it loads is operator config (`VLM_MODEL_PATH` / `VLM_MMPROJ_PATH`, ledger D5 — this page names no model identity). `VLM_GPU_LAYERS` (in `.env`, default `auto`) controls how many transformer layers live in VRAM; the rest run from system RAM. `auto` fits the available card. This — not a container cap — is the knob for small-VRAM hosts.

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
| `ai-vlm` (profile `vlm`)       | 4         | 10G / 4G                          | `device_ids: GPU_LLM` (default 0)                      |
| `ai-gateway`                   | 8         | 20G / 10G                         | `device_ids: GPU_AI_SERVICES` (default 1)              |
| `backend`                      | 2         | 10G (raised from 6G for NEM-3890) | GPU reservation, no device_ids (any GPU)               |
| `ai-llm-vllm` (profile `vllm`) | 4         | 24G / 16G                         | all GPUs visible; selection via `CUDA_VISIBLE_DEVICES` |

VRAM demand per model lives in the gateway/backend model registry, not in
compose — see [VRAM Requirements](../_includes/vram-requirements.md). What the
table above caps is host RAM only. No measured steady-state figure exists for
the post-R8 stack: VRAM demand is dominated by the `ai-vlm` GGUF pair the
operator configures (`VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`), and `VLM_GPU_LAYERS=auto`
(default) trades layers against whatever the card has free. The pre-R8 figures
this page carried — a 30B LLM's ~14-18GB, the gateway's ~10GB, ~23GB steady
state on one 24GB card — retired with the legacy path on 2026-09-29 and are not
reproducible against the shipped stack.

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
