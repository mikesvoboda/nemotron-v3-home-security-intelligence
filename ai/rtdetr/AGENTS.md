# RT-DETRv2 Object Detection Server

## Purpose

FastAPI-based HTTP server that wraps RT-DETRv2 object detection model for real-time security monitoring. Provides GPU-accelerated inference via ONNX Runtime, detecting security-relevant objects in camera images.

## Key Files

### `model.py` (634 lines)

Main inference server implementation:

- **RTDETRv2Model class**: ONNX/PyTorch model wrapper
  - Loads RT-DETRv2 ONNX model with CUDA acceleration
  - Preprocesses images (resize to 640x640, normalize to [0,1])
  - Runs inference with ONNX Runtime
  - Postprocesses outputs (filters by confidence and class)
  - Performs model warmup on startup (5 iterations)
- **FastAPI endpoints**: `/health`, `/detect`, `/detect/batch`
- **Pydantic models**: `Detection`, `DetectionResponse`, `BoundingBox`
- **Security filtering**: Only returns security-relevant object classes

**Port**: 8001
**Expected VRAM**: ~4GB

### `example_client.py` (187 lines)

Example HTTP client demonstrating API usage:

- `check_health()`: Server health check
- `detect_from_file()`: Single image detection via file upload
- `detect_from_base64()`: Single image detection via base64
- `detect_batch()`: Batch detection for multiple images
- `print_detections()`: Pretty-print detection results

### `test_model.py` (337 lines)

Comprehensive unit tests with pytest:

- **Pydantic model tests**: BoundingBox, Detection, DetectionResponse
- **RTDETRv2Model tests**:
  - Model initialization
  - Image preprocessing (RGB conversion, normalization)
  - Postprocessing (ONNX output format parsing)
  - Confidence filtering
  - Security class filtering
- **API endpoint tests**:
  - Health check
  - Single detection (file upload and base64)
  - Batch detection
  - Error handling (model not loaded, invalid input)

**Coverage**: ~95%

### `requirements.txt`

Python dependencies:

- **Web**: fastapi, uvicorn, python-multipart
- **Deep learning**: torch, torchvision, onnxruntime-gpu
- **Image processing**: pillow, opencv-python, numpy
- **Utilities**: pydantic, python-dotenv, pynvml

### `README.md`

Comprehensive documentation for RT-DETRv2 server (see file for full details)

### `__init__.py`

Package initialization with version: "1.0.0"

## Model Information

### RT-DETRv2 (Real-Time Detection Transformer v2)

- **Model**: PekingU/rtdetr_r50vd_coco_o365
- **Format**: ONNX (optimized for inference)
- **Input size**: 640x640 RGB
- **Output**: Bounding boxes, class labels, confidence scores
- **Inference time**: 30-50ms per image on RTX A5500
- **Training data**: COCO + Objects365

### Security-Relevant Classes

The server filters detections to these 8 classes:

- `person` - Human detection
- `car` - Passenger vehicle
- `truck` - Large vehicle
- `dog` - Canine
- `cat` - Feline
- `bird` - Avian
- `bicycle` - Bike
- `motorcycle` - Motorbike

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
  "vram_used_gb": 4.2
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
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
./ai/start_detector.sh
```

### Direct execution:

```bash
cd ai/rtdetr
python model.py
```

Server runs on: `http://0.0.0.0:8001`

## Configuration

Environment variables or defaults:

- `MODEL_PATH`: Path to ONNX model (default: `rtdetrv2_r50vd.onnx`)
- `CONFIDENCE_THRESHOLD`: Minimum detection confidence (default: 0.5)
- `DEVICE`: Inference device (default: `cuda:0` if available, else `cpu`)
- `PORT`: Server port (default: 8001)

## Implementation Patterns

### Preprocessing Pipeline

1. Convert image to RGB if needed (handles grayscale)
2. Resize to 640x640 using bilinear interpolation
3. Convert to numpy array (float32)
4. Normalize to [0, 1] range
5. Transpose to CHW format (channels, height, width)
6. Add batch dimension

### ONNX Runtime Inference

- Uses `CUDAExecutionProvider` for GPU acceleration
- Falls back to `CPUExecutionProvider` if CUDA unavailable
- Configures device_id from `device` parameter (e.g., "cuda:1" → device_id=1)

### Postprocessing Pipeline

1. Parse ONNX outputs: `[boxes, scores, labels]`
2. Filter by confidence threshold (default 0.5)
3. Map label indices to COCO class names
4. Filter to security-relevant classes only
5. Scale bounding boxes from 640x640 to original image size
6. Format as `{class, confidence, bbox}` dictionaries

### Model Warmup

On startup, runs 5 dummy inferences with random images to:

- Load model weights into GPU memory
- Compile CUDA kernels
- Optimize inference graph
- Ensure consistent performance from first real request

## Integration with Backend

Called by `backend/services/detector_client.py`:

```python
from backend.services.detector_client import DetectorClient

client = DetectorClient()  # Uses settings.rtdetr_url (http://localhost:8001)
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
- **VRAM usage**: ~4GB
- **Throughput**: ~20-30 images/second
- **Batch processing**: Improves throughput for multiple images
- **Warmup overhead**: ~1-2 seconds on startup

## Error Handling

- **Model not found**: Server starts but returns 503 on detection requests
- **Invalid image**: Returns 400 with error details
- **CUDA unavailable**: Falls back to CPU inference (slower)
- **Low confidence**: Detections filtered out (not returned)
- **Non-security classes**: Filtered out (not returned)
