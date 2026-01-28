"""Unit tests for Model Zoo and EnrichmentPipeline.

Tests cover:
- ModelConfig dataclass
- MODEL_ZOO registry initialization and access
- ModelManager context manager operations
- ModelManager reference counting
- EnrichmentPipeline detection filtering
- EnrichmentResult data structures
- BoundingBox operations
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    FaceResult,
    LicensePlateResult,
    get_enrichment_pipeline,
    reset_enrichment_pipeline,
)
from backend.services.model_zoo import (
    ModelConfig,
    ModelManager,
    get_available_models,
    get_enabled_models,
    get_model_config,
    get_model_manager,
    get_model_zoo,
    get_total_vram_if_loaded,
    reset_model_manager,
    reset_model_zoo,
)


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_model_config_creation(self) -> None:
        """Test creating a ModelConfig with all fields."""

        async def mock_load(path: str) -> Any:
            return MagicMock()

        config = ModelConfig(
            name="test-model",
            path="test/path",
            category="detection",
            vram_mb=500,
            load_fn=mock_load,
        )

        assert config.name == "test-model"
        assert config.path == "test/path"
        assert config.category == "detection"
        assert config.vram_mb == 500
        assert config.enabled is True  # Default
        assert config.available is False  # Default

    def test_model_config_disabled(self) -> None:
        """Test creating a disabled model config."""

        async def mock_load(path: str) -> Any:
            return MagicMock()

        config = ModelConfig(
            name="disabled-model",
            path="test/path",
            category="detection",
            vram_mb=400,
            load_fn=mock_load,
            enabled=False,
        )

        assert config.enabled is False


class TestModelZoo:
    """Tests for MODEL_ZOO registry functions."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()

    def test_get_model_zoo_initializes(self) -> None:
        """Test that get_model_zoo initializes the registry."""
        zoo = get_model_zoo()

        assert "yolo11-license-plate" in zoo
        assert "yolo11-face" in zoo
        assert "paddleocr" in zoo
        assert "yolo26-general" in zoo

    def test_get_model_config_found(self) -> None:
        """Test getting a model config that exists."""
        config = get_model_config("yolo11-license-plate")

        assert config is not None
        assert config.name == "yolo11-license-plate"
        assert config.category == "detection"
        assert config.vram_mb == 300

    def test_get_model_config_not_found(self) -> None:
        """Test getting a model config that doesn't exist."""
        config = get_model_config("nonexistent-model")
        assert config is None

    def test_get_enabled_models(self) -> None:
        """Test getting list of enabled models."""
        enabled = get_enabled_models()

        # yolo26-general is disabled by default
        enabled_names = [m.name for m in enabled]
        assert "yolo11-license-plate" in enabled_names
        assert "yolo11-face" in enabled_names
        assert "paddleocr" in enabled_names
        assert "yolo26-general" not in enabled_names

    def test_get_total_vram_if_loaded(self) -> None:
        """Test VRAM calculation for specified models."""
        total = get_total_vram_if_loaded(["yolo11-license-plate", "yolo11-face"])

        # 300 + 200 = 500
        assert total == 500

    def test_get_total_vram_with_unknown_model(self) -> None:
        """Test VRAM calculation ignores unknown models."""
        total = get_total_vram_if_loaded(["yolo11-license-plate", "unknown"])

        assert total == 300  # Only license plate counted

    def test_get_available_models_initially_empty(self) -> None:
        """Test that no models are available initially."""
        available = get_available_models()

        # All models start with available=False
        assert len(available) == 0

    def test_get_available_models_after_marking_available(self) -> None:
        """Test get_available_models after marking a model as available."""
        zoo = get_model_zoo()

        # Mark a model as available
        zoo["yolo11-license-plate"].available = True

        available = get_available_models()
        available_names = [m.name for m in available]

        assert "yolo11-license-plate" in available_names
        assert len(available) == 1


class TestModelManager:
    """Tests for ModelManager class."""

    def setup_method(self) -> None:
        """Reset managers before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset managers after each test."""
        reset_model_zoo()
        reset_model_manager()

    def test_model_manager_init(self) -> None:
        """Test ModelManager initialization."""
        manager = ModelManager()

        assert manager.loaded_models == []
        assert manager.total_loaded_vram == 0

    def test_is_loaded_false_initially(self) -> None:
        """Test that no models are loaded initially."""
        manager = ModelManager()

        assert manager.is_loaded("yolo11-license-plate") is False
        assert manager.is_loaded("yolo11-face") is False

    @pytest.mark.asyncio
    async def test_load_context_manager_success(self) -> None:
        """Test successful model loading via context manager."""
        manager = ModelManager()
        mock_model = MagicMock()

        # Mock the load function in the model config
        async def mock_load(path: str) -> Any:
            return mock_model

        # Patch the model config's load_fn
        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            async with manager.load("yolo11-license-plate") as model:
                assert model is mock_model
                assert manager.is_loaded("yolo11-license-plate")

            # After context exits, model should be unloaded
            assert not manager.is_loaded("yolo11-license-plate")

    @pytest.mark.asyncio
    async def test_load_unknown_model_raises(self) -> None:
        """Test that loading unknown model raises KeyError."""
        manager = ModelManager()

        with pytest.raises(KeyError, match="Unknown model"):
            async with manager.load("nonexistent-model"):
                pass

    @pytest.mark.asyncio
    async def test_load_disabled_model_raises(self) -> None:
        """Test that loading disabled model raises RuntimeError."""
        manager = ModelManager()

        with pytest.raises(RuntimeError, match="disabled"):
            async with manager.load("yolo26-general"):
                pass

    @pytest.mark.asyncio
    async def test_reference_counting_nested_loads(self) -> None:
        """Test that nested loads of same model use reference counting."""
        manager = ModelManager()
        mock_model = MagicMock()
        load_count = 0

        async def mock_load(path: str) -> Any:
            nonlocal load_count
            load_count += 1
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            async with manager.load("yolo11-license-plate") as model1:
                async with manager.load("yolo11-license-plate") as model2:
                    assert model1 is model2
                    assert manager.is_loaded("yolo11-license-plate")

                # Still loaded due to outer context
                assert manager.is_loaded("yolo11-license-plate")

            # Now unloaded
            assert not manager.is_loaded("yolo11-license-plate")

        # Should only have loaded once
        assert load_count == 1

    @pytest.mark.asyncio
    async def test_preload_and_unload(self) -> None:
        """Test explicit preload and unload."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-face"),
            "load_fn",
            mock_load,
        ):
            await manager.preload("yolo11-face")
            assert manager.is_loaded("yolo11-face")

            await manager.unload("yolo11-face")
            assert not manager.is_loaded("yolo11-face")

    @pytest.mark.asyncio
    async def test_unload_all(self) -> None:
        """Test unloading all models."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with (
            patch.object(
                get_model_config("yolo11-face"),
                "load_fn",
                mock_load,
            ),
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load,
            ),
        ):
            await manager.preload("yolo11-face")
            await manager.preload("yolo11-license-plate")

            assert len(manager.loaded_models) == 2

            await manager.unload_all()

            assert len(manager.loaded_models) == 0

    def test_get_status(self) -> None:
        """Test getting manager status."""
        manager = ModelManager()
        status = manager.get_status()

        assert "loaded_models" in status
        assert "total_loaded_vram_mb" in status
        assert "load_counts" in status
        assert status["loaded_models"] == []
        assert status["total_loaded_vram_mb"] == 0

    def test_global_model_manager(self) -> None:
        """Test global model manager singleton."""
        manager1 = get_model_manager()
        manager2 = get_model_manager()

        assert manager1 is manager2

        reset_model_manager()

        manager3 = get_model_manager()
        assert manager3 is not manager1

    @pytest.mark.asyncio
    async def test_cuda_cache_cleared_on_unload(self) -> None:
        """Test that CUDA cache is cleared when model is unloaded."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with (
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load,
            ),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            async with manager.load("yolo11-license-plate"):
                pass  # Model is loaded here

            # CUDA cache should be cleared after unload
            mock_torch.cuda.empty_cache.assert_called()

    @pytest.mark.asyncio
    async def test_cuda_cache_cleared_on_unload_all(self) -> None:
        """Test that CUDA cache is cleared when all models are unloaded."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with (
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load,
            ),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            await manager.preload("yolo11-license-plate")
            await manager.unload_all()

            # CUDA cache should be cleared after unload_all
            mock_torch.cuda.empty_cache.assert_called()

    @pytest.mark.asyncio
    async def test_cuda_not_available_no_error(self) -> None:
        """Test that unload works when CUDA is not available."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with (
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load,
            ),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            async with manager.load("yolo11-license-plate"):
                pass

            # Should not call empty_cache when CUDA not available
            mock_torch.cuda.empty_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_torch_not_installed_no_error(self) -> None:
        """Test that unload works when torch is not installed."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            # Mock torch import to raise ImportError
            original_import = __builtins__["__import__"]

            def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
                if name == "torch":
                    raise ImportError("No module named 'torch'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                # This should not raise even when torch is not installed
                async with manager.load("yolo11-license-plate"):
                    pass

    @pytest.mark.asyncio
    async def test_load_failure_propagates_exception(self) -> None:
        """Test that load failure propagates the exception."""
        manager = ModelManager()

        async def failing_load(path: str) -> Any:
            raise ValueError("Model loading failed!")

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            failing_load,
        ):
            with pytest.raises(ValueError, match="Model loading failed!"):
                async with manager.load("yolo11-license-plate"):
                    pass

            # Model should not be in loaded list after failure
            assert not manager.is_loaded("yolo11-license-plate")

    @pytest.mark.asyncio
    async def test_available_flag_set_after_successful_load(self) -> None:
        """Test that model config available flag is set after successful load."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        config = get_model_config("yolo11-license-plate")
        assert config is not None
        assert config.available is False

        with patch.object(config, "load_fn", mock_load):
            async with manager.load("yolo11-license-plate"):
                # Available flag should be set during load
                assert config.available is True

    @pytest.mark.asyncio
    async def test_total_loaded_vram_with_models(self) -> None:
        """Test total_loaded_vram property with loaded models."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with (
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load,
            ),
            patch.object(
                get_model_config("yolo11-face"),
                "load_fn",
                mock_load,
            ),
        ):
            await manager.preload("yolo11-license-plate")
            assert manager.total_loaded_vram == 300

            await manager.preload("yolo11-face")
            assert manager.total_loaded_vram == 500  # 300 + 200

            await manager.unload("yolo11-license-plate")
            assert manager.total_loaded_vram == 200

            await manager.unload("yolo11-face")
            assert manager.total_loaded_vram == 0

    @pytest.mark.asyncio
    async def test_unload_nonexistent_model_no_error(self) -> None:
        """Test that unloading a non-existent model doesn't raise."""
        manager = ModelManager()

        # Should not raise
        await manager.unload("nonexistent-model")
        assert not manager.is_loaded("nonexistent-model")

    @pytest.mark.asyncio
    async def test_get_status_with_loaded_models(self) -> None:
        """Test get_status with loaded models."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            await manager.preload("yolo11-license-plate")

            status = manager.get_status()

            assert "yolo11-license-plate" in status["loaded_models"]
            assert status["total_loaded_vram_mb"] == 300
            assert status["load_counts"]["yolo11-license-plate"] == 1

    @pytest.mark.asyncio
    async def test_preload_already_loaded_no_duplicate(self) -> None:
        """Test that preloading an already loaded model doesn't duplicate it."""
        manager = ModelManager()
        mock_model = MagicMock()
        load_count = 0

        async def mock_load(path: str) -> Any:
            nonlocal load_count
            load_count += 1
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            await manager.preload("yolo11-license-plate")
            await manager.preload("yolo11-license-plate")

            # Should only load once
            assert load_count == 1
            assert len(manager.loaded_models) == 1


