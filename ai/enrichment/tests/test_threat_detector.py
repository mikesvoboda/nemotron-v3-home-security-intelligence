"""Unit tests for ThreatDetector.

Tests cover:
- ThreatDetection dataclass
- ThreatResult dataclass
- ThreatDetector initialization and configuration
- Detection with mocked model
- Confidence threshold handling
- Severity classification
- Logging for all threat detections
- Factory function

NOTE: These tests use safe test images (simple colored images),
not real weapon images.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from ai.enrichment.models.threat_detector import (
    SEVERITY_ORDER,
    THREAT_CLASSES,
    THREAT_CLASSES_BY_NAME,
    ThreatDetection,
    ThreatDetector,
    ThreatResult,
    load_threat_detector,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a safe test image (no weapons - just a solid color)."""
    return Image.new("RGB", (640, 480), color="white")


@pytest.fixture
def sample_numpy_image() -> np.ndarray:
    """Create a safe test numpy image."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_yolo_model() -> MagicMock:
    """Create a mock YOLO model that returns no detections."""
    mock = MagicMock()
    mock.names = {0: "knife", 1: "gun", 2: "rifle"}

    # Create mock results with no detections
    mock_results = MagicMock()
    mock_results.boxes = None

    # Model returns list of results
    mock.return_value = [mock_results]

    return mock


def _create_mock_box(conf_value: float, cls_value: int, bbox: list[float]) -> MagicMock:
    """Helper to create a properly mocked YOLO detection box.

    The mock needs to handle:
    - float(box.conf[0]) -> conf_value
    - int(box.cls[0]) -> cls_value
    - box.xyxy[0].tolist() -> bbox
    """
    mock_box = MagicMock()

    # Mock conf[0] to return something that float() can convert
    mock_conf = MagicMock()
    mock_conf.__getitem__ = MagicMock(return_value=conf_value)
    mock_box.conf = mock_conf

    # Mock cls[0] to return something that int() can convert
    mock_cls = MagicMock()
    mock_cls.__getitem__ = MagicMock(return_value=cls_value)
    mock_box.cls = mock_cls

    # Mock xyxy[0].tolist() to return bbox
    mock_xyxy_item = MagicMock()
    mock_xyxy_item.tolist = MagicMock(return_value=bbox)
    mock_xyxy = MagicMock()
    mock_xyxy.__getitem__ = MagicMock(return_value=mock_xyxy_item)
    mock_box.xyxy = mock_xyxy

    return mock_box


@pytest.fixture
def mock_yolo_model_with_detections() -> MagicMock:
    """Create a mock YOLO model that returns weapon detections."""
    mock = MagicMock()
    mock.names = {0: "knife", 1: "gun", 2: "rifle"}

    # Create mock detection boxes using helper
    mock_box1 = _create_mock_box(
        conf_value=0.85,
        cls_value=1,  # gun
        bbox=[100.0, 150.0, 200.0, 250.0],
    )
    mock_box2 = _create_mock_box(
        conf_value=0.72,
        cls_value=0,  # knife
        bbox=[300.0, 100.0, 400.0, 200.0],
    )

    # Create mock results with detections
    mock_results = MagicMock()
    mock_results.boxes = [mock_box1, mock_box2]

    # Model returns list of results
    mock.return_value = [mock_results]

    return mock


@pytest.fixture
def detector_with_mock(mock_yolo_model: MagicMock) -> ThreatDetector:
    """Create a ThreatDetector with a mocked YOLO model."""
    detector = ThreatDetector(model_path="/fake/path", device="cpu")
    detector.model = mock_yolo_model
    detector._class_names = mock_yolo_model.names
    return detector


# =============================================================================
# ThreatDetection Dataclass Tests
# =============================================================================


class TestThreatDetection:
    """Tests for ThreatDetection dataclass."""

    def test_create_threat_detection(self) -> None:
        """ThreatDetection stores detection data correctly."""
        detection = ThreatDetection(
            threat_type="gun",
            confidence=0.95,
            bbox=[100.0, 150.0, 200.0, 250.0],
            severity="critical",
        )

        assert detection.threat_type == "gun"
        assert detection.confidence == 0.95
        assert detection.bbox == [100.0, 150.0, 200.0, 250.0]
        assert detection.severity == "critical"

    def test_to_dict(self) -> None:
        """to_dict serializes detection correctly."""
        detection = ThreatDetection(
            threat_type="knife",
            confidence=0.8756,
            bbox=[100.5, 150.7, 200.3, 250.9],
            severity="high",
        )

        result = detection.to_dict()

        assert result["threat_type"] == "knife"
        assert result["confidence"] == 0.8756
        assert result["bbox"] == [100.5, 150.7, 200.3, 250.9]
        assert result["severity"] == "high"

    def test_to_dict_rounds_values(self) -> None:
        """to_dict rounds confidence and bbox values appropriately."""
        detection = ThreatDetection(
            threat_type="rifle",
            confidence=0.87564321,
            bbox=[100.123456, 150.789012, 200.345678, 250.901234],
            severity="critical",
        )

        result = detection.to_dict()

        assert result["confidence"] == 0.8756  # 4 decimal places
        assert result["bbox"] == [100.12, 150.79, 200.35, 250.9]  # 2 decimal places


# =============================================================================
# ThreatResult Dataclass Tests
# =============================================================================


class TestThreatResult:
    """Tests for ThreatResult dataclass."""

    def test_create_empty_result(self) -> None:
        """ThreatResult with no threats has correct defaults."""
        result = ThreatResult()

        assert result.threats == []
        assert result.has_threat is False
        assert result.max_severity == "none"
        assert result.inference_time_ms == 0.0

    def test_create_result_with_threats(self) -> None:
        """ThreatResult with threats stores data correctly."""
        threats = [
            ThreatDetection("gun", 0.9, [100.0, 100.0, 200.0, 200.0], "critical"),
            ThreatDetection("knife", 0.8, [300.0, 300.0, 400.0, 400.0], "high"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="critical",
            inference_time_ms=45.5,
        )

        assert len(result.threats) == 2
        assert result.has_threat is True
        assert result.max_severity == "critical"
        assert result.inference_time_ms == 45.5

    def test_to_dict(self) -> None:
        """to_dict serializes result correctly."""
        threats = [
            ThreatDetection("gun", 0.9, [100.0, 100.0, 200.0, 200.0], "critical"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="critical",
            inference_time_ms=45.567,
        )

        data = result.to_dict()

        assert len(data["threats"]) == 1
        assert data["has_threat"] is True
        assert data["max_severity"] == "critical"
        assert data["inference_time_ms"] == 45.57

    def test_to_context_string_no_threats(self) -> None:
        """to_context_string for result with no threats."""
        result = ThreatResult()

        context = result.to_context_string()

        assert "No weapons" in context
        assert "THREAT" not in context

    def test_to_context_string_with_critical_threat(self) -> None:
        """to_context_string for result with critical threat."""
        threats = [
            ThreatDetection("gun", 0.95, [100.0, 100.0, 200.0, 200.0], "critical"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="critical",
        )

        context = result.to_context_string()

        assert "[THREAT DETECTED]" in context
        assert "[CRITICAL]" in context
        assert "GUN" in context
        assert "95%" in context
        assert "Maximum severity: CRITICAL" in context

    def test_to_context_string_with_high_threat(self) -> None:
        """to_context_string for result with high severity threat."""
        threats = [
            ThreatDetection("knife", 0.82, [100.0, 100.0, 200.0, 200.0], "high"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="high",
        )

        context = result.to_context_string()

        assert "[HIGH]" in context
        assert "KNIFE" in context

    def test_to_context_string_with_medium_threat(self) -> None:
        """to_context_string for result with medium severity threat."""
        threats = [
            ThreatDetection("bat", 0.75, [100.0, 100.0, 200.0, 200.0], "medium"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="medium",
        )

        context = result.to_context_string()

        assert "[MEDIUM]" in context
        assert "BAT" in context

    def test_to_context_string_multiple_threats(self) -> None:
        """to_context_string for result with multiple threats."""
        threats = [
            ThreatDetection("gun", 0.90, [100.0, 100.0, 200.0, 200.0], "critical"),
            ThreatDetection("knife", 0.80, [300.0, 300.0, 400.0, 400.0], "high"),
        ]

        result = ThreatResult(
            threats=threats,
            has_threat=True,
            max_severity="critical",
        )

        context = result.to_context_string()

        assert "GUN" in context
        assert "KNIFE" in context
        assert "[CRITICAL]" in context
        assert "[HIGH]" in context


# =============================================================================
# Severity Constants Tests
# =============================================================================


class TestSeverityConstants:
    """Tests for severity-related constants."""

    def test_severity_order(self) -> None:
        """SEVERITY_ORDER ranks severities correctly."""
        assert SEVERITY_ORDER["critical"] < SEVERITY_ORDER["high"]
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"]
        assert SEVERITY_ORDER["medium"] < SEVERITY_ORDER["none"]

    def test_threat_classes_mapping(self) -> None:
        """THREAT_CLASSES maps class IDs to threat types and severities."""
        # Verify some expected mappings
        assert THREAT_CLASSES[1] == ("gun", "critical")
        assert THREAT_CLASSES[0] == ("knife", "high")
        assert THREAT_CLASSES[4] == ("bat", "medium")

    def test_threat_classes_by_name_mapping(self) -> None:
        """THREAT_CLASSES_BY_NAME maps threat names to severities."""
        assert THREAT_CLASSES_BY_NAME["gun"] == "critical"
        assert THREAT_CLASSES_BY_NAME["rifle"] == "critical"
        assert THREAT_CLASSES_BY_NAME["knife"] == "high"
        assert THREAT_CLASSES_BY_NAME["bat"] == "medium"


# =============================================================================
# ThreatDetector Initialization Tests
# =============================================================================


class TestThreatDetectorInit:
    """Tests for ThreatDetector initialization."""

    def test_init_with_defaults(self) -> None:
        """ThreatDetector initializes with default values."""
        detector = ThreatDetector(model_path="/models/threat")

        assert detector.model_path == "/models/threat"
        assert detector.device == "cuda:0"
        assert detector.confidence_threshold == 0.5
        assert detector.model is None

    def test_init_with_custom_device(self) -> None:
        """ThreatDetector accepts custom device."""
        detector = ThreatDetector(model_path="/models/threat", device="cpu")

        assert detector.device == "cpu"

    def test_init_with_custom_threshold(self) -> None:
        """ThreatDetector accepts custom confidence threshold."""
        detector = ThreatDetector(
            model_path="/models/threat",
            confidence_threshold=0.7,
        )

        assert detector.confidence_threshold == 0.7


# =============================================================================
# ThreatDetector Model Loading Tests
# =============================================================================


class TestThreatDetectorLoadModel:
    """Tests for ThreatDetector model loading."""

    def test_load_model_missing_ultralytics(self) -> None:
        """load_model raises ImportError if ultralytics not installed."""
        # Note: detector variable exists to verify instantiation works without loading
        _ = ThreatDetector(model_path="/models/threat")

        with (
            patch.dict("sys.modules", {"ultralytics": None}),
            pytest.raises(ImportError, match="ultralytics"),
        ):
            # Force reimport to trigger the ImportError
            import importlib

            import ai.enrichment.models.threat_detector as module

            importlib.reload(module)
            module.ThreatDetector("/test").load_model()

    def test_load_model_success(self) -> None:
        """load_model loads YOLO model successfully."""
        detector = ThreatDetector(model_path="/models/threat", device="cpu")

        mock_yolo_class = MagicMock()
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.names = {0: "knife", 1: "gun"}
        mock_yolo_class.return_value = mock_yolo_instance

        with (
            patch(
                "ai.enrichment.models.threat_detector.torch.cuda.is_available",
                return_value=False,
            ),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
            patch(
                "ai.enrichment.models.threat_detector.YOLO",
                mock_yolo_class,
                create=True,
            ),
        ):
            # Simulate the import inside load_model
            result = detector.load_model()

        # load_model returns self for chaining
        assert result is detector

    def test_load_model_returns_self_for_chaining(self) -> None:
        """load_model returns self for method chaining."""
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.names = {0: "knife", 1: "gun"}
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        detector = ThreatDetector(model_path="/models/threat", device="cpu")

        with (
            patch(
                "ai.enrichment.models.threat_detector.torch.cuda.is_available",
                return_value=False,
            ),
            patch("ultralytics.YOLO", mock_yolo_class),
        ):
            result = detector.load_model()

        # load_model returns self for chaining
        assert result is detector
        assert detector.model is mock_yolo_instance


# =============================================================================
# ThreatDetector Detection Tests
# =============================================================================


class TestThreatDetectorDetection:
    """Tests for ThreatDetector threat detection."""

    def test_detect_threats_model_not_loaded(self, sample_image: Image.Image) -> None:
        """detect_threats raises RuntimeError if model not loaded."""
        detector = ThreatDetector(model_path="/models/threat")

        with pytest.raises(RuntimeError, match="not loaded"):
            detector.detect_threats(sample_image)

    def test_detect_threats_no_detections(
        self,
        detector_with_mock: ThreatDetector,
        sample_image: Image.Image,
    ) -> None:
        """detect_threats returns empty result when no threats detected."""
        result = detector_with_mock.detect_threats(sample_image)

        assert result.has_threat is False
        assert result.threats == []
        assert result.max_severity == "none"
        assert result.inference_time_ms > 0

    def test_detect_threats_with_pil_image(
        self,
        detector_with_mock: ThreatDetector,
        sample_image: Image.Image,
    ) -> None:
        """detect_threats works with PIL Image input."""
        result = detector_with_mock.detect_threats(sample_image)

        # Model should have been called
        detector_with_mock.model.assert_called_once()

        # Verify result has expected attributes (avoid import path issues)
        assert hasattr(result, "threats")
        assert hasattr(result, "has_threat")
        assert hasattr(result, "max_severity")
        assert result.has_threat is False

    def test_detect_threats_with_numpy_image(
        self,
        detector_with_mock: ThreatDetector,
        sample_numpy_image: np.ndarray,
    ) -> None:
        """detect_threats works with numpy array input."""
        result = detector_with_mock.detect_threats(sample_numpy_image)

        # Model should have been called
        detector_with_mock.model.assert_called_once()

        # Verify result has expected attributes (avoid import path issues)
        assert hasattr(result, "threats")
        assert hasattr(result, "has_threat")
        assert hasattr(result, "max_severity")
        assert result.has_threat is False

    def test_detect_threats_filters_low_confidence(
        self,
        mock_yolo_model_with_detections: MagicMock,
        sample_image: Image.Image,
    ) -> None:
        """detect_threats filters detections below confidence threshold."""
        detector = ThreatDetector(
            model_path="/fake/path",
            device="cpu",
            confidence_threshold=0.90,  # Higher than mock detections (0.85, 0.72)
        )
        detector.model = mock_yolo_model_with_detections
        detector._class_names = mock_yolo_model_with_detections.names

        result = detector.detect_threats(sample_image)

        # All detections should be filtered out (0.85 and 0.72 < 0.90)
        assert result.has_threat is False
        assert len(result.threats) == 0

    def test_detect_threats_tracks_max_severity(
        self,
        sample_image: Image.Image,
    ) -> None:
        """detect_threats correctly identifies maximum severity."""
        detector = ThreatDetector(model_path="/fake/path", device="cpu")

        # Create mock with critical and high severity detections
        mock = MagicMock()
        mock.names = {0: "knife", 1: "gun"}

        # Gun detection (critical) and Knife detection (high) using helper
        mock_box_gun = _create_mock_box(
            conf_value=0.85,
            cls_value=1,  # gun
            bbox=[100.0, 100.0, 200.0, 200.0],
        )
        mock_box_knife = _create_mock_box(
            conf_value=0.80,
            cls_value=0,  # knife
            bbox=[300.0, 300.0, 400.0, 400.0],
        )

        mock_results = MagicMock()
        mock_results.boxes = [mock_box_knife, mock_box_gun]  # Knife first, then gun
        mock.return_value = [mock_results]

        detector.model = mock
        detector._class_names = mock.names

        result = detector.detect_threats(sample_image)

        # Maximum severity should be critical (gun), not high (knife)
        assert result.max_severity == "critical"

    def test_detect_threats_logs_warnings(
        self,
        sample_image: Image.Image,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """detect_threats logs all threat detections at WARNING level."""
        import logging

        detector = ThreatDetector(model_path="/fake/path", device="cpu")

        # Create mock with detection using helper
        mock = MagicMock()
        mock.names = {1: "gun"}

        mock_box = _create_mock_box(
            conf_value=0.85,
            cls_value=1,  # gun
            bbox=[100.0, 100.0, 200.0, 200.0],
        )

        mock_results = MagicMock()
        mock_results.boxes = [mock_box]
        mock.return_value = [mock_results]

        detector.model = mock
        detector._class_names = mock.names

        with caplog.at_level(logging.WARNING):
            detector.detect_threats(sample_image)

        # Verify warning was logged
        assert any("THREAT DETECTED" in record.message for record in caplog.records)
        assert any("gun" in record.message for record in caplog.records)


# =============================================================================
# ThreatDetector Configuration Tests
# =============================================================================


class TestThreatDetectorConfiguration:
    """Tests for ThreatDetector configuration methods."""

    def test_set_confidence_threshold_valid(self) -> None:
        """set_confidence_threshold accepts valid threshold."""
        detector = ThreatDetector(model_path="/models/threat")

        detector.set_confidence_threshold(0.7)

        assert detector.confidence_threshold == 0.7

    def test_set_confidence_threshold_boundary_low(self) -> None:
        """set_confidence_threshold accepts 0.0."""
        detector = ThreatDetector(model_path="/models/threat")

        detector.set_confidence_threshold(0.0)

        assert detector.confidence_threshold == 0.0

    def test_set_confidence_threshold_boundary_high(self) -> None:
        """set_confidence_threshold accepts 1.0."""
        detector = ThreatDetector(model_path="/models/threat")

        detector.set_confidence_threshold(1.0)

        assert detector.confidence_threshold == 1.0

    def test_set_confidence_threshold_invalid_low(self) -> None:
        """set_confidence_threshold rejects negative threshold."""
        detector = ThreatDetector(model_path="/models/threat")

        with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
            detector.set_confidence_threshold(-0.1)

    def test_set_confidence_threshold_invalid_high(self) -> None:
        """set_confidence_threshold rejects threshold > 1.0."""
        detector = ThreatDetector(model_path="/models/threat")

        with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
            detector.set_confidence_threshold(1.5)

    def test_get_supported_classes_model_not_loaded(self) -> None:
        """get_supported_classes returns default classes when model not loaded."""
        detector = ThreatDetector(model_path="/models/threat")

        classes = detector.get_supported_classes()

        assert "knife" in classes
        assert "gun" in classes
        assert "rifle" in classes

    def test_get_supported_classes_model_loaded(
        self,
        detector_with_mock: ThreatDetector,
    ) -> None:
        """get_supported_classes returns model classes when loaded."""
        classes = detector_with_mock.get_supported_classes()

        assert "knife" in classes
        assert "gun" in classes
        assert "rifle" in classes


# =============================================================================
# ThreatDetector Unload Tests
# =============================================================================


class TestThreatDetectorUnload:
    """Tests for ThreatDetector model unloading."""

    def test_unload_clears_model(self) -> None:
        """unload sets model to None."""
        detector = ThreatDetector(model_path="/models/threat")
        detector.model = MagicMock()

        with patch(
            "ai.enrichment.models.threat_detector.torch.cuda.is_available", return_value=False
        ):
            detector.unload()

        assert detector.model is None

    def test_unload_clears_cuda_cache(self) -> None:
        """unload clears CUDA cache when available."""
        detector = ThreatDetector(model_path="/models/threat")
        detector.model = MagicMock()

        with (
            patch(
                "ai.enrichment.models.threat_detector.torch.cuda.is_available",
                return_value=True,
            ),
            patch("ai.enrichment.models.threat_detector.torch.cuda.empty_cache") as mock_empty,
        ):
            detector.unload()

        mock_empty.assert_called_once()

    def test_unload_when_model_none(self) -> None:
        """unload handles model being None gracefully."""
        detector = ThreatDetector(model_path="/models/threat")
        detector.model = None

        # Should not raise
        detector.unload()

        assert detector.model is None


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestLoadThreatDetector:
    """Tests for load_threat_detector factory function."""

    def test_load_threat_detector_creates_and_loads(self) -> None:
        """load_threat_detector creates detector and calls load_model."""
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.names = {0: "knife", 1: "gun"}
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch(
                "ai.enrichment.models.threat_detector.torch.cuda.is_available",
                return_value=False,
            ),
            patch("ultralytics.YOLO", mock_yolo_class),
        ):
            detector = load_threat_detector(
                model_path="/models/threat",
                device="cpu",
                confidence_threshold=0.6,
            )

        # Verify the detector was created and model loaded
        assert detector is not None
        assert detector.model is mock_yolo_instance
        assert detector.confidence_threshold == 0.6

    def test_load_threat_detector_passes_parameters(self) -> None:
        """load_threat_detector passes all parameters to detector."""
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.names = {}
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch(
                "ai.enrichment.models.threat_detector.torch.cuda.is_available",
                return_value=False,
            ),
            patch("ultralytics.YOLO", mock_yolo_class),
        ):
            detector = load_threat_detector(
                model_path="/models/custom",
                device="cuda:1",
                confidence_threshold=0.8,
            )

        # Verify parameters were passed correctly
        assert detector.model_path == "/models/custom"
        assert detector.device == "cpu"  # Falls back to CPU since CUDA not available
        assert detector.confidence_threshold == 0.8
