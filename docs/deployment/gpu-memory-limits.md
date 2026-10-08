---
title: GPU Memory Limits Configuration
description: How GPU assignment and memory limits are configured per container
source_refs:
  - docker-compose.prod.yml:134-264
  - docker-compose.prod.yml:278-345
  - docker-compose.prod.yml:348-418
  - docker-compose.prod.yml:435-666
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
3. **Resident sharing inside each GPU process.** `ai-gateway`'s Triton starts with `--model-control-mode=none`, so its models are resident — sized at container start, never budgeted or evicted at runtime. `ai-vlm` is one llama.cpp server holding one GGUF pair. The backend `ModelManager` has no eviction pass either (see `backend/main.py`'s preload note).

### Key Properties

- **No cross-container contention by default:** the VLM engine and the gateway sit on separate cards (`GPU_LLM=0`, `GPU_AI_SERVICES=1`).
- **No runtime eviction anywhere:** gateway models are Triton-resident and the backend zoo has no eviction pass — `priority` / `never_evict` in `models.yml` are parsed but unread. VRAM headroom is a sizing decision made before boot, not a runtime safety net.
- **Graceful degradation is the VLM's job alone:** `ai-vlm` offloads transformer layers to system RAM via `VLM_GPU_LAYERS` (default `auto`) when its card is smaller than the GGUF pair it was configured with. Nothing else in the stack trades VRAM against system RAM — a gateway that does not fit simply fails to load.

---

## Configuration Mechanisms

### 1. GPU Assignment (compose)

```yaml
# docker-compose.prod.yml (measured)
services:
  ai-vlm: # default compose set
    devices:
      - nvidia.com/gpu=${GPU_LLM:-0} # Podman CDI device passthrough
    environment:
      - CUDA_VISIBLE_DEVICES=${GPU_LLM:-0}
    deploy:
      resources:
        limits: { cpus: '4', memory: 10G }
        reservations:
          memory: 4G
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

  backend:
    deploy:
      resources:
        limits: { cpus: '2', memory: 10G }
        reservations:
          devices:
            - driver: nvidia # count: 1, no device_ids -> any GPU
              count: 1
              capabilities: [gpu]
```

Set `GPU_LLM` and `GPU_AI_SERVICES` in `.env`. On a single-GPU box, set both to the same index and size the VLM down with `VLM_GPU_LAYERS` (below).

> **Note:** the `memory:` values above are host RAM, not VRAM. There is no `options.memory` GPU-memory field anywhere in this project's compose file.

### 2. VLM VRAM Sizing (VLM_GPU_LAYERS)

The shipped reasoning engine is `ai-vlm` (llama.cpp, in the default compose set, container port 8098). Which GGUF pair it loads is operator config — `VLM_MODEL_PATH` / `VLM_MMPROJ_PATH`, mapped into the container as `MODEL_PATH` / `MMPROJ_PATH`; this page names no model identity. The knobs, all from `.env`:

| Setting              | Compose var      | Default | Effect                                                                                                                |
| -------------------- | ---------------- | ------- | --------------------------------------------------------------------------------------------------------------------- |
| `VLM_GPU_LAYERS`     | `GPU_LAYERS`     | `auto`  | How many transformer layers live in VRAM; the rest run from system RAM. `auto` lets llama.cpp fit the available card. |
| `VLM_CTX_SIZE`       | `CTX_SIZE`       | `32768` | One token pool, split across `VLM_PARALLEL` slots (default 2), so each request gets 16,384 cells.                     |
| `VLM_CACHE_TYPE_K/V` | `CACHE_TYPE_K/V` | `q8_0`  | KV quantization; halves the pool's VRAM footprint.                                                                    |

This is the dial for small-VRAM hosts — not a container cap. Lower `VLM_GPU_LAYERS` and more of the model runs from system RAM, slower.

### 3. PyTorch Memory Allocator

Where PyTorch runs on the host (AI dev scripts), the environment written by `setup_lib/linux_optimizer.py` sets:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

`expandable_segments` reduces fragmentation as models load incrementally. The same file exports `CUDA_DEVICE_ORDER=PCI_BUS_ID` so device numbering matches `nvidia-smi`.

---

## Measured Resource Limits

From `docker-compose.prod.yml` (host RAM/CPU caps + GPU assignment):

| Service                        | CPU limit | RAM limit / reservation           | GPU assignment                                                  |
| ------------------------------ | --------- | --------------------------------- | --------------------------------------------------------------- |
| `ai-vlm` (default compose set) | 4         | 10G / 4G                          | `device_ids: GPU_LLM` (default 0)                               |
| `ai-gateway`                   | 8         | 20G / 10G                         | `device_ids: GPU_AI_SERVICES` (default 1)                       |
| `backend`                      | 2         | 10G (raised from 6G for NEM-3890) | GPU reservation `count: 1`, no `device_ids` (any GPU)           |
| `ai-llm-vllm` (profile `vllm`) | 4         | 24G / 16G                         | all GPUs visible; selection via your own `CUDA_VISIBLE_DEVICES` |

`ai-llm-vllm` is the optional vLLM benchmarking engine under the `vllm` profile. Its compose comment is explicit that all GPUs are passed through and that `CUDA_VISIBLE_DEVICES` from `.env` does the selection — it is not wired to `GPU_LLM` / `GPU_AI_SERVICES`, so pin it yourself if you enable the profile.

VRAM demand per model lives in the gateway/backend model registry, not in compose — see [VRAM Requirements](../_includes/vram-requirements.md). What the table above caps is host RAM only. No measured steady-state figure exists for the shipped stack: VRAM demand is dominated by the `ai-vlm` GGUF pair the operator configures, and `VLM_GPU_LAYERS=auto` trades layers against whatever that card has free. Measure your own host — `nvidia-smi`, or the two endpoints below.

---

## Memory Management Best Practices

### 1. Monitor GPU Memory Usage

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Single snapshot
nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free \
  --format=csv,noheader,nounits

# Which models the gateway reports ready
curl -s http://localhost:8090/health | jq '.models, .models_loaded, .models_total'

# Backend view of model VRAM
curl -s http://localhost:8000/api/system/models/vram-summary
```

### 2. Troubleshooting CUDA OOM

Because nothing evicts at runtime, an OOM is always a sizing problem, and the fix is always to load less:

- **`ai-vlm` OOM at load:** lower `VLM_GPU_LAYERS` (or set it explicitly instead of `auto`), shrink `VLM_CTX_SIZE`, or leave `VLM_CACHE_TYPE_K/V` at `q8_0`. Give `GPU_LLM` its own card if the two services are sharing one.
- **`ai-gateway` OOM at load:** the Triton repository it mounts decides its footprint, and it is fixed at build/boot time. `GATEWAY_MODEL_SET=vlm` is the shipped set (`yolo26` + `reid`); the threat model only joins when `GATEWAY_ENABLE_THREAT=true`, which is the one knob that changes gateway VRAM.
- **Backend OOM loading the specialist legs:** expected on a small host. `BACKEND_MODEL_PRELOAD` ships `false`, so the face and re-ID legs stay unloaded and report `unavailable` (counts on `hsi_specialist_unavailable_total`) instead of competing with the gateway for VRAM.
- **Two containers on one card:** the usual cause is `GPU_LLM` and `GPU_AI_SERVICES` pointing at the same index while the VLM runs at high offload. Split the cards, or shrink the VLM.

---

## Related Documentation

- **[Multi-GPU Support](../developer/multi-gpu.md)** - User-facing GPU configuration guide
- **[Container Orchestration](./container-orchestration.md)** - Container management and health checks
