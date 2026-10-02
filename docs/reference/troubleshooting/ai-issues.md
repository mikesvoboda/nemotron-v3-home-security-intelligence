# AI Service Troubleshooting

> Solving AI service and pipeline problems — the `ai-gateway` Triton container
> (detection) and the `ai-vlm` llama.cpp container (per-event reasoning).

**Time to read:** ~6 min
**Prerequisites:** [GPU Issues](gpu-issues.md) for hardware problems

AI runs as two containers:

- **`ai-gateway`** (:8090) — FastAPI in front of NVIDIA Triton. Two routers:
  `/yolo26` (object detection) and `/enrich-lt` (a readiness lane for the two
  resident specialists). Triton's model directory holds `{yolo26, reid, threat}`;
  `reid` is always resident, `threat` only when `GATEWAY_ENABLE_THREAT=true`
  (compose default `false`).
- **`ai-vlm`** (:8098) — llama.cpp `llama-server`. It is behind the `vlm` compose
  profile, so a bring-up must name the profile. The event path POSTs
  `/v1/chat/completions` to it.

Identity questions (faces, license plates, person re-identification) are answered
**in-process in the backend** as database lookups against your own registrations,
not by a separate AI service. When a lookup's weights are not resident it returns
`unavailable: <why>` and the event is still written.

For debugging a model outside a container there is one host-run helper:
`./ai/start_detector.sh` (YOLO26 on the host; it binds :8090, so run it with
`ai-gateway` down or set `YOLO26_PORT`).

---

## Service Not Running

### Symptoms

- Detections stop being created
- The backend readiness check reports the AI dependency failing
- `ai-vlm` never reaches `healthy`

### Diagnosis

```bash
# Container status (ai-vlm is profiled — include the profile or it shows as stopped)
podman compose -f docker-compose.prod.yml --profile vlm ps ai-gateway ai-vlm

# Logs
podman compose -f docker-compose.prod.yml logs --tail=50 ai-gateway
podman compose -f docker-compose.prod.yml --profile vlm logs --tail=50 ai-vlm

# Host-run detector (only if you run it)
pgrep -f "ai/yolo26/model.py"
```

Health through the gateway and the VLM:

```bash
# Gateway: one aggregate over the active residency set (yolo26 + reid, + threat if enabled)
curl http://localhost:8090/health
curl http://localhost:8090/yolo26/health
curl http://localhost:8090/enrich-lt/health

# VLM
curl http://localhost:8098/health
```

`GET /health` returns `"status": "degraded"` if Triton is not ready or any
resident model is not ready — check the `models` object it returns for which one.

### Solutions

**1. Start the AI services with the profile:**

```bash
podman compose -f docker-compose.prod.yml --profile vlm up -d ai-gateway ai-vlm
```

A `up -d` that omits `--profile vlm` starts `ai-gateway` but never `ai-vlm`, so
the detector runs and events queue without verdicts.

**2. Check for startup errors:**

```bash
podman compose -f docker-compose.prod.yml logs ai-gateway | tail -50
```

Common startup errors:

- Missing model files (run `./ai/download_models.sh`)
- Port already in use (the host-run `./ai/start_detector.sh` also binds :8090)
- CUDA initialization failure (see [Triton Rootless CUDA](triton-rootless-cuda.md))
- `GATEWAY_MODEL_SET` not `vlm` — the gateway refuses to start on any other value

**3. Check the VLM weights are mounted:**

Weights are host-mounted, never baked. The shipped pair is
`Qwen3VL-8B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`:

```bash
ls -la "${AI_MODELS_PATH:-/export/ai_models}/vlm/"
```

---

## Degraded Mode

### Symptoms

- `GET /api/system/health` shows the AI dependency degraded
- Events land with `risk_score: null`
- Detection works but nothing gets a risk verdict (or the reverse)

### Diagnosis

```bash
# Backend's own view
curl http://localhost:8000/api/system/health | jq .services
curl http://localhost:8000/api/health/ai-services | jq .services

# The two containers directly
curl http://localhost:8090/health     # AI Gateway (detection)
curl http://localhost:8098/health     # ai-vlm (reasoning)
```

### What each failure means

| `ai-gateway` | `ai-vlm` | Result                                                             |
| ------------ | -------- | ------------------------------------------------------------------ |
| Up           | Up       | Full functionality                                                 |
| Up           | Down     | Detections and events are created; each event lands `needs review` |
| Down         | Up       | No new detections; the analysis path has nothing to work on        |
| Down         | Down     | No events                                                          |

When the VLM cannot produce a valid verdict — transport, schema, or probe
failure after its one retry — the analyzer still writes the event with
`risk_score: null`, `risk_level: null`, and an honest "VLM verification failed;
this event needs review" summary. It never fabricates a low score. A null score
on a recent event is the signal that the VLM was down or slow, not that the scene
was benign.

