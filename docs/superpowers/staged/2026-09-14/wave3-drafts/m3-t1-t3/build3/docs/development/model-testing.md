# AI Model Testing Guide

## Overview

This guide covers testing strategies for AI model integrations in the enrichment service. The enrichment service manages multiple ML models with different priorities, VRAM requirements, and use cases. Testing these models requires specialized patterns for unit testing, integration testing, mocking, and benchmarking.

## Test Architecture

```
ai/enrichment/tests/
├── conftest.py              # Pytest configuration (adds ai/ to path)
├── test_model_manager.py    # OnDemandModelManager tests
├── test_pose_estimator.py   # PoseEstimator tests
├── test_threat_detector.py  # ThreatDetector tests
├── test_demographics.py     # Demographics model tests
├── test_person_reid.py      # Person re-identification tests
├── test_action_recognizer.py # Action recognition tests
└── fixtures/
    └── images/
        ├── person_standing.jpg
        ├── person_crouching.jpg
        ├── vehicle_car.jpg
        └── empty_scene.jpg
```

## Unit Testing Models

### Test Structure

Each model should have a corresponding test file that covers:

1. **Model initialization** - Constructor validation, path handling
2. **Model loading** - GPU/CPU selection, VRAM allocation
3. **Inference** - Output format, edge cases, error handling
4. **Model unloading** - Resource cleanup, CUDA cache clearing

### Testing Patterns

#### 1. Model Loading Tests

```python
import pytest
from unittest.mock import patch, MagicMock

from ai.enrichment.models.pose_estimator import PoseEstimator


def test_model_loads_successfully():
    """Test model loads without error."""
    with patch("ai.enrichment.models.pose_estimator.YOLO") as mock_yolo:
        mock_yolo.return_value = MagicMock()
        estimator = PoseEstimator("/models/yolov8n-pose.pt")
        estimator.load_model()

        assert estimator.model is not None
        mock_yolo.assert_called_once_with("/models/yolov8n-pose.pt")


def test_model_loads_on_gpu():
    """Test model uses GPU when available."""
    with (
        patch("ai.enrichment.models.pose_estimator.YOLO") as mock_yolo,
        patch("torch.cuda.is_available", return_value=True),
    ):
        mock_model = MagicMock()
        mock_yolo.return_value = mock_model

        estimator = PoseEstimator("/models/yolov8n-pose.pt", device="cuda:0")
        estimator.load_model()

        mock_model.to.assert_called_once_with("cuda:0")


def test_model_falls_back_to_cpu():
    """Test model falls back to CPU when CUDA unavailable."""
    with (
        patch("ai.enrichment.models.pose_estimator.YOLO") as mock_yolo,
        patch("torch.cuda.is_available", return_value=False),
    ):
        mock_yolo.return_value = MagicMock()

        estimator = PoseEstimator("/models/yolov8n-pose.pt", device="cuda:0")
        estimator.load_model()

        assert estimator.device == "cpu"


def test_model_path_validation():
    """Test path traversal prevention."""
    with pytest.raises(ValueError, match="path traversal"):
        PoseEstimator("../../../etc/passwd")
```

#### 2. Inference Tests

