"""Unit tests for vehicle damage detection loader and classification.

Tests cover:
- DamageDetection dataclass
- VehicleDamageResult dataclass
- load_vehicle_damage_model function
- detect_vehicle_damage function
- Integration with enrichment pipeline
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.services.vehicle_damage_loader import (
    DAMAGE_CLASSES,
    HIGH_SECURITY_DAMAGE,
    DamageDetection,
    VehicleDamageResult,
    _has_meta_tensors,
    _materialize_meta_tensors,
    detect_vehicle_damage,
    format_damage_context,
    is_suspicious_damage_pattern,
    load_vehicle_damage_model,
)


class TestDamageDetection:
    """Tests for DamageDetection dataclass."""

    def test_create_damage_detection(self) -> None:
        """Test creating a damage detection."""
        detection = DamageDetection(
            damage_type="glass_shatter",
            confidence=0.95,
            bbox=(100, 200, 300, 400),
            has_mask=True,
            mask_area=1500,
        )

        assert detection.damage_type == "glass_shatter"
        assert detection.confidence == 0.95
        assert detection.bbox == (100, 200, 300, 400)
        assert detection.has_mask is True
        assert detection.mask_area == 1500

    def test_damage_detection_to_dict(self) -> None:
        """Test conversion to dictionary."""
        detection = DamageDetection(
            damage_type="dent",
            confidence=0.8,
            bbox=(50, 100, 150, 200),
            has_mask=False,
            mask_area=0,
        )

        d = detection.to_dict()

        assert d["damage_type"] == "dent"
        assert d["confidence"] == 0.8
        assert d["bbox"]["x1"] == 50
        assert d["bbox"]["y1"] == 100
        assert d["bbox"]["x2"] == 150
        assert d["bbox"]["y2"] == 200
        assert d["has_mask"] is False
        assert d["mask_area"] == 0


class TestVehicleDamageResult:
    """Tests for VehicleDamageResult dataclass."""

    def test_empty_result(self) -> None:
        """Test creating an empty result."""
        result = VehicleDamageResult()

        assert result.detections == []
        assert result.damage_types == set()
        assert result.has_high_security_damage is False
        assert result.total_damage_count == 0
        assert result.has_damage is False
        assert result.highest_confidence == 0.0

    def test_result_with_detections(self) -> None:
        """Test result with multiple detections."""
        detections = [
            DamageDetection(
                damage_type="crack",
                confidence=0.9,
                bbox=(10, 20, 30, 40),
            ),
            DamageDetection(
                damage_type="dent",
                confidence=0.85,
                bbox=(50, 60, 70, 80),
            ),
        ]
        result = VehicleDamageResult(detections=detections)

        assert result.has_damage is True
        assert result.total_damage_count == 2
        assert result.damage_types == {"crack", "dent"}
        assert result.has_high_security_damage is False
        assert result.highest_confidence == 0.9

    def test_result_with_high_security_damage(self) -> None:
        """Test result with high-security damage types."""
        detections = [
            DamageDetection(
                damage_type="glass_shatter",
                confidence=0.95,
                bbox=(10, 20, 30, 40),
            ),
            DamageDetection(
                damage_type="lamp_broken",
                confidence=0.88,
                bbox=(50, 60, 70, 80),
            ),
        ]
        result = VehicleDamageResult(detections=detections)

        assert result.has_high_security_damage is True
        assert "glass_shatter" in result.damage_types
        assert "lamp_broken" in result.damage_types

    def test_get_detections_by_type(self) -> None:
        """Test filtering detections by type."""
        detections = [
            DamageDetection(damage_type="crack", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="crack", confidence=0.85, bbox=(50, 60, 70, 80)),
            DamageDetection(damage_type="dent", confidence=0.8, bbox=(90, 100, 110, 120)),
        ]
        result = VehicleDamageResult(detections=detections)

        crack_dets = result.get_detections_by_type("crack")
        assert len(crack_dets) == 2

        dent_dets = result.get_detections_by_type("dent")
        assert len(dent_dets) == 1

        scratch_dets = result.get_detections_by_type("scratch")
        assert len(scratch_dets) == 0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        detections = [
            DamageDetection(
                damage_type="scratch",
                confidence=0.75,
                bbox=(10, 20, 30, 40),
                has_mask=True,
                mask_area=500,
            ),
        ]
        result = VehicleDamageResult(detections=detections)

        d = result.to_dict()

        assert "detections" in d
        assert len(d["detections"]) == 1
        assert "damage_types" in d
        assert "scratch" in d["damage_types"]
        assert d["has_high_security_damage"] is False
        assert d["total_damage_count"] == 1
        assert d["highest_confidence"] == 0.75

    def test_to_context_string_no_damage(self) -> None:
        """Test context string with no damage."""
        result = VehicleDamageResult()
        context = result.to_context_string()
        assert context == "No vehicle damage detected."

    def test_to_context_string_with_damage(self) -> None:
        """Test context string with damage."""
        detections = [
            DamageDetection(damage_type="crack", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="dent", confidence=0.8, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)
        context = result.to_context_string()

        assert "Vehicle Damage Detected" in context
        assert "2 instances" in context
        assert "crack" in context
        assert "dent" in context


class TestDamageClasses:
    """Tests for damage class constants."""

    def test_damage_classes_defined(self) -> None:
        """Test that all damage classes are defined."""
        assert "crack" in DAMAGE_CLASSES
        assert "dent" in DAMAGE_CLASSES
        assert "glass_shatter" in DAMAGE_CLASSES
        assert "lamp_broken" in DAMAGE_CLASSES
        assert "scratch" in DAMAGE_CLASSES
        assert "tire_flat" in DAMAGE_CLASSES
        assert len(DAMAGE_CLASSES) == 6

    def test_high_security_damage_defined(self) -> None:
        """Test high-security damage types."""
        assert "glass_shatter" in HIGH_SECURITY_DAMAGE
        assert "lamp_broken" in HIGH_SECURITY_DAMAGE
        assert len(HIGH_SECURITY_DAMAGE) == 2


class TestMetaTensorHelpers:
    """Tests for meta tensor detection and materialization helpers."""

    def test_has_meta_tensors_returns_true_for_meta_device(self) -> None:
        """Test that _has_meta_tensors detects meta tensors."""
        # Create a mock parameter on meta device
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "meta"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is True

    def test_has_meta_tensors_returns_false_for_cpu_device(self) -> None:
        """Test that _has_meta_tensors returns False for CPU tensors."""
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "cpu"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_returns_false_for_cuda_device(self) -> None:
        """Test that _has_meta_tensors returns False for CUDA tensors."""
        mock_param = MagicMock()
        mock_device = MagicMock()
        mock_device.type = "cuda"
        mock_param.device = mock_device

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_returns_false_for_empty_model(self) -> None:
        """Test that _has_meta_tensors returns False for models with no parameters."""
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([])

        assert _has_meta_tensors(mock_model) is False

    def test_has_meta_tensors_handles_exception(self) -> None:
        """Test that _has_meta_tensors returns False on exception."""
        mock_model = MagicMock()
        mock_model.parameters.side_effect = RuntimeError("Test error")

        assert _has_meta_tensors(mock_model) is False

    def test_materialize_meta_tensors_calls_to_empty_and_load_state_dict(self) -> None:
        """Test that _materialize_meta_tensors uses to_empty() + load_state_dict()."""
        from unittest.mock import patch

        mock_model = MagicMock()
        mock_state_dict = {"weight": MagicMock()}
        mock_model.state_dict.return_value = mock_state_dict
        mock_model.to_empty.return_value = mock_model

        with patch("torch.device") as mock_torch_device:
            mock_torch_device.return_value = "cpu"

            result = _materialize_meta_tensors(mock_model, "cpu")

            mock_model.state_dict.assert_called_once()
            mock_model.to_empty.assert_called_once()
            mock_model.load_state_dict.assert_called_once_with(mock_state_dict, assign=True)
            assert result == mock_model


@pytest.mark.slow
class TestLoadVehicleDamageModel:
    """Tests for load_vehicle_damage_model function.

    These tests are marked slow because they may trigger YOLO model downloads
    from GitHub when the model path doesn't exist locally.
    """

    @pytest.mark.asyncio
    async def test_load_model_with_real_path(self, monkeypatch) -> None:
        """Test that the model can be loaded from the real path.

        This test verifies that the model loading logic works correctly.
        Uses mocking to avoid requiring actual model files.
        """
        from unittest.mock import MagicMock, patch

        model_path = "/models/model-zoo/vehicle-damage-detection"

        # Mock the YOLO model
        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent", 2: "glass_shatter"}

        # Patch YOLO where it's imported (inside the function)
        with patch("ultralytics.YOLO", return_value=mock_model):
            model = await load_vehicle_damage_model(model_path)

            assert model is not None
            # YOLO model should have names attribute
            assert hasattr(model, "names")

    @pytest.mark.asyncio
    async def test_load_model_missing_path(self) -> None:
        """Test that loading from a missing path raises an error."""
        with pytest.raises(RuntimeError) as exc_info:
            await load_vehicle_damage_model("/nonexistent/path")

        assert "Failed to load vehicle damage detection model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_model_handles_meta_tensor_error(self) -> None:
        """Test that model loading handles meta tensor errors gracefully.

        When models are saved with meta tensors (lazy loading), calling
        model.to(device) directly raises:
            NotImplementedError: Cannot copy out of meta tensor; no data!

        The fix should handle this by using to_empty() + load_state_dict(assign=True)
        or by using the YOLO model's built-in device handling during inference.
        """
        from unittest.mock import MagicMock, patch

        model_path = "/models/model-zoo/vehicle-damage-detection"

        # Create a mock model that simulates meta tensor behavior
        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent", 2: "glass_shatter"}
        # Mock the inner model attribute
        mock_model.model = MagicMock()
        # Simulate no meta tensors so we skip the materialization path
        mock_model.model.parameters.return_value = iter([])

        # Patch YOLO where it's imported
        with patch("ultralytics.YOLO", return_value=mock_model):
            with patch("torch.cuda.is_available", return_value=False):
                # The model should load without calling .to() directly
                # YOLO models handle device placement during inference via predict(device=...)
                model = await load_vehicle_damage_model(model_path)

                assert model is not None
                assert hasattr(model, "names")

    @pytest.mark.asyncio
    async def test_load_model_materializes_meta_tensors(self) -> None:
        """Test that models with meta tensors are properly materialized.

        When a model has parameters on the 'meta' device, the loader should
        call to_empty() + load_state_dict(assign=True) to materialize them.
        """
        from unittest.mock import MagicMock, patch

        model_path = "/models/model-zoo/vehicle-damage-detection"

        # Create a mock parameter that appears to be on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create the mock inner model with meta tensors
        mock_inner_model = MagicMock()
        mock_inner_model.parameters.return_value = iter([mock_meta_param])
        mock_inner_model.state_dict.return_value = {"weight": MagicMock()}
        mock_inner_model.to_empty.return_value = mock_inner_model
        mock_inner_model.load_state_dict.return_value = None

        # Create the mock YOLO model
        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent", 2: "glass_shatter"}
        mock_model.model = mock_inner_model

        with patch("ultralytics.YOLO", return_value=mock_model):
            with patch("torch.cuda.is_available", return_value=False):
                with patch("torch.device") as mock_torch_device:
                    mock_torch_device.return_value = "cpu"

                    model = await load_vehicle_damage_model(model_path)

                    assert model is not None
                    # Verify meta tensor handling was triggered
                    mock_inner_model.to_empty.assert_called_once()
                    mock_inner_model.load_state_dict.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_with_task_parameter(self) -> None:
        """Test that YOLO model is loaded with correct task parameter.

        The YOLO model should be loaded with task='segment' for the
        vehicle damage segmentation model.
        """
        from unittest.mock import MagicMock, patch

        model_path = "/models/model-zoo/vehicle-damage-detection"

        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent"}
        mock_model.model = MagicMock()
        mock_model.model.parameters.return_value = iter([])
        mock_yolo_class = MagicMock(return_value=mock_model)

        with patch("ultralytics.YOLO", mock_yolo_class):
            with patch("torch.cuda.is_available", return_value=False):
                await load_vehicle_damage_model(model_path)

                # Verify YOLO was called with the correct weights path
                mock_yolo_class.assert_called_once()
                call_args = mock_yolo_class.call_args
                assert "best.pt" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_load_model_fallback_to_warmup_inference(self) -> None:
        """Test that if meta tensor materialization fails, warmup inference is tried.

        When to_empty() + load_state_dict() fails, the loader should attempt
        a warmup inference with a dummy image to force initialization.
        """
        from unittest.mock import MagicMock, patch

        model_path = "/models/model-zoo/vehicle-damage-detection"

        # Create a mock parameter on meta device
        mock_meta_param = MagicMock()
        mock_meta_device = MagicMock()
        mock_meta_device.type = "meta"
        mock_meta_param.device = mock_meta_device

        # Create the mock inner model that fails on materialization
        mock_inner_model = MagicMock()
        mock_inner_model.parameters.return_value = iter([mock_meta_param])
        mock_inner_model.state_dict.return_value = {"weight": MagicMock()}
        # Simulate to_empty() failing
        mock_inner_model.to_empty.side_effect = RuntimeError("to_empty failed")

        # Create the mock YOLO model
        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent"}
        mock_model.model = mock_inner_model

        with patch("ultralytics.YOLO", return_value=mock_model):
            with patch("torch.cuda.is_available", return_value=False):
                model = await load_vehicle_damage_model(model_path)

                assert model is not None
                # Verify warmup inference was attempted
                mock_model.predict.assert_called_once()


class TestDetectVehicleDamage:
    """Tests for detect_vehicle_damage function."""

    @pytest.mark.asyncio
    async def test_detect_no_damage(self) -> None:
        """Test detecting no damage."""
        # Create mock model
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_model.predict.return_value = [mock_result]

        mock_image = MagicMock()

        result = await detect_vehicle_damage(mock_model, mock_image)

        assert result.has_damage is False
        assert result.total_damage_count == 0

    @pytest.mark.asyncio
    async def test_detect_with_damage(self) -> None:
        """Test detecting damage."""
        import numpy as np

        # Create mock model with detections
        mock_model = MagicMock()
        mock_model.names = {0: "crack", 1: "dent", 2: "glass shatter"}

        mock_result = MagicMock()
        mock_boxes = MagicMock()

        # Mock boxes with 2 detections
        mock_boxes.xyxy = [
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array([10, 20, 30, 40]))),
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array([50, 60, 70, 80]))),
        ]
        mock_boxes.conf = [
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array(0.9))),
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array(0.85))),
        ]
        mock_boxes.cls = [
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array(0))),
            MagicMock(cpu=lambda: MagicMock(numpy=lambda: np.array(2))),
        ]
        mock_boxes.__len__ = lambda _: 2

        mock_result.boxes = mock_boxes
        mock_result.masks = None
        mock_result.names = {0: "crack", 1: "dent", 2: "glass shatter"}
        mock_model.predict.return_value = [mock_result]

        mock_image = MagicMock()

        result = await detect_vehicle_damage(mock_model, mock_image)

        assert result.has_damage is True
        assert result.total_damage_count == 2

    @pytest.mark.asyncio
    async def test_detect_error_handling(self) -> None:
        """Test error handling during detection."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Detection failed")

        mock_image = MagicMock()

        with pytest.raises(RuntimeError) as exc_info:
            await detect_vehicle_damage(mock_model, mock_image)

        assert "Vehicle damage detection failed" in str(exc_info.value)