The identity lookups degrade independently: a face/plate/re-ID leg whose weights
are not resident returns `unavailable: <why>` in the text handed to the VLM. With
the compose default `BACKEND_MODEL_PRELOAD=false`, the face and person-re-ID legs
come up `unavailable` until a host with enough VRAM opts in by setting it `true`.

---

## Specialist Lookups (Faces / Plates / Person Re-ID)

Three lookup legs run per batch, in the backend process, and answer identity
questions against your own registrations:

- **Faces** — SCRFD detection + w600k embeddings, matched against the enrolled
  gallery
- **Plates** — FastALPR detection + OCR, matched against registered plates
- **Person re-ID** — OSNet embeddings, matched against the person gallery

Each leg degrades to `unavailable: <why>` on its own. `unavailable` is a class,
never a score — it is not "unknown person", it is "this lookup did not run".

### Symptoms

- Events exist but the specialist text reads `unavailable: ...`
- Faces/re-ID are `unavailable` on every event even though you enrolled people

### Diagnosis

```bash
# Are the lookup weights resident in the backend? BACKEND_MODEL_PRELOAD gates the
# boot preload sweep; with it false (compose default) membership reads never load.
podman compose -f docker-compose.prod.yml exec -T backend \
  env | grep -E 'BACKEND_MODEL_PRELOAD|GATEWAY_ENABLE_THREAT'

# Backend logs show which leg went unavailable and why
podman compose -f docker-compose.prod.yml logs backend 2>&1 | grep -i "specialist unavailable"

# A recent event's detections — the specialist text is part of the stored analysis
EVENT_ID=$(curl -s "http://localhost:8000/api/events?limit=1" | jq -r '.items[0].id')
curl -s "http://localhost:8000/api/events/$EVENT_ID/detections" | jq '.items[0]'
```

### Solutions

**1. Face / re-ID come up `unavailable` right after boot**

That is the shipped default, not a fault. `BACKEND_MODEL_PRELOAD=false` keeps the
boot sweep off so a small host never loads weights it cannot hold. On a host that
can, opt in:

```bash
# In .env, then restart the backend
BACKEND_MODEL_PRELOAD=true
```

**2. Plates are `unavailable`**

The plate leg degrades to `unavailable: <why>` when the FastALPR weights are not
present. Run `./ai/download_models.sh` and confirm the weights landed, then
restart the backend.

**3. Re-ID matches are too loose or too strict**

```bash
# Higher = stricter. 0.7 is the OSNet vector-space value and is PROVISIONAL —
# calibrate against your own galleries.
REID_SIMILARITY_THRESHOLD=0.7

# Cap concurrent embedding work on a busy host (default 10, range 1-100)
REID_MAX_CONCURRENT_REQUESTS=2

# Timeout for embedding generation, seconds (default 30.0)
REID_EMBEDDING_TIMEOUT=10.0
```

---

## Batch Not Processing

### Symptoms

- Detections created but no events
- Batches accumulating without completion

### Diagnosis

```bash
curl http://localhost:8000/api/system/pipeline | jq .batch_aggregator
curl http://localhost:8000/api/system/telemetry | jq .queues
curl http://localhost:8000/api/system/health/ready | jq .workers
```

### Solutions

**1. Check batch settings** — a batch closes on 90 s of window, 30 s of idle, or
500 detections:

```bash
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
```

**2. Check the analysis worker** (readiness reports each worker with a boolean
`running`):

```bash
curl http://localhost:8000/api/system/health/ready \
  | jq '.workers[] | select(.name=="analysis_worker") | .running'
```

**3. Check the VLM** — a batch only closes into a scored event once `ai-vlm`
answers. If `ai-vlm` is down the events still land, but unscored; if the
`ai-gateway` detector is down no batch closes at all.

**4. Check Redis** — batch state lives in Redis:

```bash
redis-cli keys "batch:*"
```

---

## Analysis Failing (null risk scores)

### Symptoms

- Events created with `risk_score: null`, `risk_level: null`
- `summary` reads "VLM verification failed; this event needs review"

### Diagnosis

```bash
# VLM health and logs
curl http://localhost:8098/health
podman compose -f docker-compose.prod.yml --profile vlm logs --tail=50 ai-vlm

# One direct request. If this returns text but ignores your image, the
# multimodal projector is missing — see the mmproj note below.
curl http://localhost:8098/v1/models
```

### Solutions

**1. The serve is up but never sees the images**

`ai-vlm` builds its `--mmproj` argument only when `MMPROJ_PATH` is set and
readable (`ai/vlm/Dockerfile:143-144`). A container that starts without a usable
projector serves and passes both healthchecks while answering text-only, so a
healthy check does not prove the model saw the stills. Check the mount:

```bash
podman compose -f docker-compose.prod.yml --profile vlm exec ai-vlm \
  ls -la /models/
podman compose -f docker-compose.prod.yml --profile vlm logs ai-vlm 2>&1 | grep -i mmproj
```

**2. Timeouts**

