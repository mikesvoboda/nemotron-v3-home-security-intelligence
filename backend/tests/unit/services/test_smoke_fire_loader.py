"""Unit tests for smoke/fire detection model loader.

Tests cover:
- Model loading and initialization
- CRITICAL priority designation (never evict from VRAM)
- VRAM usage estimation (300-400MB)
- Detection functions for smoke and fire
- Detection result structure and attributes
- Integration with ModelManager

These tests are written TDD-style and should FAIL until smoke_fire_loader.py
is implemented (NEM-5298 Phase 5).

Model: YOLOv8n Fire & Smoke (luminous0219/fire-and-smoke-detection-yolov8)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ===========================================================================
# Test: Module Import and Constants
# ===========================================================================


class TestSmokeFireLoaderImports:
    """Test that the smoke_fire_loader module can be imported."""

    def test_module_import(self) -> None:
        """Test that smoke_fire_loader module can be imported."""
        # This will fail until smoke_fire_loader.py is created
        from backend.services import smoke_fire_loader

        assert smoke_fire_loader is not None

    def test_load_function_exists(self) -> None:
        """Test that load_smoke_fire_model function exists."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        assert callable(load_smoke_fire_model)

    def test_detect_function_exists(self) -> None:
        """Test that detect_smoke_fire function exists."""
        from backend.services.smoke_fire_loader import detect_smoke_fire

        assert callable(detect_smoke_fire)

    def test_detection_class_exists(self) -> None:
        """Test that SmokeFireDetection dataclass exists."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        assert SmokeFireDetection is not None

    def test_result_class_exists(self) -> None:
        """Test that SmokeFireDetectionResult dataclass exists."""
        from backend.services.smoke_fire_loader import SmokeFireDetectionResult

        assert SmokeFireDetectionResult is not None


class TestSmokeFireConstants:
    """Test constants defined in the module."""

    def test_smoke_fire_classes_defined(self) -> None:
        """Test that SMOKE_FIRE_CLASSES frozenset is defined."""
        from backend.services.smoke_fire_loader import SMOKE_FIRE_CLASSES

        assert isinstance(SMOKE_FIRE_CLASSES, frozenset)
        assert "smoke" in SMOKE_FIRE_CLASSES
        assert "fire" in SMOKE_FIRE_CLASSES

    def test_model_vram_mb_constant(self) -> None:
        """Test that VRAM usage constant is defined (300-400MB)."""
        from backend.services.smoke_fire_loader import SMOKE_FIRE_VRAM_MB

        assert isinstance(SMOKE_FIRE_VRAM_MB, int)
        assert 300 <= SMOKE_FIRE_VRAM_MB <= 400

    def test_smoke_confidence_threshold_default(self) -> None:
        """Test that smoke confidence threshold is 0.75."""
        from backend.services.smoke_fire_loader import SMOKE_CONFIDENCE_THRESHOLD

        assert SMOKE_CONFIDENCE_THRESHOLD == 0.75

    def test_fire_confidence_threshold_default(self) -> None:
        """Test that fire confidence threshold is 0.70."""
        from backend.services.smoke_fire_loader import FIRE_CONFIDENCE_THRESHOLD

        assert FIRE_CONFIDENCE_THRESHOLD == 0.70


# ===========================================================================
# Test: Model Loading
# ===========================================================================


class TestLoadSmokeFireModel:
    """Tests for the load_smoke_fire_model function."""

    @pytest.mark.asyncio
    async def test_load_model_returns_model_instance(self) -> None:
        """Test that load_smoke_fire_model returns a model instance."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        with patch("backend.services.smoke_fire_loader.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            model = await load_smoke_fire_model("/models/model-zoo/smoke-fire-yolov8n")

            assert model is not None

    @pytest.mark.asyncio
    async def test_load_model_from_correct_path(self) -> None:
        """Test that model is loaded from the correct path."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        with patch("backend.services.smoke_fire_loader.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            await load_smoke_fire_model("/models/model-zoo/smoke-fire-yolov8n")

            # Should have been called with a path to a .pt file
            mock_yolo.assert_called()
            call_args = str(mock_yolo.call_args)
            assert "smoke-fire" in call_args.lower() or "model.pt" in call_args

    @pytest.mark.asyncio
    async def test_load_model_pre_fuses_for_thread_safety(self) -> None:
        """Test that model is pre-fused for thread-safe concurrent use."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        with patch("backend.services.smoke_fire_loader.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_inner_model = MagicMock()
            mock_inner_model.is_fused.return_value = False
            mock_model.model = mock_inner_model
            mock_yolo.return_value = mock_model

            await load_smoke_fire_model("/models/model-zoo/smoke-fire-yolov8n")

            # Model should be fused after loading
            mock_model.fuse.assert_called()

    @pytest.mark.asyncio
    async def test_load_model_raises_import_error_without_ultralytics(self) -> None:
        """Test that ImportError is raised if ultralytics not installed."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        with patch.dict("sys.modules", {"ultralytics": None}):
            with pytest.raises(ImportError):
                await load_smoke_fire_model("/models/model-zoo/smoke-fire-yolov8n")

    @pytest.mark.asyncio
    async def test_load_model_raises_runtime_error_on_failure(self) -> None:
        """Test that RuntimeError is raised if model loading fails."""
        from backend.services.smoke_fire_loader import load_smoke_fire_model

        with patch("backend.services.smoke_fire_loader.YOLO") as mock_yolo:
            mock_yolo.side_effect = RuntimeError("Model file not found")

            with pytest.raises(RuntimeError) as exc_info:
                await load_smoke_fire_model("/invalid/path")

            assert "smoke" in str(exc_info.value).lower() or "fire" in str(exc_info.value).lower()


# ===========================================================================
# Test: CRITICAL Priority and VRAM Management
# ===========================================================================


class TestSmokeFireModelPriority:
    """Tests for CRITICAL priority designation."""

    def test_model_registered_in_model_zoo(self) -> None:
        """Test that smoke_fire model is registered in MODEL_ZOO."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None

    def test_model_has_critical_priority(self) -> None:
        """Test that model has CRITICAL priority (never evict)."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None
        # CRITICAL priority should be indicated by a priority field or special handling
        assert config.priority == "critical" or getattr(config, "never_evict", False)

    def test_model_vram_estimate_in_config(self) -> None:
        """Test that VRAM estimate is 300-400MB in config."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None
        assert 300 <= config.vram_mb <= 400

    def test_model_is_enabled_by_default(self) -> None:
        """Test that model is enabled by default."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None
        assert config.enabled is True

    def test_model_should_preload_at_startup(self) -> None:
        """Test that model is marked for preloading at startup."""
        from backend.services.model_zoo import get_model_config

        config = get_model_config("smoke-fire-yolov8n")
        assert config is not None
        # Model should have a preload flag or be in a preload list
        assert getattr(config, "preload", False) is True


# ===========================================================================
# Test: Detection Data Classes
# ===========================================================================


class TestSmokeFireDetection:
    """Tests for SmokeFireDetection dataclass."""

    def test_detection_creation(self) -> None:
        """Test creating a SmokeFireDetection instance."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.85,
            bbox=(100, 100, 200, 200),
        )

        assert detection.detection_type == "fire"
        assert detection.confidence == 0.85
        assert detection.bbox == (100, 100, 200, 200)

    def test_detection_type_smoke(self) -> None:
        """Test detection with type 'smoke'."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="smoke",
            confidence=0.80,
            bbox=(50, 50, 150, 150),
        )

        assert detection.detection_type == "smoke"

    def test_detection_type_fire(self) -> None:
        """Test detection with type 'fire'."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.90,
            bbox=(0, 0, 100, 100),
        )

        assert detection.detection_type == "fire"

    def test_detection_is_high_priority_fire(self) -> None:
        """Test that fire detection is marked as high priority."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.75,
            bbox=(0, 0, 100, 100),
        )

        assert detection.is_high_priority is True

    def test_detection_is_high_priority_smoke(self) -> None:
        """Test that high-confidence smoke is also high priority."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="smoke",
            confidence=0.85,
            bbox=(0, 0, 100, 100),
        )

        # Smoke is also high priority (home safety)
        assert detection.is_high_priority is True

    def test_detection_to_dict(self) -> None:
        """Test converting detection to dictionary."""
        from backend.services.smoke_fire_loader import SmokeFireDetection

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.92,
            bbox=(10, 20, 30, 40),
        )

        result = detection.to_dict()

        assert result["detection_type"] == "fire"
        assert result["confidence"] == 0.92
        assert result["bbox"] == [10, 20, 30, 40]
        assert result["is_high_priority"] is True