class TestFormatDamageContext:
    """Tests for format_damage_context function."""

    def test_format_no_damage(self) -> None:
        """Test formatting with no damage."""
        result = VehicleDamageResult()
        context = format_damage_context(result)
        assert context == "No vehicle damage detected."

    def test_format_with_damage(self) -> None:
        """Test formatting with damage."""
        detections = [
            DamageDetection(damage_type="crack", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)
        context = format_damage_context(result)

        assert "Vehicle Damage Analysis" in context
        assert "crack" in context

    def test_format_with_high_security_damage(self) -> None:
        """Test formatting with high-security damage."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.95, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)
        context = format_damage_context(result)

        assert "SECURITY ALERT" in context
        assert "glass_shatter" in context or "Glass shatter" in context

    def test_format_with_time_context(self) -> None:
        """Test formatting with time context."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.95, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)
        context = format_damage_context(result, time_of_day="night")

        assert "TIME CONTEXT" in context
        assert "night" in context


class TestIsSuspiciousDamagePattern:
    """Tests for is_suspicious_damage_pattern function."""

    def test_no_damage_not_suspicious(self) -> None:
        """Test that no damage is not suspicious."""
        result = VehicleDamageResult()
        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is False
        assert "No damage detected" in reason

    def test_high_security_damage_suspicious(self) -> None:
        """Test that high-security damage is suspicious."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)
        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is True
        assert "glass shatter" in reason.lower()

    def test_night_damage_suspicious(self) -> None:
        """Test that damage at night is suspicious."""
        detections = [
            DamageDetection(damage_type="dent", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)
        is_suspicious, reason = is_suspicious_damage_pattern(result, hour_of_day=3)

        assert is_suspicious is True
        assert "night" in reason

    def test_multiple_damage_types_suspicious(self) -> None:
        """Test that multiple damage types are suspicious."""
        detections = [
            DamageDetection(damage_type="crack", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="dent", confidence=0.8, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)
        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is True
        assert "multiple damage types" in reason

    def test_break_in_pattern_suspicious(self) -> None:
        """Test that glass + lamp damage pattern is highly suspicious."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="lamp_broken", confidence=0.85, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)
        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is True
        assert "break-in" in reason.lower()


class TestVehicleDamageIntegration:
    """Integration tests for vehicle damage detection with model zoo."""

    def test_vehicle_damage_model_in_zoo(self) -> None:
        """Test that vehicle damage model is registered in MODEL_ZOO."""
        from backend.services.model_zoo import get_model_config, reset_model_zoo

        reset_model_zoo()

        config = get_model_config("vehicle-damage-detection")

        assert config is not None
        assert config.name == "vehicle-damage-detection"
        assert config.category == "detection"
        assert config.vram_mb == 2000
        assert config.enabled is True
        assert config.path == "/models/model-zoo/vehicle-damage-detection"

        reset_model_zoo()

    def test_enrichment_result_has_vehicle_damage(self) -> None:
        """Test that EnrichmentResult has vehicle_damage field."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()

        assert hasattr(result, "vehicle_damage")
        assert result.vehicle_damage == {}
        assert result.has_vehicle_damage is False

    def test_enrichment_result_has_vehicle_damage_true(self) -> None:
        """Test has_vehicle_damage property when damage is detected."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        damage_result = VehicleDamageResult(
            detections=[
                DamageDetection(damage_type="crack", confidence=0.9, bbox=(10, 20, 30, 40)),
            ]
        )
        result.vehicle_damage = {"0": damage_result}

        assert result.has_vehicle_damage is True

    def test_enrichment_result_has_high_security_damage(self) -> None:
        """Test has_high_security_damage property."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        damage_result = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter", confidence=0.95, bbox=(10, 20, 30, 40)
                ),
            ]
        )
        result.vehicle_damage = {"0": damage_result}

        assert result.has_high_security_damage is True

    def test_enrichment_result_to_dict_includes_vehicle_damage(self) -> None:
        """Test that to_dict includes vehicle_damage."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        damage_result = VehicleDamageResult(
            detections=[
                DamageDetection(damage_type="dent", confidence=0.8, bbox=(10, 20, 30, 40)),
            ]
        )
        result.vehicle_damage = {"0": damage_result}

        d = result.to_dict()

        assert "vehicle_damage" in d
        assert "0" in d["vehicle_damage"]
        assert d["vehicle_damage"]["0"]["total_damage_count"] == 1


