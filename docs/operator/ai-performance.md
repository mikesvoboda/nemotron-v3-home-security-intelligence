# AI Services Performance Tuning

> Optimize AI inference for throughput and latency.

**Time to read:** ~6 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Performance Baselines

Expected performance on NVIDIA RTX A5500 (24GB):

| Service   | Metric           | Target    | Acceptable |
| --------- | ---------------- | --------- | ---------- |
| RT-DETRv2 | Latency (single) | 30-50ms   | < 100ms    |
| RT-DETRv2 | Throughput       | 20-30 fps | 10 fps     |
| Nemotron  | Latency          | 2-5s      | < 10s      |
| Nemotron  | Tokens/sec       | 30-50     | 15         |

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
curl http://localhost:8000/api/system/gpu/history?minutes=30
```

---

## RT-DETRv2 Tuning

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
curl -X POST http://localhost:8090/detect/batch \
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

### Context Size

Larger context allows longer prompts but uses more VRAM.

```bash
# Default: 4096 tokens
--ctx-size 4096

# For complex batches
--ctx-size 8192

# Memory-constrained
--ctx-size 2048
```

### GPU Layers

Controls how much of the model runs on GPU vs CPU.

```bash
# Full GPU (default, requires ~3GB VRAM)
--n-gpu-layers 99

# Partial GPU (if VRAM limited)
--n-gpu-layers 20
```

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
command: ["uvicorn", "backend.main:app", "--workers", "4"]
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

[Back to Operator Hub](../operator-hub.md)