class TestModelManagerMetrics:
    """Tests for ModelManager metrics instrumentation (NEM-4145)."""

    def setup_method(self) -> None:
        """Reset managers before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset managers after each test."""
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_load_duration_metric_recorded(self) -> None:
        """Test that load duration metric is recorded when model loads."""
        from backend.core.metrics import MODEL_LOAD_DURATION

        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            # Simulate some load time
            await asyncio.sleep(0.01)
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            async with manager.load("yolo11-license-plate"):
                pass

        # Verify load duration was recorded (should be at least 10ms)
        value = MODEL_LOAD_DURATION.labels(model="yolo11-license-plate")._value.get()
        assert value >= 0.01

    @pytest.mark.asyncio
    async def test_restart_metric_not_recorded_on_first_load(self) -> None:
        """Test that restart metric is not recorded on first model load."""
        from backend.core.metrics import MODEL_RESTARTS_TOTAL

        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        # Get initial restart count
        initial_count = MODEL_RESTARTS_TOTAL.labels(
            model="yolo11-face", reason="manual"
        )._value.get()

        with patch.object(
            get_model_config("yolo11-face"),
            "load_fn",
            mock_load,
        ):
            async with manager.load("yolo11-face"):
                pass

        # Restart count should not have changed
        final_count = MODEL_RESTARTS_TOTAL.labels(model="yolo11-face", reason="manual")._value.get()
        assert final_count == initial_count

    @pytest.mark.asyncio
    async def test_restart_metric_recorded_on_reload(self) -> None:
        """Test that restart metric is recorded when model is reloaded."""
        from backend.core.metrics import MODEL_RESTARTS_TOTAL

        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            # First load
            async with manager.load("yolo11-license-plate"):
                pass

            # Get restart count after first load
            initial_count = MODEL_RESTARTS_TOTAL.labels(
                model="yolo11-license-plate", reason="manual"
            )._value.get()

            # Second load (reload) - model was previously loaded
            async with manager.load("yolo11-license-plate"):
                pass

        # Restart count should have incremented
        final_count = MODEL_RESTARTS_TOTAL.labels(
            model="yolo11-license-plate", reason="manual"
        )._value.get()
        assert final_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_reload_with_specific_reason(self) -> None:
        """Test reload method records restart with specific reason."""
        from backend.core.metrics import MODEL_RESTARTS_TOTAL

        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-face"),
            "load_fn",
            mock_load,
        ):
            # First load
            await manager.preload("yolo11-face")

            # Get initial counts for different reasons
            initial_oom = MODEL_RESTARTS_TOTAL.labels(
                model="yolo11-face", reason="oom"
            )._value.get()
            initial_crash = MODEL_RESTARTS_TOTAL.labels(
                model="yolo11-face", reason="crash"
            )._value.get()

            # Reload with OOM reason
            await manager.reload("yolo11-face", "oom")

            # OOM count should have incremented
            assert (
                MODEL_RESTARTS_TOTAL.labels(model="yolo11-face", reason="oom")._value.get()
                == initial_oom + 1
            )

            # Crash count should not have changed
            assert (
                MODEL_RESTARTS_TOTAL.labels(model="yolo11-face", reason="crash")._value.get()
                == initial_crash
            )

            await manager.unload("yolo11-face")

    @pytest.mark.asyncio
    async def test_reload_with_invalid_reason_raises(self) -> None:
        """Test that reload with invalid reason raises ValueError."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            await manager.preload("yolo11-license-plate")

            with pytest.raises(ValueError, match="Invalid restart reason"):
                await manager.reload("yolo11-license-plate", "invalid_reason")

            await manager.unload("yolo11-license-plate")

    @pytest.mark.asyncio
    async def test_reload_all_valid_reasons(self) -> None:
        """Test reload works with all valid restart reasons."""
        from backend.core.metrics import MODEL_RESTART_REASONS

        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            # First load
            await manager.preload("yolo11-license-plate")

            # Test all valid reasons
            for reason in MODEL_RESTART_REASONS:
                model = await manager.reload("yolo11-license-plate", reason)
                assert model is mock_model

            await manager.unload("yolo11-license-plate")

    @pytest.mark.asyncio
    async def test_previously_loaded_tracking(self) -> None:
        """Test that previously_loaded set tracks models correctly."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        # Initially empty
        assert len(manager._previously_loaded) == 0

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            async with manager.load("yolo11-license-plate"):
                pass

        # Should be tracked after load
        assert "yolo11-license-plate" in manager._previously_loaded

        # Should still be tracked even after unload
        assert "yolo11-license-plate" in manager._previously_loaded

    @pytest.mark.asyncio
    async def test_load_duration_updates_on_reload(self) -> None:
        """Test that load duration metric updates on reload."""
        from backend.core.metrics import MODEL_LOAD_DURATION

        manager = ModelManager()
        mock_model = MagicMock()
        load_times = [0.05, 0.03]  # Different load times
        load_index = [0]

        async def mock_load(path: str) -> Any:
            await asyncio.sleep(load_times[load_index[0]])
            load_index[0] = min(load_index[0] + 1, len(load_times) - 1)
            return mock_model

        with patch.object(
            get_model_config("yolo11-face"),
            "load_fn",
            mock_load,
        ):
            # First load
            async with manager.load("yolo11-face"):
                first_duration = MODEL_LOAD_DURATION.labels(model="yolo11-face")._value.get()
                assert first_duration >= 0.05

            # Second load
            async with manager.load("yolo11-face"):
                second_duration = MODEL_LOAD_DURATION.labels(model="yolo11-face")._value.get()
                # Should be updated to the new (shorter) load time
                assert second_duration >= 0.03


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_bounding_box_creation(self) -> None:
        """Test creating a bounding box."""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=150, confidence=0.95)

        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 100
        assert bbox.y2 == 150
        assert bbox.confidence == 0.95

    def test_bounding_box_to_tuple(self) -> None:
        """Test conversion to tuple."""
        bbox = BoundingBox(x1=10.5, y1=20.5, x2=100.5, y2=150.5)
        assert bbox.to_tuple() == (10.5, 20.5, 100.5, 150.5)

    def test_bounding_box_to_int_tuple(self) -> None:
        """Test conversion to integer tuple."""
        bbox = BoundingBox(x1=10.5, y1=20.5, x2=100.5, y2=150.5)
        assert bbox.to_int_tuple() == (10, 20, 100, 150)

    def test_bounding_box_width_height(self) -> None:
        """Test width and height properties."""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=150)

        assert bbox.width == 90
        assert bbox.height == 130

    def test_bounding_box_center(self) -> None:
        """Test center point calculation."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        assert bbox.center == (50, 50)


class TestLicensePlateResult:
    """Tests for LicensePlateResult dataclass."""

    def test_license_plate_result_creation(self) -> None:
        """Test creating a license plate result."""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=50)
        result = LicensePlateResult(
            bbox=bbox,
            text="ABC123",
            confidence=0.95,
            ocr_confidence=0.87,
            source_detection_id=42,
        )

        assert result.text == "ABC123"
        assert result.confidence == 0.95
        assert result.ocr_confidence == 0.87
        assert result.source_detection_id == 42


class TestFaceResult:
    """Tests for FaceResult dataclass."""

    def test_face_result_creation(self) -> None:
        """Test creating a face result."""
        bbox = BoundingBox(x1=50, y1=60, x2=150, y2=180)
        result = FaceResult(
            bbox=bbox,
            confidence=0.92,
            source_detection_id=101,
        )

        assert result.confidence == 0.92
        assert result.source_detection_id == 101


class TestEnrichmentResult:
    """Tests for EnrichmentResult dataclass."""

    def test_empty_result(self) -> None:
        """Test empty enrichment result."""
        result = EnrichmentResult()

        assert result.license_plates == []
        assert result.faces == []
        assert result.errors == []
        assert result.processing_time_ms == 0.0
        assert result.has_license_plates is False
        assert result.has_readable_plates is False
        assert result.has_faces is False

    def test_has_license_plates(self) -> None:
        """Test has_license_plates property."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="",
            )
        )

        assert result.has_license_plates is True
        assert result.has_readable_plates is False

    def test_has_readable_plates(self) -> None:
        """Test has_readable_plates property."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="ABC123",
            )
        )

        assert result.has_readable_plates is True

    def test_plate_texts(self) -> None:
        """Test plate_texts property."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="ABC123",
            )
        )
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="",  # Empty
            )
        )
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="XYZ789",
            )
        )

        assert result.plate_texts == ["ABC123", "XYZ789"]

    def test_to_context_string_empty(self) -> None:
        """Test context string for empty result."""
        result = EnrichmentResult()
        assert result.to_context_string() == "No additional context extracted."

    def test_to_context_string_with_plates(self) -> None:
        """Test context string with license plates."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="ABC123",
                ocr_confidence=0.95,
            )
        )

        context = result.to_context_string()
        assert "License Plates (1 detected)" in context
        assert "ABC123" in context
        assert "95%" in context

    def test_to_context_string_with_unreadable_plate(self) -> None:
        """Test context string with unreadable plate."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="",
            )
        )

        context = result.to_context_string()
        assert "[unreadable]" in context

    def test_to_context_string_with_faces(self) -> None:
        """Test context string with faces."""
        result = EnrichmentResult()
        result.faces.append(
            FaceResult(
                bbox=BoundingBox(x1=50, y1=60, x2=150, y2=180),
                confidence=0.88,
            )
        )

        context = result.to_context_string()
        assert "Faces (1 detected)" in context
        assert "88%" in context

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = EnrichmentResult()
        result.license_plates.append(
            LicensePlateResult(
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=50),
                text="ABC123",
                confidence=0.9,
                ocr_confidence=0.85,
            )
        )
        result.processing_time_ms = 150.5

        d = result.to_dict()

        assert "license_plates" in d
        assert len(d["license_plates"]) == 1
        assert d["license_plates"][0]["text"] == "ABC123"
        assert d["processing_time_ms"] == 150.5


