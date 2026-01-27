# YOLO26 Object Detection Server

## Purpose

FastAPI-based HTTP server that wraps YOLO26m TensorRT object detection model for real-time security monitoring. Provides GPU-accelerated inference via Ultralytics YOLO with TensorRT optimization, detecting security-relevant objects in camera images.

## Port and Resources

- **Port**: 8095
- **Expected VRAM**: ~2GB with TensorRT FP16 engine
- **Inference Time**: 10-20ms per image on RTX A5500 (TensorRT optimized)

## Directory Contents

```
ai/yolo26/
├── AGENTS.md          # This file
├── __init__.py        # Package init (version 1.0.0)
├── Dockerfile         # Container build (TensorRT 24.09)
├── metrics.py         # Prometheus metrics definitions and helpers
├── model.py           # FastAPI inference server
├── requirements.txt   # Python dependencies
├── README.md          # Usage documentation
└── tests/             # Unit tests
    ├── conftest.py    # Test fixtures
    ├── test_metrics.py # Metrics module tests
    └── test_model.py  # Server tests
```

## Key Files

### `model.py` (Main Server)

FastAPI server implementation using Ultralytics YOLO with TensorRT.

**Classes:**

| Class               | Description                                                          |
| ------------------- | -------------------------------------------------------------------- |
| `BoundingBox`       | Pydantic model: x, y, width, height                                  |
| `Detection`         | Single detection: class_name, confidence, bbox                       |
| `DetectionResponse` | Response: detections[], inference_time_ms, dimensions                |
| `HealthResponse`    | Health: status, model_loaded, device, vram_used_gb, tensorrt_enabled |
| `YOLO26Model`       | Model wrapper with load_model(), detect(), detect_batch()            |

**Key Functions in YOLO26Model:**

```python
def load_model(self) -> None:
    """Load TensorRT engine via Ultralytics YOLO"""

def detect(self, image: Image.Image) -> tuple[list[dict], float]:
    """Single image detection, returns (detections, inference_time_ms)"""

def detect_batch(self, images: list[Image.Image]) -> tuple[list[list[dict]], float]:
    """Sequential batch detection"""

def _warmup(self, num_iterations: int = 3) -> None:
    """Runs 3 warmup iterations on startup"""
```

**Constants:**

```python
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
```

**Security Features:**

- Image magic bytes validation (prevents non-image uploads)
- Path traversal protection
- Size limits enforced
- Only security-relevant classes returned

### `Dockerfile`

Container build configuration:

- **Base image**: `nvcr.io/nvidia/tensorrt:24.09-py3`
- **Non-root user**: `yolo26` for security
- **Health check**: 60s start period for model loading
- **Model path**: `/models/yolo26/exports/yolo26m_fp16.engine`

### `requirements.txt`

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
ultralytics>=8.4.0
torch>=2.0.0
torchvision>=0.15.0
pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.26.0
pydantic>=2.4.0
nvidia-ml-py>=12.560.30
prometheus-client>=0.21.0
```

## API Endpoints

### GET /health

Returns server health status.

```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "model_name": "/models/yolo26/exports/yolo26m_fp16.engine",
  "vram_used_gb": 1.8,
  "tensorrt_enabled": true
}
```

### GET /metrics

Prometheus metrics endpoint for monitoring.

### POST /detect

Single image detection. Accepts multipart file upload or JSON with base64.

**Request (file upload):**

```bash
curl -X POST http://localhost:8095/detect \
  -F "file=@image.jpg"
