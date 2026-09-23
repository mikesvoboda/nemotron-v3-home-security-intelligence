# YOLO26 Deployment Guide

> **SUPERSEDED (2026-09-22).** The standalone `ai-yolo26` container this guide describes no longer exists in `docker-compose.prod.yml`. Since the AI-gateway consolidation (commit bc7d6101), YOLO26 runs as a Triton model inside **`ai-gateway`**, served at `http://ai-gateway:8090/yolo26/*` (host: `http://localhost:8090/yolo26/*`). Benchmark tables and export notes below are kept as the historical record. Current AI topology: [Container Orchestration](./container-orchestration.md).

This guide documents the YOLO26 object detection model's deployment in the Home Security Intelligence system.

## Overview

### What is YOLO26?

YOLO26 is the object detection model used in this project, featuring:

- **CNN-based architecture** optimized for real-time inference
- **Built-in NMS** (Non-Maximum Suppression) - no post-processing required
- **TensorRT optimization** for NVIDIA GPUs with FP16 precision
- **Security-focused class filtering** for home monitoring (person, car, truck, dog, cat, bird, bicycle, motorcycle, bus)

In the current deployment the model is loaded by the gateway's Triton server (`ai/gateway/adapters/yolo26.py`, model name `yolo26`) and exposed through the FastAPI router at `/yolo26` with endpoints `/health`, `/detect`, `/detect/batch`, `/segment`. The standalone HuggingFace-Transformers server (`ai/yolo26/model.py`, launched by `./ai/start_detector.sh`) survives only for host-run development.

### Performance Characteristics

YOLO26 with TensorRT FP16 provides excellent performance for security monitoring (historical benchmark, standalone TensorRT server):

| Metric           | YOLO26m TensorRT FP16 |
| ---------------- | --------------------- |
| Mean Latency     | 5.76ms                |
| P95 Latency      | 6.29ms                |
| P99 Latency      | 6.44ms                |
| Throughput (FPS) | 174                   |
| VRAM Usage       | ~100 MB               |
| Model Size       | 43.1 MB               |

## Prerequisites

### Hardware Requirements

- **GPU**: NVIDIA GPU with Compute Capability 7.0+ (Turing architecture or newer)
  - RTX 20xx, RTX 30xx, RTX 40xx series
  - Quadro RTX series
  - Tesla T4, V100, A100
- **VRAM**: Minimum 2GB available (YOLO26m uses ~100MB during inference)
- **Driver**: NVIDIA Driver 525.0+ with TensorRT 8.6+ support

### Software Requirements

- TensorRT 10.0+ (included in the container image)
- CUDA 12.0+ (included in the container image)
- Podman or Docker with NVIDIA container toolkit

### Model Files

The gateway's Triton model repository is built and cached automatically (`triton-kernel-cache`/`triton-tmp-cache` volumes plus `${AI_MODELS_PATH}/triton` mounted at `/models/cache`). For the standalone dev server, `YOLO26_MODEL_PATH` points at a weights file — current default `/models/yolo26/yolo26m.pt` (`.env.example`): a `.pt` triggers an automatic TensorRT rebuild on first start; a pre-built `.engine` is used directly.