class TestDetectionInput:
    """Tests for DetectionInput dataclass."""

    def test_detection_input_creation(self) -> None:
        """Test creating a detection input."""
        bbox = BoundingBox(x1=0, y1=0, x2=200, y2=300)
        detection = DetectionInput(
            class_name="car",
            confidence=0.92,
            bbox=bbox,
            id=123,
        )

        assert detection.class_name == "car"
        assert detection.confidence == 0.92
        assert detection.id == 123


class TestEnrichmentPipeline:
    """Tests for EnrichmentPipeline class."""

    def setup_method(self) -> None:
        """Reset pipelines before each test."""
        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

    def teardown_method(self) -> None:
        """Reset pipelines after each test."""
        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

    def test_pipeline_init(self) -> None:
        """Test pipeline initialization."""
        pipeline = EnrichmentPipeline()

        assert pipeline.min_confidence == 0.5
        assert pipeline.license_plate_enabled is True
        assert pipeline.face_detection_enabled is True
        assert pipeline.ocr_enabled is True

    def test_pipeline_init_custom(self) -> None:
        """Test pipeline initialization with custom settings."""
        pipeline = EnrichmentPipeline(
            min_confidence=0.7,
            license_plate_enabled=False,
            face_detection_enabled=True,
            ocr_enabled=False,
        )

        assert pipeline.min_confidence == 0.7
        assert pipeline.license_plate_enabled is False
        assert pipeline.ocr_enabled is False

    @pytest.mark.asyncio
    async def test_enrich_batch_empty(self) -> None:
        """Test enriching empty batch."""
        pipeline = EnrichmentPipeline()
        result = await pipeline.enrich_batch([], {})

        assert result.license_plates == []
        assert result.faces == []

    @pytest.mark.asyncio
    async def test_enrich_batch_low_confidence_filtered(self) -> None:
        """Test that low confidence detections are filtered."""
        pipeline = EnrichmentPipeline(min_confidence=0.5)

        detections = [
            DetectionInput(
                class_name="car",
                confidence=0.3,  # Below threshold
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
            )
        ]

        result = await pipeline.enrich_batch(detections, {})

        # Should not attempt to detect license plates for low confidence
        assert result.license_plates == []

    @pytest.mark.asyncio
    async def test_enrich_batch_filters_vehicles(self) -> None:
        """Test that only vehicle classes trigger license plate detection."""
        mock_manager = AsyncMock(spec=ModelManager)
        pipeline = EnrichmentPipeline(
            model_manager=mock_manager,
            license_plate_enabled=True,
            face_detection_enabled=False,
        )

        # Mock the context manager
        mock_model = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_model
        mock_context.__aexit__.return_value = None
        mock_manager.load.return_value = mock_context

        # Non-vehicle detection should not trigger plate detection
        detections = [
            DetectionInput(
                class_name="dog",
                confidence=0.9,
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
            )
        ]

        result = await pipeline.enrich_batch(detections, {})

        # Should not have loaded the license plate model
        mock_manager.load.assert_not_called()
        assert result.license_plates == []

    @pytest.mark.asyncio
    async def test_enrich_batch_filters_persons(self) -> None:
        """Test that only person class triggers face detection."""
        mock_manager = AsyncMock(spec=ModelManager)
        pipeline = EnrichmentPipeline(
            model_manager=mock_manager,
            license_plate_enabled=False,
            face_detection_enabled=True,
        )

        # Mock the context manager
        mock_model = MagicMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_model
        mock_context.__aexit__.return_value = None
        mock_manager.load.return_value = mock_context

        # Non-person detection should not trigger face detection
        detections = [
            DetectionInput(
                class_name="car",
                confidence=0.9,
                bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
            )
        ]

        result = await pipeline.enrich_batch(detections, {})

        # Should not have loaded the face model
        mock_manager.load.assert_not_called()
        assert result.faces == []

    def test_global_enrichment_pipeline(self) -> None:
        """Test global enrichment pipeline singleton."""
        pipeline1 = get_enrichment_pipeline()
        pipeline2 = get_enrichment_pipeline()

        assert pipeline1 is pipeline2

        reset_enrichment_pipeline()

        pipeline3 = get_enrichment_pipeline()
        assert pipeline3 is not pipeline1


