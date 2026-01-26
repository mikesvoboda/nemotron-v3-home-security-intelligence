# YOLO26 Inference Server

HTTP server wrapping YOLO26m TensorRT object detection model for home security monitoring.

## Features

- FastAPI-based REST API
- CUDA/GPU acceleration with TensorRT optimization
- Ultralytics YOLO inference engine
- Batch processing support
- Filters to security-relevant classes only
- Prometheus metrics for monitoring

## Installation

```bash
pip install -r requirements.txt
```

## Model Setup

YOLO26 uses a pre-exported TensorRT engine for optimal inference speed. Configure the model path with `YOLO26_MODEL_PATH`:

- Default path: `/models/yolo26/exports/yolo26m_fp16.engine`
- Production path: `/export/ai_models/model-zoo/yolo26/exports/yolo26m_fp16.engine`

### Exporting TensorRT Engine

To export a new TensorRT engine (requires matching TensorRT version):

```python
from ultralytics import YOLO

# Load PyTorch model
model = YOLO("yolo26m.pt")

# Export to TensorRT FP16
model.export(format="engine", half=True)
```

## Running the Server

### Using Docker/Podman:

```bash
docker compose -f docker-compose.prod.yml up ai-detector-yolo26
```

### Direct execution:

```bash
cd ai/yolo26
python model.py
```

Server runs on: `http://localhost:8095`

## API Endpoints

### Health Check

```bash
GET /health
```

Response:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "vram_used_gb": 1.8,
  "tensorrt_enabled": true
}
```

### Prometheus Metrics

```bash
GET /metrics
```

Returns Prometheus-format metrics for monitoring inference performance.

### Single Image Detection

```bash
POST /detect
Content-Type: multipart/form-data

file: <image file>
```

Or with base64:

```bash
POST /detect
Content-Type: application/json

{
  "image_base64": "<base64 encoded image>"
}
```

Response:

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": {
        "x": 100,
        "y": 150,
        "width": 200,
        "height": 400
      }
    }
  ],
  "inference_time_ms": 15.2,
  "image_width": 1920,
  "image_height": 1080
}
```

### Batch Detection

```bash
POST /detect/batch
Content-Type: multipart/form-data

files: <image file 1>
files: <image file 2>
...
```

Response:

```json
{
  "results": [
    {
      "index": 0,
      "filename": "image1.jpg",
      "image_width": 1920,
      "image_height": 1080,
      "detections": [...]
    }
  ],
  "total_inference_time_ms": 30.5,
  "num_images": 2
}
```

## Detected Classes

The server filters detections to security-relevant classes only:

- person
- car
- truck
- dog
- cat
- bird
- bicycle
- motorcycle
- bus

## Configuration

Environment variables:

| Variable                       | Default                                      | Description                                        |
| ------------------------------ | -------------------------------------------- | -------------------------------------------------- |
| `YOLO26_MODEL_PATH`            | `/models/yolo26/exports/yolo26m_fp16.engine` | TensorRT engine path                               |
| `YOLO26_CONFIDENCE`            | `0.5`                                        | Min confidence threshold                           |
| `YOLO26_CACHE_CLEAR_FREQUENCY` | `1`                                          | Clear CUDA cache every N detections (0 to disable) |
| `HOST`                         | `0.0.0.0`                                    | Bind address                                       |
| `PORT`                         | `8095`                                       | Server port                                        |

## Performance

- Expected inference time: 10-20ms per image (on RTX A5500 with TensorRT)
- Expected VRAM usage: ~2GB
- Batch processing improves throughput for multiple images
- TensorRT provides 2-3x speedup over native PyTorch

## Comparison with RT-DETRv2

| Feature        | YOLO26 (TensorRT)        | RT-DETRv2 (HuggingFace)  |
| -------------- | ------------------------ | ------------------------ |
| Port           | 8095                     | 8090                     |
| Framework      | Ultralytics + TensorRT   | HuggingFace Transformers |
| Inference Time | 10-20ms                  | 30-50ms                  |
| VRAM Usage     | ~2GB                     | ~3GB                     |
| Model Size     | Smaller (FP16 optimized) | Larger                   |
| Accuracy       | Comparable               | Comparable               |

## Architecture

- **Model wrapper**: `YOLO26Model` class handles TensorRT inference
- **FastAPI app**: REST API with async endpoints
- **Preprocessing**: Handled internally by Ultralytics
- **Postprocessing**: Filters by confidence and class, formats bounding boxes
- **Warmup**: Runs 3 dummy inferences on startup to optimize GPU performance

## Integration

This server is called by the backend detection service:

```python
import httpx

async with httpx.AsyncClient() as client:
    files = {"file": open("camera_image.jpg", "rb")}
    response = await client.post("http://localhost:8095/detect", files=files)
    detections = response.json()["detections"]
```

## Prometheus Metrics

Available at `/metrics`:

- `yolo26_inference_requests_total` - Total requests by endpoint and status
- `yolo26_inference_latency_seconds` - Latency histogram
- `yolo26_detections_per_image` - Detection count histogram
- `yolo26_model_loaded` - Model status gauge (0/1)
- `yolo26_gpu_utilization_percent` - GPU utilization
- `yolo26_gpu_memory_used_gb` - GPU memory usage
- `yolo26_gpu_temperature_celsius` - GPU temperature
- `yolo26_gpu_power_watts` - GPU power consumption
