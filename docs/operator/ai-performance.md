# AI Services Performance Tuning

> Optimize AI inference for throughput and latency.

**Time to read:** ~6 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Performance Baselines

Expected performance on NVIDIA RTX A5500 (24GB):

| Service  | Metric           | Target    | Acceptable |
| -------- | ---------------- | --------- | ---------- |
| YOLO26   | Latency (single) | 30-50ms   | < 100ms    |
| YOLO26   | Throughput       | 20-30 fps | 10 fps     |
| Nemotron | Latency          | 2-5s      | < 10s      |
| Nemotron | Tokens/sec       | 30-50     | 15         |

---

## GPU Monitoring

### Real-time Monitoring

```bash
# Basic monitoring (1 second refresh)
nvidia-smi -l 1

# Detailed process view
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv

# Temperature and power
nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv -l 1
```

### Dashboard Metrics

The system broadcasts GPU stats via WebSocket at `/ws/system`. Check the dashboard for:

- GPU utilization %
- VRAM usage
- Temperature
- Inference FPS

### Historical Metrics

```bash
# Query GPU stats from API
curl "http://localhost:8000/api/system/gpu/history?since=2025-12-30T09:45:00Z&limit=300"
```

---

## YOLO26 Tuning

### Confidence Threshold

Higher thresholds reduce false positives but may miss detections.

```bash
# In .env
DETECTION_CONFIDENCE_THRESHOLD=0.5  # Default

# Conservative (fewer false positives)
DETECTION_CONFIDENCE_THRESHOLD=0.7

# Aggressive (catch more objects)
DETECTION_CONFIDENCE_THRESHOLD=0.3
```

### Batch Processing

For high-throughput scenarios (multiple cameras):

```bash
# Send multiple images per request
curl -X POST http://localhost:8095/detect/batch \
  -F "images=@image1.jpg" \
  -F "images=@image2.jpg" \
  -F "images=@image3.jpg"
```

### Hardware-Specific Tuning

| GPU Series | Recommendations                 |
| ---------- | ------------------------------- |
| RTX 30xx   | Default settings work well      |
| RTX 40xx   | Can increase batch size         |
| A-series   | Enable FP16 for lower VRAM GPUs |

---

## Nemotron LLM Tuning

### GPU Layers Configuration

Controls how many model layers run on GPU vs CPU. More GPU layers = faster inference but more VRAM.

**Configuration locations and their defaults:**

| Location                  | Default | Model    | Rationale                       |
| ------------------------- | ------- | -------- | ------------------------------- |
| `docker-compose.prod.yml` | 35      | Nano 30B | Conservative for 16GB GPUs      |
| `ai/nemotron/Dockerfile`  | 35      | Nano 30B | Matches compose default         |
| `ai/start_llm.sh`         | 99      | Mini 4B  | All layers on GPU (small model) |

**Recommended settings by GPU VRAM:**

| VRAM  | GPU_LAYERS | Notes                                    |
| ----- | ---------- | ---------------------------------------- |
| 8GB   | 20-25      | Partial offload, slower inference        |
| 12GB  | 30-35      | Balanced performance                     |
| 16GB  | 40-45      | Good performance                         |
| 24GB+ | 50-53      | Maximum layers (Nano 30B has ~53 layers) |

**Setting GPU_LAYERS:**

```bash
# In .env or shell
export GPU_LAYERS=45

# Or override in docker-compose command
GPU_LAYERS=45 docker compose -f docker-compose.prod.yml up ai-llm -d

# For host-run development (Mini 4B), use all layers
# ai/start_llm.sh already uses --n-gpu-layers 99
```

### Context Size Configuration

Controls the maximum context window. Larger contexts allow more batch data but use significantly more VRAM.

**Configuration locations and their defaults:**