class TestModelZooLoadFunctions:
    """Tests for model loading functions."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()

    @pytest.mark.asyncio
    async def test_load_yolo_model_import_error(self) -> None:
        """Test that load_yolo_model raises ImportError when ultralytics missing."""
        from backend.services.model_zoo import load_yolo_model

        with patch.dict("sys.modules", {"ultralytics": None}):
            # Remove ultralytics from sys.modules to trigger ImportError
            import sys

            if "ultralytics" in sys.modules:
                del sys.modules["ultralytics"]

            # Mock the import to raise ImportError
            with (
                patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'ultralytics'"),
                ),
                pytest.raises(ImportError),
            ):
                await load_yolo_model("test/path")

    @pytest.mark.asyncio
    async def test_load_yolo_model_runtime_error(self) -> None:
        """Test that load_yolo_model raises RuntimeError on load failure."""
        from backend.services.model_zoo import load_yolo_model

        mock_yolo = MagicMock()
        mock_yolo.side_effect = ValueError("Invalid model path")

        with (
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo)}),
            pytest.raises(RuntimeError, match="Failed to load YOLO model"),
        ):
            await load_yolo_model("invalid/path")

    @pytest.mark.asyncio
    async def test_load_paddle_ocr_not_installed(self) -> None:
        """Test that load_paddle_ocr raises RuntimeError when paddleocr not installed.

        PaddleOCR is an optional dependency. When not installed, the loader raises
        RuntimeError (not ImportError) to enable graceful degradation without
        logging full tracebacks.
        """
        from backend.services.model_zoo import load_paddle_ocr

        # Mock _is_paddleocr_available to return False
        with (
            patch(
                "backend.services.model_zoo._is_paddleocr_available",
                return_value=False,
            ),
            pytest.raises(RuntimeError, match="paddleocr package not installed"),
        ):
            await load_paddle_ocr("test/config")

    @pytest.mark.asyncio
    async def test_load_paddle_ocr_runtime_error(self) -> None:
        """Test that load_paddle_ocr raises RuntimeError on load failure."""
        from backend.services.model_zoo import load_paddle_ocr

        mock_paddleocr_module = MagicMock()
        mock_paddleocr_class = MagicMock()
        mock_paddleocr_class.side_effect = ValueError("PaddleOCR initialization failed")
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        # Mock both the availability check and the module import
        with (
            patch(
                "backend.services.model_zoo._is_paddleocr_available",
                return_value=True,
            ),
            patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}),
            pytest.raises(RuntimeError, match="Failed to load PaddleOCR"),
        ):
            await load_paddle_ocr("config/path")


class TestPaddleocrAvailability:
    """Tests for PaddleOCR availability checking."""

    def test_is_paddleocr_available_when_not_installed(self) -> None:
        """Test _is_paddleocr_available returns False when paddleocr not installed."""
        from backend.services.model_zoo import _is_paddleocr_available

        # Mock find_spec to return None (module not found)
        with patch("importlib.util.find_spec", return_value=None):
            assert _is_paddleocr_available() is False

    def test_is_paddleocr_available_when_installed(self) -> None:
        """Test _is_paddleocr_available returns True when paddleocr is installed."""
        from backend.services.model_zoo import _is_paddleocr_available

        # Mock find_spec to return a spec (module found)
        mock_spec = MagicMock()
        with patch("importlib.util.find_spec", return_value=mock_spec):
            assert _is_paddleocr_available() is True

    def test_is_paddleocr_available_handles_import_error(self) -> None:
        """Test _is_paddleocr_available handles ImportError gracefully."""
        from backend.services.model_zoo import _is_paddleocr_available

        # Mock find_spec to raise ImportError
        with patch("importlib.util.find_spec", side_effect=ImportError("test")):
            assert _is_paddleocr_available() is False


class TestOptionalDependencyHandling:
    """Tests for graceful handling of missing optional dependencies."""

    def setup_method(self) -> None:
        """Reset managers before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset managers after each test."""
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_load_paddleocr_logs_info_when_not_installed(self) -> None:
        """Test that loading paddleocr when not installed logs at INFO level, not ERROR."""
        manager = ModelManager()

        # Mock paddleocr as unavailable
        with (
            patch(
                "backend.services.model_zoo._is_paddleocr_available",
                return_value=False,
            ),
            pytest.raises(RuntimeError, match="paddleocr package not installed"),
        ):
            await manager.preload("paddleocr")

        # Model should not be loaded
        assert not manager.is_loaded("paddleocr")


class TestConcurrentModelLoading:
    """Tests for concurrent model loading scenarios."""

    def setup_method(self) -> None:
        """Reset managers before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset managers after each test."""
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_concurrent_load_same_model(self) -> None:
        """Test concurrent loads of the same model."""
        manager = ModelManager()
        mock_model = MagicMock()
        load_count = 0

        async def mock_load(path: str) -> Any:
            nonlocal load_count
            load_count += 1
            await asyncio.sleep(0.01)  # Simulate loading time
            return mock_model

        with patch.object(
            get_model_config("yolo11-license-plate"),
            "load_fn",
            mock_load,
        ):
            # Start two concurrent loads
            async def load_task() -> Any:
                async with manager.load("yolo11-license-plate") as model:
                    await asyncio.sleep(0.05)
                    return model

            results = await asyncio.gather(load_task(), load_task())

            # Both should get the same model
            assert results[0] is mock_model
            assert results[1] is mock_model

        # Model should be loaded only once
        assert load_count == 1

    @pytest.mark.asyncio
    async def test_load_multiple_models_sequentially(self) -> None:
        """Test loading multiple different models."""
        manager = ModelManager()
        mock_models = {}

        async def mock_load_plate(path: str) -> Any:
            mock_models["plate"] = MagicMock(name="plate_model")
            return mock_models["plate"]

        async def mock_load_face(path: str) -> Any:
            mock_models["face"] = MagicMock(name="face_model")
            return mock_models["face"]

        with (
            patch.object(
                get_model_config("yolo11-license-plate"),
                "load_fn",
                mock_load_plate,
            ),
            patch.object(
                get_model_config("yolo11-face"),
                "load_fn",
                mock_load_face,
            ),
        ):
            async with manager.load("yolo11-license-plate") as plate_model:
                assert plate_model is mock_models["plate"]
                assert manager.is_loaded("yolo11-license-plate")

            async with manager.load("yolo11-face") as face_model:
                assert face_model is mock_models["face"]
                assert manager.is_loaded("yolo11-face")

            # Both should be unloaded now
            assert not manager.is_loaded("yolo11-license-plate")
            assert not manager.is_loaded("yolo11-face")


class TestYoloWorldLoader:
    """Tests for YOLO-World model loader and detection functions."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()
        reset_model_manager()

    def test_yolo_world_model_in_zoo(self) -> None:
        """Test that yolo-world-s is registered in the model zoo."""
        zoo = get_model_zoo()

        assert "yolo-world-s" in zoo
        config = zoo["yolo-world-s"]
        assert config.name == "yolo-world-s"
        assert config.path == "/models/model-zoo/yolo-world-s"
        assert config.category == "detection"
        assert config.vram_mb == 1500
        assert config.enabled is True
        assert config.available is False

    def test_yolo_world_in_enabled_models(self) -> None:
        """Test that yolo-world-s appears in enabled models list."""
        enabled = get_enabled_models()
        enabled_names = [m.name for m in enabled]

        assert "yolo-world-s" in enabled_names

    def test_yolo_world_vram_calculation(self) -> None:
        """Test VRAM calculation includes yolo-world-s."""
        total = get_total_vram_if_loaded(["yolo-world-s"])
        assert total == 1500

        # Combined with other models
        total = get_total_vram_if_loaded(["yolo-world-s", "yolo11-license-plate"])
        assert total == 1800  # 1500 + 300

    @pytest.mark.asyncio
    async def test_load_yolo_world_import_error(self) -> None:
        """Test that load_yolo_world_model raises ImportError when ultralytics missing."""
        from backend.services.yolo_world_loader import load_yolo_world_model

        # Mock the import to raise ImportError
        # Note: With Python 3.14 + coverage, the error message may vary due to
        # coverage instrumentation intercepting the import. We accept either the
        # custom error message or the raw Python ImportError.
        with (
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'ultralytics'"),
            ),
            pytest.raises(ImportError, match="ultralytics"),
        ):
            await load_yolo_world_model("yolov8s-worldv2.pt")

    @pytest.mark.asyncio
    async def test_load_yolo_world_runtime_error(self) -> None:
        """Test that load_yolo_world_model raises RuntimeError on load failure."""
        from backend.services.yolo_world_loader import load_yolo_world_model

        mock_yolo_world = MagicMock()
        mock_yolo_world.side_effect = ValueError("Invalid model path")

        with (
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLOWorld=mock_yolo_world)}),
            pytest.raises(RuntimeError, match="Failed to load YOLO-World model"),
        ):
            await load_yolo_world_model("invalid/path")

    @pytest.mark.asyncio
    async def test_load_yolo_world_success(self) -> None:
        """Test successful YOLO-World model loading."""
        from backend.services.yolo_world_loader import (
            SECURITY_PROMPTS,
            load_yolo_world_model,
        )

        mock_model = MagicMock()
        mock_yolo_world_class = MagicMock(return_value=mock_model)

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLOWorld = mock_yolo_world_class

        with patch.dict("sys.modules", {"ultralytics": mock_ultralytics}):
            result = await load_yolo_world_model("yolov8s-worldv2.pt")

            assert result is mock_model
            mock_yolo_world_class.assert_called_once_with("yolov8s-worldv2.pt")
            # Verify default prompts are set
            mock_model.set_classes.assert_called_once_with(SECURITY_PROMPTS)

    @pytest.mark.asyncio
    async def test_manager_load_yolo_world(self) -> None:
        """Test loading yolo-world-s via ModelManager."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        config = get_model_config("yolo-world-s")
        assert config is not None

        with patch.object(config, "load_fn", mock_load):
            async with manager.load("yolo-world-s") as model:
                assert model is mock_model
                assert manager.is_loaded("yolo-world-s")
                assert config.available is True

            # After context exits, model should be unloaded
            assert not manager.is_loaded("yolo-world-s")


class TestYoloWorldPrompts:
    """Tests for YOLO-World security prompts constants."""

    def test_security_prompts_not_empty(self) -> None:
        """Test that SECURITY_PROMPTS contains items."""
        from backend.services.yolo_world_loader import SECURITY_PROMPTS

        assert len(SECURITY_PROMPTS) > 0
        assert isinstance(SECURITY_PROMPTS, list)
        assert all(isinstance(p, str) for p in SECURITY_PROMPTS)

    def test_security_prompts_contain_key_items(self) -> None:
        """Test that SECURITY_PROMPTS contains expected security items."""
        from backend.services.yolo_world_loader import SECURITY_PROMPTS

        # Packages
        assert "package" in SECURITY_PROMPTS
        assert "cardboard box" in SECURITY_PROMPTS

        # Threats
        assert "knife" in SECURITY_PROMPTS
        assert "crowbar" in SECURITY_PROMPTS

        # Items of interest
        assert "backpack" in SECURITY_PROMPTS
        assert "ladder" in SECURITY_PROMPTS

    def test_vehicle_security_prompts(self) -> None:
        """Test VEHICLE_SECURITY_PROMPTS contains vehicle items."""
        from backend.services.yolo_world_loader import VEHICLE_SECURITY_PROMPTS

        assert "car" in VEHICLE_SECURITY_PROMPTS
        assert "license plate" in VEHICLE_SECURITY_PROMPTS

    def test_animal_prompts(self) -> None:
        """Test ANIMAL_PROMPTS contains common animals."""
        from backend.services.yolo_world_loader import ANIMAL_PROMPTS

        assert "dog" in ANIMAL_PROMPTS
        assert "cat" in ANIMAL_PROMPTS

    def test_get_all_security_prompts(self) -> None:
        """Test get_all_security_prompts combines all prompt lists."""
        from backend.services.yolo_world_loader import (
            ANIMAL_PROMPTS,
            SECURITY_PROMPTS,
            VEHICLE_SECURITY_PROMPTS,
            get_all_security_prompts,
        )

        all_prompts = get_all_security_prompts()

        expected_length = (
            len(SECURITY_PROMPTS) + len(VEHICLE_SECURITY_PROMPTS) + len(ANIMAL_PROMPTS)
        )
        assert len(all_prompts) == expected_length

    def test_get_threat_prompts(self) -> None:
        """Test get_threat_prompts returns threat-focused prompts."""
        from backend.services.yolo_world_loader import get_threat_prompts

        threats = get_threat_prompts()

        assert "knife" in threats
        assert "crowbar" in threats
        assert "bolt cutters" in threats
        # Should not contain benign items
        assert "package" not in threats
        assert "dog" not in threats

    def test_get_delivery_prompts(self) -> None:
        """Test get_delivery_prompts returns delivery-focused prompts."""
        from backend.services.yolo_world_loader import get_delivery_prompts

        delivery = get_delivery_prompts()

        assert "package" in delivery
        assert "cardboard box" in delivery
        assert "Amazon box" in delivery
        # Should not contain threats
        assert "knife" not in delivery


class TestDetectWithPrompts:
    """Tests for detect_with_prompts helper function."""

    @pytest.mark.asyncio
    async def test_detect_with_prompts_default_prompts(self) -> None:
        """Test detect_with_prompts uses SECURITY_PROMPTS by default."""
        from backend.services.yolo_world_loader import (
            SECURITY_PROMPTS,
            detect_with_prompts,
        )

        # Create mock model
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = None  # No detections
        mock_model.predict.return_value = [mock_result]

        detections = await detect_with_prompts(mock_model, "test_image.jpg")

        # Verify default prompts were set
        mock_model.set_classes.assert_called_once_with(SECURITY_PROMPTS)
        assert detections == []

    @pytest.mark.asyncio
    async def test_detect_with_prompts_custom_prompts(self) -> None:
        """Test detect_with_prompts with custom prompts."""
        from backend.services.yolo_world_loader import detect_with_prompts

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_model.predict.return_value = [mock_result]

        custom_prompts = ["custom object", "another object"]
        await detect_with_prompts(mock_model, "test.jpg", prompts=custom_prompts)

        mock_model.set_classes.assert_called_once_with(custom_prompts)

    @pytest.mark.asyncio
    async def test_detect_with_prompts_returns_detections(self) -> None:
        """Test detect_with_prompts returns properly formatted detections."""
        from backend.services.yolo_world_loader import detect_with_prompts

        # Create mock detection results
        mock_model = MagicMock()
        mock_result = MagicMock()

        # Mock boxes with detection data
        import numpy as np

        mock_boxes = MagicMock()
        mock_boxes.xyxy = [MagicMock()]
        mock_boxes.xyxy[0].cpu.return_value.numpy.return_value = np.array(
            [10.0, 20.0, 100.0, 150.0]
        )
        mock_boxes.conf = [MagicMock()]
        mock_boxes.conf[0].cpu.return_value.numpy.return_value = 0.85
        mock_boxes.cls = [MagicMock()]
        mock_boxes.cls[0].cpu.return_value.numpy.return_value = 0

        mock_result.boxes = mock_boxes
        mock_result.names = {0: "package"}

        # Make len() work on mock boxes
        mock_boxes.__len__ = MagicMock(return_value=1)

        mock_model.predict.return_value = [mock_result]

        detections = await detect_with_prompts(
            mock_model,
            "test.jpg",
            prompts=["package"],
            confidence_threshold=0.5,
        )

        assert len(detections) == 1
        assert detections[0]["class_name"] == "package"
        assert detections[0]["confidence"] == 0.85
        assert detections[0]["bbox"]["x1"] == 10.0
        assert detections[0]["bbox"]["y1"] == 20.0
        assert detections[0]["bbox"]["x2"] == 100.0
        assert detections[0]["bbox"]["y2"] == 150.0
        assert detections[0]["class_id"] == 0

    @pytest.mark.asyncio
    async def test_detect_with_prompts_respects_thresholds(self) -> None:
        """Test detect_with_prompts passes confidence and IoU thresholds."""
        from backend.services.yolo_world_loader import detect_with_prompts

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_model.predict.return_value = [mock_result]

        await detect_with_prompts(
            mock_model,
            "test.jpg",
            confidence_threshold=0.7,
            iou_threshold=0.3,
        )

        mock_model.predict.assert_called_once()
        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs["conf"] == 0.7
        assert call_kwargs["iou"] == 0.3


class TestDepthAnythingLoader:
    """Tests for Depth Anything V2 model loader and helper functions."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()
        reset_model_manager()

    def test_depth_model_in_zoo(self) -> None:
        """Test that depth-anything-v2-small is registered in the model zoo."""
        zoo = get_model_zoo()

        assert "depth-anything-v2-small" in zoo
        config = zoo["depth-anything-v2-small"]
        assert config.name == "depth-anything-v2-small"
        assert config.path == "/models/model-zoo/depth-anything-v2-small"
        assert config.category == "depth-estimation"
        assert config.vram_mb == 150
        assert config.enabled is True
        assert config.available is False

    def test_depth_model_in_enabled_models(self) -> None:
        """Test that depth-anything-v2-small appears in enabled models list."""
        enabled = get_enabled_models()
        enabled_names = [m.name for m in enabled]

        assert "depth-anything-v2-small" in enabled_names

    def test_depth_model_vram_calculation(self) -> None:
        """Test VRAM calculation includes depth-anything-v2-small."""
        total = get_total_vram_if_loaded(["depth-anything-v2-small"])
        assert total == 150

        # Combined with other models
        total_combined = get_total_vram_if_loaded(
            ["depth-anything-v2-small", "yolo11-license-plate"]
        )
        assert total_combined == 450  # 150 + 300

    @pytest.mark.asyncio
    async def test_load_depth_model_import_error(self) -> None:
        """Test that load_depth_model raises ImportError when dependencies missing."""
        from backend.services.depth_anything_loader import load_depth_model

        with (
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'transformers'"),
            ),
            pytest.raises(ImportError),
        ):
            await load_depth_model("depth-anything/Depth-Anything-V2-Small-hf")

    @pytest.mark.asyncio
    async def test_load_depth_model_runtime_error(self) -> None:
        """Test that load_depth_model raises RuntimeError on load failure."""
        from backend.services.depth_anything_loader import load_depth_model

        mock_pipeline = MagicMock()
        mock_pipeline.side_effect = ValueError("Model loading failed")

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.pipeline = mock_pipeline

        with (
            patch.dict(
                "sys.modules",
                {
                    "torch": mock_torch,
                    "transformers": mock_transformers,
                },
            ),
            pytest.raises(RuntimeError, match="Failed to load Depth Anything V2"),
        ):
            await load_depth_model("depth-anything/Depth-Anything-V2-Small-hf")


