# YOLO26 Deployment Guide

This guide documents the YOLO26 object detection service deployment in the Home Security Intelligence system.

## Overview

### What is YOLO26?

YOLO26 is the object detection model used in this project, featuring:

- **CNN-based architecture** optimized for real-time inference
- **Built-in NMS** (Non-Maximum Suppression) - no post-processing required
- **TensorRT optimization** for NVIDIA GPUs with FP16 precision
- **Security-focused class filtering** for home monitoring (person, car, truck, dog, cat, bird, bicycle, motorcycle, bus)

### Performance Characteristics

YOLO26 with TensorRT FP16 provides excellent performance for security monitoring:

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

Before migrating, ensure the TensorRT engine file exists:

```bash
# Check for the model file
ls -la /export/ai_models/model-zoo/yolo26/exports/yolo26m_fp16.engine

# Expected output:
# -rw-r--r-- 1 user user 43.1M Jan 26 00:00 yolo26m_fp16.engine
```

If the engine file doesn't exist, see [Exporting TensorRT Engines](#exporting-tensorrt-engines) below.

### Directory Structure

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

### Environment Variables

| Variable                       | Default                                      | Description                                      |
| ------------------------------ | -------------------------------------------- | ------------------------------------------------ |
| `YOLO26_URL`                   | `http://ai-yolo26:8095`                      | YOLO26 service endpoint (Docker network)         |
| `YOLO26_CONFIDENCE`            | `0.5`                                        | Minimum confidence threshold (0.0-1.0)           |
| `YOLO26_MODEL_PATH`            | `/models/yolo26/exports/yolo26m_fp16.engine` | Path to TensorRT engine inside container         |
| `YOLO26_API_KEY`               | (none)                                       | Optional API key for service authentication      |
| `YOLO26_READ_TIMEOUT`          | `30.0`                                       | Inference timeout in seconds (5-120)             |
| `YOLO26_CACHE_CLEAR_FREQUENCY` | `1`                                          | Clear CUDA cache every N detections (0=disabled) |

### Model Selection

| Model   | File                  | Speed   | Accuracy | Use Case                         |
| ------- | --------------------- | ------- | -------- | -------------------------------- |
| yolo26n | `yolo26n_fp16.engine` | 223 FPS | Lower    | Maximum throughput, edge devices |
| yolo26s | `yolo26s_fp16.engine` | 206 FPS | Medium   | Balanced speed/accuracy          |
| yolo26m | `yolo26m_fp16.engine` | 174 FPS | Higher   | Best accuracy (recommended)      |

## Migration Steps

### Step 1: Verify Model Files Exist

```bash
# Check that the TensorRT engine exists
if [ -f "/export/ai_models/model-zoo/yolo26/exports/yolo26m_fp16.engine" ]; then
    echo "Model file found"
    ls -lh /export/ai_models/model-zoo/yolo26/exports/
else
    echo "ERROR: Model file not found. Run export script first."
    exit 1
fi
```

### Step 2: Build the ai-yolo26 Container

```bash
# Navigate to project root
cd /path/to/home-security-intelligence

# Build the YOLO26 container (always use --no-cache for clean builds)
podman-compose -f docker-compose.prod.yml build --no-cache ai-yolo26

# Verify the build succeeded
podman images | grep ai-yolo26
```

### Step 3: Configure YOLO26

Configure YOLO26 options in your `.env` file:

```bash
# Optional: Adjust confidence threshold if needed
YOLO26_CONFIDENCE=0.5

# Optional: Use a different model variant
# YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26s_fp16.engine  # For faster inference
```

### Step 4: Start the YOLO26 Service

```bash
# Start the YOLO26 container
podman-compose -f docker-compose.prod.yml up -d ai-yolo26

# Wait for model loading (typically 30-60 seconds)
sleep 60

# Check container status
podman-compose -f docker-compose.prod.yml ps ai-yolo26
```

### Step 5: Restart the Backend Service

The backend must be restarted to pick up the new `DETECTOR_TYPE` setting:

```bash
# Restart backend to use YOLO26
podman-compose -f docker-compose.prod.yml restart backend

# Or rebuild if you made code changes
podman-compose -f docker-compose.prod.yml build --no-cache backend
podman-compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### Step 6: Verify Health Endpoint

```bash
# Check YOLO26 service health
curl -s http://localhost:8095/health | jq .

# Expected response:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "device": "cuda:0",
#   "cuda_available": true,
#   "model_name": "/models/yolo26/exports/yolo26m_fp16.engine",
#   "vram_used_gb": 0.1,
#   "tensorrt_enabled": true
# }
```

### Step 7: Test Detection

```bash
# Test with a sample image
curl -X POST \
  -F "file=@/path/to/test-image.jpg" \
  http://localhost:8095/detect | jq .

# Expected response:
# {
#   "detections": [
#     {
#       "class": "person",
#       "confidence": 0.92,
#       "bbox": { "x": 100, "y": 50, "width": 200, "height": 400 }
#     }
#   ],
#   "inference_time_ms": 5.8,
#   "image_width": 1920,
#   "image_height": 1080
# }
```

## Rollback Procedure

If you encounter issues after migration, rolling back is simple:

### Step 1: Update Environment

```bash
# Edit .env to switch back to YOLO26
DETECTOR_TYPE=yolo26
```

### Step 2: Restart Backend

```bash
# Restart the backend to use YOLO26
podman-compose -f docker-compose.prod.yml restart backend
```

### Step 3: Verify Rollback

```bash
# Check backend logs to confirm detector type
podman-compose -f docker-compose.prod.yml logs backend | grep -i "detector"

# Expected: "DetectorClient initialized" with "detector_type": "yolo26"
```

### Important Notes on Rollback

- **No data migration required**: Both detectors produce identical detection format
- **Detections are preserved**: Existing detections in the database remain valid
- **No schema changes**: The Detection model works with both detectors
- **Optionally stop YOLO26**: `podman-compose -f docker-compose.prod.yml stop ai-yolo26`

## Performance Expectations

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
- For maximum accuracy requirements, continue using YOLO26
- Run accuracy validation: `scripts/benchmark_yolo26_accuracy.py`

## Monitoring

### Prometheus Metrics

YOLO26 exposes metrics with the `yolo26_` prefix:

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

### Accessing Metrics

```bash
# Prometheus metrics endpoint
curl http://localhost:8095/metrics

# Example output:
# yolo26_model_loaded 1.0
# yolo26_inference_latency_seconds_bucket{endpoint="detect",le="0.01"} 847.0
# yolo26_gpu_memory_used_gb 0.098
# yolo26_gpu_utilization_percent 15.0
```

### Grafana Dashboard Integration

The YOLO26 metrics integrate with the existing AI Services dashboard. Key panels:

1. **Inference Latency** - P50, P95, P99 latency over time
2. **Request Rate** - Detections per second
3. **GPU Utilization** - GPU usage and temperature
4. **Model Status** - Health and availability

To add YOLO26 panels to Grafana:

```promql
# Average inference latency
rate(yolo26_inference_latency_seconds_sum[5m]) / rate(yolo26_inference_latency_seconds_count[5m])

# Requests per second
rate(yolo26_inference_requests_total[1m])

# P95 latency
histogram_quantile(0.95, rate(yolo26_inference_latency_seconds_bucket[5m]))
```

### Backend Metrics

The backend also tracks detector metrics with labels:

```promql
# AI request duration by detector type
hsi_ai_request_duration_seconds{ai_service="yolo26"}

# Detection counts
hsi_detections_processed_total
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Model File Not Found

**Symptom:** Container starts but returns 503 on `/detect`

```json
{ "detail": "Model not loaded" }
```

**Solution:** Ensure the TensorRT engine exists and is mounted correctly:

```bash
# Check host path
ls -la /export/ai_models/model-zoo/yolo26/exports/

# Check container mount
podman exec ai-yolo26 ls -la /models/yolo26/exports/

# If missing, export the engine (see below)
```

#### 2. TensorRT Engine Incompatibility

**Symptom:** Container crashes on startup with TensorRT error

```
[TRT] Error: The engine was generated with a different version of TensorRT
```

**Solution:** Re-export the TensorRT engine for your GPU/TensorRT version:

```bash
# Run export inside container with matching TensorRT version
podman run --rm \
    --security-opt=label=disable \
    --hooks-dir=/usr/share/containers/oci/hooks.d/ \
    --device nvidia.com/gpu=all \
    -v /export/ai_models/model-zoo:/models:z \
    ghcr.io/your-org/ai-yolo26:latest \
    python -c "
from ultralytics import YOLO
model = YOLO('yolo26m.pt')
model.export(format='engine', half=True, device=0)
"
```

#### 3. CUDA Out of Memory

**Symptom:** OOM error during inference

```
RuntimeError: CUDA out of memory
```

**Solution:**

1. Use a smaller model variant (`yolo26n` instead of `yolo26m`)
2. Ensure no other processes are using GPU memory
3. Reduce batch size if using batch endpoint

```bash
# Check GPU memory usage
nvidia-smi

# Use smaller model
YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26n_fp16.engine
```

#### 4. Connection Refused from Backend

**Symptom:** Backend logs show connection errors to YOLO26

```
httpx.ConnectError: Connection refused
```

**Solution:** Verify the service is running and accessible:

```bash
# Check container status
podman-compose -f docker-compose.prod.yml ps ai-yolo26

# Check if service is listening
podman exec ai-yolo26 curl -s http://localhost:8095/health

# Verify network connectivity from backend
podman exec backend curl -s http://ai-yolo26:8095/health
```

#### 5. High Latency (Not Matching Benchmarks)

**Symptom:** Inference times much higher than expected

**Solution:**

1. Verify TensorRT engine is being used (not PyTorch fallback)
2. Check GPU utilization during inference
3. Ensure CUDA cache clearing is not too aggressive

```bash
# Check if TensorRT is enabled
curl http://localhost:8095/health | jq .tensorrt_enabled

# Should return: true

# Disable aggressive cache clearing if needed
YOLO26_CACHE_CLEAR_FREQUENCY=0
```

#### 6. Detections Not Appearing

**Symptom:** No detections returned for images that should have objects

**Solution:**

1. Verify confidence threshold is not too high
2. Check that the object class is in the security-relevant list
3. Test with the `/detect` endpoint directly

```bash
# Test with lower confidence
YOLO26_CONFIDENCE=0.3

# Security-relevant classes:
# person, car, truck, dog, cat, bird, bicycle, motorcycle, bus
```

### Health Check Endpoints

| Endpoint   | Method | Description        |
| ---------- | ------ | ------------------ |
| `/health`  | GET    | Full health status |
| `/metrics` | GET    | Prometheus metrics |
| `/detect`  | POST   | Object detection   |

### Log Analysis

```bash
# View YOLO26 container logs
podman-compose -f docker-compose.prod.yml logs -f ai-yolo26

# Filter for errors
podman-compose -f docker-compose.prod.yml logs ai-yolo26 2>&1 | grep -i error

# Check backend detector logs
podman-compose -f docker-compose.prod.yml logs backend | grep -i "yolo26\|detector"
```

## Exporting TensorRT Engines

If you need to create or recreate TensorRT engines:

```bash
# Build benchmark container
podman build -t yolo26-benchmark -f Dockerfile.yolo26-benchmark .

# Export all model variants
podman run --rm \
    --security-opt=label=disable \
    --hooks-dir=/usr/share/containers/oci/hooks.d/ \
    --device nvidia.com/gpu=all \
    -v /export/ai_models/model-zoo:/models:z \
    -v $(pwd)/scripts:/scripts:z \
    yolo26-benchmark python3 /scripts/export_yolo26.py \
    --output-dir /models/yolo26/exports \
    --variants n s m \
    --format engine \
    --half
```

**Important:** TensorRT engines are GPU-specific. If you change GPUs, you must re-export the engines.

## Related Documentation

- [YOLO26 vs YOLO26 Benchmark Results](../benchmarks/yolo26-vs-yolo26.md)
- [YOLO26 Export Formats](../benchmarks/yolo26-export-formats.md)
- [Container Orchestration](./container-orchestration.md)
- [Multi-GPU Support](../development/multi-gpu.md)
