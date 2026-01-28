# AI Enrichment Light Service

The `ai-enrichment-light` service is a lightweight GPU microservice designed for small, efficient AI models that run on a secondary GPU (e.g., NVIDIA A400 4GB). It complements the heavier `ai-enrichment` service by hosting models with lower VRAM requirements.

## Overview

| Property             | Value                               |
| -------------------- | ----------------------------------- |
| **Container Name**   | `ai-enrichment-light`               |
| **Port**             | 8096                                |
| **Expected VRAM**    | ~1.2GB (with TensorRT optimization) |
| **Target GPU**       | GPU 1 (secondary, e.g., A400 4GB)   |
| **Source Directory** | `ai/enrichment-light/`              |

## Models Hosted

The service hosts five lightweight models optimized for efficient inference:

| Model                 | VRAM   | Purpose                    | Security Value                                  |
| --------------------- | ------ | -------------------------- | ----------------------------------------------- |
| **YOLOv8n-pose**      | ~300MB | Human pose estimation      | Detect suspicious postures (crouching, running) |
| **Threat Detector**   | ~400MB | Weapon detection           | Identify knives, guns, bats, etc.               |
| **OSNet-x0.25**       | ~100MB | Person re-identification   | Track individuals across cameras                |
| **Pet Classifier**    | ~200MB | Cat/dog classification     | Reduce false positives from pets                |
| **Depth Anything V2** | ~150MB | Monocular depth estimation | Distance context for detections                 |

## API Endpoints

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "models_loaded": {
    "pose_estimator": true,
    "threat_detector": true,
    "person_reid": true,
    "pet_classifier": true,
    "depth_estimator": true
  },
  "gpu_available": true,
  "gpu_memory_used_gb": 1.15,
  "uptime_seconds": 3600.5
}
```

### Pose Analysis

```http
POST /pose-analyze
Content-Type: application/json

{
  "image_base64": "<base64-encoded-image>"
}
```

**Response:**

```json
{
  "keypoints": [
    { "name": "nose", "x": 320, "y": 150, "confidence": 0.95 },
    { "name": "left_shoulder", "x": 280, "y": 200, "confidence": 0.92 }
  ],
  "posture": "standing",
  "alerts": [],
  "inference_time_ms": 15.3
}
```

### Threat Detection

```http
POST /threat-detect
Content-Type: application/json

{
  "image_base64": "<base64-encoded-image>"
}
```

**Response:**

```json
{
  "threats_detected": [
    {
      "class": "knife",
      "confidence": 0.87,
      "bbox": { "x": 100, "y": 150, "width": 50, "height": 120 }
    }
  ],
  "is_threat": true,
  "max_confidence": 0.87,
  "inference_time_ms": 12.5
}
```

### Person Re-identification

```http
POST /person-reid
Content-Type: application/json

{
  "image_base64": "<base64-encoded-image>"
}
```

**Response:**

```json
{
  "embedding": [0.123, -0.456, 0.789, ...],
  "embedding_dim": 512,
  "inference_time_ms": 8.2
}
```

### Pet Classification

```http
POST /pet-classify
Content-Type: application/json

{
  "image_base64": "<base64-encoded-image>"
}
```

**Response:**

```json
{
  "pet_type": "dog",
  "breed": "unknown",
  "confidence": 0.94,
  "is_household_pet": true,
  "inference_time_ms": 10.1
}
```

### Depth Estimation

```http
POST /depth-estimate
Content-Type: application/json

{
  "image_base64": "<base64-encoded-image>"
}
```

**Response:**

```json
{
  "depth_map_base64": "<base64-encoded-png>",
  "min_depth": 0.15,
  "max_depth": 0.95,
  "mean_depth": 0.52,
  "inference_time_ms": 18.7
}
```

### Prometheus Metrics

```http
GET /metrics
```

Returns Prometheus-formatted metrics for monitoring.

## Configuration

### Environment Variables

| Variable            | Default                                            | Description                 |
| ------------------- | -------------------------------------------------- | --------------------------- |
| `HOST`              | `0.0.0.0`                                          | Server bind address         |
| `PORT`              | `8096`                                             | Server port                 |
| `POSE_MODEL_PATH`   | `/models/yolov8n-pose/yolov8n-pose.pt`             | Pose model path             |
| `THREAT_MODEL_PATH` | `/models/threat-detection-yolov8n/weights/best.pt` | Threat model path           |
| `REID_MODEL_PATH`   | `/models/osnet-x0-25/osnet_x0_25.pth`              | Re-ID model path            |
| `PET_MODEL_PATH`    | `/models/pet-classifier`                           | Pet classifier path         |
| `DEPTH_MODEL_PATH`  | `/models/depth-anything-v2-small`                  | Depth model path            |
| `PYROSCOPE_ENABLED` | `true`                                             | Enable continuous profiling |
| `PYROSCOPE_URL`     | `http://pyroscope:4040`                            | Pyroscope server URL        |

### Model Assignment

Models are assigned to either `light` or `heavy` service via environment variables:

```bash
# In docker-compose.prod.yml or .env
ENRICHMENT_POSE_SERVICE=light      # Default: light
ENRICHMENT_THREAT_SERVICE=light    # Default: light
ENRICHMENT_REID_SERVICE=light      # Default: light
ENRICHMENT_PET_SERVICE=light       # Default: light
ENRICHMENT_DEPTH_SERVICE=light     # Default: light
```

### Preload Configuration

Control which models load at startup vs on-demand:

```bash
# Preload specific models at startup (comma-separated)
ENRICHMENT_LIGHT_PRELOAD_MODELS=pose_estimator,threat_detector

# Empty = all models load on-demand (saves startup time)
ENRICHMENT_LIGHT_PRELOAD_MODELS=
```