class TestDepthHelperFunctions:
    """Tests for depth estimation helper functions."""

    def test_normalize_depth_map_basic(self) -> None:
        """Test basic depth map normalization."""
        import numpy as np

        from backend.services.depth_anything_loader import normalize_depth_map

        # Create a depth map with values 0-255
        depth_map = np.array([[0, 128], [255, 64]], dtype=np.float32)

        normalized = normalize_depth_map(depth_map)

        # Should be normalized to [0, 1]
        assert normalized.min() == 0.0
        assert normalized.max() == 1.0
        assert normalized.dtype == np.float32

    def test_normalize_depth_map_uniform(self) -> None:
        """Test normalization of uniform depth map."""
        import numpy as np

        from backend.services.depth_anything_loader import normalize_depth_map

        # Uniform depth - all same value
        depth_map = np.full((100, 100), 128.0, dtype=np.float32)

        normalized = normalize_depth_map(depth_map)

        # Should be all zeros when uniform (0 / 0 case handled)
        assert np.allclose(normalized, 0.0)

    def test_normalize_depth_map_dict_input(self) -> None:
        """Test normalization with dict-like output from pipeline."""
        import numpy as np

        from backend.services.depth_anything_loader import normalize_depth_map

        depth_array = np.array([[10.0, 50.0], [100.0, 25.0]], dtype=np.float32)
        depth_output = {"depth": depth_array}

        normalized = normalize_depth_map(depth_output)

        assert normalized.shape == (2, 2)
        assert normalized.min() == 0.0
        assert normalized.max() == 1.0

    def test_get_depth_at_bbox_center(self) -> None:
        """Test getting depth at bbox center."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        # Create a depth map where center has known value
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[50, 50] = 0.75  # Center value

        bbox = (40.0, 40.0, 60.0, 60.0)  # Center at (50, 50)
        depth = get_depth_at_bbox(depth_map, bbox, method="center")

        assert depth == 0.75

    def test_get_depth_at_bbox_mean(self) -> None:
        """Test getting average depth over bbox."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        # Create a depth map where region has known values
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[10:20, 10:20] = 0.5  # All 0.5 in region

        bbox = (10.0, 10.0, 20.0, 20.0)
        depth = get_depth_at_bbox(depth_map, bbox, method="mean")

        assert abs(depth - 0.5) < 0.01

    def test_get_depth_at_bbox_median(self) -> None:
        """Test getting median depth over bbox."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        # Create depth map with varied values
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[10:15, 10:20] = 0.3
        depth_map[15:20, 10:20] = 0.7

        bbox = (10.0, 10.0, 20.0, 20.0)
        depth = get_depth_at_bbox(depth_map, bbox, method="median")

        # Median should be around 0.5 (between 0.3 and 0.7)
        assert 0.3 <= depth <= 0.7

    def test_get_depth_at_bbox_min(self) -> None:
        """Test getting minimum depth in bbox (closest point)."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        depth_map = np.ones((100, 100), dtype=np.float32) * 0.8
        depth_map[15, 15] = 0.1  # Closest point

        bbox = (10.0, 10.0, 20.0, 20.0)
        depth = get_depth_at_bbox(depth_map, bbox, method="min")

        assert abs(depth - 0.1) < 0.001

    def test_get_depth_at_bbox_invalid_method(self) -> None:
        """Test that invalid method raises ValueError."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        depth_map = np.zeros((100, 100), dtype=np.float32)
        bbox = (10.0, 10.0, 20.0, 20.0)

        with pytest.raises(ValueError, match="Unknown depth sampling method"):
            get_depth_at_bbox(depth_map, bbox, method="invalid")

    def test_get_depth_at_bbox_invalid_bbox(self) -> None:
        """Test handling of invalid bounding box."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        depth_map = np.zeros((100, 100), dtype=np.float32)

        # Invalid bbox (x2 <= x1)
        bbox = (50.0, 50.0, 20.0, 20.0)
        depth = get_depth_at_bbox(depth_map, bbox, method="center")

        # Should return default 0.5
        assert depth == 0.5

    def test_get_depth_at_bbox_clamped_to_boundaries(self) -> None:
        """Test that bbox is clamped to image boundaries."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_bbox

        depth_map = np.full((100, 100), 0.3, dtype=np.float32)

        # Bbox extends beyond image
        bbox = (-10.0, -10.0, 200.0, 200.0)
        depth = get_depth_at_bbox(depth_map, bbox, method="mean")

        # Should still work, using clamped coordinates
        assert abs(depth - 0.3) < 0.01

    def test_get_depth_at_point(self) -> None:
        """Test getting depth at a specific point."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_point

        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[25, 50] = 0.65

        depth = get_depth_at_point(depth_map, 50, 25)
        assert abs(depth - 0.65) < 0.001

    def test_get_depth_at_point_clamped(self) -> None:
        """Test that point coordinates are clamped to boundaries."""
        import numpy as np

        from backend.services.depth_anything_loader import get_depth_at_point

        depth_map = np.full((100, 100), 0.42, dtype=np.float32)

        # Point outside image
        depth = get_depth_at_point(depth_map, 200, 150)

        # Should be clamped to edge
        assert abs(depth - 0.42) < 0.001

    def test_estimate_relative_distances(self) -> None:
        """Test estimating distances for multiple detections."""
        import numpy as np

        from backend.services.depth_anything_loader import estimate_relative_distances

        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[15, 15] = 0.2  # First bbox center
        depth_map[55, 55] = 0.8  # Second bbox center

        bboxes = [
            (10.0, 10.0, 20.0, 20.0),  # Center at (15, 15)
            (50.0, 50.0, 60.0, 60.0),  # Center at (55, 55)
        ]

        distances = estimate_relative_distances(depth_map, bboxes)

        assert len(distances) == 2
        assert abs(distances[0] - 0.2) < 0.001
        assert abs(distances[1] - 0.8) < 0.001

    def test_depth_to_proximity_label(self) -> None:
        """Test converting depth to proximity labels."""
        from backend.services.depth_anything_loader import depth_to_proximity_label

        assert depth_to_proximity_label(0.1) == "very close"
        assert depth_to_proximity_label(0.25) == "close"
        assert depth_to_proximity_label(0.45) == "moderate distance"
        assert depth_to_proximity_label(0.65) == "far"
        assert depth_to_proximity_label(0.85) == "very far"

    def test_format_depth_for_nemotron_empty(self) -> None:
        """Test formatting with empty inputs."""
        from backend.services.depth_anything_loader import format_depth_for_nemotron

        result = format_depth_for_nemotron([], [])
        assert result == "No spatial depth information available."

    def test_format_depth_for_nemotron_with_data(self) -> None:
        """Test formatting depth info for Nemotron."""
        from backend.services.depth_anything_loader import format_depth_for_nemotron

        detections = [
            {"class_name": "person"},
            {"class_name": "car"},
        ]
        depth_values = [0.12, 0.48]

        result = format_depth_for_nemotron(detections, depth_values)

        assert "Spatial context:" in result
        assert "person is very close" in result
        assert "car is moderate distance" in result
        assert "0.12" in result
        assert "0.48" in result

    def test_format_depth_for_nemotron_mismatched_lengths(self) -> None:
        """Test formatting handles mismatched list lengths."""
        from backend.services.depth_anything_loader import format_depth_for_nemotron

        detections = [
            {"class_name": "person"},
            {"class_name": "car"},
            {"class_name": "truck"},
        ]
        depth_values = [0.2, 0.5]  # One fewer than detections

        # Should use minimum length without error
        result = format_depth_for_nemotron(detections, depth_values)

        assert "person" in result
        assert "car" in result
        assert "truck" not in result  # Should be truncated

    def test_format_depth_for_nemotron_label_key(self) -> None:
        """Test formatting handles 'label' key as fallback."""
        from backend.services.depth_anything_loader import format_depth_for_nemotron

        detections = [{"label": "bicycle"}]  # Uses 'label' instead of 'class_name'
        depth_values = [0.3]

        result = format_depth_for_nemotron(detections, depth_values)

        assert "bicycle" in result

    def test_rank_detections_by_proximity(self) -> None:
        """Test ranking detections by proximity."""
        from backend.services.depth_anything_loader import rank_detections_by_proximity

        detections = [
            {"class_name": "far_object"},
            {"class_name": "close_object"},
            {"class_name": "medium_object"},
        ]
        depth_values = [0.9, 0.1, 0.5]

        ranked = rank_detections_by_proximity(detections, depth_values)

        # Should be sorted by depth (closest first)
        assert len(ranked) == 3
        assert ranked[0][0]["class_name"] == "close_object"
        assert ranked[0][1] == 0.1
        assert ranked[0][2] == 1  # Original index

        assert ranked[1][0]["class_name"] == "medium_object"
        assert ranked[1][1] == 0.5

        assert ranked[2][0]["class_name"] == "far_object"
        assert ranked[2][1] == 0.9

    def test_rank_detections_by_proximity_mismatched(self) -> None:
        """Test that mismatched lengths raise ValueError."""
        from backend.services.depth_anything_loader import rank_detections_by_proximity

        detections = [{"class_name": "a"}, {"class_name": "b"}]
        depth_values = [0.5]  # One fewer

        with pytest.raises(ValueError, match="Detection and depth value counts must match"):
            rank_detections_by_proximity(detections, depth_values)


