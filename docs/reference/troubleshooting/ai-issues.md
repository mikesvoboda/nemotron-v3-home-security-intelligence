# AI Service Troubleshooting

> Solving AI service and pipeline problems (YOLO26, Nemotron, and the enrichment models
> — Florence-2, CLIP/SigLIP, enrichment — served by the Triton `ai-gateway` container).

**Time to read:** ~6 min
**Prerequisites:** [GPU Issues](gpu-issues.md) for hardware problems

In production, AI is two containers: `ai-gateway` (:8090, Triton serving YOLO26,
Florence-2, CLIP and enrichment models behind path routers `/yolo26`, `/florence`,
`/clip`, `/enrichment`, `/enrich-lt`) and `ai-llm` (:8091, llama.cpp). Standalone
host-run servers exist for debugging: `./ai/start_detector.sh` (YOLO26) and
`./ai/start_nemotron.sh` / `./ai/start_llm.sh` (llama.cpp). There is no
`scripts/start-ai.sh` — that wrapper was removed.

---

## Service Not Running

### Symptoms

- Health check: `"yolo26": "connection refused"`
- Health check: `"nemotron": "connection refused"`
- No detections being created

### Diagnosis

```bash
# Check AI container status
docker compose -f docker-compose.prod.yml ps ai-gateway ai-llm

# Check host-run processes (only if you run AI on the host)
pgrep -f "model.py"      # YOLO26 standalone
pgrep -f "llama-server"  # Nemotron (llama.cpp)

# Check logs
docker compose -f docker-compose.prod.yml logs --tail=50 ai-gateway
docker compose -f docker-compose.prod.yml logs --tail=50 ai-llm
# Host-run: start_detector.sh logs to its terminal; start_nemotron.sh writes /tmp/nemotron.log
```

Per-model health through the gateway:

```bash
curl http://localhost:8090/health              # aggregate (all models)
curl http://localhost:8090/yolo26/health
curl http://localhost:8090/florence/health
curl http://localhost:8090/clip/health
curl http://localhost:8090/enrichment/health
```

### Solutions

**1. Start AI services:**

```bash
# Containerized (production)
docker compose -f docker-compose.prod.yml up -d ai-gateway ai-llm

# Host-run (debug mode)
./ai/start_detector.sh &
./ai/start_nemotron.sh
```

**2. Check for startup errors:**

```bash
docker compose -f docker-compose.prod.yml logs ai-gateway | tail -50
```

Common startup errors:

- Missing model files (run `./ai/download_models.sh`)
- Port already in use
- CUDA initialization failure (see [Triton Rootless CUDA](triton-rootless-cuda.md))

**3. Check model files exist:**

```bash
# Production LLM (ai-llm container): Nemotron-3-Nano-30B-A3B Q4_K_M, ~14.7GB
ls -la "${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km/"
```

---

## Degraded Mode

### Symptoms

- Health check shows `"ai": "degraded"`
- One service healthy, one unhealthy
- Partial functionality

### Diagnosis

```bash
# Check overall service health
curl http://localhost:8000/api/system/health | jq .services

# Check the two AI services the backend health checks track
curl http://localhost:8090/health  # AI Gateway (YOLO26 + enrichment models)
curl http://localhost:8091/health  # Nemotron (llama.cpp)

# Per-model detail from the backend's perspective (includes circuit-breaker state)
curl http://localhost:8000/api/health/ai-services | jq .services
```

### Solutions

**Understand degraded behavior:**

| YOLO26 | Nemotron | Result                                                |
| ------ | -------- | ----------------------------------------------------- |
| Up     | Up       | Full functionality                                    |
| Up     | Down     | Detections work, no risk analysis                     |
| Down   | Up       | No new detections, existing events can be re-analyzed |
| Down   | Down     | System unhealthy                                      |

> Optional enrichment services (Florence/CLIP/Enrichment) typically degrade **enrichment quality** rather than fully stopping event creation. The core “detections → batches → LLM → events” path can still function if YOLO26 and Nemotron are healthy.

---

## Enrichment Issues (Florence / CLIP / Enrichment)

The enrichment models (Florence-2, CLIP/SigLIP embeddings, enrichment) provide enhanced
context for detections, including:

- **Florence-2**: Visual attributes, OCR, dense captions
- **CLIP** (SigLIP 2 in the Triton gateway): Embedding generation for re-identification
- **Enrichment**: Orchestrates and aggregates enrichment data (vehicle, clothing,
  demographics, action, pose, pet, depth models)

In production these all run inside the `ai-gateway` container (port 8090, routers
`/florence`, `/clip`, `/enrichment`, `/enrich-lt`). The enrichment pipeline is
**optional** — the core detection and risk analysis pipeline works without it.