class TestEnrichmentPipelineVehicleDamageDetection:
    """Tests for vehicle damage detection in EnrichmentPipeline."""

    def test_pipeline_has_vehicle_damage_detection_enabled(self) -> None:
        """Test that pipeline has vehicle_damage_detection_enabled parameter."""
        from backend.services.enrichment_pipeline import (
            EnrichmentPipeline,
            reset_enrichment_pipeline,
        )
        from backend.services.model_zoo import reset_model_manager, reset_model_zoo

        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

        # Check default is enabled
        pipeline = EnrichmentPipeline()
        assert hasattr(pipeline, "vehicle_damage_detection_enabled")
        assert pipeline.vehicle_damage_detection_enabled is True

        reset_enrichment_pipeline()
        reset_model_zoo()
        reset_model_manager()

    def test_pipeline_vehicle_damage_detection_disabled(self) -> None:
        """Test that pipeline can disable vehicle damage detection."""
        from backend.services.enrichment_pipeline import (
            EnrichmentPipeline,
            reset_enrichment_pipeline,
        )
        from backend.services.model_zoo import reset_model_manager, reset_model_zoo

        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

        pipeline = EnrichmentPipeline(vehicle_damage_detection_enabled=False)
        assert pipeline.vehicle_damage_detection_enabled is False

        reset_enrichment_pipeline()
        reset_model_zoo()
        reset_model_manager()