class TestViTPoseLoader:
    """Tests for ViTPose model loader and pose classification."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()

    def test_vitpose_model_in_zoo(self) -> None:
        """Test that vitpose-small is registered in the model zoo."""
        config = get_model_config("vitpose-small")

        assert config is not None
        assert config.name == "vitpose-small"
        assert config.path == "/models/model-zoo/vitpose-small"
        assert config.category == "pose"
        assert config.vram_mb == 1500
        assert config.enabled is True

    def test_keypoint_dataclass(self) -> None:
        """Test Keypoint dataclass creation."""
        from backend.services.vitpose_loader import Keypoint

        kp = Keypoint(x=100.5, y=200.5, confidence=0.95, name="left_shoulder")

        assert kp.x == 100.5
        assert kp.y == 200.5
        assert kp.confidence == 0.95
        assert kp.name == "left_shoulder"

    def test_pose_result_dataclass(self) -> None:
        """Test PoseResult dataclass creation and to_dict."""
        from backend.services.vitpose_loader import Keypoint, PoseResult

        keypoints = {
            "nose": Keypoint(x=50.0, y=30.0, confidence=0.9, name="nose"),
            "left_shoulder": Keypoint(x=40.0, y=60.0, confidence=0.85, name="left_shoulder"),
        }

        result = PoseResult(
            keypoints=keypoints,
            pose_class="standing",
            pose_confidence=0.8,
            bbox=[10.0, 20.0, 100.0, 200.0],
        )

        assert result.pose_class == "standing"
        assert result.pose_confidence == 0.8
        assert "nose" in result.keypoints
        assert result.bbox == [10.0, 20.0, 100.0, 200.0]

        # Test to_dict
        d = result.to_dict()
        assert d["pose_class"] == "standing"
        assert d["pose_confidence"] == 0.8
        assert "nose" in d["keypoints"]
        assert d["keypoints"]["nose"]["x"] == 50.0

    def test_keypoint_index_enum(self) -> None:
        """Test KeypointIndex enum values."""
        from backend.services.vitpose_loader import KeypointIndex

        assert KeypointIndex.NOSE.value == 0
        assert KeypointIndex.LEFT_SHOULDER.value == 5
        assert KeypointIndex.RIGHT_HIP.value == 12
        assert KeypointIndex.LEFT_ANKLE.value == 15

    def test_keypoint_names_list(self) -> None:
        """Test KEYPOINT_NAMES list."""
        from backend.services.vitpose_loader import KEYPOINT_NAMES

        assert len(KEYPOINT_NAMES) == 17
        assert KEYPOINT_NAMES[0] == "nose"
        assert KEYPOINT_NAMES[5] == "left_shoulder"
        assert KEYPOINT_NAMES[16] == "right_ankle"


class TestPoseClassification:
    """Tests for pose classification logic."""

    def test_classify_pose_unknown_insufficient_keypoints(self) -> None:
        """Test pose classification with insufficient keypoints."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Empty keypoints
        keypoints: dict[str, Any] = {}
        pose, confidence = classify_pose(keypoints)
        assert pose == "unknown"
        assert confidence == 0.0

        # Only one keypoint
        keypoints = {"nose": Keypoint(x=50.0, y=30.0, confidence=0.9, name="nose")}
        pose, confidence = classify_pose(keypoints)
        assert pose == "unknown"
        assert confidence == 0.0

    def test_classify_pose_standing(self) -> None:
        """Test classification of standing pose."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Create keypoints for standing pose
        # In image coordinates, Y increases downward
        keypoints = {
            "left_shoulder": Keypoint(x=45.0, y=100.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=55.0, y=100.0, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=45.0, y=200.0, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=55.0, y=200.0, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=45.0, y=300.0, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=55.0, y=300.0, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=45.0, y=400.0, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=55.0, y=400.0, confidence=0.9, name="right_ankle"),
        }

        pose, confidence = classify_pose(keypoints)
        assert pose == "standing"
        assert confidence > 0.5

    def test_classify_pose_crouching(self) -> None:
        """Test classification of crouching pose."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Create keypoints for crouching pose (bent knees, compressed torso)
        # Crouching: hip is above knee (hip_y < knee_y in image coords)
        # but torso is compressed (small shoulder-to-hip distance relative to hip-to-knee)
        # Y increases downward in image coordinates
        keypoints = {
            "left_shoulder": Keypoint(x=45.0, y=160.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=55.0, y=160.0, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=45.0, y=180.0, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=55.0, y=180.0, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=45.0, y=220.0, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=55.0, y=220.0, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=45.0, y=250.0, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=55.0, y=250.0, confidence=0.9, name="right_ankle"),
        }
        # Torso length: 180 - 160 = 20
        # Upper leg length: 220 - 180 = 40
        # Ratio: 20/40 = 0.5 < 0.8 (compressed torso = crouching)

        pose, confidence = classify_pose(keypoints)
        assert pose == "crouching"
        assert confidence > 0.5

    def test_classify_pose_running(self) -> None:
        """Test classification of running pose."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Create keypoints for running pose (wide leg spread, arm asymmetry)
        keypoints = {
            "left_shoulder": Keypoint(x=45.0, y=100.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=55.0, y=100.0, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=45.0, y=200.0, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=55.0, y=200.0, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=30.0, y=300.0, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=70.0, y=300.0, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=20.0, y=400.0, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=80.0, y=400.0, confidence=0.9, name="right_ankle"),
            "left_wrist": Keypoint(x=30.0, y=80.0, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=70.0, y=150.0, confidence=0.9, name="right_wrist"),
            "left_elbow": Keypoint(x=35.0, y=120.0, confidence=0.9, name="left_elbow"),
            "right_elbow": Keypoint(x=65.0, y=120.0, confidence=0.9, name="right_elbow"),
        }

        pose, confidence = classify_pose(keypoints)
        assert pose == "running"
        assert confidence > 0.5

    def test_classify_pose_sitting(self) -> None:
        """Test classification of sitting pose."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Create keypoints for sitting pose (hips at or below knee level)
        keypoints = {
            "left_shoulder": Keypoint(x=45.0, y=100.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=55.0, y=100.0, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=45.0, y=200.0, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=55.0, y=200.0, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=60.0, y=200.0, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=70.0, y=200.0, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=70.0, y=250.0, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=80.0, y=250.0, confidence=0.9, name="right_ankle"),
        }

        pose, confidence = classify_pose(keypoints)
        assert pose == "sitting"
        assert confidence > 0.5

    def test_classify_pose_lying(self) -> None:
        """Test classification of lying pose."""
        from backend.services.vitpose_loader import Keypoint, classify_pose

        # Create keypoints for lying pose (horizontal orientation)
        keypoints = {
            "left_shoulder": Keypoint(x=100.0, y=50.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150.0, y=50.0, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=200.0, y=55.0, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=250.0, y=55.0, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=300.0, y=52.0, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=350.0, y=52.0, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=400.0, y=50.0, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=450.0, y=50.0, confidence=0.9, name="right_ankle"),
        }

        pose, confidence = classify_pose(keypoints)
        assert pose == "lying"
        assert confidence > 0.5


