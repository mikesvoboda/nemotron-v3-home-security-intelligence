---
title: Multi-GPU Support
description: User guide for configuring multi-GPU support for AI services
last_updated: 2026-10-02
source_refs:
  - docs/plans/2025-01-23-multi-gpu-support-design.md:1
  - backend/api/schemas/gpu_config.py:1
  - backend/services/gpu_config_service.py:1
  - backend/models/gpu_config.py:1
  - frontend/src/hooks/useGpuConfig.ts:1
  - frontend/src/services/gpuConfigApi.ts:1
---

# Multi-GPU Support

This guide covers configuring and managing multi-GPU support for AI services in Home Security Intelligence.

---

## Overview

Multi-GPU support allows you to distribute AI workloads across multiple GPUs, providing:

- **Improved Performance** - Run models concurrently to reduce latency
- **Better Capacity** - Utilize all available VRAM across GPUs
- **Model Isolation** - Keep the LLM stable by separating it from smaller models
- **Future-Proofing** - Prepare for larger models as the system evolves

---

## Hardware Requirements

### Minimum Requirements

| Component         | Requirement                        |
| ----------------- | ---------------------------------- |
| GPU               | NVIDIA with CUDA support           |
| VRAM (Single)     | 24 GB minimum for all AI services  |
| Container Toolkit | NVIDIA Container Toolkit installed |

### Reference Hardware

The system is optimized for configurations like:

| GPU   | Model     | VRAM  | Best For                                         |
| ----- | --------- | ----- | ------------------------------------------------ |
| GPU 0 | RTX A5500 | 24 GB | VLM engine (`ai-vlm`, sized by `VLM_GPU_LAYERS`) |
| GPU 1 | RTX A400  | 4 GB  | Detection + lookup specialists (`ai-gateway`)    |

### VRAM Requirements by Service

The stack boots two GPU services (`docker-compose.prod.yml`):

| Service (compose) | Model                                                                      | VRAM                                                                               | Default GPU           |
| ----------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------- |
| ai-vlm            | GGUF pair — identity is config (`VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`)        | config-driven; `VLM_GPU_LAYERS=auto` fits the card                                 | 0 (`GPU_LLM`)         |
| ai-gateway        | YOLO26 + re-ID/threat specialists (Triton routers `/yolo26`, `/enrich-lt`) | per-model `vram_mb` in `models.yml`; no measured gateway-total figure is published | 1 (`GPU_AI_SERVICES`) |

Compose threads GPU placement through exactly two variables: `GPU_LLM`
(`ai-vlm`) and `GPU_AI_SERVICES` (`ai-gateway`), each defaulting to a card index
(`docker-compose.prod.yml:163`, `docker-compose.prod.yml:398`).

> **Limitation.** The GPU Configuration API and its Settings UI present a per-model
> assignment roster built from the `AI_SERVICE_VRAM_REQUIREMENTS_MB` dict at
> `backend/services/gpu_detection_service.py:35` (display names and descriptions come
> from `AI_SERVICE_METADATA` at `backend/api/routes/gpu_config.py:1181`). Every key in
> that dict is a per-model container name, and none of them is a service
> `docker-compose.prod.yml` declares — the shipped GPU services are the two in the table
> above. The auto-assignment strategies take their input from those keys too
> (`backend/api/routes/gpu_config.py:460-461`), and `ISOLATION_FIRST` special-cases one of
> them by name (branch at `backend/api/routes/gpu_config.py:521`), so the per-model budget controls in that UI have no
> effect on the shipped stack: production GPU placement is decided solely by `GPU_LLM` and
> `GPU_AI_SERVICES`. Aligning the roster with the compose service names is an open
> config-code task; until then, treat the per-model table in that UI as display-only and
> size the two real services with the variables above.

See [VRAM Requirements](../_includes/vram-requirements.md) for the
lookup-model table and sizing guidance.

---

## Accessing GPU Settings

The GPU Configuration page is accessible via the Settings menu:

1. Navigate to **Settings** in the main navigation
2. Select the **GPU Configuration** tab
3. The page displays detected GPUs and current assignments

---

## Understanding GPU Cards

Each detected GPU is displayed with real-time utilization:

```
GPU 0: RTX A5500    24 GB   [##########------] 19.3/24 GB used
GPU 1: RTX A400      4 GB   [##--------------]  0.3/4 GB used
```

Information shown per GPU:

- **Index** - Zero-based GPU identifier
- **Name** - GPU model name
- **Total VRAM** - Total video memory capacity
- **Used VRAM** - Current memory utilization
- **Compute Capability** - CUDA compute capability version

---

## Assignment Strategies

Select a strategy based on your priorities:

### Manual

- **Description**: You control each service-to-GPU assignment explicitly
- **Best For**: Fine-tuned control, specific hardware configurations
- **Algorithm**: No automatic assignment; user sets each service manually

### VRAM-Based (Recommended)

- **Description**: Largest models assigned to GPU with most available VRAM
- **Best For**: Maximizing VRAM utilization, general use
- **Algorithm**: Sort models by VRAM requirement descending, assign to GPU with most free space

### Latency-Optimized

- **Description**: Critical path models on fastest GPU
- **Best For**: Minimizing detection-to-analysis latency
- **Algorithm**: Assigns the detector-critical services to the highest-compute GPU, distributes others