class TestSmokeFireDetectionResult:
    """Tests for SmokeFireDetectionResult dataclass."""

    def test_empty_result(self) -> None:
        """Test creating an empty result."""
        from backend.services.smoke_fire_loader import SmokeFireDetectionResult

        result = SmokeFireDetectionResult()

        assert result.detections == []
        assert result.has_detections is False
        assert result.has_fire is False
        assert result.has_smoke is False

    def test_result_with_fire(self) -> None:
        """Test result with fire detection."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.88,
            bbox=(0, 0, 100, 100),
        )
        result = SmokeFireDetectionResult(detections=[detection])

        assert result.has_detections is True
        assert result.has_fire is True
        assert result.has_smoke is False

    def test_result_with_smoke(self) -> None:
        """Test result with smoke detection."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        detection = SmokeFireDetection(
            detection_type="smoke",
            confidence=0.78,
            bbox=(0, 0, 100, 100),
        )
        result = SmokeFireDetectionResult(detections=[detection])

        assert result.has_detections is True
        assert result.has_fire is False
        assert result.has_smoke is True

    def test_result_highest_confidence(self) -> None:
        """Test that highest confidence is calculated correctly."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        detections = [
            SmokeFireDetection(detection_type="smoke", confidence=0.75, bbox=(0, 0, 100, 100)),
            SmokeFireDetection(detection_type="fire", confidence=0.95, bbox=(0, 0, 100, 100)),
            SmokeFireDetection(detection_type="smoke", confidence=0.80, bbox=(0, 0, 100, 100)),
        ]
        result = SmokeFireDetectionResult(detections=detections)

        assert result.highest_confidence == 0.95

    def test_result_to_context_string(self) -> None:
        """Test generating context string for LLM prompt."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
        )

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.90,
            bbox=(0, 0, 100, 100),
        )
        result = SmokeFireDetectionResult(detections=[detection])

        context = result.to_context_string()

        assert "FIRE" in context.upper() or "CRITICAL" in context.upper()