class TestViTPoseLoaderFunctions:
    """Tests for ViTPose model loading functions."""

    @pytest.mark.asyncio
    async def test_load_vitpose_model_import_error(self) -> None:
        """Test that load_vitpose_model raises ImportError when transformers missing."""
        from backend.services.vitpose_loader import load_vitpose_model

        with patch.dict("sys.modules", {"transformers": None}):
            import sys

            if "transformers" in sys.modules:
                del sys.modules["transformers"]

            with (
                patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'transformers'"),
                ),
                pytest.raises(ImportError),
            ):
                await load_vitpose_model("test/path")

    @pytest.mark.asyncio
    async def test_load_vitpose_model_runtime_error(self) -> None:
        """Test that load_vitpose_model raises RuntimeError on load failure."""
        from backend.services.vitpose_loader import load_vitpose_model

        mock_processor = MagicMock()
        mock_processor.from_pretrained.side_effect = ValueError("Model loading failed")

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor = mock_processor

        with (
            patch.dict(
                "sys.modules",
                {
                    "transformers": mock_transformers,
                    "torch": MagicMock(),
                },
            ),
            pytest.raises(RuntimeError, match="Failed to load ViTPose model"),
        ):
            await load_vitpose_model("invalid/path")

    @pytest.mark.asyncio
    async def test_extract_pose_from_crop_error_handling(self) -> None:
        """Test extract_pose_from_crop handles errors gracefully."""
        from backend.services.vitpose_loader import PoseResult, extract_pose_from_crop

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])
        # Make the model raise an error during inference
        mock_model.side_effect = ValueError("Inference failed")

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        # Create a mock PIL Image
        mock_image = MagicMock()
        mock_image.height = 256
        mock_image.width = 192

        with patch.dict("sys.modules", {"torch": MagicMock()}):
            result = await extract_pose_from_crop(
                mock_model,
                mock_processor,
                mock_image,
                bbox=[0, 0, 192, 256],
            )

            # Should return unknown pose on error
            assert isinstance(result, PoseResult)
            assert result.pose_class == "unknown"
            assert result.pose_confidence == 0.0

    @pytest.mark.asyncio
    async def test_extract_poses_batch_empty_input(self) -> None:
        """Test extract_poses_batch with empty input."""
        from backend.services.vitpose_loader import extract_poses_batch

        mock_model = MagicMock()
        mock_processor = MagicMock()

        results = await extract_poses_batch(mock_model, mock_processor, [])

        assert results == []

    @pytest.mark.asyncio
    async def test_extract_poses_batch_error_handling(self) -> None:
        """Test extract_poses_batch handles errors gracefully."""
        from backend.services.vitpose_loader import PoseResult, extract_poses_batch

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu")])

        mock_processor = MagicMock()
        mock_processor.side_effect = ValueError("Processing failed")

        # Create mock PIL Images
        mock_images = [MagicMock(height=256, width=192) for _ in range(3)]

        with patch.dict("sys.modules", {"torch": MagicMock()}):
            results = await extract_poses_batch(
                mock_model,
                mock_processor,
                mock_images,
                bboxes=[[0, 0, 192, 256]] * 3,
            )

            # Should return unknown poses on error
            assert len(results) == 3
            for result in results:
                assert isinstance(result, PoseResult)
                assert result.pose_class == "unknown"


