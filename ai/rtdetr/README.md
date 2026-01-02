# RT-DETRv2 Inference Server

HTTP server wrapping RT-DETRv2 object detection model for home security monitoring.

## Features

- FastAPI-based REST API
- CUDA/GPU acceleration (RTX A5500)
- PyTorch + HuggingFace Transformers inference
- Batch processing support
- Filters to security-relevant classes only

## Installation

```bash
pip install -r requirements.txt
```

## Model Setup

RT-DETRv2 is loaded via HuggingFace Transformers. Configure the model source with `RTDETR_MODEL_PATH`:

- HuggingFace model id (default in `docker-compose.prod.yml`): `PekingU/rtdetr_r50vd_coco_o365`
- Or a local path to a compatible Transformers model directory

## Running the Server

### Using the startup script:

```bash
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
./ai/start_detector.sh
```

### Direct execution:

```bash
cd ai/rtdetr
python model.py
```

Server runs on: `http://localhost:8090`

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
  "vram_used_gb": 4.2
}
```

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
  "inference_time_ms": 45.2,
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
  "total_inference_time_ms": 90.5,
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

## Configuration

Environment variables or command-line arguments:

- `RTDETR_MODEL_PATH`: HuggingFace model id or local model directory
- `RTDETR_CONFIDENCE`: Minimum detection confidence (default: 0.5)
- `DEVICE`: Inference device (default: `cuda:0` if available, else `cpu`)
- `PORT`: Server port (default: 8090)

## Performance

- Expected inference time: 30-50ms per image (on RTX A5500)
- Expected VRAM usage: ~4GB
- Batch processing improves throughput for multiple images

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest test_model.py -v
```

## Architecture

- **Model wrapper**: `RTDETRv2Model` class handles inference
- **FastAPI app**: REST API with async endpoints
- **Preprocessing**: Resizes images to 640x640, normalizes to [0,1]
- **Postprocessing**: Filters by confidence and class, scales bounding boxes to original image size
- **Warmup**: Runs 5 dummy inferences on startup to optimize GPU performance

## Integration

This server is called by the backend detection service:

```python
import httpx

async with httpx.AsyncClient() as client:
    files = {"file": open("camera_image.jpg", "rb")}
    response = await client.post("http://localhost:8090/detect", files=files)
    detections = response.json()["detections"]
```
