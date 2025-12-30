# RT-DETRv2 Object Detection Server

## Purpose

FastAPI-based HTTP server that wraps RT-DETRv2 object detection model for real-time security monitoring. Provides GPU-accelerated inference via HuggingFace Transformers, detecting security-relevant objects in camera images.

## Key Files

### `model.py` (435 lines)

Main inference server implementation using HuggingFace Transformers:

- **RTDETRv2Model class**: HuggingFace Transformers model wrapper
  - Loads RT-DETRv2 using `AutoModelForObjectDetection` with CUDA acceleration
  - Uses `AutoImageProcessor` for image preprocessing
  - Default model: `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` (configurable via `RTDETR_MODEL_PATH`)
  - Preprocesses images (RGB conversion, normalization)
  - Runs inference with PyTorch on GPU
  - Postprocesses outputs using processor's `post_process_object_detection()`
  - Performs model warmup on startup (3 iterations with 640x480 gray images)
- **FastAPI endpoints**: `/health`, `/detect`, `/detect/batch`
- **Pydantic models**: `Detection`, `DetectionResponse`, `BoundingBox`, `HealthResponse`
- **Security filtering**: Only returns security-relevant object classes

**Port**: 8090 (configurable via PORT env var)
**Expected VRAM**: ~3GB

### `example_client.py` (187 lines)

Example HTTP client demonstrating API usage:

- `check_health()`: Server health check
- `detect_from_file()`: Single image detection via file upload
- `detect_from_base64()`: Single image detection via base64
- `detect_batch()`: Batch detection for multiple images
- `print_detections()`: Pretty-print detection results

### `test_model.py` (337 lines)

Unit tests with pytest:

- **Pydantic model tests**: BoundingBox, Detection, DetectionResponse
- **RTDETRv2Model tests**:
  - Model initialization
  - Image preprocessing (RGB conversion, normalization)
  - Postprocessing (output format parsing)
  - Confidence filtering
  - Security class filtering
- **API endpoint tests**:
  - Health check
  - Single detection (file upload and base64)
  - Batch detection
  - Error handling (model not loaded, invalid input)

### `requirements.txt`

Python dependencies:

- **Web**: fastapi>=0.104.0, uvicorn[standard]>=0.24.0, python-multipart>=0.0.6
- **Deep learning**: torch>=2.0.0, torchvision>=0.15.0, transformers>=4.35.0
- **Image processing**: pillow>=10.0.0, opencv-python>=4.8.0, numpy>=1.24.0
- **Utilities**: pydantic>=2.4.0, python-dotenv>=1.0.0
- **Monitoring**: pynvml>=11.5.0

### `README.md`

Comprehensive documentation for RT-DETRv2 server (see file for full details)

### `__init__.py`

Package initialization with version: "1.0.0"

## Model Information

### RT-DETRv2 (Real-Time Detection Transformer v2)

- **Default Model**: `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` (or any HuggingFace-compatible path)
- **Format**: PyTorch model loaded via HuggingFace Transformers
- **Input**: Any size RGB image (processor handles resizing)
- **Output**: Bounding boxes, class labels, confidence scores
- **Inference time**: 30-50ms per image on RTX A5500
- **Training data**: COCO + Objects365
- **Configuration**: Set `RTDETR_MODEL_PATH` environment variable to change model

### Security-Relevant Classes

The server filters detections to these 9 classes (defined in `SECURITY_CLASSES` constant):

- `person` - Human detection
- `car` - Passenger vehicle
- `truck` - Large vehicle
- `dog` - Canine
- `cat` - Feline
- `bird` - Avian
- `bicycle` - Bike
- `motorcycle` - Motorbike
- `bus` - Public transport vehicle

All other COCO classes (chairs, bottles, etc.) are filtered out.

## API Endpoints

### `GET /health`

Health check with GPU status.

**Response**:

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

Single image object detection.

**Request** (multipart/form-data):

```
file: <image file>
```

**Request** (JSON with base64):

```json
{
  "image_base64": "<base64 encoded image>"
}
```