class TestViTPoseModelManager:
    """Tests for ViTPose model loading via ModelManager."""

    def setup_method(self) -> None:
        """Reset managers before each test."""
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        """Reset managers after each test."""
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_load_vitpose_via_manager(self) -> None:
        """Test loading ViTPose model via ModelManager."""
        manager = ModelManager()
        mock_model = (MagicMock(), MagicMock())  # (model, processor) tuple

        async def mock_load(path: str) -> Any:
            return mock_model

        config = get_model_config("vitpose-small")
        assert config is not None

        with patch.object(config, "load_fn", mock_load):
            async with manager.load("vitpose-small") as model:
                assert model is mock_model
                assert manager.is_loaded("vitpose-small")

            # After context exits, model should be unloaded
            assert not manager.is_loaded("vitpose-small")

    @pytest.mark.asyncio
    async def test_vitpose_vram_tracking(self) -> None:
        """Test that VRAM is properly tracked for ViTPose model."""
        manager = ModelManager()
        mock_model = (MagicMock(), MagicMock())

        async def mock_load(path: str) -> Any:
            return mock_model

        config = get_model_config("vitpose-small")
        assert config is not None

        with patch.object(config, "load_fn", mock_load):
            await manager.preload("vitpose-small")

            # Should show 1500 MB VRAM usage
            assert manager.total_loaded_vram == 1500

            await manager.unload("vitpose-small")
            assert manager.total_loaded_vram == 0
