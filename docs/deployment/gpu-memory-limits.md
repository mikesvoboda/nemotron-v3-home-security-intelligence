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
| `ai-detector`         | YOLO26                                  | 2G           | Any | Object detection, runs frequently          |
| `ai-yolo26`           | YOLO26 TensorRT                         | 1.5G         | 1   | Optional TensorRT-optimized variant        |
| `ai-florence`         | Florence-2-Large                        | 2G           | 1   | Vision-language dense captioning           |
| `ai-clip`             | CLIP ViT-L                              | 1.5G         | 1   | Entity re-identification embeddings        |
| `ai-enrichment-light` | Pose, Threat, ReID, Pet, Depth (~1.2GB) | 2G           | 1   | Light-weight models, efficient inference   |
| `ai-enrichment`       | Vehicle, Fashion, Demographics (~4.3GB) | 3G           | 1   | Large transformer models with lazy load    |
| `backend`             | FastAPI application                     | 2G           | Any | GPU for inference acceleration             |

### Allocation Strategy

- **GPU 0 (24GB A5500)**: `ai-llm` gets exclusive allocation (24G)
- **GPU 1 (4GB A400)**: Shared among 6 services
  - `ai-yolo26`: 1.5G
  - `ai-florence`: 2G
  - `ai-clip`: 1.5G
  - `ai-enrichment-light`: 2G
  - `ai-enrichment`: 3G
  - Other services: fallback with count constraint

**Note**: GPU 1 services use `device_ids: ['1']` to pin to specific GPU. Total limits exceed 4G because services don't all run simultaneously; lazy loading and caching reduce active memory.

---

## Memory Management Best Practices

### 1. Monitor GPU Memory Usage

Use `nvidia-smi` to monitor real-time GPU memory:

```bash
# Real-time monitoring (updates every 1 second)
watch -n 1 nvidia-smi

# Single snapshot
nvidia-smi --query-gpu=index,name,memory.total,memory.used,memory.free \
  --format=csv,noheader,nounits
```

### 2. Set Conservative Limits

When deploying new services:

1. Run service in isolation and note peak memory usage
2. Add 10-20% buffer for spikes
3. Set limit to conservative value (e.g., measured usage + 500MB)

### 3. PyTorch Memory Configuration

For services using PyTorch, enable memory optimization:

```yaml
environment:
  - PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512 # Reduce fragmentation
  - CUDA_LAUNCH_BLOCKING=1 # Optional: easier debugging (slower)
  - TORCH_CUDA_LAUNCH_BLOCKING=1 # PyTorch variant
```

### 4. Model Lazy Loading

For services with multiple models (like `ai-enrichment`):

- Load models on-demand rather than at startup
- Use `VRAM_BUDGET_GB` to control memory pressure
- Monitor memory as inference requests arrive

---

## Troubleshooting

### Container Crashes with CUDA Out of Memory

**Symptoms**: Container exits with CUDA out of memory error after running for a while

**Solutions**:

1. Check current GPU memory: `nvidia-smi`
2. Identify memory-hungry process: `nvidia-smi pmon -c 1`
3. Increase memory limit: Edit `docker-compose.prod.yml` and increase `options.memory`
4. Rebuild container without cache: `podman-compose build --no-cache <service>`
5. Restart service: `podman-compose restart <service>`

### Container Won't Start with Memory Limit

**Symptoms**: Service fails to start after adding memory limit

**Solutions**:

1. Verify limit is valid syntax: `24g`, `1500m`, `1024` (bytes)
2. Check GPU has enough free memory: `nvidia-smi`
3. Try lower limit as test: `podman-compose exec <service> nvidia-smi`
4. Verify NVIDIA Container Toolkit installed: `docker run --gpus all nvidia/cuda nvidia-smi`

### Multiple Services Competing for Memory

**Symptoms**: One service works in isolation but fails when others run

**Solutions**:

1. Check total memory usage: `nvidia-smi`
2. Compare against GPU capacity
3. Adjust service memory limits to fit GPU capacity
4. Implement request rate limiting to reduce concurrent models
5. Use GPU affinity to distribute services: `device_ids: ['0']` vs `device_ids: ['1']`

### Memory Fragmentation Issues

**Symptoms**: Services run with low utilization but OOM occurs during spikes

**Solutions**:

1. Reduce PyTorch allocator block size:
   ```yaml
   environment:
     - PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:256 # More aggressive
   ```
2. Clear PyTorch cache periodically in application code:
   ```python
   if torch.cuda.is_available():
       torch.cuda.empty_cache()
   ```
3. Restart services during low-traffic periods to defragment

---

## Implementation Details

### How Docker Compose Deploy Options Work

When using `docker-compose.prod.yml` with NVIDIA Container Toolkit:

1. Docker/Podman reads `deploy.resources.reservations.devices`
2. NVIDIA Container Runtime validates GPU device IDs
3. Runtime sets environment variables for container:
   - `CUDA_VISIBLE_DEVICES`: Specifies which GPUs are visible
   - `NVIDIA_VISIBLE_DEVICES`: Nvidia runtime option
   - Memory limits enforced at allocation time

### GPU Memory Reservation vs Limit

- **Reservation** (`reservations.devices`): Declares GPU resource requirements
- **Limit** (`options.memory`): Hard memory cap enforced by NVIDIA driver

Current configuration uses reservations with memory options, which provides:

- Scheduler awareness for multi-container deployments
- Hard limits to prevent spillover
- Runtime enforcement by NVIDIA driver

---

## Monitoring and Alerting

### Key Metrics to Monitor

1. **GPU Memory Utilization**

   - Alert threshold: > 90% of limit
   - Action: Reduce load or increase limit

2. **GPU Memory Allocation Failures**

   - Indicates OOM condition
   - Action: Restart service or check logs

3. **Service Restart Rate**
   - High restart rate suggests memory pressure
   - Action: Review memory allocations and usage patterns

### Prometheus Metrics

Enable GPU monitoring via prometheus for alerting:

```yaml
# monitoring/prometheus.yml
- job_name: 'gpu-metrics'
  static_configs:
    - targets: ['localhost:9100'] # node_exporter with GPU plugin
```

---

## Related Documentation

- **[Multi-GPU Support](../development/multi-gpu.md)** - User-facing GPU configuration guide
- **[Container Orchestration](./container-orchestration.md)** - Container management and health checks
- **[AI Pipeline Architecture](../architecture/ai-pipeline.md)** - Model sizes and requirements
- **[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/overview.html)** - Official documentation

---

## Changelog

- **2026-01-26 (NEM-3803)**: Initial GPU memory limits configuration
  - Added memory limits to all GPU-enabled services
  - Configured PyTorch memory allocator for all PyTorch services
  - Documented allocation strategy and monitoring procedures