Available model names for preloading:

- `pose_estimator`
- `threat_detector`
- `person_reid`
- `pet_classifier`
- `depth_estimator`

### TensorRT Acceleration

YOLO models support TensorRT optimization for faster inference:

```bash
POSE_USE_TENSORRT=true      # Default: true
THREAT_USE_TENSORRT=true    # Default: true
```

TensorRT engines are cached in `/cache/tensorrt/` and persist across container restarts.

## Docker Compose Configuration

```yaml
ai-enrichment-light:
  build:
    context: .
    dockerfile: ai/enrichment-light/Dockerfile
  ports:
    - '8096:8096'
  volumes:
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/yolov8n-pose:/models/yolov8n-pose:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/threat-detection-yolov8n:/models/threat-detection-yolov8n:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/osnet-x0-25:/models/osnet-x0-25:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/pet-classifier:/models/pet-classifier:ro
    - ${AI_MODELS_PATH:-/export/ai_models}/model-zoo/depth-anything-v2-small:/models/depth-anything-v2-small:ro
    - enrichment-light-tensorrt-cache:/cache/tensorrt
  environment:
    - SERVICE_NAME=ai-enrichment-light
    - PYROSCOPE_ENABLED=${PYROSCOPE_ENABLED:-true}
    - ENRICHMENT_PRELOAD_MODELS=${ENRICHMENT_LIGHT_PRELOAD_MODELS:-}
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['${GPU_CLIP:-1}']
            capabilities: [gpu]
```

## Backend Integration

The backend routes requests to the appropriate enrichment service based on configuration:

```python
# From backend/services/enrichment_client.py
ENRICHMENT_URL = os.environ.get("ENRICHMENT_URL", "http://ai-enrichment:8094")
ENRICHMENT_LIGHT_URL = os.environ.get("ENRICHMENT_LIGHT_URL", "http://ai-enrichment-light:8096")

# Route based on model assignment
if os.environ.get("ENRICHMENT_POSE_SERVICE", "light") == "light":
    response = await httpx.post(f"{ENRICHMENT_LIGHT_URL}/pose-analyze", ...)
else:
    response = await httpx.post(f"{ENRICHMENT_URL}/pose-analyze", ...)
```

## Prometheus Metrics

| Metric                                                        | Type      | Description               |
| ------------------------------------------------------------- | --------- | ------------------------- |
| `enrichment_light_inference_requests_total{endpoint, status}` | Counter   | Total inference requests  |
| `enrichment_light_inference_latency_seconds{endpoint}`        | Histogram | Inference latency         |
| `enrichment_light_gpu_memory_used_gb`                         | Gauge     | GPU memory usage          |
| `enrichment_light_model_loaded{model}`                        | Gauge     | Model loaded status (0/1) |

## Health Checks

The service uses an HTTP health check:

```yaml
healthcheck:
  test:
    [
      'CMD',
      'python',
      '-c',
      "import httpx; r = httpx.get('http://localhost:8096/health'); r.raise_for_status()",
    ]
  interval: 30s
  timeout: 10s
  start_period: 90s
  retries: 3
```

The 90-second start period allows time for model loading.

## GPU Memory Budget

Typical VRAM allocation on a 4GB GPU:

| Model             | VRAM (TensorRT) | VRAM (PyTorch) |
| ----------------- | --------------- | -------------- |
| YOLOv8n-pose      | ~200MB          | ~300MB         |
| Threat Detector   | ~250MB          | ~400MB         |
| OSNet-x0.25       | ~100MB          | ~100MB         |
| Pet Classifier    | ~150MB          | ~200MB         |
| Depth Anything V2 | ~150MB          | ~150MB         |
| **Total**         | **~850MB**      | **~1.2GB**     |

This leaves headroom for CUDA context and dynamic allocations on a 4GB GPU.

## Comparison: Light vs Heavy Enrichment

| Aspect          | ai-enrichment-light            | ai-enrichment                         |
| --------------- | ------------------------------ | ------------------------------------- |
| **Port**        | 8096                           | 8094                                  |
| **Target GPU**  | GPU 1 (A400 4GB)               | GPU 0 (A5500 24GB)                    |
| **VRAM Budget** | ~1.2GB                         | ~6.8GB                                |
| **Model Types** | Small, efficient               | Large transformers                    |
| **Models**      | Pose, threat, reid, pet, depth | Vehicle, fashion, age, gender, action |

## Troubleshooting

### Model Not Loading

Check model assignment:

```bash
# Verify model is assigned to light service
echo $ENRICHMENT_POSE_SERVICE  # Should be 'light'

# Check preload configuration
echo $ENRICHMENT_LIGHT_PRELOAD_MODELS
```

### GPU Memory Issues

```bash
# Check GPU memory from container
docker exec ai-enrichment-light nvidia-smi

# Check which models are loaded
curl http://localhost:8096/health | jq '.models_loaded'
```

### TensorRT Engine Not Building

```bash
# Check TensorRT cache
docker exec ai-enrichment-light ls -la /cache/tensorrt/

# View container logs for TensorRT build progress
docker logs ai-enrichment-light 2>&1 | grep -i tensorrt
```

## Related Documentation

- [AI Orchestration Overview](../../architecture/ai-orchestration/README.md)
- [Model Zoo](../../architecture/ai-orchestration/model-zoo.md)
- [GPU Memory Limits](../../deployment/gpu-memory-limits.md)
- [Enrichment Pipeline](../../architecture/ai-orchestration/enrichment-pipeline.md)