One verdict attempt is bounded by `AI_VLM_READ_TIMEOUT` (default 25 s) and
includes a single retry at temperature 0. A sleeping server (see `SLEEP_IDLE_SECONDS`)
wakes under `AI_VLM_WAKE_TIMEOUT_SECONDS` (default 90 s). If verdicts are timing
out on a slow card, raise the read timeout — but the retry already shares that
budget, so a value at or above 30 s leaves the retry no room.

**3. A cold start still loading**

`ai-vlm` gets a 120 s health grace (`start_period`) before it is judged down. A
first request after boot is slower than steady-state; check whether the serve
settles before treating it as failed.

**4. Restart**

```bash
podman compose -f docker-compose.prod.yml --profile vlm restart ai-vlm
podman compose -f docker-compose.prod.yml restart ai-gateway
```

---

## Detection Quality Issues

### Symptoms

- Too many false positives, missing obvious detections, wrong classifications

### Solutions

**Adjust the confidence threshold** (higher = fewer detections and fewer false
positives):

```bash
# Default 0.40; used as the fallback when no class-specific threshold applies
DETECTION_CONFIDENCE_THRESHOLD=0.6
```

**Detection works best with** good lighting, a clear unobstructed view, and at
least ~640×480. Objects should be neither too far (too few pixels) nor so close
they are cut off, and roughly square to the frame.

---

## Slow Inference

### Symptoms

- Detection latency far above the served baseline
- Verdicts take many seconds
- GPU utilization low during inference

### Diagnosis

```bash
curl http://localhost:8000/api/system/pipeline-latency | jq
watch -n 1 nvidia-smi
```

### Solutions

**1. Verify the GPU is in use** — see [GPU Issues: CPU Fallback](gpu-issues.md#cpu-fallback)

**2. Check for thermal throttling** — see [GPU Issues: Thermal Throttling](gpu-issues.md#thermal-throttling)

**3. Reduce concurrent VLM load** — each `ai-vlm` slot holds its own context.
Fewer slots mean less KV-cache pressure:

```bash
# PARALLEL slots (compose default 2); per-slot context is CTX_SIZE / PARALLEL
VLM_PARALLEL=1
VLM_CTX_SIZE=16384
```

**4. Free VRAM for other residents** — `ai-vlm` sleeps to CPU RAM after
`VLM_SLEEP_IDLE_SECONDS` (default 300) of idleness, returning the VRAM to the
gateway. To never sleep it, set the value empty; to hand back VRAM sooner, lower it.

---

## Model Loading Issues

### Symptoms

- "Model file not found" / "Failed to load model"
- Service starts but the first request fails

### Solutions

**1. Download models:**

```bash
./ai/download_models.sh
```

**2. Verify the weights on disk:**

```bash
# Triton zoo (yolo26, reid, threat) — mounted into ai-gateway
ls -la "${AI_MODELS_PATH:-/export/ai_models}/model-zoo/"

# VLM GGUF pair — mounted into ai-vlm at /models
ls -la "${AI_MODELS_PATH:-/export/ai_models}/vlm/"
```

**3. Check the paths the containers actually read:**

`ai-vlm` reads `MODEL_PATH` and `MMPROJ_PATH` (compose defaults point at the
Qwen3VL pair inside `/models`). The Triton weights are linked out of
`${AI_MODELS_PATH}/triton:/models/cache` at container start by the gateway
entrypoint.

---

## Circuit Breaker Open

### Symptoms

- An AI service reports "unavailable (circuit open)"
- Requests are rejected immediately
- Health checks return a cached error

### Diagnosis

```bash
curl http://localhost:8000/api/system/circuit-breakers | jq
```

### Solutions

**1. Wait for automatic recovery.** The registry breakers recover on their own
after a timeout: 30 s for `yolo26`, 60 s for the infrastructure breakers
(`postgresql`, `redis`). The separate health-check circuitry half-opens
implicitly after its 30 s reset and is not exposed on the reset endpoint.

**2. Manual reset** (registry breakers only; API key header required when
`API_KEY_ENABLED=true`):

```bash
curl -X POST http://localhost:8000/api/system/circuit-breakers/yolo26/reset
```

**3. Fix the underlying cause** — a breaker opens only after repeated failures.
Check service health, network reachability, and GPU/resource availability before
resetting, or it will re-open.

---

## Next Steps

- [GPU Issues](gpu-issues.md) — Hardware problems
- [Connection Issues](connection-issues.md) — Network problems
- [Troubleshooting Index](index.md) — Back to symptom index

## See Also

- [AI Overview](../../operator/ai-overview.md) — AI services architecture
- [AI Configuration](../../operator/ai-configuration.md) — Environment variables
- [AI Troubleshooting (Operator)](../../operator/ai-troubleshooting.md) — Quick fixes
- [Pipeline Overview](../../developer/pipeline-overview.md) — How the AI pipeline works

---

[Back to Operator Hub](../../operator/README.md)
