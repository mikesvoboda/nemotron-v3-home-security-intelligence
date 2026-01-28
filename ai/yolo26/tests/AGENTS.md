# YOLO26 Tests

## Purpose

Unit tests for the YOLO26 inference server, covering the FastAPI-based object detection service with TensorRT acceleration, Prometheus metrics, pose estimation, and instance segmentation.

## Directory Structure

```
ai/yolo26/tests/
├── AGENTS.md                 # This file
├── __init__.py               # Package marker
├── conftest.py               # Shared pytest fixtures
├── test_metrics.py           # Prometheus metrics tests
├── test_model.py             # Core detection model tests
├── test_pose_estimation.py   # Pose estimation and behavior detection tests
└── test_segmentation.py      # Instance segmentation tests
```

## Key Files

### conftest.py

Shared pytest fixtures for YOLO26 tests.

| Fixture                 | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `dummy_image`           | Random PIL Image (480x640) for testing            |
| `dummy_image_bytes`     | JPEG bytes of dummy image                         |
| `dummy_image_base64`    | Base64-encoded dummy image                        |
| `mock_yolo_model`       | Mock YOLO model returning single person detection |
| `mock_empty_yolo_model` | Mock YOLO model returning no detections           |

### test_metrics.py

Tests for Prometheus metrics instrumentation (monitoring/observability).

| Test Class                   | Purpose                                     |
| ---------------------------- | ------------------------------------------- |
| `TestMetricsDefinition`      | Verify metrics exist with correct types     |
| `TestMetricsRecording`       | Test recording values to metrics            |
| `TestMetricsHelperFunctions` | Test helper functions for metrics recording |
| `TestMetricsExport`          | Test Prometheus export format               |
| `TestBackwardsCompatibility` | Ensure legacy metric names still work       |

Metrics tested:

- `yolo26_inference_duration_seconds` (histogram)
- `yolo26_requests_total` (counter)
- `yolo26_detections_total` (counter by class)
- `yolo26_vram_bytes` (gauge)
- `yolo26_errors_total` (counter)
- `yolo26_batch_size` (histogram)

### test_model.py

Comprehensive tests for the YOLO26Model class and FastAPI endpoints.

| Test Class                               | Purpose                                        |
| ---------------------------------------- | ---------------------------------------------- |
| `TestBoundingBox`                        | BoundingBox Pydantic model                     |
| `TestDetection`                          | Detection schema with class alias              |
| `TestDetectionResponse`                  | Full detection response format                 |
| `TestYOLO26Model`                        | Model initialization, detect, batch detect     |
| `TestAPIEndpoints`                       | /health, /detect, /detect/batch endpoints      |
| `TestSizeLimits`                         | DoS protection (10MB max file size)            |
| `TestInvalidImageHandling`               | Corrupted/invalid image error handling         |
| `TestMagicByteValidation`                | File format detection via magic bytes          |
| `TestFileExtensionValidation`            | Supported image extension validation           |
| `TestHealthResponse`                     | Health check response with GPU metrics         |
| `TestGetGpuMetrics`                      | pynvml GPU metrics collection                  |
| `TestTensorRTVersionUtilities`           | TensorRT version mismatch detection (NEM-3871) |
| `TestYOLO26ModelTensorRTVersionHandling` | Auto-rebuild on version mismatch               |
| `TestInferenceHealthCheck`               | Warmup validation (NEM-3877, NEM-3878)         |
| `TestTensorRTFallback`                   | Fallback to PyTorch on TensorRT failure        |
| `TestModelInferenceHealthyMetric`        | MODEL_INFERENCE_HEALTHY metric                 |

### test_pose_estimation.py

Tests for pose estimation with fall/aggression/loitering detection (NEM-3910).

| Test Class                | Purpose                                        |
| ------------------------- | ---------------------------------------------- |
| `TestPoseSchemas`         | Keypoint, PoseDetection, BehaviorFlags schemas |
| `TestFallDetection`       | Fall detection logic from keypoint positions   |
| `TestAggressionDetection` | Raised arms and rapid movement detection       |
| `TestLoiteringDetection`  | Stationary person tracking over time           |
| `TestPoseClassification`  | Pose class determination (standing, crouching) |
| `TestYOLO26PoseModel`     | YOLO26PoseModel wrapper class                  |
| `TestPoseAPIEndpoints`    | /pose/health, /pose/detect, /pose/analyze      |
| `TestPoseMetrics`         | Pose-specific Prometheus metrics               |
| `TestEdgeCases`           | Empty/partial keypoints, multi-frame tracking  |

Keypoint fixtures:

- `standing_keypoints` - Normal upright pose
- `fallen_keypoints` - Person lying horizontal
- `aggressive_keypoints` - Arms raised above head
- `crouching_keypoints` - Compressed torso posture

### test_segmentation.py

Tests for instance segmentation support (NEM-3912).

| Test Class                    | Purpose                                      |
| ----------------------------- | -------------------------------------------- |
| `TestSegmentationResponse`    | SegmentationDetection and response schemas   |
| `TestYOLO26ModelSegmentation` | segment() method and mask handling           |
| `TestSegmentationEndpoint`    | /segment FastAPI endpoint                    |
| `TestMaskEncoding`            | RLE encoding/decoding and polygon conversion |

Segmentation fixtures:

- `mock_yolo_segmentation_model` - Mock with mask data
- `mock_empty_yolo_segmentation_model` - Mock with no masks

## Running Tests

```bash
# Run all YOLO26 tests
cd ai/yolo26 && python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_model.py -v

# Run specific test class
python -m pytest tests/test_model.py::TestYOLO26Model -v

# Run with coverage
python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Run tests matching pattern
python -m pytest tests/ -v -k "tensorrt"
```

## Test Patterns

### Mocking YOLO Models

Tests mock the Ultralytics YOLO model to avoid GPU dependencies:

```python
@pytest.fixture
def mock_yolo_model():
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_boxes = MagicMock()

    # Mock detection
    mock_box = MagicMock()
    mock_box.cls.item.return_value = 0  # person
    mock_box.conf.item.return_value = 0.95
    mock_box.xyxy = [MagicMock(tolist=lambda: [100, 150, 300, 550])]

    mock_boxes.__iter__.return_value = iter([mock_box])
    mock_result.boxes = mock_boxes
    mock_model.predict.return_value = [mock_result]

    return mock_model
```

### Testing API Endpoints

Uses FastAPI's TestClient with mocked model instance:

```python
@pytest.fixture(autouse=True)
def mock_model(self):
    mock_instance = MagicMock()
    mock_instance.detect.return_value = ([...], 45.2)
    model_module.model = mock_instance
    yield mock_instance
```

### Security Class Filtering

Tests verify only security-relevant COCO classes are returned:

- person (0), car (2), truck (7), dog (16), cat (15), bird (14)
- bicycle (1), motorcycle (3), bus (5)

## Entry Points

1. **Fixtures**: `conftest.py`
2. **Core tests**: `test_model.py`
3. **Metrics tests**: `test_metrics.py`
4. **Pose tests**: `test_pose_estimation.py`
5. **Segmentation tests**: `test_segmentation.py`

## Related Documentation

- Parent module: `ai/yolo26/AGENTS.md`
- Model implementation: `ai/yolo26/model.py`
- Metrics module: `ai/yolo26/metrics.py`
- Pose estimation: `ai/yolo26/pose_estimation.py`