| Location                  | Default | Rationale                                            |
| ------------------------- | ------- | ---------------------------------------------------- |
| `docker-compose.prod.yml` | 131072  | Production batch processing with multiple detections |
| `ai/nemotron/Dockerfile`  | 131072  | Match production compose default                     |
| `ai/start_llm.sh`         | 4096    | Development use, smaller context sufficient          |

**VRAM impact of context size (approximate for Nano 30B):**

| CTX_SIZE | Additional VRAM | Use Case                           |
| -------- | --------------- | ---------------------------------- |
| 2048     | ~500MB          | Minimal, single detection analysis |
| 4096     | ~1GB            | Development, testing               |
| 8192     | ~2GB            | Small batches                      |
| 32768    | ~4GB            | Medium batches                     |
| 131072   | ~8-12GB         | Production batch processing        |

**Setting CTX_SIZE:**

```bash
# In .env or shell
export CTX_SIZE=8192

# Or override in docker-compose command
CTX_SIZE=8192 docker compose -f docker-compose.prod.yml up ai-llm -d

# For memory-constrained systems
CTX_SIZE=4096 GPU_LAYERS=25 docker compose -f docker-compose.prod.yml up ai-llm -d
```

**Trade-offs:**

- **Large context (131072)**: Can analyze many detections in a single batch, better contextual reasoning, higher VRAM
- **Small context (4096)**: Faster startup, lower VRAM, may need to split large batches

### Parallelism

Handle multiple concurrent requests:

```bash
# Default: 2 parallel requests
--parallel 2

# High-throughput (more VRAM)
--parallel 4

# Single request (lowest VRAM)
--parallel 1
```

### Continuous Batching

Improves throughput for concurrent requests:

```bash
--cont-batching
```

Already enabled by default in `ai/start_llm.sh`.

---

## System-Wide Tuning

### Backend Worker Count

In `docker-compose.prod.yml`, adjust uvicorn workers:

```yaml
command: ['uvicorn', 'backend.main:app', '--workers', '4']
```

- **2 workers**: Low memory usage
- **4 workers**: Balanced (default)
- **8 workers**: High concurrency (CPU-bound)

### Detection Queue Size

In `backend/core/config.py`:

```python
DETECTION_QUEUE_MAX_SIZE = 10000  # Default
```

Increase for high camera counts, decrease for memory efficiency.

### Batch Timing

Trade-off between latency and context quality:

```bash
# .env

# Fast response (less context)
BATCH_WINDOW_SECONDS=30
BATCH_IDLE_TIMEOUT_SECONDS=10

# Better context (slower response)
BATCH_WINDOW_SECONDS=120
BATCH_IDLE_TIMEOUT_SECONDS=45

# Default
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
```

---

## Monitoring Performance

### Inference Latency

Enable detailed timing in logs:

```python
# backend/services/detector_client.py
logging.DEBUG  # Set log level
```

### Prometheus Metrics

If monitoring stack enabled:

```bash
curl http://localhost:8000/api/metrics | grep ai_
```

Available metrics:

- `ai_detection_latency_seconds`
- `ai_analysis_latency_seconds`
- `ai_detection_count`
- `ai_error_count`

---

## Performance Checklist

Before production deployment:

- [ ] GPU utilization under load < 90%
- [ ] VRAM usage under load < 80% of total
- [ ] Detection latency < 100ms
- [ ] LLM latency < 10s
- [ ] GPU temperature < 80C
- [ ] No OOM errors in logs
- [ ] Backend response time < 500ms

---

## Next Steps

- [AI TLS](ai-tls.md) - Secure communications
- [AI Troubleshooting](ai-troubleshooting.md) - Common issues

---

## See Also

- [GPU Setup](gpu-setup.md) - Hardware configuration
- [GPU Troubleshooting](../reference/troubleshooting/gpu-issues.md) - Thermal throttling and VRAM issues
- [Batching Logic](../developer/batching-logic.md) - Understanding batch timing
- [Environment Variable Reference](../reference/config/env-reference.md) - All configuration options

---

[Back to Operator Hub](./)
