"""Unit tests for YOLO26 Object Detection Module.

Tests cover:
- Detection dataclass and constants
- YOLO26Result dataclass and methods
- Model path validation
- Detection pipeline
- Batch inference
- Confidence filtering
- Integration with model (mocked)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# Add the ai/enrichment directory to sys.path to enable imports
# This must happen before importing the local module
_enrichment_dir = Path(__file__).parent.parent
if str(_enrichment_dir) not in sys.path:
    sys.path.insert(0, str(_enrichment_dir))

from models.yolo26_detector import (
    COCO_CLASSES,
    YOLO26_DEFAULT_MODEL,
    YOLO26_MODEL_PATH_ENV,
    Detection,
    YOLO26Detector,
    YOLO26Result,
    validate_model_path,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_image() -> Image.Image:
    """Create a dummy PIL image for testing."""
    return Image.new("RGB", (640, 480), color="red")


@pytest.fixture
def dummy_numpy_image() -> np.ndarray:
    """Create a dummy numpy image for testing."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_detections() -> list[Detection]:
    """Create sample detections for testing."""
    return [
        Detection(
            class_name="person",
            class_id=0,
            confidence=0.95,
            bbox=[100.0, 50.0, 200.0, 300.0],
        ),
        Detection(
            class_name="car",
            class_id=2,
            confidence=0.87,
            bbox=[300.0, 200.0, 500.0, 350.0],
        ),
        Detection(
            class_name="dog",
            class_id=16,
            confidence=0.72,
            bbox=[50.0, 400.0, 150.0, 470.0],
        ),
    ]


