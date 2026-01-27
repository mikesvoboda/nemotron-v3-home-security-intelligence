---
title: Multi-GPU Support
description: User guide for configuring multi-GPU support for AI services
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

| GPU   | Model     | VRAM  | Best For                          |
| ----- | --------- | ----- | --------------------------------- |
| GPU 0 | RTX A5500 | 24 GB | Large models (LLM - Nemotron 30B) |
| GPU 1 | RTX A400  | 4 GB  | Small/medium models (Enrichment)  |

### VRAM Requirements by Service

| Service       | Model                        | VRAM Estimate  |
| ------------- | ---------------------------- | -------------- |
| ai-llm        | Nemotron-3-Nano-30B (Q4_K_M) | ~21.7 GB       |
| ai-yolo26     | YOLO26                       | ~650 MB        |
| ai-florence   | Florence-2-Large             | ~1.5 GB        |
| ai-clip       | CLIP ViT-L                   | ~1.2 GB        |
| ai-enrichment | Model Zoo (9 models)         | ~6.8 GB budget |

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
- **Algorithm**: Assigns ai-yolo26 and ai-llm to GPU 0 (typically fastest), distributes others

### Isolation-First

- **Description**: LLM gets dedicated GPU, all other services share remaining GPUs
- **Best For**: Preventing LLM memory pressure from affecting other models
- **Algorithm**: ai-llm alone on largest GPU, everything else on remaining GPU(s)

### Balanced

- **Description**: Distribute VRAM evenly across all GPUs
- **Best For**: Multi-GPU systems where you want even utilization
- **Algorithm**: Bin-packing to minimize VRAM variance across GPUs

---

## Manual Assignment

When using Manual strategy or overriding automatic assignments:

1. Select **Manual** from the strategy dropdown (or leave current strategy)
2. For each service in the assignment table:
   - Select the target GPU from the dropdown
   - Optionally adjust VRAM budget for ai-enrichment
3. Review any warnings about VRAM capacity
4. Click **Save** to persist changes

### VRAM Budget Override

The ai-enrichment service supports a VRAM budget override:

- Default budget: **6.8 GB**
- Adjust when assigning to a smaller GPU
- The system will auto-suggest appropriate budgets

Example: Assigning ai-enrichment to a 4 GB GPU will suggest a 3.5 GB budget.

---

## Applying Changes and Restart Flow

Changes to GPU assignments require container restarts:

1. **Save Configuration** - Saves to database and generates YAML files
2. **Click "Apply & Restart Services"** - Triggers container recreation
3. **Monitor Status** - UI shows restart progress and health status
4. **Verify Health** - All services should return to "running" status

### Generated Files

The system generates two configuration files:

| File                                     | Purpose                                             |
| ---------------------------------------- | --------------------------------------------------- |
| `config/docker-compose.gpu-override.yml` | Docker Compose override for container orchestration |
| `config/gpu-assignments.yml`             | Human-readable reference file                       |

### Example Override File

```yaml
# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY
services:
  ai-llm:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids:
                - '0'
              capabilities:
                - gpu
  ai-enrichment:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids:
                - '1'
              capabilities:
                - gpu
    environment:
      - VRAM_BUDGET_GB=3.5
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

1. Check container logs: `podman logs ai-llm`
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
