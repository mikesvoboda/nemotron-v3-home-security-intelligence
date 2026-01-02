# AI Service Troubleshooting

> Solving AI service and pipeline problems (RT-DETRv2, Nemotron, and optional Florence/CLIP/Enrichment).

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

If you are running the optional services, also check:

```bash
curl http://localhost:8092/health  # Florence-2 (optional)
curl http://localhost:8093/health  # CLIP (optional)
curl http://localhost:8094/health  # Enrichment (optional)
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
# Check overall service health (includes AI service URLs from config)
curl http://localhost:8000/api/system/health | jq .services

# Check individual AI services
curl http://localhost:8090/health  # RT-DETRv2
curl http://localhost:8091/health  # Nemotron
curl http://localhost:8092/health  # Florence-2 (optional)
curl http://localhost:8093/health  # CLIP (optional)
curl http://localhost:8094/health  # Enrichment (optional)
```

### Solutions

**Understand degraded behavior:**

| RT-DETRv2 | Nemotron | Result                                                |
| --------- | -------- | ----------------------------------------------------- |
| Up        | Up       | Full functionality                                    |
| Up        | Down     | Detections work, no risk analysis                     |
| Down      | Up       | No new detections, existing events can be re-analyzed |
| Down      | Down     | System unhealthy                                      |

> Optional enrichment services (Florence/CLIP/Enrichment) typically degrade **enrichment quality** rather than fully stopping event creation. The core “detections → batches → LLM → events” path can still function if RT-DETRv2 and Nemotron are healthy.

---

## Optional Enrichment Issues (Florence / CLIP / Enrichment)

### Symptoms

- Events exist, but “extra context” fields are missing (no attributes, no re-identification hints, etc.)
- Backend logs mention enrichment timeouts or connection errors
- CPU spikes on the backend when enrichment is enabled (model-zoo work can be heavy)

### Quick Diagnosis

```bash
# Confirm the backend is configured to reach the optional services
curl http://localhost:8000/api/system/config | jq '.florence_url, .clip_url, .enrichment_url'

# Check health endpoints
curl http://localhost:8092/health  # Florence-2
curl http://localhost:8093/health  # CLIP
curl http://localhost:8094/health  # Enrichment
```

### Common Causes

1. **Wrong URL from backend** (container vs host networking)
2. **GPU/VRAM pressure** (too many services competing)
3. **Timeouts** (services are up, but slow to respond under load)

### Solutions

**1. Fix container vs host networking**

- **Production compose**: backend should use compose DNS names (`http://ai-florence:8092`, `http://ai-clip:8093`, `http://ai-enrichment:8094`)
- **Host-run AI**: backend should use `localhost` (or `host.docker.internal` / `host.containers.internal` when backend is containerized)

**2. Temporarily disable optional enrichment**

If you need the system running reliably, disable the optional features first, then re-enable one-by-one after you stabilize GPU/latency.

See `docs/reference/config/env-reference.md` for the feature toggles.

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
