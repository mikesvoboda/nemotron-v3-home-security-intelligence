# AI Services Performance Tuning

> Optimize AI inference for throughput and latency.

**Time to read:** ~6 min
**Prerequisites:** [AI Services Management](ai-services.md)

---

## Performance Baselines

Detection timing on an RTX A5500-class card:

| Service | Metric           | Target               | Acceptable                                |
| ------- | ---------------- | -------------------- | ----------------------------------------- |
| YOLO26  | Latency (single) | 30-50ms              | < 100ms                                   |
| YOLO26  | Throughput       | 20-30 fps            | 10 fps                                    |
| ai-vlm  | Verdict latency  | single-digit seconds | bounded by `AI_VLM_READ_TIMEOUT` (25.0 s) |

There is **no published VLM throughput baseline for the shipped identity**, and the
histogram will not give you one: `hsi_ai_request_duration_seconds` is observed by the
detector client only, so it carries `service="yolo26"`. Verdict latency for the VLM is
recorded per row in `event_verifications.latency_ms`, not as a metric:

```sql
SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) p95_ms, count(*)
FROM event_verifications WHERE latency_ms IS NOT NULL;
```

Measure your own before tuning against a number from another box — a verdict is one
`vlm_assess` call that must fit one llama.cpp slot, so its latency is dominated by slot
sizing, KV quantization, and whether the serve is awake.

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

# llama.cpp's own counters (the serve runs with --metrics)
curl -s http://localhost:8098/metrics | grep '^llama_' | head -30
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

In the compose stack the gateway runs YOLO26 as an **FP32 ONNX** model on the ONNX
Runtime CUDA execution provider (NEM-5551: INT8 ONNX was incompatible with the CUDA
provider), so TensorRT engine knobs do not apply to it.

### Hardware-Specific Tuning

| GPU Series | Recommendations                 |
| ---------- | ------------------------------- |
| RTX 30xx   | Default settings work well      |
| RTX 40xx   | Can increase batch size         |
| A-series   | Enable FP16 for lower VRAM GPUs |

---

## ai-vlm Tuning (the Reasoning Engine)

Everything below is llama.cpp slotting for the `ai-vlm` container. The rule that matters
most: **`VLM_CTX_SIZE` and `VLM_PARALLEL` are read by two processes** — the server
(compose maps them to `CTX_SIZE`/`PARALLEL`) and the backend's prompt budget
(`config.py` `vlm_context_window = VLM_CTX_SIZE // VLM_PARALLEL`). Change them as a pair.

### GPU Layers Configuration

Controls how many model layers run on GPU vs CPU. More GPU layers = faster inference but
more VRAM.

| Location                             | Effective value | Notes                                                                         |
| ------------------------------------ | --------------- | ----------------------------------------------------------------------------- |
| `docker-compose.prod.yml`            | `auto`          | `GPU_LAYERS=${VLM_GPU_LAYERS:-auto}` → llama.cpp `--fit` decides by free VRAM |
| `ai/vlm/Dockerfile` `ENV GPU_LAYERS` | `99`            | Applies only when compose is bypassed                                         |

Leave it at `auto` unless you have a measured reason to pin it: with `auto` the same
`.env` works on an 8 GB card and a 24 GB one, and the shipped GGUF pair's disk size sets
the floor either way.

```bash
# In .env — pin it only if auto is choosing badly
VLM_GPU_LAYERS=40

# Override for a single up — process env wins over .env
VLM_GPU_LAYERS=40 podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm
```

> [!NOTE]
> These variables reach the **AI container** through compose interpolation. The Python
> backend reads `data/runtime.env` _after_ `.env` via pydantic-settings, so check
> `runtime.env` if a backend-side setting (e.g. `AI_VLM_URL`) appears to ignore `.env`.

### Context Size and Slot Sizing

Controls the maximum context window. Larger contexts allow more batch data but use
significantly more VRAM.

| Setting                    | Shipped        | What it actually is                                                       |
| -------------------------- | -------------- | ------------------------------------------------------------------------- |
| `VLM_CTX_SIZE`             | `32768`        | llama.cpp's **total** `--ctx-size` pool for `ai-vlm`                      |
| `VLM_PARALLEL`             | `2`            | Slots the pool is split across                                            |
| derived per-request budget | `16384`        | `VLM_CTX_SIZE // VLM_PARALLEL` — one request occupies exactly one slot    |
| `CTX_SIZE` / `PARALLEL`    | `262144` / `8` | The backend's **separate legacy budget field**. Not what `ai-vlm` runs on |

The KV pool is a function of the architecture and the slot numbers, not of the weights'
size: the shipped 4B and 8B share `block_count 36 / head_count 32`, so the whole
32768/2 pool measures 4,608 MiB at f16 and **q8_0 halves it** — which is what the shipped
`VLM_CACHE_TYPE_K`/`VLM_CACHE_TYPE_V` (`q8_0`, plus `VLM_FLASH_ATTENTION=true`, which a
quantized V cache requires) already do.

**A full batch does not fit the slot, by design.** Detections arrive at roughly **61
tokens a row** and `batch_max_detections` is **500**, so a worst-case batch is ~30K text
tokens against a 16,384-token slot. The client **fits** the prompt rather than trusting
the arithmetic: `vlm_client._fitted_prompt` drops the weakest rows and says so in the
prompt. Each key frame costs at most the **1,280** vision tokens the client reserves for
it (`LLAMA_ARG_IMAGE_MAX_TOKENS=1280`, also bounding encoder VRAM).