def _create_mock_result_with_boxes():
    """Create a single mock result with detection boxes."""
    mock_box1 = MagicMock()
    mock_box1.conf = [MagicMock(__getitem__=lambda _self, _x: 0.95)]
    mock_box1.cls = [MagicMock(__getitem__=lambda _self, _x: 0)]
    mock_box1.xyxy = [MagicMock(tolist=lambda: [100.0, 50.0, 200.0, 300.0])]

    mock_box2 = MagicMock()
    mock_box2.conf = [MagicMock(__getitem__=lambda _self, _x: 0.87)]
    mock_box2.cls = [MagicMock(__getitem__=lambda _self, _x: 2)]
    mock_box2.xyxy = [MagicMock(tolist=lambda: [300.0, 200.0, 500.0, 350.0])]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box1, mock_box2]
    return mock_result


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model with detection results."""
    mock_model = MagicMock()

    # Create a side_effect that returns one result per input image
    def model_call_side_effect(images, **_kwargs):
        # If images is a list, return one result per image
        if isinstance(images, list):
            return [_create_mock_result_with_boxes() for _ in images]
        # Single image, return list with one result
        return [_create_mock_result_with_boxes()]

    mock_model.side_effect = model_call_side_effect
    mock_model.to = MagicMock(return_value=mock_model)
    mock_model.names = {0: "person", 1: "bicycle", 2: "car"}

    return mock_model


@pytest.fixture
def mock_yolo26_detector(mock_yolo_model):
    """Create a YOLO26Detector with mocked YOLO model."""
    with (
        patch("ultralytics.YOLO", return_value=mock_yolo_model),
        patch("torch.cuda.is_available", return_value=False),
    ):
        detector = YOLO26Detector("/fake/model.pt", device="cpu")
        detector.load_model()
        yield detector


# =============================================================================
# Tests for Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_coco_classes_count(self):
        """Test that COCO classes has 80 entries."""
        assert len(COCO_CLASSES) == 80

    def test_coco_classes_common_entries(self):
        """Test that common class names are present."""
        assert "person" in COCO_CLASSES
        assert "car" in COCO_CLASSES
        assert "dog" in COCO_CLASSES
        assert "cat" in COCO_CLASSES

    def test_default_model_path_env(self):
        """Test that the environment variable name is correct."""
        assert YOLO26_MODEL_PATH_ENV == "YOLO26_ENRICHMENT_MODEL_PATH"

    def test_default_model_name(self):
        """Test default model name is yolo26m.pt."""
        assert YOLO26_DEFAULT_MODEL == "yolo26m.pt"


# =============================================================================
# Tests for Detection Dataclass
# =============================================================================


class TestDetectionDataclass:
    """Tests for the Detection dataclass."""

    def test_detection_creation(self):
        """Test creating a Detection instance."""
        det = Detection(
            class_name="person",
            class_id=0,
            confidence=0.95,
            bbox=[100.0, 50.0, 200.0, 300.0],
        )
        assert det.class_name == "person"
        assert det.class_id == 0
        assert det.confidence == 0.95
        assert det.bbox == [100.0, 50.0, 200.0, 300.0]

    def test_detection_equality(self):
        """Test that identical detections are equal."""
        det1 = Detection(
            class_name="car",
            class_id=2,
            confidence=0.87,
            bbox=[100.0, 50.0, 200.0, 300.0],
        )
        det2 = Detection(
            class_name="car",
            class_id=2,
            confidence=0.87,
            bbox=[100.0, 50.0, 200.0, 300.0],
        )
        assert det1 == det2

    def test_detection_to_dict(self):
        """Test converting Detection to dictionary."""
        det = Detection(
            class_name="person",
            class_id=0,
            confidence=0.9567,
            bbox=[100.123, 50.456, 200.789, 300.012],
        )
        result = det.to_dict()
        assert result["class_name"] == "person"
        assert result["class_id"] == 0
        assert result["confidence"] == 0.9567
        assert all(isinstance(x, float) for x in result["bbox"])


# =============================================================================
# Tests for YOLO26Result Dataclass
# =============================================================================


class TestYOLO26ResultDataclass:
    """Tests for the YOLO26Result dataclass."""

    def test_result_with_detections(self, sample_detections):
        """Test YOLO26Result with detections."""
        result = YOLO26Result(
            detections=sample_detections,
            detection_count=3,
            classes_detected={"person", "car", "dog"},
            inference_time_ms=25.5,
        )
        assert result.detection_count == 3
        assert len(result.classes_detected) == 3
        assert result.inference_time_ms == 25.5

    def test_result_empty(self):
        """Test YOLO26Result with no detections."""
        result = YOLO26Result()
        assert result.detection_count == 0
        assert len(result.detections) == 0
        assert len(result.classes_detected) == 0

    def test_result_to_dict(self, sample_detections):
        """Test converting YOLO26Result to dictionary."""
        result = YOLO26Result(
            detections=sample_detections,
            detection_count=3,
            classes_detected={"person", "car", "dog"},
            inference_time_ms=25.567,
        )
        result_dict = result.to_dict()
        assert len(result_dict["detections"]) == 3
        assert result_dict["detection_count"] == 3
        assert result_dict["inference_time_ms"] == 25.57

    def test_result_to_context_string(self, sample_detections):
        """Test generating context string."""
        result = YOLO26Result(
            detections=sample_detections,
            detection_count=3,
            classes_detected={"person", "car", "dog"},
            inference_time_ms=25.5,
        )
        context = result.to_context_string()
        assert "YOLO26 detected 3 object(s)" in context
        assert "person" in context
        assert "car" in context
        assert "dog" in context

    def test_result_to_context_string_empty(self):
        """Test context string with no detections."""
        result = YOLO26Result()
        context = result.to_context_string()
        assert "No objects detected" in context

    def test_filter_by_class(self, sample_detections):
        """Test filtering detections by class."""
        result = YOLO26Result(
            detections=sample_detections,
            detection_count=3,
            classes_detected={"person", "car", "dog"},
        )
        filtered = result.filter_by_class({"person", "car"})
        assert len(filtered) == 2
        assert all(d.class_name in {"person", "car"} for d in filtered)

    def test_filter_by_confidence(self, sample_detections):
        """Test filtering detections by confidence threshold."""
        result = YOLO26Result(
            detections=sample_detections,
            detection_count=3,
            classes_detected={"person", "car", "dog"},
        )
        filtered = result.filter_by_confidence(0.85)
        assert len(filtered) == 2
        assert all(d.confidence >= 0.85 for d in filtered)


# =============================================================================
# Tests for Model Path Validation
# =============================================================================


class TestModelPathValidation:
    """Tests for model path validation security."""

    def test_valid_local_path(self):
        """Test that valid local paths are accepted."""
        path = validate_model_path("/models/yolo26m.pt")
        assert path.startswith("/")

    def test_valid_relative_path(self):
        """Test that valid relative paths are accepted."""
        path = validate_model_path("./models/yolo26m.pt")
        assert path  # Returns resolved path

    def test_valid_model_name(self):
        """Test that model names (non-paths) are accepted."""
        path = validate_model_path("yolo26m.pt")
        assert path == "yolo26m.pt"

    def test_rejects_path_traversal(self):
        """Test that path traversal is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/../../../etc/passwd")

    def test_rejects_embedded_traversal(self):
        """Test that embedded traversal sequences are rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/subdir/../../../etc/passwd")


# =============================================================================
# Tests for YOLO26Detector Initialization
# =============================================================================


class TestYOLO26DetectorInit:
    """Tests for YOLO26Detector initialization."""

    def test_init_with_valid_path(self):
        """Test initialization with valid model path."""
        detector = YOLO26Detector("/models/yolo26m.pt", device="cpu")
        assert detector.model_path == "/models/yolo26m.pt"
        assert detector.device == "cpu"
        assert detector.model is None

    def test_init_with_cuda_device(self):
        """Test initialization with CUDA device."""
        detector = YOLO26Detector("/models/yolo26m.pt", device="cuda:0")
        assert detector.device == "cuda:0"

    def test_init_default_confidence(self):
        """Test default confidence threshold."""
        detector = YOLO26Detector("/models/yolo26m.pt")
        assert detector.confidence_threshold == 0.25

    def test_init_custom_confidence(self):
        """Test custom confidence threshold."""
        detector = YOLO26Detector("/models/yolo26m.pt", confidence_threshold=0.5)
        assert detector.confidence_threshold == 0.5

    def test_init_rejects_path_traversal(self):
        """Test that initialization rejects path traversal."""
        with pytest.raises(ValueError, match="path traversal"):
            YOLO26Detector("../../../etc/passwd")


# =============================================================================
# Tests for Detection Pipeline
# =============================================================================


class TestDetectionPipeline:
    """Tests for the detection pipeline."""

    def test_detect_returns_result(self, mock_yolo26_detector, dummy_image):
        """Test that detect returns a YOLO26Result."""
        result = mock_yolo26_detector.detect(dummy_image)
        assert isinstance(result, YOLO26Result)

    def test_detect_with_numpy_array(self, mock_yolo26_detector, dummy_numpy_image):
        """Test detection with numpy array input."""
        result = mock_yolo26_detector.detect(dummy_numpy_image)
        assert isinstance(result, YOLO26Result)

    def test_detect_without_loaded_model(self, dummy_image):
        """Test that detection fails if model not loaded."""
        detector = YOLO26Detector("/fake/model.pt", device="cpu")
        with pytest.raises(RuntimeError, match="not loaded"):
            detector.detect(dummy_image)

    def test_detect_has_inference_time(self, mock_yolo26_detector, dummy_image):
        """Test that detection result has inference time."""
        result = mock_yolo26_detector.detect(dummy_image)
        assert result.inference_time_ms >= 0


# =============================================================================
# Tests for Batch Inference
# =============================================================================


class TestBatchInference:
    """Tests for batch inference."""

    def test_detect_batch_returns_list(self, mock_yolo26_detector, dummy_image):
        """Test that batch detect returns a list of results."""
        images = [dummy_image, dummy_image]
        results = mock_yolo26_detector.detect_batch(images)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, YOLO26Result) for r in results)

    def test_detect_batch_without_loaded_model(self, dummy_image):
        """Test that batch detection fails if model not loaded."""
        detector = YOLO26Detector("/fake/model.pt", device="cpu")
        with pytest.raises(RuntimeError, match="not loaded"):
            detector.detect_batch([dummy_image])


# =============================================================================
# Tests for Confidence Threshold
# =============================================================================


class TestConfidenceThreshold:
    """Tests for confidence threshold handling."""

    def test_set_confidence_threshold(self, mock_yolo26_detector):
        """Test setting confidence threshold."""
        mock_yolo26_detector.set_confidence_threshold(0.7)
        assert mock_yolo26_detector.confidence_threshold == 0.7

    def test_set_invalid_confidence_too_low(self, mock_yolo26_detector):
        """Test that setting confidence < 0 raises error."""
        with pytest.raises(ValueError):
            mock_yolo26_detector.set_confidence_threshold(-0.1)

    def test_set_invalid_confidence_too_high(self, mock_yolo26_detector):
        """Test that setting confidence > 1 raises error."""
        with pytest.raises(ValueError):
            mock_yolo26_detector.set_confidence_threshold(1.5)


# =============================================================================
# Tests for Model Lifecycle
# =============================================================================


class TestModelLifecycle:
    """Tests for model loading and unloading."""

    def test_load_model_sets_model(self, mock_yolo_model):
        """Test that load_model sets the model attribute."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            detector = YOLO26Detector("/fake/model.pt", device="cpu")
            result = detector.load_model()
            assert detector.model is not None
            assert result is detector  # Returns self

    def test_unload_model_clears_model(self, mock_yolo26_detector):
        """Test that unload clears the model."""
        assert mock_yolo26_detector.model is not None
        mock_yolo26_detector.unload()
        assert mock_yolo26_detector.model is None