**Response**:

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

### `POST /detect/batch`

Batch detection for multiple images.

**Request** (multipart/form-data):

```
files: <image file 1>
files: <image file 2>
...
```

**Response**:

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

## Starting the Server

### Using startup script:

```bash
cd /path/to/home_security_intelligence
./ai/start_detector.sh
```

### Direct execution:

```bash
cd ai/rtdetr
python model.py
```

Server runs on: `http://0.0.0.0:8090`

## Configuration

Environment variables with defaults:

| Variable            | Default                                        | Description                        |
| ------------------- | ---------------------------------------------- | ---------------------------------- |
| `RTDETR_MODEL_PATH` | `/export/ai_models/rt-detrv2/rtdetr_v2_r101vd` | HuggingFace model path             |
| `RTDETR_CONFIDENCE` | `0.5`                                          | Minimum detection confidence (0-1) |
| `HOST`              | `0.0.0.0`                                      | Server bind address                |
| `PORT`              | `8090`                                         | Server port                        |

**Note on host binding**: The server defaults to `0.0.0.0` to allow connections from Docker/Podman containers. When AI servers run natively on the host while the backend runs in containers, binding to `127.0.0.1` would prevent container-to-host connectivity.

## Important Patterns and Conventions

### Preprocessing Pipeline

1. Load image using PIL
2. Convert to RGB if not already (handles RGBA, grayscale, etc.)
3. Use `AutoImageProcessor.from_pretrained()` to preprocess
4. Processor handles resizing, normalization, tensor conversion
5. Move tensors to configured device (CUDA/CPU)

### PyTorch Inference

- Uses HuggingFace `AutoModelForObjectDetection`
- Loads model with `.to(device)` for GPU acceleration
- Inference runs in `torch.no_grad()` context for memory efficiency
- Falls back to CPU if CUDA unavailable

### Postprocessing Pipeline

1. Use processor's `post_process_object_detection()` for output parsing
2. Pass original image dimensions as `target_sizes` for correct bbox scaling
3. Filter by confidence threshold (default 0.5)
4. Map label indices to class names using `model.config.id2label`
5. Filter to security-relevant classes only (person, car, truck, dog, cat, bird, bicycle, motorcycle, bus)
6. Format as `{class, confidence, bbox}` dictionaries

### Model Warmup

On startup, runs 3 dummy inferences with gray 640x480 images to:

- Load model weights into GPU memory
- Compile CUDA kernels
- Optimize inference graph
- Ensure consistent performance from first real request

## Integration with Backend

Called by `backend/services/detector_client.py`:

```python
from backend.services.detector_client import DetectorClient

client = DetectorClient()  # Uses settings.rtdetr_url (http://localhost:8090)
detections = await client.detect_objects(
    image_path="/export/foscam/front_door/image.jpg",
    camera_id="front_door",
    session=db_session
)
# Returns list of Detection model instances stored in database
```

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_model.py -v

# Test with example client (requires running server)
python example_client.py
```

## Performance Characteristics

- **Inference time**: 30-50ms per image (RTX A5500)
- **VRAM usage**: ~3-4GB
- **Throughput**: ~20-30 images/second
- **Batch processing**: Currently sequential (room for optimization)
- **Warmup overhead**: ~1-2 seconds on startup (3 warmup iterations with 640x480 gray images)

## Error Handling

- **Model not found**: Server fails to start with error message (or starts in degraded mode)
- **Model load failure**: Returns 503 on detection requests until model loads
- **Invalid image**: Returns 400 with error details
- **CUDA unavailable**: Falls back to CPU inference (slower)
- **Low confidence**: Detections filtered out (not returned)
- **Non-security classes**: Filtered out (not returned)

## Entry Points for Understanding the Code

1. **Start here**: Read this file and `README.md`
2. **Main server**: `model.py` - FastAPI app with detection endpoints
3. **API testing**: `example_client.py` - Example client usage
4. **Unit tests**: `test_model.py` - Test coverage
5. **Dependencies**: `requirements.txt` - Required packages