```python
import numpy as np
from PIL import Image
from unittest.mock import MagicMock, patch

from ai.enrichment.models.pose_estimator import PoseEstimator, PoseResult


@pytest.fixture
def mock_pose_estimator():
    """Create a PoseEstimator with mocked model."""
    with patch("ai.enrichment.models.pose_estimator.YOLO"):
        estimator = PoseEstimator("/models/yolov8n-pose.pt")
        estimator.model = MagicMock()
        return estimator


def test_pose_estimation_output_format(mock_pose_estimator):
    """Test output matches expected schema."""
    # Create mock inference result
    mock_keypoints = MagicMock()
    mock_keypoints.xy = [np.zeros((17, 2))]
    mock_keypoints.conf = [np.ones(17) * 0.9]

    mock_result = MagicMock()
    mock_result.keypoints = [mock_keypoints]

    mock_pose_estimator.model.return_value = [mock_result]

    test_image = Image.new("RGB", (640, 480))
    result = mock_pose_estimator.estimate_pose(test_image)

    assert isinstance(result, PoseResult)
    assert hasattr(result, "keypoints")
    assert hasattr(result, "pose_class")
    assert hasattr(result, "confidence")
    assert hasattr(result, "is_suspicious")
    assert len(result.keypoints) == 17  # COCO format


def test_handles_empty_image(mock_pose_estimator):
    """Test graceful handling of no detections."""
    mock_result = MagicMock()
    mock_result.keypoints = None
    mock_pose_estimator.model.return_value = [mock_result]

    empty_image = Image.new("RGB", (10, 10))
    result = mock_pose_estimator.estimate_pose(empty_image)

    assert result.pose_class == "unknown"
    assert result.confidence == 0.0
    assert result.is_suspicious is False


def test_handles_no_results(mock_pose_estimator):
    """Test graceful handling of empty results list."""
    mock_pose_estimator.model.return_value = []

    test_image = Image.new("RGB", (640, 480))
    result = mock_pose_estimator.estimate_pose(test_image)

    assert result.pose_class == "unknown"
    assert result.confidence == 0.0


def test_model_not_loaded_raises():
    """Test RuntimeError when model not loaded."""
    estimator = PoseEstimator.__new__(PoseEstimator)
    estimator.model = None

    with pytest.raises(RuntimeError, match="not loaded"):
        estimator.estimate_pose(Image.new("RGB", (100, 100)))
```

#### 3. VRAM Management Tests

```python
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from ai.enrichment.model_manager import (
    ModelConfig,
    ModelPriority,
    OnDemandModelManager,
)


def create_model_config(
    name: str,
    vram_mb: int,
    priority: ModelPriority = ModelPriority.MEDIUM,
) -> ModelConfig:
    """Create a model config with mock loader/unloader."""
    model = MagicMock(name=name)
    return ModelConfig(
        name=name,
        vram_mb=vram_mb,
        priority=priority,
        loader_fn=lambda: model,
        unloader_fn=lambda m: None,
    )


@pytest.mark.asyncio
async def test_vram_eviction():
    """Test LRU eviction works correctly."""
    manager = OnDemandModelManager(vram_budget_gb=2.0)  # 2048MB

    # Register models that together exceed budget
    manager.register_model(create_model_config("model_a", 1000))  # 1GB
    manager.register_model(create_model_config("model_b", 1000))  # 1GB
    manager.register_model(create_model_config("model_c", 1000))  # 1GB

    # Load first two models (2GB used, at budget)
    await manager.get_model("model_a")
    await asyncio.sleep(0.01)  # Ensure different timestamps
    await manager.get_model("model_b")

    # Loading third should evict model_a (oldest)
    await manager.get_model("model_c")

    assert "model_a" not in manager.loaded_models
    assert "model_b" in manager.loaded_models
    assert "model_c" in manager.loaded_models


@pytest.mark.asyncio
async def test_priority_respected_during_eviction():
    """Test CRITICAL models evicted last."""
    manager = OnDemandModelManager(vram_budget_gb=1.5)  # 1536MB

    # Register models with different priorities
    manager.register_model(
        create_model_config("threat_detector", 400, ModelPriority.CRITICAL)
    )
    manager.register_model(
        create_model_config("depth_estimator", 150, ModelPriority.LOW)
    )
    manager.register_model(
        create_model_config("action_recognizer", 1000, ModelPriority.LOW)
    )

    # Load CRITICAL model first
    await manager.get_model("threat_detector")
    await asyncio.sleep(0.01)
    await manager.get_model("depth_estimator")

    # Loading large model should evict LOW priority, not CRITICAL
    await manager.get_model("action_recognizer")

    # CRITICAL model should be preserved
    assert "threat_detector" in manager.loaded_models
    assert "depth_estimator" not in manager.loaded_models
    assert "action_recognizer" in manager.loaded_models


@pytest.mark.asyncio
async def test_vram_usage_tracking():
    """Test VRAM usage is tracked correctly."""
    manager = OnDemandModelManager(vram_budget_gb=4.0)

    manager.register_model(create_model_config("model_a", 500))
    manager.register_model(create_model_config("model_b", 300))

    assert manager._current_vram_usage() == 0

    await manager.get_model("model_a")
    assert manager._current_vram_usage() == 500

    await manager.get_model("model_b")
    assert manager._current_vram_usage() == 800


@pytest.mark.asyncio
async def test_cuda_cache_cleared_on_unload():
    """Test CUDA cache is cleared when unloading models."""
    manager = OnDemandModelManager(vram_budget_gb=1.0)
    manager.register_model(create_model_config("test_model", 500))

    await manager.get_model("test_model")

    with (
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.empty_cache") as mock_empty_cache,
    ):
        await manager.unload_model("test_model")
        mock_empty_cache.assert_called_once()
```