# =============================================================================
# Tests for Class Name Utilities
# =============================================================================


class TestClassNameUtilities:
    """Tests for class name utility methods."""

    def test_get_class_names(self, mock_yolo26_detector):
        """Test getting class names."""
        class_names = mock_yolo26_detector.get_class_names()
        assert isinstance(class_names, list)
        assert len(class_names) > 0

    def test_get_class_id_found(self, mock_yolo26_detector):
        """Test getting class ID for existing class."""
        cls_id = mock_yolo26_detector.get_class_id("person")
        assert cls_id == 0

    def test_get_class_id_not_found(self, mock_yolo26_detector):
        """Test getting class ID for non-existent class."""
        cls_id = mock_yolo26_detector.get_class_id("nonexistent_class")
        assert cls_id is None


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_small_image(self, mock_yolo26_detector):
        """Test detection with very small image."""
        small_image = Image.new("RGB", (32, 32), color="blue")
        result = mock_yolo26_detector.detect(small_image)
        assert isinstance(result, YOLO26Result)

    def test_grayscale_image_converted(self, mock_yolo26_detector):
        """Test that grayscale images are converted to RGB."""
        gray_image = Image.new("L", (640, 480), color=128)
        result = mock_yolo26_detector.detect(gray_image)
        assert isinstance(result, YOLO26Result)

    def test_empty_batch(self):
        """Test batch detection with empty list."""
        # Use a fresh detector without mocking to verify empty list behavior
        detector = YOLO26Detector("/fake/model.pt", device="cpu")
        detector.model = MagicMock()  # Mock the model directly
        detector.model.return_value = []  # Empty results
        detector._class_names = {}
        results = detector.detect_batch([])
        assert results == []