# ===========================================================================
# Test: Smoke/Fire Detection Function
# ===========================================================================


class TestDetectSmokeFire:
    """Tests for detect_smoke_fire function."""

    @pytest.fixture
    def mock_image(self) -> MagicMock:
        """Create a mock PIL Image."""
        mock = MagicMock()
        mock.size = (640, 480)
        return mock

    @pytest.mark.asyncio
    async def test_detect_returns_result(self, mock_image: MagicMock) -> None:
        """Test that detect_smoke_fire returns a result."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetectionResult,
            detect_smoke_fire,
        )

        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]

        result = await detect_smoke_fire(mock_model, mock_image)

        assert isinstance(result, SmokeFireDetectionResult)

    @pytest.mark.asyncio
    async def test_detect_with_fire(self, mock_image: MagicMock) -> None:
        """Test detection when fire is present."""
        from backend.services.smoke_fire_loader import detect_smoke_fire

        # Create mock YOLO result with fire detection
        mock_boxes = MagicMock()
        mock_boxes.__len__ = MagicMock(return_value=1)
        mock_boxes.cls = [MagicMock(item=MagicMock(return_value=1))]  # fire class
        mock_boxes.conf = [MagicMock(item=MagicMock(return_value=0.85))]
        mock_boxes.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 20, 30, 40]))]

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]
        mock_model.names = {0: "smoke", 1: "fire"}

        result = await detect_smoke_fire(mock_model, mock_image)

        assert result.has_fire is True
        assert len(result.detections) > 0

    @pytest.mark.asyncio
    async def test_detect_with_smoke(self, mock_image: MagicMock) -> None:
        """Test detection when smoke is present."""
        from backend.services.smoke_fire_loader import detect_smoke_fire

        # Create mock YOLO result with smoke detection
        mock_boxes = MagicMock()
        mock_boxes.__len__ = MagicMock(return_value=1)
        mock_boxes.cls = [MagicMock(item=MagicMock(return_value=0))]  # smoke class
        mock_boxes.conf = [MagicMock(item=MagicMock(return_value=0.80))]
        mock_boxes.xyxy = [MagicMock(tolist=MagicMock(return_value=[10, 20, 30, 40]))]

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]
        mock_model.names = {0: "smoke", 1: "fire"}

        result = await detect_smoke_fire(mock_model, mock_image)

        assert result.has_smoke is True

    @pytest.mark.asyncio
    async def test_detect_respects_confidence_threshold(self, mock_image: MagicMock) -> None:
        """Test that confidence threshold is respected."""
        from backend.services.smoke_fire_loader import detect_smoke_fire

        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]

        await detect_smoke_fire(mock_model, mock_image, confidence_threshold=0.5)

        # Verify predict was called with the confidence threshold
        mock_model.predict.assert_called()
        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs.get("conf") == 0.5

    @pytest.mark.asyncio
    async def test_detect_no_detection(self, mock_image: MagicMock) -> None:
        """Test when no smoke/fire is detected."""
        from backend.services.smoke_fire_loader import detect_smoke_fire

        mock_model = MagicMock()
        mock_model.predict.return_value = [MagicMock(boxes=None)]

        result = await detect_smoke_fire(mock_model, mock_image)

        assert result.has_detections is False
        assert result.has_fire is False
        assert result.has_smoke is False


# ===========================================================================
# Test: Batch Detection
# ===========================================================================


class TestDetectSmokeFireBatch:
    """Tests for batch smoke/fire detection."""

    @pytest.mark.asyncio
    async def test_batch_detect_empty_list(self) -> None:
        """Test batch detection with empty image list."""
        from backend.services.smoke_fire_loader import detect_smoke_fire_batch

        mock_model = MagicMock()

        results = await detect_smoke_fire_batch(mock_model, [])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_detect_multiple_images(self) -> None:
        """Test batch detection with multiple images."""
        from backend.services.smoke_fire_loader import detect_smoke_fire_batch

        mock_images = [MagicMock() for _ in range(3)]

        mock_model = MagicMock()
        mock_model.predict.return_value = [
            MagicMock(boxes=None),
            MagicMock(boxes=None),
            MagicMock(boxes=None),
        ]

        results = await detect_smoke_fire_batch(mock_model, mock_images)

        assert len(results) == 3


# ===========================================================================
# Test: Format Context for LLM
# ===========================================================================


class TestFormatSmokeFireContext:
    """Tests for formatting smoke/fire results for LLM context."""

    def test_format_no_detection(self) -> None:
        """Test formatting when no smoke/fire detected."""
        from backend.services.smoke_fire_loader import format_smoke_fire_context

        result = format_smoke_fire_context(None)

        assert "not performed" in result.lower() or "no" in result.lower()

    def test_format_with_fire(self) -> None:
        """Test formatting when fire is detected."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
            format_smoke_fire_context,
        )

        detection = SmokeFireDetection(
            detection_type="fire",
            confidence=0.92,
            bbox=(0, 0, 100, 100),
        )
        result = SmokeFireDetectionResult(detections=[detection])

        context = format_smoke_fire_context(result)

        assert "FIRE" in context.upper()
        assert "CRITICAL" in context.upper() or "ALERT" in context.upper()

    def test_format_with_smoke(self) -> None:
        """Test formatting when smoke is detected."""
        from backend.services.smoke_fire_loader import (
            SmokeFireDetection,
            SmokeFireDetectionResult,
            format_smoke_fire_context,
        )

        detection = SmokeFireDetection(
            detection_type="smoke",
            confidence=0.80,
            bbox=(0, 0, 100, 100),
        )
        result = SmokeFireDetectionResult(detections=[detection])

        context = format_smoke_fire_context(result)

        assert "SMOKE" in context.upper()
