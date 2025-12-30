# RT-DETRv2 Object Detection Server

## Purpose

FastAPI-based HTTP server that wraps RT-DETRv2 object detection model for real-time security monitoring. Provides GPU-accelerated inference via HuggingFace Transformers, detecting security-relevant objects in camera images.

## Production Deployment

In production, RT-DETRv2 runs in a Podman container (`ai-detector_1`) with NVIDIA GPU passthrough:

- **Container**: `nemotron-v3-home-security-intelligence_ai-detector_1`
- **Port**: 8090
- **GPU VRAM**: ~650 MiB

## Directory Contents

```
ai/rtdetr/
├── AGENTS.md          # This file
├── __init__.py        # Package init (version 1.0.0)
├── model.py           # FastAPI inference server (HuggingFace Transformers)
├── example_client.py  # Python client example using httpx
├── test_model.py      # Unit tests (pytest) - NOTE: some tests reference deprecated ONNX API
├── requirements.txt   # Python dependencies
├── README.md          # Usage documentation (some ONNX references outdated)
└── .gitkeep           # Git placeholder
```

## Key Files

### `model.py`

Main inference server implementation using HuggingFace Transformers:

**Classes:**

- `BoundingBox`: Pydantic model for bbox coordinates (x, y, width, height)
- `Detection`: Single detection with class_name, confidence, bbox
- `DetectionResponse`: Response with detections list, inference time, image dimensions
- `HealthResponse`: Health check with model status, device, VRAM usage
- `RTDETRv2Model`: HuggingFace Transformers model wrapper
  - `load_model()`: Loads model via `AutoModelForObjectDetection.from_pretrained()`
  - `detect()`: Single image detection, returns (detections, inference_time_ms)
  - `detect_batch()`: Sequential batch detection
  - `_warmup()`: Runs 3 warmup iterations on startup

**FastAPI Endpoints:**

- `GET /health`: Health check with GPU status
- `POST /detect`: Single image detection (file upload or base64)
- `POST /detect/batch`: Batch detection for multiple files

**Configuration (environment variables):**

- `RTDETR_MODEL_PATH`: HuggingFace model path (default: `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd`)
- `RTDETR_CONFIDENCE`: Minimum confidence threshold (default: 0.5)
- `HOST`: Server bind address (default: 0.0.0.0)
- `PORT`: Server port (default: 8090)

**Port**: 8090
**Expected VRAM**: ~3GB

### `example_client.py`

Async HTTP client demonstrating API usage with httpx:

- `check_health()`: Server health check
- `detect_from_file()`: Single image detection via file upload
- `detect_from_base64()`: Single image detection via base64
- `detect_batch()`: Batch detection for multiple images
- `print_detections()`: Pretty-print detection results

### `test_model.py`

Unit tests with pytest. **Note**: Some tests reference a deprecated ONNX-based API (`use_onnx=True`, `preprocess_image()`, `postprocess_detections()`) that no longer exists in `model.py`. These tests may need updating.

**Working tests:**

- Pydantic model tests (BoundingBox, Detection, DetectionResponse)
- API endpoint tests with mocked model

**Outdated tests:**

- `test_model_initialization` references `use_onnx` parameter
- `test_preprocess_image` references method that doesn't exist
- `test_postprocess_detections_onnx_format` references ONNX format

### `requirements.txt`

Python dependencies:

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
torch>=2.0.0
torchvision>=0.15.0
transformers>=4.35.0
pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0
pydantic>=2.4.0
python-dotenv>=1.0.0
pynvml>=11.5.0
```

### `__init__.py`

Package initialization: `__version__ = "1.0.0"`

## Model Information

### RT-DETRv2 (Real-Time Detection Transformer v2)

- **Framework**: HuggingFace Transformers (PyTorch)
- **Default Model**: `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd`
- **Input**: Any size RGB image (processor handles resizing)
- **Output**: Bounding boxes, class labels, confidence scores
- **Inference time**: 30-50ms per image on RTX A5500
- **VRAM**: ~3-4GB

### Security-Relevant Classes

Defined in `SECURITY_CLASSES` constant (9 classes):

```python
{"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}
```

All other COCO classes are filtered out.

## API Endpoints

### `GET /health`

```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "model_name": "/export/ai_models/rt-detrv2/rtdetr_v2_r101vd",
  "vram_used_gb": 3.2
}
```

### `POST /detect`

Accepts multipart file upload or JSON with base64.

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": { "x": 100, "y": 150, "width": 200, "height": 400 }
    }
  ],
  "inference_time_ms": 45.2,
  "image_width": 1920,
  "image_height": 1080
}
```

### `POST /detect/batch`

Accepts multiple files, returns results per image.

## Starting the Server

```bash
# Using startup script
./ai/start_detector.sh

# Direct execution
cd ai/rtdetr && python model.py
```

Server runs on: `http://0.0.0.0:8090`

## Inference Pipeline

1. Load image via PIL
2. Convert to RGB if needed
3. Preprocess with `AutoImageProcessor`
4. Run inference with `torch.no_grad()`
5. Postprocess with `post_process_object_detection()`
6. Filter by confidence threshold (0.5)
7. Filter to security-relevant classes only
8. Return detections with scaled bounding boxes

## Backend Integration

Called by `backend/services/detector_client.py`:

```python
from backend.services.detector_client import DetectorClient

client = DetectorClient()
detections = await client.detect_objects(
    image_path="/export/foscam/front_door/image.jpg",
    camera_id="front_door",
    session=db_session
)
```

## Testing

```bash
pip install -r requirements.txt
pytest test_model.py -v
python example_client.py  # requires running server
```

## Known Issues

1. **Test file outdated**: `test_model.py` references deprecated ONNX API methods that no longer exist in `model.py`
2. **README.md outdated**: References "ONNX Runtime" but code uses HuggingFace Transformers
3. **start_detector.sh**: References ONNX model path but code uses HuggingFace model path

## Entry Points

1. **Main server**: `model.py` - FastAPI app with HuggingFace Transformers
2. **Client example**: `example_client.py` - httpx-based async client
3. **Tests**: `test_model.py` - pytest unit tests (partially outdated)
4. **Startup**: `../start_detector.sh` - Shell script to launch server