```

**Request (base64):**

```json
{ "image_base64": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": { "x": 100, "y": 150, "width": 200, "height": 400 }
    }
  ],
  "inference_time_ms": 15.2,
  "image_width": 1920,
  "image_height": 1080
}
```

### POST /detect/batch

Batch detection for multiple files.

**Request:**

```bash
curl -X POST http://localhost:8095/detect/batch \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg"
```

**Response:**

```json
{
  "results": [
    {"index": 0, "filename": "image1.jpg", "detections": [...], ...},
    {"index": 1, "filename": "image2.jpg", "detections": [...], ...}
  ],
  "total_inference_time_ms": 30.5,
  "num_images": 2
}
```

## Environment Variables

| Variable                       | Default                                      | Description                                        |
| ------------------------------ | -------------------------------------------- | -------------------------------------------------- |
| `YOLO26_MODEL_PATH`            | `/models/yolo26/exports/yolo26m_fp16.engine` | TensorRT engine path                               |
| `YOLO26_CONFIDENCE`            | `0.5`                                        | Min confidence threshold                           |
| `YOLO26_CACHE_CLEAR_FREQUENCY` | `1`                                          | Clear CUDA cache every N detections (0 to disable) |
| `HOST`                         | `0.0.0.0`                                    | Bind address                                       |
| `PORT`                         | `8095`                                       | Server port                                        |

## Inference Pipeline

1. Load image via PIL
2. Validate image magic bytes (security check)
3. Convert to RGB if needed
4. Run inference with Ultralytics YOLO (TensorRT engine)
5. Filter by confidence threshold (0.5)
6. Filter to security-relevant classes only (9 classes)
7. Convert bounding boxes to x, y, width, height format
8. Return detections

## Backend Integration

Called by `backend/services/detector_client.py` when DETECTOR_TYPE is set to "yolo26":

```python
from backend.services.detector_client import DetectorClient

client = DetectorClient()  # Will use YOLO26 if configured
detections = await client.detect_objects(
    image_path="/export/foscam/front_door/image.jpg",
    camera_id="front_door",
    session=db_session
)
```

## Starting the Server

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-detector-yolo26
```

### Native (Development)

```bash
cd ai/yolo26 && python model.py
```

## TensorRT Engine

The YOLO26m TensorRT engine should be pre-exported and mounted at:
`/export/ai_models/model-zoo/yolo26/exports/yolo26m_fp16.engine`

To export a new engine (requires matching TensorRT version):

```bash
from ultralytics import YOLO
model = YOLO("yolo26m.pt")
model.export(format="engine", half=True)
```

## Prometheus Metrics

All metrics are defined in `metrics.py` and follow Prometheus naming conventions.

### Core Metrics (NEM-3700)

| Metric                              | Type      | Labels          | Description                       |
| ----------------------------------- | --------- | --------------- | --------------------------------- |
| `yolo26_inference_duration_seconds` | Histogram | endpoint        | Inference duration (p50/p90/p95)  |
| `yolo26_requests_total`             | Counter   | endpoint,status | Total requests by endpoint/status |
| `yolo26_detections_total`           | Counter   | class_name      | Detections by object class        |
| `yolo26_vram_bytes`                 | Gauge     | -               | VRAM usage in bytes               |
| `yolo26_errors_total`               | Counter   | error_type      | Errors by type                    |
| `yolo26_batch_size`                 | Histogram | -               | Batch size distribution           |

### Legacy Metrics (backwards compatibility)

| Metric                             | Type      | Description              |
| ---------------------------------- | --------- | ------------------------ |
| `yolo26_inference_requests_total`  | Counter   | Total inference requests |
| `yolo26_inference_latency_seconds` | Histogram | Inference latency        |
| `yolo26_detections_per_image`      | Histogram | Detections per image     |
| `yolo26_model_loaded`              | Gauge     | Model load status (0/1)  |
| `yolo26_gpu_utilization_percent`   | Gauge     | GPU utilization          |
| `yolo26_gpu_memory_used_gb`        | Gauge     | GPU memory used (GB)     |
| `yolo26_gpu_temperature_celsius`   | Gauge     | GPU temperature          |
| `yolo26_gpu_power_watts`           | Gauge     | GPU power usage          |

### Metrics Helper Functions

```python
from metrics import record_inference, record_detection, record_error

# After successful inference:
record_inference(endpoint="detect", duration_seconds=0.045, success=True)

# Record detections:
record_detections([{"class": "person"}, {"class": "car"}])

# On error:
record_error(error_type="invalid_image")
```

### Grafana Dashboard

The AI Services dashboard (`monitoring/grafana/dashboards/ai-services.json`) provides:

- YOLO26 overview (model status, latency, request rate, VRAM, errors)
- Inference latency percentiles (p50, p90, p95, p99)
- Request rate by endpoint and status
- Detections by class (stacked area chart)
- Error breakdown by type
- Batch size distribution
- GPU metrics (utilization, temperature, power)

## Entry Points

1. **Main server**: `model.py` - Start here for understanding the API
2. **Backend client**: `backend/services/detector_client.py` - For production integration
