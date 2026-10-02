# YOLO26 Deployment Guide

This guide documents deploying the YOLO26 object detector: what runs, how to
verify it, and how to re-export its TensorRT engine.

## Overview

### What is YOLO26?

YOLO26 is the system's object detector:

- **CNN-based architecture** optimized for real-time inference
- **Built-in NMS** (Non-Maximum Suppression) - no post-processing required
- **TensorRT optimization** for NVIDIA GPUs with FP16 precision
- **COCO class vocabulary**, filtered per class on the backend side (see
  [Confidence Thresholds](#confidence-thresholds))

### Where It Runs

Detection is one Triton model inside **`ai-gateway`** — the only vision service
in this stack.

```
backend (DetectorClient)
  -> POST http://ai-gateway:8090/yolo26/detect        (multipart image)
  -> Triton, model name "yolo26", TensorRT FP16 plan
  -> gateway adapter post-processes to {class, confidence, bbox}
```

`ai/gateway/adapters/yolo26.py` mounts the router; `ai/gateway/main.py` mounts
that router at `/yolo26`. Triton starts with `--model-control-mode=none`, so the
plan is resident from container start — there is no load/unload call at runtime.

For debugging a set of weights outside the container, `./ai/start_detector.sh`
runs `ai/yolo26/model.py` directly on the host. It listens on `YOLO26_PORT`
(default 8090, which collides with the gateway's host port — run one or the
other) and is a development stand-in, not the production path.

## Prerequisites

### Hardware Requirements

- **GPU**: NVIDIA GPU with Compute Capability 7.0+ (Turing architecture or newer)
  - RTX 20xx, RTX 30xx, RTX 40xx series
  - Quadro RTX series
  - Tesla T4, V100, A100
- **VRAM**: The gateway container reserves its card via
  `deploy.resources.reservations.devices.device_ids` on `GPU_AI_SERVICES`
  (default 1) — see [GPU Memory Limits](./gpu-memory-limits.md).
- **Driver**: NVIDIA Driver 525.0+ with TensorRT 8.6+ support

### Software Requirements

- TensorRT 10.0+ (included in the container image)
- CUDA 12.0+ (included in the container image)
- Podman or Docker with NVIDIA container toolkit

### Model Files

The gateway's Triton model repository is built and cached automatically
(`triton-kernel-cache` / `triton-tmp-cache` volumes plus
`${AI_MODELS_PATH}/triton` mounted at `/models/cache`). Which repositories
Triton actually serves is decided at boot by `GATEWAY_MODEL_SET` — `vlm` is the
shipped value and selects `{yolo26, reid}`, plus `threat` only when
`GATEWAY_ENABLE_THREAT=true`. Any other value raises at container start.

For the host-run dev server, `YOLO26_MODEL_PATH` points at a weights file —
current default `/models/yolo26/yolo26m.pt` (`.env.example`): a `.pt` triggers
an automatic TensorRT rebuild on first start; a pre-built `.engine` is used
directly. Exported engines land under the model-zoo exports directory:

```
/export/ai_models/model-zoo/yolo26/
  exports/
    yolo26n_fp16.engine   #  7.3 MB - Fastest, nano model
    yolo26s_fp16.engine   # 21.9 MB - Balanced, small model
    yolo26m_fp16.engine   # 43.1 MB - Best accuracy, medium model (default)
    yolo26n.onnx           #  9.5 MB - ONNX format (portable)
    yolo26s.onnx           # 36.5 MB - ONNX format (portable)
    yolo26m.onnx           # 78.2 MB - ONNX format (portable)
```

## Configuration Options

### Environment Variables

| Variable                            | Default                           | Description                                                                                                 |
| ----------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `YOLO26_URL`                        | `http://ai-gateway:8090/yolo26`   | Detector endpoint the backend calls; host-run dev: `http://localhost:8090`                                  |
| `AI_GATEWAY_URL` + `USE_AI_GATEWAY` | `http://ai-gateway:8090` / `true` | When gateway mode is on, the backend derives the detector URL from the gateway URL and ignores `YOLO26_URL` |
| `GATEWAY_MODEL_SET`                 | `vlm`                             | Triton repository selection at boot. `vlm` is the only accepted value; anything else raises.                |
| `GATEWAY_ENABLE_THREAT`             | `false`                           | Adds the `threat` Triton model to the gateway's set. Opt-in; also changes gateway VRAM.                     |
| `YOLO26_MODEL_PATH`                 | `/models/yolo26/yolo26m.pt`       | Weights for the host-run dev server (`.pt` auto-rebuilds an engine)                                         |
| `YOLO26_PORT`                       | `8090`                            | Host-run dev server port (collides with the gateway's host port)                                            |
| `YOLO26_API_KEY`                    | (none)                            | Optional bearer key the `DetectorClient` sends                                                              |
| `YOLO26_READ_TIMEOUT`               | `30.0`                            | Read/write timeout on the detector HTTP client, seconds (5-120)                                             |
| `DETECTION_CONFIDENCE_THRESHOLD`    | `0.40`                            | Backend-side floor for classes without a per-class override                                                 |
| `DETECTION_CLASS_THRESHOLDS`        | see below                         | Per-class overrides, JSON dict                                                                              |

`YOLO26_CONFIDENCE` is read by the host-run dev server only; the gateway
adapter applies its own `CONFIDENCE_THRESHOLD = 0.25` floor before the backend's
per-class gate ever sees a detection.

### Confidence Thresholds

Three gates sit in series, and a detection has to clear all three:

1. **Gateway adapter**: `CONFIDENCE_THRESHOLD = 0.25`, `NMS_THRESHOLD = 0.45`,
   `TARGET_SIZE = 640` (`ai/gateway/adapters/yolo26.py`). Fixed in code.
2. **Backend per-class gate**: `settings.detection_class_thresholds`
   (`backend/core/config.py`) — `person` 0.40, `car`/`truck`/`motorcycle`/
   `bicycle`/`backpack`/`handbag`/`suitcase` 0.50, `bus` 0.55, and
   `dog`/`cat`/`bird` 0.45. Unlisted classes fall back to
   `detection_confidence_threshold` (0.40).
3. Override both from `.env`, e.g.
   `DETECTION_CLASS_THRESHOLDS={"person": 0.45, "car": 0.70, "truck": 0.70, "bus": 0.70, "motorcycle": 0.65, "bicycle": 0.65, "dog": 0.55, "cat": 0.55, "bird": 0.55, "backpack": 0.60, "handbag": 0.60, "suitcase": 0.60}`

### Model Selection

Latency for the three shipped variants, end to end on an RTX A5500 at 640x640 —
full methodology and the 1280x1280 sweep in
[YOLO26 Benchmarks](../benchmarks/yolo26-benchmarks.md), which
`scripts/benchmark_yolo26_latency.py` regenerates:

| Variant | Typical latency (batch 1, 640x640) | Use Case                     |
| ------- | ---------------------------------- | ---------------------------- |
| yolo26n | 44.83ms                            | Lightweight, edge deployment |
| yolo26s | 73.74ms                            | Maximum throughput per frame |
| yolo26m | 138.84ms                           | Default, best accuracy       |

## Deployment Steps

### Step 1: Start the Gateway

```bash
# The gateway is part of the standard stack
docker compose -f docker-compose.prod.yml up -d ai-gateway

# Triton warm-up can take up to its health check's start_period
docker compose -f docker-compose.prod.yml ps ai-gateway
```

### Step 2: Verify the YOLO26 Router

```bash
# Router health (model readiness via Triton)
curl -s http://localhost:8090/yolo26/health | jq .

# Aggregated gateway health. /health reports each model Triton declares ready:
# {status, triton_server_ready, models: {name: bool}, models_loaded, models_total}
curl -s http://localhost:8090/health | jq '.models.yolo26, .models_loaded, .models_total'
```

`status` is `healthy` only when Triton itself is ready **and** every active
model reports ready; otherwise `degraded`.

### Step 3: Test Detection

```bash
curl -X POST \
  -F "file=@/path/to/test-image.jpg" \
  http://localhost:8090/yolo26/detect | jq .
```

## Monitoring

Prometheus scrapes Triton directly and the gateway's FastAPI layer separately,
and deliberately de-duplicates them:

- **`triton-metrics` job** → `ai-gateway:8002/metrics` (15s interval): the
  `nv_*` families — `nv_inference_request_success` / `_failure`, queue and
  compute duration, `nv_gpu_utilization`, `nv_gpu_memory_used_bytes`, labelled
  `model="yolo26"` and `service="triton"`.
- **Gateway app job** → `ai-gateway:8090/metrics`: the gateway merges Triton's
  text into this endpoint, and the Prometheus config drops the `nv_*` series
  from this target so nothing double-counts. What remains is
  `hsi_ai_inference_duration_seconds` / `hsi_ai_inference_errors_total` from the
  gateway's request middleware, labelled `service=<adapter prefix>`.
- **Backend**: every detector round-trip is timed by the client regardless of
  topology, on the `service` label:

```promql
# Detector round-trip latency attributed to yolo26 (label name is "service")
rate(hsi_ai_request_duration_seconds_sum{service="yolo26"}[5m])
  / rate(hsi_ai_request_duration_seconds_count{service="yolo26"}[5m])
```

The `job:yolo26_inference_latency:p95_5m` recording rule already computes that
p95 from the histogram buckets
(`monitoring/profiling-recording-rules.yml`), and
`job:triton_inference_latency:avg5m` derives the Triton-side mean from
`nv_inference_request_duration_us / nv_inference_request_success`.

The host-run dev server publishes its own `yolo26_*` families
(`ai/yolo26/metrics.py`: `yolo26_inference_duration_seconds`,
`yolo26_requests_total`, `yolo26_detections_total`, `yolo26_vram_bytes`,
`yolo26_errors_total`, `yolo26_batch_size`). Those exist only when you started
that script and are not in any production scrape target.

## Troubleshooting

### Gateway YOLO26 router unhealthy

```bash
# Router + Triton readiness
curl -s http://localhost:8090/yolo26/health | jq .
curl -s http://localhost:8090/health | jq '{status, models_loaded, models_total}'

# Gateway logs
docker compose -f docker-compose.prod.yml logs ai-gateway | grep -i "yolo26\|triton"
```

### Detections missing or too few

1. Work the three gates in order — the gateway's 0.25 floor, then
   `DETECTION_CONFIDENCE_THRESHOLD` and `DETECTION_CLASS_THRESHOLDS`. Too high a
   per-class value suppresses real detections; the class defaults above are
   deliberately recall-favouring.
2. Check the class name matches COCO spelling exactly (`car`, not `vehicle`) —
   an override for a class the model never emits is inert.
3. Exercise the router directly: `curl -X POST -F "file=@test.jpg" http://localhost:8090/yolo26/detect`.

### CUDA Out of Memory

Nothing evicts at runtime — Triton's models are resident and there is no
unload path — so an OOM means the mounted set was too large for the card:

1. Use a smaller variant (`yolo26n` instead of `yolo26m`) and re-export.
2. Check whether `GATEWAY_ENABLE_THREAT=true` is adding the threat model to this
   container's footprint.
3. Make sure `GPU_LLM` and `GPU_AI_SERVICES` are different indices, so the VLM
   engine is not sharing this card. See
   [GPU Memory Limits](./gpu-memory-limits.md).

### Backend can't reach the detector

```bash
# From the backend container
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import httpx; print(httpx.get('http://ai-gateway:8090/yolo26/health', timeout=5).status_code)"

# What URL is the backend actually using?
docker compose -f docker-compose.prod.yml exec backend env | grep -E "YOLO26_URL|AI_GATEWAY_URL|USE_AI_GATEWAY"
```

A 401 here means the gateway expects a key the client is not sending
(`YOLO26_API_KEY`). A timeout means `YOLO26_READ_TIMEOUT` (30s) is shorter than
a cold TensorRT plan build.

### Health Check Endpoints

| Endpoint               | Method | Description                                                    |
| ---------------------- | ------ | -------------------------------------------------------------- |
| `/yolo26/health`       | GET    | YOLO26 router/model readiness                                  |
| `/yolo26/detect`       | POST   | Object detection (multipart `file`)                            |
| `/yolo26/detect/batch` | POST   | Batched detection (multipart `files`)                          |
| `/yolo26/segment`      | POST   | Instance segmentation; detection-only when `output1` is absent |
| `/health`              | GET    | Aggregated Triton model health                                 |
| `/metrics`             | GET    | Prometheus metrics (Triton merged + gateway app)               |

(all on port 8090, inside `ai-gateway`)

## Exporting TensorRT Engines

TensorRT plans are built by the gateway's Triton startup for the shipped
repository. `scripts/export_yolo26.py` produces plans and ONNX by hand — for the
host-run dev server, or to pre-bake so a first boot skips the build. Run it on
the host (it needs `ultralytics` plus a matching TensorRT install):

```bash
python scripts/export_yolo26.py \
    --output-dir /export/ai_models/model-zoo/yolo26/exports \
    --variants n s m \
    --format engine \
    --half
```

**Important:** TensorRT engines are GPU- and TensorRT-version-specific. If you
change GPUs or upgrade TensorRT, re-export (or point `YOLO26_MODEL_PATH` back at
a `.pt` and let the dev server rebuild).

Validate accuracy against the FP32 reference before swapping a plan into
production — `scripts/benchmark_yolo26_accuracy.py`.

## Related Documentation

- [YOLO26 Export Formats](../benchmarks/yolo26-export-formats.md)
- [YOLO26 Benchmarks](../benchmarks/yolo26-benchmarks.md)
- [Container Orchestration](./container-orchestration.md)
- [Multi-GPU Support](../developer/multi-gpu.md)