### Isolation-First

- **Description**: The reasoning engine gets a dedicated GPU, all other services share the remaining GPUs
- **Best For**: Preventing the reasoning engine's memory pressure from affecting other models
- **Algorithm**: The reasoning engine alone on the largest GPU, everything else on the remaining GPU(s)

### Balanced

- **Description**: Distribute VRAM evenly across all GPUs
- **Best For**: Multi-GPU systems where you want even utilization
- **Algorithm**: Bin-packing to minimize VRAM variance across GPUs

---

## Manual Assignment

When using Manual strategy or overriding automatic assignments:

1. Select **Manual** from the strategy dropdown (or leave current strategy)
2. For each service in the assignment table, select the target GPU from the
   dropdown
3. Review any warnings about VRAM capacity
4. Click **Save** to persist changes

---

## Applying Changes and Restart Flow

Changes to GPU assignments require container restarts:

1. **Save Configuration** - Saves to database and generates YAML files
2. **Click "Apply & Restart Services"** - Triggers container recreation
3. **Monitor Status** - UI shows restart progress and health status
4. **Verify Health** - All services should return to "running" status

### Generated Files

The GPU Config Service writes two files under `config/`
(`backend/services/gpu_config_service.py:223`):

| File                                     | Purpose                                             |
| ---------------------------------------- | --------------------------------------------------- |
| `config/docker-compose.gpu-override.yml` | Docker Compose override for container orchestration |
| `config/gpu-assignments.yml`             | Human-readable reference file                       |

Each override entry pins one compose service to a device id:

```yaml
# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY
services:
  ai-vlm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids:
                - '0'
              capabilities:
                - gpu
  ai-gateway:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids:
                - '1'
              capabilities:
                - gpu
```

---

## Troubleshooting

### No GPUs Detected

**Symptoms**: UI shows "No GPUs detected" message

**Solutions**:

1. Verify NVIDIA drivers are installed: `nvidia-smi`
2. Check NVIDIA Container Toolkit: `docker run --gpus all nvidia/cuda:12.0-base nvidia-smi`
3. Ensure containers have GPU access in docker-compose.prod.yml
4. Click "Re-scan GPUs" to trigger detection

### Service Fails to Start After Assignment Change

**Symptoms**: Service remains in "starting" or "error" state

**Solutions**:

1. Check container logs: `podman logs ai-vlm`
2. Verify GPU is available: The assigned GPU may be in use by another process
3. Check VRAM capacity: The model may exceed available VRAM
4. Review warnings shown during configuration

### VRAM Budget Exceeded Warning

**Symptoms**: Warning about VRAM budget exceeding GPU capacity

**Solutions**:

1. Accept the auto-adjusted budget suggestion
2. Manually set a lower VRAM budget
3. Assign the service to a larger GPU
4. Note: Some models in Model Zoo may not load with reduced budget

### Fallback Behavior

If an assigned GPU becomes unavailable at runtime:

1. Services automatically fall back to any available GPU
2. A warning is logged
3. Performance may be affected
4. Reassign services via UI once GPU is restored

---

## FAQ

### Can I assign multiple services to the same GPU?

Yes. This is the default configuration for single-GPU systems. Services share VRAM, so ensure total requirements don't exceed GPU capacity.

### What happens during a container restart?

1. The affected container is stopped
2. The override file is applied
3. The container is recreated with new GPU assignment
4. Models are reloaded on the new GPU
5. Health checks verify the service is operational

### How do I revert to default configuration?

1. Select "VRAM-Based" strategy
2. Click "Preview Changes" to see proposed assignments
3. Click "Apply" to restore recommended configuration
4. Alternatively, delete `config/docker-compose.gpu-override.yml` and restart all services

### Can I use AMD GPUs?

Currently, only NVIDIA GPUs with CUDA support are supported. AMD GPU support (ROCm) is a future consideration.

### How often should I reconfigure GPU assignments?

- After adding/removing GPUs
- When changing AI models
- If you notice VRAM pressure or performance issues
- After system updates that affect GPU drivers

---

## API Reference

For programmatic access, see the GPU Configuration API endpoints:

| Method | Endpoint                         | Purpose                                |
| ------ | -------------------------------- | -------------------------------------- |
| GET    | `/api/system/gpus`               | List detected GPUs with utilization    |
| GET    | `/api/system/gpu-config`         | Get current assignments and strategies |
| PUT    | `/api/system/gpu-config`         | Update assignments (saves to DB/YAML)  |
| POST   | `/api/system/gpu-config/apply`   | Apply config and restart services      |
| GET    | `/api/system/gpu-config/status`  | Get restart progress and health        |
| POST   | `/api/system/gpu-config/detect`  | Re-scan for GPUs                       |
| GET    | `/api/system/gpu-config/preview` | Preview auto-assignment for strategy   |

---

## Related Documentation

- **[Design Document](../plans/2025-01-23-multi-gpu-support-design.md)** - Technical design and implementation details
- **[AI Pipeline](../../ai/AGENTS.md)** - AI service architecture and VRAM requirements
- **[Container Orchestration](../deployment/container-orchestration.md)** - Container startup and health checks