### Symptoms

- Events exist, but "extra context" fields are missing (no attributes, no re-identification hints, etc.)
- Backend logs mention enrichment timeouts or connection errors
- CPU spikes on the backend when enrichment is enabled
- Circuit breakers open for enrichment services

### Quick Diagnosis

```bash
# Confirm the URLs the backend uses (gateway-routed in production)
docker compose -f docker-compose.prod.yml exec -T backend env | grep -E 'FLORENCE_URL|CLIP_URL|ENRICHMENT_URL|AI_GATEWAY'

# Check feature toggles (are enrichment features enabled?)
curl http://localhost:8000/api/v1/settings | jq '.features'

# Check per-model health in the gateway
curl http://localhost:8090/florence/health
curl http://localhost:8090/clip/health
curl http://localhost:8090/enrichment/health

# Check circuit breaker status (breakers are named per operation, e.g. florence_extract,
# clip_embed, enrichment_vehicle — see GET /api/system/circuit-breakers)
curl http://localhost:8000/api/system/circuit-breakers | jq '.circuit_breakers | keys'
```

### Understanding Feature Toggles

| Variable                    | Default | Effect When Disabled                             |
| --------------------------- | ------- | ------------------------------------------------ |
| `VISION_EXTRACTION_ENABLED` | `true`  | No Florence-2 attributes, OCR, or dense captions |
| `REID_ENABLED`              | `true`  | No CLIP embeddings or re-identification          |
| `SCENE_CHANGE_ENABLED`      | `true`  | No scene change detection between frames         |

### Common Causes

1. **Wrong URL from backend** (container vs host networking)
2. **GPU/VRAM pressure** (too many models competing for limited VRAM inside `ai-gateway`)
3. **Timeouts** (models are up, but slow to respond under load)
4. **Circuit breakers open** (service failures triggered protection)
5. **Feature toggles disabled** (enrichment turned off in config)

### Solutions

**1. Fix container vs host networking**

- **Production compose**: backend should use the gateway URL and routers —
  `FLORENCE_URL=http://ai-gateway:8090/florence`, `CLIP_URL=http://ai-gateway:8090/clip`,
  `ENRICHMENT_URL=http://ai-gateway:8090/enrichment` (what `docker-compose.prod.yml` sets).
- **Host-run AI**: backend should use `http://localhost:8090/<router>` (or
  `http://host.docker.internal:8090/<router>` when the backend is containerized).
  See [Deployment Modes](../../operator/deployment-modes.md).

**2. Disable optional enrichment temporarily**

If you need the system running reliably while debugging, disable the optional features:

```bash
# In .env - disable all enrichment
VISION_EXTRACTION_ENABLED=false
REID_ENABLED=false
SCENE_CHANGE_ENABLED=false

# Restart backend to apply
docker compose -f docker-compose.prod.yml restart backend
```

Then re-enable one-by-one after stabilizing GPU/latency.

**3. Adjust timeouts for slow models**

If models are healthy but timing out under load:

```bash
# In .env - increase timeouts (defaults in comments)
FLORENCE_READ_TIMEOUT=60.0    # Default 30.0 (max 120)
CLIP_READ_TIMEOUT=30.0        # Default 5.0 (max 60)
ENRICHMENT_READ_TIMEOUT=120.0 # Default 60.0 (max 180)
```

**4. Reset circuit breakers**

If circuit breakers opened due to transient failures:

```bash
# Check circuit breaker status and registered names
curl http://localhost:8000/api/system/circuit-breakers | jq '.circuit_breakers | keys'

# Reset a specific breaker by its registered name
# (e.g. florence_extract, clip_embed, enrichment_vehicle; API key header required
#  when API_KEY_ENABLED=true)
curl -X POST http://localhost:8000/api/system/circuit-breakers/florence_extract/reset

# Or restart backend to reset all circuit breakers
docker compose -f docker-compose.prod.yml restart backend
```

**5. Check GPU/VRAM availability**

All gateway models share one GPU. Check utilization:

```bash
nvidia-smi

# Expected VRAM usage:
# - YOLO26 (TensorRT): ~2GB
# - Nemotron LLM: ~14.7GB (30B Q4_K_M), ~3GB (host-run mini 4B)
# - Florence-2: ~1.5GB
# - SigLIP 2 embeddings: ~0.2GB
# (full table: docs/_includes/vram-requirements.md)
```

If GPU is overloaded, consider:

- Running fewer AI services simultaneously
- Using smaller model quantizations
- Disabling non-essential enrichment features

**6. Tune re-identification settings**

If re-ID is slow or producing poor matches:

```bash
# Adjust similarity threshold (higher = stricter matching; default 0.85, range 0.5-1.0)
REID_SIMILARITY_THRESHOLD=0.85

# Reduce TTL if embeddings are stale (default 24h, max 168)
REID_TTL_HOURS=12

# Limit concurrent re-ID operations (default 10, range 1-100)
REID_MAX_CONCURRENT_REQUESTS=2

# Timeout for embedding generation (seconds; default 30)
REID_EMBEDDING_TIMEOUT=10.0
```

**7. Restart failed services**

```bash
# Host-run detector only
./ai/start_detector.sh

# Host-run Nemotron only
./ai/start_nemotron.sh

# Containerized stack
docker compose -f docker-compose.prod.yml restart ai-gateway   # YOLO26 + all enrichment models
docker compose -f docker-compose.prod.yml restart ai-llm       # LLM
```

### Verifying Enrichment is Working

After enabling enrichment, verify data is being populated:

```bash
# Get a recent event, then inspect its detections' enrichment_data
EVENT_ID=$(curl -s "http://localhost:8000/api/events?limit=1" | jq -r '.items[0].id')

# All enrichment results for the event's detections (plates, faces, clothing, violence...)
curl -s "http://localhost:8000/api/events/$EVENT_ID/enrichments" | jq '.enrichments[0]'

# Composite enrichment fields on a detection (vehicle/person/pet/weather)
curl -s "http://localhost:8000/api/events/$EVENT_ID/detections" | jq '.items[0].enrichment_data'

# Pipeline coverage summary for the event
curl -s "http://localhost:8000/api/events/$EVENT_ID" | jq '.enrichment_status'
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
# Defaults: 90 second window, 30 second idle timeout
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
```

**2. Check analysis worker:**

The readiness endpoint reports each worker with a boolean `running` field:

```bash
curl http://localhost:8000/api/system/health/ready | jq '.workers[] | select(.name=="analysis_worker") | .running'
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
docker compose -f docker-compose.prod.yml logs --tail=50 ai-llm   # containerized
tail -f /tmp/nemotron.log                                          # ./ai/start_nemotron.sh

# Test Nemotron directly (llama.cpp completion endpoint)
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test prompt", "max_tokens": 50}'
```

### Solutions

**1. Check Nemotron is responding:**

If health check passes but analysis fails:

- Check for timeout (increase `NEMOTRON_READ_TIMEOUT`, default 120s)
- Check model is fully loaded (first requests take longer; the compose health check
  allows a 300s start period)

**2. Check prompt/response:**

```bash
# Watch Nemotron logs during analysis
docker compose -f docker-compose.prod.yml logs -f ai-llm
```

**3. Restart Nemotron:**

```bash
# Containerized
docker compose -f docker-compose.prod.yml restart ai-llm

# Host-run
pkill -f llama-server && ./ai/start_llm.sh
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
DETECTION_CONFIDENCE_THRESHOLD=0.6  # Default: 0.40
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

- Lower `PARALLEL` in `.env` for the containerized `ai-llm` (default 8 slots;
  host-run `./ai/start_llm.sh` uses `--parallel 2`)
- Process fewer cameras simultaneously

**4. Optimize settings:**

```bash
# Nemotron context window: compose default is CTX_SIZE=262144 (8 slots x 32768).
# A much smaller value reduces VRAM pressure from KV cache:
CTX_SIZE=65536
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
# Production LLM: Nemotron-3-Nano-30B-A3B Q4_K_M (~14.7GB), mounted into ai-llm at /models
ls -la "${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km/"

# Triton model zoo (YOLO26, Florence-2, SigLIP 2, enrichment models)
ls -la "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/"

# Host-run fallback LLM (./ai/start_llm.sh only — not downloaded by download_models.sh)
ls -la ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
```

**3. Check model path configuration:**

```bash
# Backend-side model-path settings (used by the host-run standalone server)
NEMOTRON_MODEL_PATH=/path/to/model.gguf
YOLO26_MODEL_PATH=/path/to/yolo26

# Containerized LLM model file: LLM_MODEL_PATH (compose default
# /models/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf inside the ai-llm container)
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

- Health-check circuitry ("unavailable (circuit open)" in `/api/system/health`) is
  in-process and half-opens implicitly after a 30s reset timeout (3 consecutive
  failures open it). It is not exposed on the reset endpoint.
- Registry breakers (listed by `GET /api/system/circuit-breakers`) recover after their
  configured timeout — 30s for `yolo26`/`nemotron`, 60s for `detector_*`.

**2. Manual reset** (registry breakers only; API key header required when
`API_KEY_ENABLED=true`):

```bash
curl -X POST http://localhost:8000/api/system/circuit-breakers/yolo26/reset
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

[Back to Operator Hub](../../operator/README.md)