#### 4. Threat Detection Tests

```python
import numpy as np
from PIL import Image
from unittest.mock import MagicMock, patch

import pytest

from ai.enrichment.models.threat_detector import (
    ThreatDetector,
    ThreatResult,
    ThreatDetection,
)


@pytest.fixture
def mock_threat_detector():
    """Create a ThreatDetector with mocked model."""
    with patch("ai.enrichment.models.threat_detector.YOLO"):
        detector = ThreatDetector("/models/weapon-detection.pt")
        detector.model = MagicMock()
        detector._class_names = {0: "knife", 1: "gun", 2: "rifle"}
        return detector


def test_threat_detection_output_format(mock_threat_detector):
    """Test threat detection returns correct format."""
    # Mock a gun detection with 95% confidence
    mock_box = MagicMock()
    mock_box.conf = [0.95]
    mock_box.cls = [1]  # gun
    mock_box.xyxy = [np.array([100, 100, 200, 200])]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]
    mock_threat_detector.model.return_value = [mock_result]

    test_image = Image.new("RGB", (640, 480))
    result = mock_threat_detector.detect_threats(test_image)

    assert isinstance(result, ThreatResult)
    assert result.has_threat is True
    assert result.max_severity == "critical"
    assert len(result.threats) == 1
    assert result.threats[0].threat_type == "gun"
    assert result.threats[0].confidence == 0.95


def test_no_threat_detected(mock_threat_detector):
    """Test clean result when no threats found."""
    mock_result = MagicMock()
    mock_result.boxes = None
    mock_threat_detector.model.return_value = [mock_result]

    test_image = Image.new("RGB", (640, 480))
    result = mock_threat_detector.detect_threats(test_image)

    assert result.has_threat is False
    assert result.max_severity == "none"
    assert len(result.threats) == 0


def test_confidence_threshold_filtering(mock_threat_detector):
    """Test low-confidence detections are filtered out."""
    mock_threat_detector.confidence_threshold = 0.5

    # Mock detection below threshold
    mock_box = MagicMock()
    mock_box.conf = [0.3]  # Below 0.5 threshold
    mock_box.cls = [1]
    mock_box.xyxy = [np.array([100, 100, 200, 200])]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]
    mock_threat_detector.model.return_value = [mock_result]

    result = mock_threat_detector.detect_threats(Image.new("RGB", (640, 480)))

    assert result.has_threat is False
    assert len(result.threats) == 0


def test_severity_levels():
    """Test severity classification for different threat types."""
    from ai.enrichment.models.threat_detector import THREAT_CLASSES_BY_NAME

    assert THREAT_CLASSES_BY_NAME["gun"] == "critical"
    assert THREAT_CLASSES_BY_NAME["rifle"] == "critical"
    assert THREAT_CLASSES_BY_NAME["knife"] == "high"
    assert THREAT_CLASSES_BY_NAME["bat"] == "medium"
```

## Integration Testing

### Testing the Enrichment Service

