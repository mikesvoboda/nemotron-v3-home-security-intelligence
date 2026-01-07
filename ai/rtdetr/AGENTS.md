# RT-DETRv2 Object Detection Server

## Purpose

FastAPI-based HTTP server that wraps RT-DETRv2 object detection model for real-time security monitoring. Provides GPU-accelerated inference via HuggingFace Transformers, detecting security-relevant objects in camera images.

## Port and Resources

- **Port**: 8090
- **Expected VRAM**: ~650 MiB in production (model.py docstring says ~3GB, but actual usage is lower)
- **Inference Time**: 30-50ms per image on RTX A5500

## Directory Contents

```
ai/rtdetr/
├── AGENTS.md          # This file
├── __init__.py        # Package init (version 1.0.0)
├── Dockerfile         # Container build (PyTorch + CUDA 12.4)
├── model.py           # FastAPI inference server
├── example_client.py  # Python client example using httpx
├── test_model.py      # Unit tests (pytest)
├── requirements.txt   # Python dependencies
├── README.md          # Usage documentation
└── .gitkeep           # Git placeholder
```

## Key Files

### `model.py` (Main Server)

FastAPI server implementation using HuggingFace Transformers.

**Classes:**

| Class               | Description                                               |
| ------------------- | --------------------------------------------------------- |
| `BoundingBox`       | Pydantic model: x, y, width, height                       |
| `Detection`         | Single detection: class_name, confidence, bbox            |
| `DetectionResponse` | Response: detections[], inference_time_ms, dimensions     |
| `HealthResponse`    | Health: status, model_loaded, device, vram_used_gb        |
| `RTDETRv2Model`     | Model wrapper with load_model(), detect(), detect_batch() |

**Key Functions in RTDETRv2Model:**

```python
def load_model(self) -> None:
    """Load model via AutoModelForObjectDetection.from_pretrained()"""

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

- **Base image**: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`
- **Non-root user**: `rtdetr` for security
- **Health check**: 60s start period for model loading
- **HuggingFace cache**: `/cache/huggingface`

### `example_client.py`

Async HTTP client demonstrating API usage with httpx:

```python
async def check_health(base_url: str) -> dict
async def detect_from_file(image_path: str, base_url: str) -> dict
async def detect_from_base64(image_path: str, base_url: str) -> dict
async def detect_batch(image_paths: list[str], base_url: str) -> dict
def print_detections(result: dict) -> None
```

### `test_model.py`

Unit tests with pytest covering:

- Pydantic model validation (BoundingBox, Detection, DetectionResponse)
- API endpoint tests with mocked model
- Size limit validation tests
- Magic bytes validation tests
- Security validation (path traversal, malformed images)

### `requirements.txt`

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

## API Endpoints

### GET /health

Returns server health status.

```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "model_name": "/export/ai_models/rt-detrv2/rtdetr_v2_r101vd",
  "vram_used_gb": 0.65
}
```

### POST /detect

Single image detection. Accepts multipart file upload or JSON with base64.

**Request (file upload):**

```bash
curl -X POST http://localhost:8090/detect \
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
  "inference_time_ms": 45.2,
  "image_width": 1920,
  "image_height": 1080
}
```

### POST /detect/batch

Batch detection for multiple files.

**Request:**

```bash
curl -X POST http://localhost:8090/detect/batch \
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
  "total_inference_time_ms": 90.5,
  "num_images": 2
}
```

## Environment Variables

| Variable                       | Default                                        | Description                                        |
| ------------------------------ | ---------------------------------------------- | -------------------------------------------------- |
| `RTDETR_MODEL_PATH`            | `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` | HuggingFace model path                             |
| `RTDETR_CONFIDENCE`            | `0.5`                                          | Min confidence threshold                           |
| `RTDETR_CACHE_CLEAR_FREQUENCY` | `1`                                            | Clear CUDA cache every N detections (0 to disable) |
| `HOST`                         | `0.0.0.0`                                      | Bind address                                       |
| `PORT`                         | `8090`                                         | Server port                                        |
| `HF_HOME`                      | `/cache/huggingface`                           | HuggingFace cache dir                              |

## Inference Pipeline

1. Load image via PIL
2. Validate image magic bytes (security check)
3. Convert to RGB if needed
4. Preprocess with `AutoImageProcessor`
5. Run inference with `torch.no_grad()`
6. Postprocess with `post_process_object_detection()`
7. Filter by confidence threshold (0.5)
8. Filter to security-relevant classes only (9 classes)
9. Return detections with scaled bounding boxes

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

## Starting the Server

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-detector
```

### Native (Development)

```bash
./ai/start_detector.sh
# or
cd ai/rtdetr && python model.py
```

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_model.py -v

# Run example client (requires running server)
python example_client.py
```

## Entry Points

1. **Main server**: `model.py` - Start here for understanding the API
2. **Client example**: `example_client.py` - For integration patterns
3. **Tests**: `test_model.py` - For API contracts and validation
4. **Backend client**: `backend/services/detector_client.py` - For production integration
