# YOLO26 Detector Service Tests

Comprehensive unit tests for the YOLO26 inference server (`ai/yolo26/model.py`).

## Test Coverage

These tests provide comprehensive coverage of the YOLO26 detector service without requiring GPU hardware or actual model files. All tests use mocking to simulate the Ultralytics YOLO model behavior.

### Test Classes

| Test Class                    | Tests  | Description                                                  |
| ----------------------------- | ------ | ------------------------------------------------------------ |
| `TestBoundingBox`             | 1      | Pydantic model validation for bounding boxes                 |
| `TestDetection`               | 2      | Pydantic model validation for detections with alias support  |
| `TestDetectionResponse`       | 2      | Response model validation                                    |
| `TestYOLO26Model`             | 17     | Core model functionality, initialization, detection, caching |
| `TestAPIEndpoints`            | 9      | FastAPI endpoints (health, metrics, detect, batch)           |
| `TestSizeLimits`              | 6      | DoS prevention via file size limits                          |
| `TestInvalidImageHandling`    | 9      | Error handling for corrupt/invalid images                    |
| `TestMagicByteValidation`     | 11     | File signature validation                                    |
| `TestFileExtensionValidation` | 11     | File extension validation                                    |
| `TestHealthResponse`          | 3      | Health response model with GPU metrics                       |
| `TestGetGpuMetrics`           | 4      | GPU metrics collection via pynvml                            |
| **Total**                     | **77** | **Complete coverage of all service functionality**           |

## Key Features Tested

### Model Functionality

- Model initialization with configurable parameters
- CUDA cache clearing to prevent memory fragmentation
- Batch processing with configurable cache clear frequency
- Security class filtering (person, car, truck, dog, cat, etc.)
- RGBA to RGB image conversion
- TensorRT engine detection

### API Endpoints

- `GET /health` - Health check with GPU metrics
- `GET /metrics` - Prometheus metrics
- `POST /detect` - Single image detection (file upload or base64)
- `POST /detect/batch` - Batch image detection

### Security & Validation

- File size limits (10MB max to prevent DoS)
- Magic byte validation (detects non-image files)
- File extension validation
- Invalid/corrupted image handling (returns 400, not 500)
- Base64 encoding validation

### GPU Metrics

- VRAM usage tracking
- GPU utilization monitoring
- Temperature monitoring
- Power consumption tracking
- Graceful degradation when pynvml unavailable

## Running Tests

### From Project Root

```bash
# Run all YOLO26 tests
uv run pytest ai/yolo26/tests/test_model.py -v

# Run with coverage
uv run pytest ai/yolo26/tests/test_model.py --cov=ai/yolo26 --cov-report=term-missing

# Run specific test class
uv run pytest ai/yolo26/tests/test_model.py::TestYOLO26Model -v

# Run specific test
uv run pytest ai/yolo26/tests/test_model.py::TestYOLO26Model::test_cuda_cache_clearing_called -v
```

### From yolo26 Directory

```bash
cd ai/yolo26
uv run pytest tests/test_model.py -v
```

## Test Fixtures

Defined in `conftest.py`:

- `dummy_image` - Random 640x480 RGB PIL image
- `dummy_image_bytes` - JPEG-encoded image bytes
- `dummy_image_base64` - Base64-encoded image
- `mock_yolo_model` - Mock Ultralytics YOLO model with single person detection
- `mock_empty_yolo_model` - Mock model returning no detections

## Mock Strategy

All tests use `unittest.mock` to avoid requiring:

- GPU hardware
- CUDA/TensorRT installation
- Actual YOLO model files
- pynvml library for GPU metrics

This allows tests to run in CI environments without GPU access.

## Test Pattern

Tests follow the pattern used in `ai/rtdetr/test_model.py`:

1. **Unit tests for Pydantic models** - Validate request/response schemas
2. **Model class tests** - Test core detection logic with mocked YOLO
3. **API endpoint tests** - Use FastAPI TestClient with mocked models
4. **Security tests** - Validate input validation and error handling
5. **GPU metrics tests** - Mock pynvml to test metrics collection

## Coverage Requirements

These tests should maintain:

- Line coverage: 90%+
- Branch coverage: 85%+
- All API endpoints covered
- All error paths covered

## CI Integration

Tests are designed to run in CI without GPU:

- No GPU hardware required
- No model files required
- Fast execution (< 10 seconds)
- Parallel execution supported via pytest-xdist

## Adding New Tests

When adding new functionality to `model.py`:

1. Add unit tests for any new Pydantic models
2. Add model class tests for new detection logic
3. Add API endpoint tests for new routes
4. Add validation tests for new input types
5. Update fixtures in `conftest.py` as needed

Follow TDD principles:

1. Write failing test first
2. Implement minimal code to pass
3. Refactor with tests as safety net

## Related Documentation

- [YOLO26 Service Documentation](../README.md)
- [TDD Workflow Guide](../../../docs/development/testing-workflow.md)
- [Testing Patterns](../../../docs/developer/patterns/AGENTS.md)