Integration tests verify that the enrichment service correctly coordinates model loading, inference, and response formatting.

```bash
# Start ai-enrichment service in test mode
podman-compose -f docker-compose.test.yml up ai-enrichment -d

# Run integration tests
pytest backend/tests/integration/test_enrichment_client.py -v
```

### Testing the Unified Endpoint

```python
import pytest
from unittest.mock import AsyncMock, patch

from backend.services.enrichment_client import EnrichmentClient


@pytest.fixture
def mock_enrichment_client():
    """Create EnrichmentClient with mocked HTTP client."""
    client = EnrichmentClient("http://localhost:8094")
    return client


@pytest.mark.asyncio
async def test_enrich_person_detection(mock_enrichment_client):
    """Test enrichment for person detection."""
    mock_response = {
        "pose": {
            "pose_class": "standing",
            "confidence": 0.85,
            "is_suspicious": False,
        },
        "clothing": {
            "upper_color": "blue",
            "lower_color": "black",
        },
    }

    with patch.object(
        mock_enrichment_client,
        "_post",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await mock_enrichment_client.enrich_detection(
            image=b"fake_image_bytes",
            detection_type="person",
            bbox=(100, 100, 300, 400),
        )

        assert result["pose"]["pose_class"] == "standing"
        assert result["clothing"]["upper_color"] == "blue"


@pytest.mark.asyncio
async def test_enrichment_handles_timeout():
    """Test graceful handling of service timeout."""
    client = EnrichmentClient("http://localhost:8094", timeout=0.001)

    with pytest.raises(TimeoutError):
        await client.enrich_detection(
            image=b"fake_image_bytes",
            detection_type="person",
            bbox=(100, 100, 300, 400),
        )
```

## Test Fixtures

### Test Images

Store test images in `ai/enrichment/tests/fixtures/images/`:

| File                   | Description              | Use Case               |
| ---------------------- | ------------------------ | ---------------------- |
| `person_standing.jpg`  | Normal standing person   | Baseline pose test     |
| `person_crouching.jpg` | Crouching person         | Suspicious pose test   |
| `person_reaching.jpg`  | Person reaching up       | Suspicious pose test   |
| `vehicle_car.jpg`      | Standard car             | Vehicle classification |
| `vehicle_truck.jpg`    | Pickup truck             | Vehicle classification |
| `weapon_knife.jpg`     | Visible knife            | Threat detection test  |
| `empty_scene.jpg`      | No detections            | Edge case testing      |
| `low_light.jpg`        | Dark/poorly lit scene    | Edge case testing      |
| `occluded_person.jpg`  | Partially visible person | Edge case testing      |

### Creating Test Images Programmatically

```python
import numpy as np
from PIL import Image

@pytest.fixture
def random_test_image():
    """Generate a random test image."""
    return Image.fromarray(
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    )


@pytest.fixture
def solid_color_image():
    """Generate a solid color test image."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))
```

### Mocking Models

For unit tests that don't need real inference:

```python
import pytest
from unittest.mock import MagicMock

from ai.enrichment.models.pose_estimator import PoseEstimator, PoseResult, Keypoint


@pytest.fixture
def mock_pose_estimator(mocker):
    """Create a fully mocked PoseEstimator."""
    mock = mocker.MagicMock(spec=PoseEstimator)
    mock.estimate_pose.return_value = PoseResult(
        keypoints=[
            Keypoint(name="nose", x=320.0, y=100.0, confidence=0.95),
            Keypoint(name="left_shoulder", x=280.0, y=150.0, confidence=0.92),
            Keypoint(name="right_shoulder", x=360.0, y=150.0, confidence=0.91),
            # ... remaining keypoints
        ],
        pose_class="standing",
        confidence=0.93,
        is_suspicious=False,
    )
    return mock


@pytest.fixture
def mock_threat_detector(mocker):
    """Create a fully mocked ThreatDetector."""
    from ai.enrichment.models.threat_detector import ThreatDetector, ThreatResult

    mock = mocker.MagicMock(spec=ThreatDetector)
    mock.detect_threats.return_value = ThreatResult(
        threats=[],
        has_threat=False,
        max_severity="none",
        inference_time_ms=45.2,
    )
    return mock


@pytest.fixture
def mock_model_manager(mocker):
    """Create a mocked OnDemandModelManager."""
    from ai.enrichment.model_manager import OnDemandModelManager

    mock = mocker.MagicMock(spec=OnDemandModelManager)
    mock.get_model = mocker.AsyncMock(return_value=MagicMock())
    mock.is_loaded.return_value = True
    mock.get_status.return_value = {
        "vram_budget_mb": 6963.2,
        "vram_used_mb": 1200,
        "loaded_models": ["pose_estimator", "threat_detector"],
    }
    return mock
```

