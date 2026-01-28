# Triton Client Tests

## Purpose

Unit tests for the Triton Inference Server client wrapper, which provides async object detection via remote NVIDIA Triton servers using gRPC or HTTP protocols.

## Directory Structure

```
ai/triton/tests/
├── AGENTS.md        # This file
├── __init__.py      # Package marker
├── conftest.py      # Shared pytest fixtures
└── test_client.py   # TritonClient unit tests
```

## Key Files

### conftest.py

Pytest fixtures for Triton client testing with mocked server connections.

| Fixture                    | Purpose                                         |
| -------------------------- | ----------------------------------------------- |
| `triton_config`            | Enabled TritonConfig with default settings      |
| `triton_config_disabled`   | Disabled TritonConfig                           |
| `sample_image_bytes`       | JPEG bytes (640x480 gray image)                 |
| `sample_image_array`       | NumPy array (480x640x3 random RGB)              |
| `mock_yolo26_outputs`      | Mock YOLO26 outputs (labels, boxes, scores)     |
| `mock_yolo_outputs`        | Alternative YOLO output format                  |
| `mock_grpc_client`         | Mock gRPC InferenceServerClient                 |
| `mock_http_client`         | Mock HTTP InferenceServerClient                 |
| `mock_triton_grpc_module`  | Mock tritonclient.grpc.aio module               |

### test_client.py

Comprehensive unit tests for the TritonClient wrapper class.

| Test Class                    | Purpose                                      |
| ----------------------------- | -------------------------------------------- |
| `TestTritonConfig`            | Configuration dataclass and from_env()       |
| `TestTritonClientInit`        | Client initialization and constants          |
| `TestTritonClientHealth`      | is_healthy(), is_model_ready() checks        |
| `TestTritonClientPreprocess`  | Image preprocessing (resize, normalize)      |
| `TestTritonClientPostprocess` | Detection postprocessing and filtering       |
| `TestTritonClientDetection`   | detect() method with retry logic             |
| `TestTritonClientBatch`       | detect_batch() for multiple images           |
| `TestTritonClientClose`       | Client cleanup and connection closing        |
| `TestDetectionDataClasses`    | BoundingBox, Detection, DetectionResult      |

## Test Coverage

### Configuration Tests

- Default configuration values
- Environment variable parsing (`TRITON_ENABLED`, `TRITON_URL`, etc.)
- Protocol selection (gRPC vs HTTP)

### Client Initialization

- Config injection
- Security classes definition (person, car, truck, dog, cat, etc.)
- COCO class ID to name mapping

### Health Checks

- Disabled client returns False
- Connection error handling
- Model readiness checks

### Image Preprocessing

- Bytes to tensor conversion
- NumPy array to tensor conversion
- Resize to 640x640
- Normalization to [0, 1] range
- Original size tracking

### Postprocessing

- YOLO26 output format (labels, boxes, scores arrays)
- YOLO output format (combined output0 array)
- Confidence threshold filtering
- Non-security class filtering
- Bounding box coordinate scaling

### Detection

- Auto-connect behavior
- Retry on transient failures (exponential backoff)
- Max retries exceeded error
- Custom confidence threshold

### Batch Detection

- Empty list handling
- Single image batch
- Multiple images batch

### Cleanup

- gRPC client close
- HTTP client close
- Connection state reset

## Running Tests

```bash
# Run all Triton tests
cd ai/triton && uv run pytest tests/ -v

# Run from project root
uv run pytest ai/triton/tests/ -v

# Run with async support
uv run pytest ai/triton/tests/ -v --asyncio-mode=auto

# Run specific test class
uv run pytest ai/triton/tests/test_client.py::TestTritonClientDetection -v

# Run with coverage
uv run pytest ai/triton/tests/ -v --cov=ai.triton --cov-report=term-missing
```

## Test Patterns

### Async Test Decorator

Tests use `@pytest.mark.asyncio` for async methods:

```python
@pytest.mark.asyncio
async def test_is_healthy_when_disabled(self, triton_config_disabled):
    client = TritonClient(triton_config_disabled)
    result = await client.is_healthy()
    assert result is False
```

### Mock Inference Outputs

YOLO26 format outputs for testing postprocessing:

```python
@pytest.fixture
def mock_yolo26_outputs():
    return {
        "labels": np.array([[0, 2, 16, ...]]),     # COCO class IDs
        "boxes": np.array([[[x1, y1, x2, y2], ...]]),  # Coordinates
        "scores": np.array([[0.95, 0.87, 0.72, ...]]), # Confidences
    }
```

### Retry Testing

Testing retry logic with controlled failure count:

```python
async def test_detect_retry_on_failure(self):
    call_count = 0

    async def mock_infer(*args):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient error")
        return {...}

    client._infer = mock_infer
    result = await client.detect(image)
    assert call_count == 3
```

## Environment Variables

Tests may be affected by these environment variables:

| Variable                       | Purpose                        |
| ------------------------------ | ------------------------------ |
| `TRITON_ENABLED`               | Enable Triton client           |
| `TRITON_URL`                   | gRPC server URL                |
| `TRITON_HTTP_URL`              | HTTP server URL                |
| `TRITON_PROTOCOL`              | 'grpc' or 'http'               |
| `TRITON_TIMEOUT`               | Request timeout in seconds     |
| `TRITON_MODEL`                 | Default model name             |
| `TRITON_MAX_RETRIES`           | Max retry attempts             |
| `TRITON_CONFIDENCE_THRESHOLD`  | Default confidence threshold   |
| `TRITON_VERBOSE`               | Enable verbose logging         |

## Entry Points

1. **Fixtures**: `conftest.py`
2. **Unit tests**: `test_client.py`
3. **Parent module**: `ai/triton/AGENTS.md`
4. **Client implementation**: `ai/triton/client.py`

## Notes

- Tests are designed to run without a Triton server (uses mocks)
- For integration tests requiring a running server, see `test_integration.py` (if exists)
- Security classes match YOLO26 server filtering for consistency