So: if verdicts are slow _and_ the reasoning mentions dropped rows, that is the fitter
working, not a fault. Raise the slot only when you have the VRAM for it, and raise both
sides of the pair.

```bash
# .env — change the pair together
VLM_CTX_SIZE=16384
VLM_PARALLEL=2      # → 8,192-token slot, ~half the KV pool

# One slot: lowest VRAM, no concurrency
VLM_PARALLEL=1
```

> [!WARNING]
> Do not export the legacy `CTX_SIZE=262144` into `ai-vlm`. The container's pool comes
> from `VLM_CTX_SIZE`; the `CTX_SIZE`/`PARALLEL` pair feeds only the backend's separate
> legacy budget field (`config.py` `nemotron_context_window`, whose validator clamps
> whatever it receives into its documented band). Mixing the two gives a prompt budget
> that the slot it lands in cannot hold.

### Parallelism

Concurrent slots sharing one context pool. Each slot gets `VLM_CTX_SIZE / VLM_PARALLEL`:

```bash
# .env — shipped
VLM_PARALLEL=2

# Fewer slots (lower VRAM; each slot reserves its own context)
VLM_PARALLEL=1
```

Concurrent requests beyond the slot count queue inside llama.cpp; the backend's own
ceiling on simultaneous AI calls is `AI_MAX_CONCURRENT_INFERENCES`.

### Residency and Wake Cost

After `VLM_SLEEP_IDLE_SECONDS` (default **300**) of idleness the weights drop to CPU RAM
and the VRAM is released. The next request pays a RAM→VRAM copy of the whole pair — for
the shipped 8B that is 5,027,784,800 B main + 752,289,728 B projector, **2.0x the bytes**
of the 4B pair it replaces.

The wake ping is budgeted at `AI_VLM_WAKE_TIMEOUT_SECONDS=90.0`, and **a failed wake is
swallowed, not retried** — so the first verdict after a quiet night can read like an
outage. Set `VLM_SLEEP_IDLE_SECONDS=` (empty) to hold the card permanently, or lower it
to give VRAM back between bursts.

### Continuous Batching

`--cont-batching` is in the `ai/vlm/Dockerfile` CMD, so it is already on. `VLM_BATCH_SIZE`
(2048) and `VLM_UBATCH_SIZE` (512) are the prompt-processing and sequence-parallel batch
sizes; `VLM_THREADS` should match the container CPU limit (compose sets `cpus: 4`).

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

Larger batches push more rows into one prompt — which the slot fitter then arbitrates.
`BATCH_MAX_DETECTIONS` (500) is the ceiling it arbitrates against.

### The Lookup Legs

`faces` and `person_reid` are residency-gated and ship **off**
(`BACKEND_MODEL_PRELOAD=false`; `setup.py` writes `true` only at >= 24 GB VRAM). Enabling
them costs ~1.0 GB of VRAM headroom for the whole enabled set and buys you identity
context in the prompt. With them off, the lines read `unavailable` on every event and
nothing errors — which is why a "fast" system can be a starved one. Confirm before
tuning:

```bash
curl -s http://localhost:8000/metrics | grep hsi_specialist_unavailable_total
```

---

## Monitoring Performance

### Inference Latency

The backend exports per-request AI timing as a Prometheus histogram rather than a log
switch. Set `LOG_LEVEL=DEBUG` in `.env` if you need the client-side timings in the
backend logs.

### Prometheus Metrics

The monitoring stack is part of the default `up -d` (no profile needed). The backend
exposes metrics at `/api/metrics` (scraped by Prometheus under that path):

```bash
curl -s http://localhost:8000/api/metrics | grep '^hsi_' | head -50
```

Relevant metric families (all `hsi_`-prefixed, defined in `backend/core/metrics.py`):

- `hsi_ai_request_duration_seconds{service}` — per-request AI latency histogram, written
  only by the detector client (`service="yolo26"`); verdict latency lives in
  `event_verifications.latency_ms`, not here
- `hsi_specialist_unavailable_total{specialist,reason}` — a counter climbing since boot
  means that lookup leg has **never** run
- `hsi_prompts_truncated_total` — what the slot fitter is doing to your batches
- `hsi_detection_queue_depth`, `hsi_analysis_queue_depth`, `hsi_dlq_depth`
- `hsi_pipeline_errors_total`, `hsi_detections_processed_total`

The VLM serve itself publishes no `hsi_*` family — read llama.cpp's own `llama_*`
series: Prometheus scrapes them under the `ai-vlm-metrics` job (`ai-vlm:8098/metrics`),
and Triton's per-model timings come from `triton-metrics` (`ai-gateway:8002`). Tokens
per second is `rate(llama_tokens_predicted_total[1m])`.

---

## Performance Checklist

Before production deployment:

- [ ] GPU utilization under load < 90%
- [ ] VRAM usage under load < 80% of total
- [ ] Detection latency < 100ms
- [ ] Verdict latency inside `AI_VLM_READ_TIMEOUT`
- [ ] `hsi_specialist_unavailable_total` reads as you expect for your card
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
- [AI pipeline: current state](../architecture/ai-pipeline-current-state.md) - §2: the four silent-failure surfaces

---

[Back to Operator Hub](README.md)