## Running Tests

### Basic Commands

```bash
# Run all model tests
pytest ai/enrichment/tests/ -v

# Run specific test file
pytest ai/enrichment/tests/test_pose_estimator.py -v

# Run tests matching pattern
pytest ai/enrichment/tests/ -k "pose" -v

# Run tests with markers
pytest ai/enrichment/tests/ -m "not slow" -v
```

### Coverage Commands

```bash
# Run with coverage report
pytest ai/enrichment/tests/ --cov=ai/enrichment --cov-report=html

# Generate terminal coverage report
pytest ai/enrichment/tests/ --cov=ai/enrichment --cov-report=term-missing

# Check coverage threshold
pytest ai/enrichment/tests/ --cov=ai/enrichment --cov-fail-under=85
```

### Debug Commands

```bash
# Run with verbose output and no capture
pytest ai/enrichment/tests/ -v -s

# Run with pdb on failure
pytest ai/enrichment/tests/ --pdb

# Run single test with debug
pytest ai/enrichment/tests/test_pose_estimator.py::test_model_loads_successfully -v -s
```

## Benchmarking

### Performance Benchmarks

Create benchmark tests to measure model performance:

```python
# ai/enrichment/tests/benchmarks/test_model_benchmarks.py
import time
import statistics
from PIL import Image

import pytest


@pytest.mark.slow
@pytest.mark.benchmark
class TestModelBenchmarks:
    """Performance benchmarks for AI models."""

    def test_pose_estimator_inference_time(self, loaded_pose_estimator):
        """Benchmark pose estimation inference time."""
        test_image = Image.new("RGB", (640, 480))

        # Warm-up
        for _ in range(3):
            loaded_pose_estimator.estimate_pose(test_image)

        # Measure
        times = []
        for _ in range(50):
            start = time.perf_counter()
            loaded_pose_estimator.estimate_pose(test_image)
            times.append((time.perf_counter() - start) * 1000)

        avg_ms = statistics.mean(times)
        p95_ms = statistics.quantiles(times, n=20)[18]  # 95th percentile

        print(f"\nPose Estimator Inference:")
        print(f"  Average: {avg_ms:.1f}ms")
        print(f"  P95: {p95_ms:.1f}ms")

        # Assert performance bounds
        assert avg_ms < 100, f"Average inference too slow: {avg_ms}ms"
        assert p95_ms < 150, f"P95 inference too slow: {p95_ms}ms"


    def test_threat_detector_inference_time(self, loaded_threat_detector):
        """Benchmark threat detection inference time."""
        test_image = Image.new("RGB", (640, 480))

        # Warm-up
        for _ in range(3):
            loaded_threat_detector.detect_threats(test_image)

        # Measure
        times = []
        for _ in range(50):
            start = time.perf_counter()
            loaded_threat_detector.detect_threats(test_image)
            times.append((time.perf_counter() - start) * 1000)

        avg_ms = statistics.mean(times)
        p95_ms = statistics.quantiles(times, n=20)[18]

        print(f"\nThreat Detector Inference:")
        print(f"  Average: {avg_ms:.1f}ms")
        print(f"  P95: {p95_ms:.1f}ms")

        assert avg_ms < 80, f"Average inference too slow: {avg_ms}ms"
```

