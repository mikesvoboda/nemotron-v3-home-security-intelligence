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

Higher thresholds reduce false positives but may miss detections. The
`backend/core/config.py` default is **0.40**; `.env.example` ships `0.5`.

```bash
# In .env
DETECTION_CONFIDENCE_THRESHOLD=0.4  # config.py default (0.5 in .env.example)

# Conservative (fewer false positives)
DETECTION_CONFIDENCE_THRESHOLD=0.7

# Aggressive (catch more objects)
DETECTION_CONFIDENCE_THRESHOLD=0.3
```

### Ad-Hoc Detection Calls

The production detector is the `ai-gateway` router on :8090 (multipart upload):

```bash
curl -X POST http://localhost:8090/yolo26/detect \
  -F "file=@image1.jpg"
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

| Location                  | Default | Model    | Rationale                                  |
| ------------------------- | ------- | -------- | ------------------------------------------ |
| `docker-compose.prod.yml` | `auto`  | Nano 30B | llama.cpp fits all layers that VRAM allows |
| `ai/nemotron/Dockerfile`  | 35      | Nano 30B | Conservative for 16GB GPUs                 |
| `ai/start_llm.sh`         | 99      | Mini 4B  | All layers on GPU (small model)            |

**Recommended settings by GPU VRAM:**

| VRAM  | GPU_LAYERS | Notes                                    |
| ----- | ---------- | ---------------------------------------- |
| 8GB   | 20-25      | Partial offload, slower inference        |
| 12GB  | 30-35      | Balanced performance                     |
| 16GB  | 40-45      | Good performance                         |
| 24GB+ | 50-53      | Maximum layers (Nano 30B has ~53 layers) |

**Setting GPU_LAYERS:**

```bash
# In .env (compose interpolates ${GPU_LAYERS:-auto})
GPU_LAYERS=45

# Or override for a single up — process env wins over .env
GPU_LAYERS=45 podman compose -f docker-compose.prod.yml up -d ai-llm

# For host-run development (Mini 4B), use all layers
# ai/start_llm.sh already uses --n-gpu-layers 99
```

> [!NOTE] > `GPU_LAYERS` / `CTX_SIZE` / `PARALLEL` reach only the **AI containers** (compose variable
> interpolation). The Python backend reads `data/runtime.env` _after_ `.env` via
> pydantic-settings, so check `runtime.env` if a backend-side setting (e.g.
> `NEMOTRON_URL`) appears to ignore `.env`.

### Context Size Configuration

Controls the maximum context window. Larger contexts allow more batch data but use significantly more VRAM.

**Configuration locations and their defaults:**

| Location                  | Default | Rationale                                   |
| ------------------------- | ------- | ------------------------------------------- |
| `docker-compose.prod.yml` | 262144  | 8 slots x 32K each (compose comment)        |
| `ai/nemotron/Dockerfile`  | 32768   | Conservative host-image default             |
| `ai/start_llm.sh`         | 4096    | Development use, smaller context sufficient |

> [!WARNING] > `CTX_SIZE` belongs to the **llama.cpp container only**. The Python backend's
> `nemotron_context_window` validator rejects anything above **131,072** (`le=131072`) —
> exporting `CTX_SIZE=262144` into the backend environment fails startup with a
> `ValidationError`.

**VRAM impact of context size (approximate for Nano 30B):**

| CTX_SIZE | Additional VRAM | Use Case                           |
| -------- | --------------- | ---------------------------------- |
| 2048     | ~500MB          | Minimal, single detection analysis |
| 4096     | ~1GB            | Development, testing               |
| 8192     | ~2GB            | Small batches                      |
| 32768    | ~4GB            | Dockerfile default, medium batches |
| 262144   | ~16-24GB        | Compose default (8 slots x 32K)    |

**Setting CTX_SIZE:**

```bash
# In .env (compose interpolates ${CTX_SIZE:-262144})
CTX_SIZE=8192

# Or override for a single up
CTX_SIZE=8192 podman compose -f docker-compose.prod.yml up -d ai-llm

# For memory-constrained systems
CTX_SIZE=4096 GPU_LAYERS=25 podman compose -f docker-compose.prod.yml up -d ai-llm
```

**Trade-offs:**

- **Large context (262144)**: Can analyze many detections in a single batch, better contextual reasoning, much higher VRAM
- **Small context (4096)**: Faster startup, lower VRAM, may need to split large batches

### Parallelism

Concurrent slots per llama.cpp slot group. Compose interpolates `PARALLEL`
(`${PARALLEL:-8}` for `ai-llm`); the host-run scripts hardcode it
(`ai/start_llm.sh` uses `--parallel 2`):

```bash
# .env — compose ai-llm default
PARALLEL=8

# Fewer slots (lower VRAM; each slot reserves its own context)
PARALLEL=2

# Single request (lowest VRAM)
PARALLEL=1
```

Note each parallel slot gets `CTX_SIZE / PARALLEL` of context (hence the compose comment
"262144 = 8 slots x 32K").

### Continuous Batching

`--cont-batching` is passed by both `ai/start_llm.sh` and the `ai/nemotron/Dockerfile`
CMD, so it is already on for the container and the host-run LLM.

---

## System-Wide Tuning

### Backend Worker Count

The production image runs uvicorn with **`--workers 1` by design**
(`backend/Dockerfile`): background services (FileWatcher, PipelineWorkerManager,
SystemBroadcaster) run in the FastAPI lifespan, and multiple workers would duplicate file
processing, race on the same queues, and double WebSocket broadcasts. Do not raise it in
compose. To scale, extract the background workers to a separate container instead:

```bash
python -m backend.services.pipeline_workers   # standalone worker mode
```

### Queue Size

The setting is `queue_max_size` (`backend/core/config.py`, default **10000**, range
100-100000, env `QUEUE_MAX_SIZE`), with `QUEUE_OVERFLOW_POLICY` defaulting to `dlq`.

```bash
# .env
QUEUE_MAX_SIZE=20000   # high camera counts
```

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

The backend exports per-request AI timing as a Prometheus histogram rather than a log
switch — see below. Set `LOG_LEVEL=DEBUG` in `.env` if you need the client-side timings in
the backend logs.

### Prometheus Metrics

The monitoring stack is part of the default `up -d` (no profile needed). The backend
exposes metrics at `/api/metrics` (scraped by Prometheus under that path):

```bash
curl -s http://localhost:8000/api/metrics | grep '^hsi_' | head -50
```

Relevant metric families (all `hsi_`-prefixed, defined in `backend/core/metrics.py`):

- `hsi_ai_request_duration_seconds{service}` — per-request AI latency histogram
- `hsi_nemotron_inference_seconds`, `hsi_florence_inference_seconds` — per-model timing
- `hsi_nemotron_tokens_per_second`, `hsi_nemotron_tokens_input_total`, `hsi_nemotron_tokens_output_total`
- `hsi_detection_queue_depth`, `hsi_analysis_queue_depth`, `hsi_dlq_depth`
- `hsi_pipeline_errors_total`, `hsi_detections_processed_total`

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

[Back to Operator Hub](README.md)
