# AI Service Troubleshooting

> Solving RT-DETRv2, Nemotron, and pipeline problems.

**Time to read:** ~6 min
**Prerequisites:** [GPU Issues](gpu-issues.md) for hardware problems

---

## Service Not Running

### Symptoms

- Health check: `"rtdetr": "connection refused"`
- Health check: `"nemotron": "connection refused"`
- No detections being created

### Diagnosis

```bash
# Check AI service status
./scripts/start-ai.sh status

# Check if processes are running
pgrep -f "model.py"      # RT-DETRv2
pgrep -f "llama-server"  # Nemotron

# Check logs
tail -f /tmp/rtdetr-detector.log
tail -f /tmp/nemotron-llm.log
```

### Solutions

**1. Start AI services:**

```bash
./scripts/start-ai.sh start
```

**2. Check for startup errors:**

```bash
cat /tmp/rtdetr-detector.log
cat /tmp/nemotron-llm.log
```

Common startup errors:

- Missing model files (run `./ai/download_models.sh`)
- Port already in use
- CUDA initialization failure

**3. Check model files exist:**

```bash
ls -la ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
# Should be ~2.5GB
```

---

## Degraded Mode

### Symptoms

- Health check shows `"ai": "degraded"`
- One service healthy, one unhealthy
- Partial functionality

### Diagnosis

```bash
# Check detailed AI status
curl http://localhost:8000/api/system/health | jq .services.ai

# Check individual services
curl http://localhost:8090/health  # RT-DETRv2
curl http://localhost:8091/health  # Nemotron
```

### Solutions

**Understand degraded behavior:**

| RT-DETRv2 | Nemotron | Result                                                |
| --------- | -------- | ----------------------------------------------------- |
| Up        | Up       | Full functionality                                    |
| Up        | Down     | Detections work, no risk analysis                     |
| Down      | Up       | No new detections, existing events can be re-analyzed |
| Down      | Down     | System unhealthy                                      |

**Restart failed service:**

```bash
# Just RT-DETRv2
./ai/start_detector.sh

# Just Nemotron
./ai/start_llm.sh

# Both
./scripts/start-ai.sh restart
```

---

## Batch Not Processing

### Symptoms

- Detections created but no events
- Batches accumulating without completion
- Pipeline status shows stale batches

### Diagnosis

```bash
# Check batch aggregator status
curl http://localhost:8000/api/system/pipeline | jq .batch_aggregator

# Check queue depths
curl http://localhost:8000/api/system/telemetry | jq .queues

# Check pipeline workers
curl http://localhost:8000/api/system/health/ready | jq .workers
```

### Solutions

**1. Check batch settings:**

```bash
# Default: 90 second window, 30 second idle timeout
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
```

**2. Check analysis worker:**

```bash
# Worker should be "running"
curl http://localhost:8000/api/system/health/ready | jq '.workers[] | select(.name=="analysis_worker")'
```

**3. Check Nemotron service:**

Batch completion requires Nemotron for risk analysis. If Nemotron is down, batches queue up.

**4. Check Redis:**

Batch state is stored in Redis:

```bash
redis-cli keys "batch:*"
```

---

## Analysis Failing

### Symptoms

- Events created with `risk_score: null`
- `risk_level: null`
- Empty `reasoning` field

### Diagnosis

```bash
# Check Nemotron health
curl http://localhost:8091/health

# Check Nemotron logs
tail -f /tmp/nemotron-llm.log

# Test Nemotron directly
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test prompt", "max_tokens": 50}'
```

### Solutions

**1. Check Nemotron is responding:**

If health check passes but analysis fails:

- Check for timeout (increase `NEMOTRON_READ_TIMEOUT`)
- Check model is fully loaded (first requests take longer)

**2. Check prompt/response:**

```bash
# Watch Nemotron logs during analysis
tail -f /tmp/nemotron-llm.log
```

**3. Restart Nemotron:**

```bash
./scripts/start-ai.sh stop
./ai/start_llm.sh
```

---

## Detection Quality Issues

### Symptoms

- Too many false positives
- Missing obvious detections
- Wrong object classifications

### Solutions

**Adjust confidence threshold:**

```bash
# Higher = fewer detections, less false positives
# Lower = more detections, more false positives
DETECTION_CONFIDENCE_THRESHOLD=0.6  # Default: 0.5
```

**Check image quality:**

Detection works best with:

- Good lighting
- Clear, unobstructed view
- Reasonable resolution (640x480 minimum)

**Check camera positioning:**

Objects should be:

- Not too far from camera
- Not too close (partial view)
- At a reasonable angle

---

## Slow Inference

### Symptoms

- Detection takes >100ms (expected: 30-50ms)
- LLM responses take >10s (expected: 2-5s)
- GPU utilization low during inference

### Diagnosis

```bash
# Check latency stats
curl http://localhost:8000/api/system/pipeline-latency | jq

# Monitor GPU during inference
watch -n 1 nvidia-smi
```

### Solutions

**1. Verify GPU is being used:**

See [GPU Issues - CPU Fallback](gpu-issues.md#cpu-fallback)

**2. Check for thermal throttling:**

See [GPU Issues - Thermal Throttling](gpu-issues.md#thermal-throttling)

**3. Reduce concurrent load:**

- Lower `--parallel` in Nemotron startup
- Process fewer cameras simultaneously

**4. Optimize settings:**

```bash
# RT-DETRv2: ensure batching for multiple images
# Nemotron: adjust context size
--ctx-size 2048  # Smaller than default 4096
```

---

## Model Loading Issues

### Symptoms

- "Model file not found"
- "Failed to load model"
- Service starts but first request fails

### Solutions

**1. Download models:**

```bash
./ai/download_models.sh
```

**2. Verify model files:**

```bash
# Nemotron model
ls -la ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
# Should be ~2.5GB

# RT-DETRv2 (auto-downloads to HuggingFace cache)
ls -la ~/.cache/huggingface/
```

**3. Check model path configuration:**

```bash
# For custom paths
NEMOTRON_MODEL_PATH=/path/to/model.gguf
RTDETR_MODEL_PATH=/path/to/rtdetr
```

---

## Circuit Breaker Open

### Symptoms

- AI service marked as "unavailable (circuit open)"
- Requests immediately rejected
- Health checks return cached error

### Diagnosis

```bash
# Check circuit breakers
curl http://localhost:8000/api/system/circuit-breakers | jq
```

### Solutions

**1. Wait for automatic recovery:**

Circuit breakers auto-reset after timeout (default: 30s).

**2. Manual reset:**

```bash
curl -X POST http://localhost:8000/api/system/circuit-breakers/rtdetr/reset
curl -X POST http://localhost:8000/api/system/circuit-breakers/nemotron/reset
```

**3. Fix underlying issue:**

Circuit opened because service repeatedly failed. Check:

- Service health
- Network connectivity
- Resource availability

---

## Next Steps

- [GPU Issues](gpu-issues.md) - Hardware problems
- [Connection Issues](connection-issues.md) - Network problems
- [Troubleshooting Index](index.md) - Back to symptom index

---

## See Also

- [AI Overview](../../operator/ai-overview.md) - AI services architecture
- [AI Configuration](../../operator/ai-configuration.md) - Environment variables
- [AI Troubleshooting (Operator)](../../operator/ai-troubleshooting.md) - Quick fixes
- [Pipeline Overview](../../developer/pipeline-overview.md) - How the AI pipeline works

---

[Back to Operator Hub](../../operator-hub.md)