### Running Benchmarks

```bash
# Run benchmark tests
pytest ai/enrichment/tests/benchmarks/ -v -s --benchmark

# Run with detailed timing
pytest ai/enrichment/tests/benchmarks/ -v -s --durations=10
```

### Example Benchmark Output

```
Model Performance Benchmarks
============================
pose_estimator:
  Load time: 1.2s
  Inference: 45ms avg, 52ms p95
  VRAM: 312MB
  Throughput: 22 img/s

threat_detector:
  Load time: 0.8s
  Inference: 38ms avg, 45ms p95
  VRAM: 398MB
  Throughput: 26 img/s

model_manager:
  Load model_a + model_b: 2.1s
  Eviction (LRU): 15ms
  Status query: <1ms
```

## GPU Testing

### Detecting GPU Availability

```python
import pytest
import torch


def gpu_available():
    """Check if GPU is available for testing."""
    return torch.cuda.is_available()


@pytest.mark.skipif(not gpu_available(), reason="GPU not available")
@pytest.mark.gpu
def test_model_uses_gpu():
    """Test that model actually runs on GPU."""
    from ai.enrichment.models.pose_estimator import PoseEstimator

    estimator = PoseEstimator("/models/yolov8n-pose.pt", device="cuda:0")
    estimator.load_model()

    # Verify model is on GPU
    assert estimator.device == "cuda:0"

    estimator.unload()
```

### GPU Memory Monitoring

```python
@pytest.mark.gpu
def test_vram_cleanup():
    """Test VRAM is properly cleaned up after unload."""
    import torch

    initial_memory = torch.cuda.memory_allocated()

    # Load and unload model
    estimator = PoseEstimator("/models/yolov8n-pose.pt", device="cuda:0")
    estimator.load_model()
    loaded_memory = torch.cuda.memory_allocated()

    estimator.unload()
    torch.cuda.empty_cache()
    final_memory = torch.cuda.memory_allocated()

    # Memory should return close to initial
    assert final_memory < initial_memory + (10 * 1024 * 1024)  # 10MB tolerance
    assert loaded_memory > initial_memory  # Model was actually loaded
```

## Troubleshooting

### Common Test Failures

#### "Model not loaded" RuntimeError

**Cause:** Calling inference before `load_model()`.

**Fix:** Ensure fixtures properly load models or mock the model attribute.

```python
# Wrong
estimator = PoseEstimator("/models/pose.pt")
result = estimator.estimate_pose(image)  # Fails!

# Correct
estimator = PoseEstimator("/models/pose.pt")
estimator.load_model()
result = estimator.estimate_pose(image)
```

#### CUDA Out of Memory

**Cause:** Too many models loaded simultaneously.

**Fix:** Use fixtures that properly clean up, or reduce VRAM budget in tests.

```python
@pytest.fixture
def model_manager():
    manager = OnDemandModelManager(vram_budget_gb=0.5)  # Small budget for tests
    yield manager
    # Cleanup
    asyncio.run(manager.unload_all())
```

#### Slow Tests

**Cause:** Loading real models takes time.

**Fix:** Use mocks for unit tests, mark integration tests as `@pytest.mark.slow`.

```python
# Unit test - use mocks
@pytest.fixture
def mock_pose_estimator(mocker):
    return mocker.MagicMock(spec=PoseEstimator)

# Integration test - mark as slow
@pytest.mark.slow
def test_full_enrichment_pipeline():
    ...
```

#### Import Errors

**Cause:** `ai` module not in Python path.

**Fix:** Ensure `conftest.py` adds project root to path.

```python
# ai/enrichment/tests/conftest.py
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

## Related Documentation

- [Testing Guide](testing.md) - General testing guide
- [TDD Workflow](testing-workflow.md) - Test-driven development patterns
- [Code Quality](code-quality.md) - Quality tools and standards
- [ai/enrichment/AGENTS.md](../../ai/enrichment/AGENTS.md) - AI enrichment architecture