Historical export layout (produced by `scripts/export_yolo26.py`, see [Exporting TensorRT Engines](#exporting-tensorrt-engines)):

```
/export/ai_models/model-zoo/yolo26/
  exports/
    yolo26n_fp16.engine   # 7.3 MB  - Fastest, nano model
    yolo26s_fp16.engine   # 21.9 MB - Balanced, small model
    yolo26m_fp16.engine   # 43.1 MB - Best accuracy, medium model (default)
    yolo26n.onnx          # 9.5 MB  - ONNX format (portable)
    yolo26s.onnx          # 36.5 MB - ONNX format (portable)
    yolo26m.onnx          # 78.2 MB - ONNX format (portable)
```

## Configuration Options

### Environment Variables (current)

| Variable                            | Default                                             | Description                                                                                                 |
| ----------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `YOLO26_URL`                        | `http://ai-gateway:8090/yolo26`                     | Detector endpoint the backend calls (compose); native dev: `http://localhost:8090`                          |
| `AI_GATEWAY_URL` + `USE_AI_GATEWAY` | `http://ai-gateway:8090` / `true`                   | When gateway mode is on, the backend derives the detector URL from the gateway URL and ignores `YOLO26_URL` |
| `YOLO26_MODEL_PATH`                 | `/models/yolo26/yolo26m.pt`                         | Weights for the standalone dev server (`.pt` auto-rebuilds an engine)                                       |
| `YOLO26_API_KEY`                    | (none)                                              | Optional API key for service authentication                                                                 |
| `YOLO26_READ_TIMEOUT`               | `30.0`                                              | Inference timeout in seconds                                                                                |
| `DETECTION_CONFIDENCE_THRESHOLD`    | `0.40` (config default; `.env.example` ships `0.5`) | Backend-side minimum confidence for detections, with per-class overrides                                    |

> **Historical:** the standalone-container variables `YOLO26_CONFIDENCE` (the gateway adapter uses a hardcoded `CONFIDENCE_THRESHOLD = 0.25`), `YOLO26_CACHE_CLEAR_FREQUENCY`, and the `YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26m_fp16.engine` engine default belong to the retired `ai-yolo26` container and are no longer read in the gateway path.

### Model Selection

| Variant | Typical latency (gateway, batch 1) | Use Case                     |
| ------- | ---------------------------------- | ---------------------------- |
| yolo26n | 44.83ms                            | Lightweight, edge deployment |
| yolo26s | 73.74ms                            | Maximum throughput per frame |
| yolo26m | 138.84ms                           | Default, best accuracy       |

(Latencies measured end-to-end on RTX A5500 at 640x640 — see [YOLO26 Benchmarks](../benchmarks/yolo26-benchmarks.md). The 5.76ms figures in the overview table are raw inference on the retired standalone TensorRT server.)

## Deployment Steps (current topology)

### Step 1: Start the Gateway

```bash
# The gateway is part of the standard stack
podman compose -f docker-compose.prod.yml up -d ai-gateway

# Triton warm-up can take up to its 180s health start_period
podman compose -f docker-compose.prod.yml ps ai-gateway
```

### Step 2: Verify the YOLO26 Router

```bash
# Router health (model readiness via Triton)
curl -s http://localhost:8090/yolo26/health | jq .

# Aggregated gateway health (all Triton models)
curl -s http://localhost:8090/health | jq .models.yolo26
```

### Step 3: Test Detection

```bash
curl -X POST \
  -F "file=@/path/to/test-image.jpg" \
  http://localhost:8090/yolo26/detect | jq .
```

## Historical: the standalone `ai-yolo26` container

These steps described the pre-consolidation deployment and no longer work — `docker-compose.prod.yml` has no `ai-yolo26` service, and no image named `ai-yolo26` is built. Retained for reference when reading older issues and runbooks.

```bash
# HISTORICAL — do not run
podman-compose -f docker-compose.prod.yml build --no-cache ai-yolo26
podman-compose -f docker-compose.prod.yml up -d ai-yolo26
curl -s http://localhost:8095/health        # port 8095 no longer served
curl -X POST -F "file=@test.jpg" http://localhost:8095/detect
```

### Historical: Rollback Procedure

Rolling the detector back is no longer possible: `detector_client.py` states YOLO26 is the only supported detector, and no alternative detector implementation remains in the tree. (The old `DETECTOR_TYPE=yolo26` toggle and the `Stop ai-yolo26` note applied to the retired container.)

## Performance Expectations (historical benchmarks)

### Benchmark Results (RTX A5500 24GB)

| Model       | Format        | Mean    | P50     | P95     | P99     | FPS | VRAM   |
| ----------- | ------------- | ------- | ------- | ------- | ------- | --- | ------ |
| yolo26n     | tensorrt-fp16 | 4.49ms  | 4.46ms  | 5.07ms  | 5.46ms  | 223 | ~50MB  |
| yolo26s     | tensorrt-fp16 | 4.86ms  | 4.81ms  | 5.47ms  | 5.67ms  | 206 | ~60MB  |
| **yolo26m** | tensorrt-fp16 | 5.76ms  | 5.75ms  | 6.29ms  | 6.44ms  | 174 | ~100MB |
| YOLO26-R101 | pytorch       | 30.64ms | 30.65ms | 31.90ms | 32.56ms | 33  | ~570MB |

### Speedup vs YOLO26

| Model   | Format        | Speedup  | Latency Reduction |
| ------- | ------------- | -------- | ----------------- |
| yolo26n | tensorrt-fp16 | **6.8x** | 85.4%             |
| yolo26s | tensorrt-fp16 | **6.3x** | 84.2%             |
| yolo26m | tensorrt-fp16 | **5.3x** | 81.2%             |

### VRAM Comparison

```
YOLO26:  ████████████████████████████████████████████████ ~570MB
YOLO26m:    ████████ ~100MB
YOLO26s:    █████ ~60MB
YOLO26n:    ████ ~50MB
```

### Accuracy Notes

- TensorRT FP16 has <0.1% mAP loss compared to FP32
- YOLO26m provides the best accuracy among YOLO26 variants
- Run accuracy validation: `scripts/benchmark_yolo26_accuracy.py`

## Monitoring

### Current metrics

Prometheus no longer scrapes a per-service `yolo26_*` endpoint — the standalone metrics target was removed with the container. Equivalent signals:

- **Triton metrics** (`triton-metrics` job → `ai-gateway:8002/metrics`, merged into `:8090/metrics`): `nv_inference_request_success/failure`, inference duration histograms per model (`model="yolo26"`).
- **Backend metrics**: detector round-trips are tracked by the backend regardless of topology:

```promql
# AI request duration attributed to the detector
rate(hsi_ai_request_duration_seconds_sum{ai_service="yolo26"}[5m])
  / rate(hsi_ai_request_duration_seconds_count{ai_service="yolo26"}[5m])

# Detection counts
hsi_detections_processed_total
```

### Historical: `yolo26_*` metrics from the standalone server

These names are emitted only by the retired `ai/yolo26/model.py` dev server (`curl http://localhost:8090/metrics` when running it locally); they are not in the production scrape set:

| Metric                             | Type      | Description                       |
| ---------------------------------- | --------- | --------------------------------- |
| `yolo26_inference_requests_total`  | Counter   | Total inference requests          |
| `yolo26_inference_latency_seconds` | Histogram | Inference latency distribution    |
| `yolo26_detections_per_image`      | Histogram | Number of detections per image    |
| `yolo26_model_loaded`              | Gauge     | Model loaded status (1=yes, 0=no) |
| `yolo26_gpu_utilization_percent`   | Gauge     | GPU utilization percentage        |
| `yolo26_gpu_memory_used_gb`        | Gauge     | GPU memory usage in GB            |
| `yolo26_gpu_temperature_celsius`   | Gauge     | GPU temperature in Celsius        |
| `yolo26_gpu_power_watts`           | Gauge     | GPU power consumption in Watts    |

## Troubleshooting

### Gateway YOLO26 router unhealthy

```bash
# Router + Triton readiness
curl -s http://localhost:8090/yolo26/health | jq .
curl -s http://localhost:8090/health | jq '{status, models_loaded, models_total}'

# Gateway logs
podman compose -f docker-compose.prod.yml logs ai-gateway | grep -i "yolo26\|triton"
```

### Detections missing or too few

1. Check the backend confidence gate: `DETECTION_CONFIDENCE_THRESHOLD` (with per-class overrides) — too high a value suppresses real detections.
2. Verify the class is security-relevant: person, car, truck, dog, cat, bird, bicycle, motorcycle, bus.
3. Exercise the router directly: `curl -X POST -F "file=@test.jpg" http://localhost:8090/yolo26/detect`.

### CUDA Out of Memory

1. Use a smaller model variant (`yolo26n` instead of `yolo26m`)
2. Ensure no host processes are using GPU memory: `nvidia-smi`
3. Inside the gateway, models evict by priority under pressure — check `http://localhost:8000/api/system/models/vram-summary`

### Backend can't reach the detector

```bash
# From the backend container
podman compose -f docker-compose.prod.yml exec backend \
  python -c "import httpx; print(httpx.get('http://ai-gateway:8090/yolo26/health', timeout=5).status_code)"

# What URL is the backend actually using?
podman compose -f docker-compose.prod.yml exec backend env | grep -E "YOLO26_URL|AI_GATEWAY_URL|USE_AI_GATEWAY"
```

### Health Check Endpoints (current)

| Endpoint               | Method | Description                           |
| ---------------------- | ------ | ------------------------------------- |
| `/yolo26/health`       | GET    | YOLO26 router/model readiness         |
| `/yolo26/detect`       | POST   | Object detection                      |
| `/yolo26/detect/batch` | POST   | Batched detection                     |
| `/yolo26/segment`      | POST   | Segmentation                          |
| `/health`              | GET    | Aggregated Triton model health        |
| `/metrics`             | GET    | Prometheus metrics (Triton + gateway) |

(all on port 8090, inside `ai-gateway`)

## Exporting TensorRT Engines

The export script exists, but the `Dockerfile.yolo26-benchmark` containerized recipe that used to accompany it is no longer in the repo. Run the export on the host (requires `ultralytics` + a matching TensorRT install):

```bash
python scripts/export_yolo26.py \
    --output-dir /export/ai_models/model-zoo/yolo26/exports \
    --variants n s m \
    --format engine \
    --half
```

**Important:** TensorRT engines are GPU- and TensorRT-version-specific. If you change GPUs or upgrade TensorRT, re-export (or just point `YOLO26_MODEL_PATH` back at a `.pt` and let the dev server rebuild).

## Related Documentation

- [YOLO26 Export Formats](../benchmarks/yolo26-export-formats.md)
- [YOLO26 Benchmarks](../benchmarks/yolo26-benchmarks.md)
- [Container Orchestration](./container-orchestration.md)
- [Multi-GPU Support](../developer/multi-gpu.md)
