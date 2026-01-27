# YOLO26 Inference Server

HTTP server wrapping YOLO26m TensorRT object detection model for home security monitoring.

## Features

- FastAPI-based REST API
- CUDA/GPU acceleration with TensorRT optimization
- **INT8 and FP16 precision support** for optimal throughput/accuracy tradeoff
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

- **FP16 (default)**: `/models/yolo26/exports/yolo26m_fp16.engine`
- **INT8 (2x throughput)**: `/models/yolo26/exports/yolo26m_int8.engine`
- Production path: `/export/ai_models/model-zoo/yolo26/exports/`

### Precision Options

| Precision | Latency | VRAM   | Accuracy     | Use Case                      |
| --------- | ------- | ------ | ------------ | ----------------------------- |
| **FP16**  | 10-20ms | ~2GB   | Baseline     | Default, highest accuracy     |
| **INT8**  | 5-10ms  | ~1.5GB | <1% mAP drop | High throughput, multi-camera |

### Exporting TensorRT Engine

Use the export script for reproducible engine generation:

```bash
# Export FP16 engine (default, higher accuracy)
python ai/yolo26/export_tensorrt.py --model yolo26m.pt --output exports/

# Export INT8 engine (2x throughput, requires calibration)
python ai/yolo26/export_tensorrt.py \
    --model yolo26m.pt \
    --int8 \
    --data config/yolo26_calibration.yaml \
    --output exports/

# Export INT8 with video frame extraction for calibration
python ai/yolo26/export_tensorrt.py \
    --model yolo26m.pt \
    --int8 \
    --data config/yolo26_calibration.yaml \
    --extract-frames \
    --output exports/
```

### INT8 Calibration

INT8 quantization requires representative calibration images to determine optimal
quantization parameters. The calibration dataset should:

- Contain 100-500 images representative of deployment conditions
- Cover various lighting conditions, camera angles, and object types
- Include all security-relevant object classes (person, car, truck, etc.)

**Calibration Dataset Configuration** (`config/yolo26_calibration.yaml`):

```yaml
path: /path/to/calibration/images
train: .
val: .
names:
  0: person
  1: bicycle
  2: car
  # ... (see full config for all classes)
```

**Frame Extraction for Videos**:

If your calibration data includes videos, use `--extract-frames` to automatically
extract frames:

```bash
python ai/yolo26/export_tensorrt.py \
    --int8 \
    --data config/yolo26_calibration.yaml \
    --extract-frames
```

### Benchmarking and Validation

Compare FP16 vs INT8 performance:

```bash
# Benchmark inference latency
python ai/yolo26/export_tensorrt.py --benchmark exports/yolo26m_fp16.engine
python ai/yolo26/export_tensorrt.py --benchmark exports/yolo26m_int8.engine

# Validate accuracy (requires COCO-format dataset)
python ai/yolo26/export_tensorrt.py --validate exports/yolo26m_fp16.engine --data coco.yaml
python ai/yolo26/export_tensorrt.py --validate exports/yolo26m_int8.engine --data coco.yaml
```

### Legacy Export (Simple)

For quick exports without the script:

```python
from ultralytics import YOLO

# Load PyTorch model
model = YOLO("yolo26m.pt")

# Export to TensorRT FP16
model.export(format="engine", half=True)

# Export to TensorRT INT8 (requires calibration data)
model.export(format="engine", int8=True, data="config/yolo26_calibration.yaml")
```

## Running the Server

### Using Docker/Podman:

```bash
docker compose -f docker-compose.prod.yml up ai-yolo26
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
| `YOLO26_MODEL_PATH_INT8`       | (empty)                                      | INT8 engine path (alternative config)              |
| `YOLO26_CONFIDENCE`            | `0.5`                                        | Min confidence threshold                           |
| `YOLO26_CACHE_CLEAR_FREQUENCY` | `1`                                          | Clear CUDA cache every N detections (0 to disable) |
| `HOST`                         | `0.0.0.0`                                    | Bind address                                       |
| `PORT`                         | `8095`                                       | Server port                                        |

## Performance

- Expected inference time: 10-20ms per image (FP16 on RTX A5500 with TensorRT)
- Expected inference time: 5-10ms per image (INT8, 2x throughput)
- Expected VRAM usage: ~2GB (FP16), ~1.5GB (INT8)
- Batch processing improves throughput for multiple images
- TensorRT provides 2-3x speedup over native PyTorch

## Comparison with YOLO26v2

| Feature        | YOLO26 (TensorRT)        | YOLO26v2 (HuggingFace)   |
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
