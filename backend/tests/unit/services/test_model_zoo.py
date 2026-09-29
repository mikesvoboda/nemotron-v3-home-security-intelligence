"""Unit tests for the Model Zoo.

Tests cover:
- ModelConfig dataclass
- MODEL_ZOO registry initialization and access
- ModelManager context manager operations
- ModelManager reference counting
- models.yml parsing contracts (paths, eviction flags, preload residency)
- Optional-dependency load-failure routing

The EnrichmentPipeline/BoundingBox/EnrichmentResult suites that used to live
here went with R8 slice S2b: that tier was retired, and its data structures
were removed with it.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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

            with patch("builtins.__import__", side_effect=mock_import, autospec=True):
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
                    autospec=True,
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
                autospec=True,
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
                autospec=True,
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
        with patch("importlib.util.find_spec", return_value=None, autospec=True):
            assert _is_paddleocr_available() is False

    def test_is_paddleocr_available_when_installed(self) -> None:
        """Test _is_paddleocr_available returns True when paddleocr is installed."""
        from backend.services.model_zoo import _is_paddleocr_available

        # Mock find_spec to return a spec (module found)
        mock_spec = MagicMock()
        with patch("importlib.util.find_spec", return_value=mock_spec, autospec=True):
            assert _is_paddleocr_available() is True

    def test_is_paddleocr_available_handles_import_error(self) -> None:
        """Test _is_paddleocr_available handles ImportError gracefully."""
        from backend.services.model_zoo import _is_paddleocr_available

        # Mock find_spec to raise ImportError
        with patch("importlib.util.find_spec", side_effect=ImportError("test"), autospec=True):
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
                autospec=True,
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


# =============================================================================
# WP4.4 kill battery (frozen triage feed archive/wp25-feed/wp44-triage/
# model_zoo.md, TEST-GAP clusters D1-D12 of 78; 104 EQUIVALENT log-text +
# 3 LOW-VALUE stay excluded per the dossier's own per-cluster notes).
# Root cause per dossier: success paths (paddleocr uninstalled in CI), the
# INFO-vs-ERROR optional-dep routing, eviction-flag reads (the smoke-fire
# assert was an `or` form None satisfies), timeout constant, and every
# diagnostic payload never executed or never asserted. Drafts UNVERIFIED —
# red/green-checked against the shipped source here; zero production change.
# =============================================================================


class TestOptionalDependencyLogRouting:
    """D1 — GAP:optdep-error-classifier (9). The INFO-vs-ERROR routing of
    optional-dependency load failures is the documented graceful-degradation
    contract (NEM-2540); existing tests only catch the exception."""

    def setup_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dep_message",
        [
            "paddleocr package not installed",  # 'not installed' arm alone
            "this dependency is optional",  # 'optional' arm alone
        ],
    )
    async def test_load_model_logs_info_not_error_for_optional_dep(self, dep_message: str) -> None:
        manager = ModelManager()

        async def missing_dep_load(path: str) -> Any:
            raise RuntimeError(dep_message)

        mock_logger = MagicMock()
        with (
            patch.object(get_model_config("yolo11-license-plate"), "load_fn", missing_dep_load),
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match=dep_message),
        ):
            await manager.preload("yolo11-license-plate")

        info_msgs = [str(c.args[0]) for c in mock_logger.info.call_args_list if c.args]
        err_msgs = [str(c.args[0]) for c in mock_logger.error.call_args_list if c.args]
        assert any("unavailable" in m for m in info_msgs), (
            f"optional-dep failure '{dep_message}' must log INFO with 'unavailable', "
            f"got INFO={info_msgs}"
        )
        assert not any("Failed to load model" in m for m in err_msgs), (
            f"optional-dep failure '{dep_message}' must not reach the ERROR branch"
        )


class TestYoloLocalPathValidation:
    """D2a/D2b — GAP:yolo-local-path-validation-guard (9) + missing-file
    diagnostics (6). Both existing yolo tests BYPASS the guard: the
    ImportError test's mock raises before validation; the runtime-error test
    uses a path where every mutant behaves identically."""

    @pytest.mark.asyncio
    async def test_load_yolo_model_missing_local_file_raises_runtime_error(
        self, tmp_path: Any
    ) -> None:
        from backend.services.model_zoo import load_yolo_model

        missing = str(tmp_path / "models" / "yolo11-face.pt")
        with patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=MagicMock())}):
            with pytest.raises(RuntimeError, match="Model file not found"):
                await load_yolo_model(missing)

    @pytest.mark.asyncio
    async def test_load_yolo_model_skips_validation_for_non_local_paths(self) -> None:
        """Bare ultralytics names (no '/') and http URLs must NOT be
        pre-validated — ultralytics resolves/downloads those itself. (A
        repo-style name like 'org/yolov8n' DOES contain '/' and IS
        validated by the guard as shipped.)"""
        from backend.services.model_zoo import load_yolo_model

        mock_yolo_cls = MagicMock()
        mock_model = MagicMock()
        mock_yolo_cls.return_value = mock_model
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        with patch.dict(
            "sys.modules",
            {"ultralytics": MagicMock(YOLO=mock_yolo_cls), "torch": fake_torch},
        ):
            for non_local in ("yolov8n.pt", "http://example.com/dir/y.pt"):
                assert await load_yolo_model(non_local) is mock_model

    @pytest.mark.asyncio
    async def test_load_yolo_model_warns_with_available_model_files(self, tmp_path: Any) -> None:
        """Branch A (parent dir exists): the warning must list the sibling
        .pt/.pth/.onnx files — that filtered listing IS the payload."""
        from backend.services.model_zoo import load_yolo_model

        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "a.pt").write_bytes(b"")
        (tmp_path / "dir" / "b.txt").write_text("")
        missing = str(tmp_path / "dir" / "ghost.pt")

        mock_logger = MagicMock()
        with (
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match="Model file not found"),
        ):
            await load_yolo_model(missing)

        warn_msgs = [str(c.args[0]) for c in mock_logger.warning.call_args_list if c.args]
        assert any("Available model files" in m and "['a.pt']" in m for m in warn_msgs), (
            f"warning must list exactly the .pt/.onnx siblings, got {warn_msgs}"
        )

    @pytest.mark.asyncio
    async def test_load_yolo_model_warns_with_mount_hint_when_dir_missing(
        self, tmp_path: Any
    ) -> None:
        """Branch B (no parent dir): mount + download hint."""
        from backend.services.model_zoo import load_yolo_model

        missing = str(tmp_path / "ghosts" / "ghost.pt")
        mock_logger = MagicMock()
        with (
            patch("backend.services.model_zoo.logger", mock_logger),
            pytest.raises(RuntimeError, match="Model file not found"),
        ):
            await load_yolo_model(missing)

        warn_msgs = [str(c.args[0]) for c in mock_logger.warning.call_args_list if c.args]
        assert any("does not exist" in m for m in warn_msgs), warn_msgs


class TestPaddleOcrSuccessPath:
    """D3 — GAP:paddleocr-ctor-kwargs-and-executor-call (14). paddleocr is
    uninstalled in CI: the success path (ctor kwargs + run_in_executor hop)
    never runs under test."""

    @pytest.mark.asyncio
    async def test_load_paddle_ocr_constructs_with_expected_options(self) -> None:
        from backend.services.model_zoo import load_paddle_ocr

        mock_module = MagicMock()
        mock_ctor = MagicMock()
        mock_instance = MagicMock()
        mock_ctor.return_value = mock_instance
        mock_module.PaddleOCR = mock_ctor

        with (
            patch(
                "backend.services.model_zoo._is_paddleocr_available",
                return_value=True,
                autospec=True,
            ),
            patch.dict("sys.modules", {"paddleocr": mock_module}),
        ):
            model = await load_paddle_ocr("config/path")

        assert model is mock_instance
        mock_ctor.assert_called_once_with(use_angle_cls=True, lang="en", show_log=False)

    def test_is_paddleocr_available_queries_exact_module_name(self) -> None:
        """D8 — GAP:is-paddleocr-available-find-spec-arg (3)."""
        from backend.services.model_zoo import _is_paddleocr_available

        seen: list[Any] = []

        def fake_find_spec(name: Any) -> Any:
            seen.append(name)
            return MagicMock() if name == "paddleocr" else None

        with patch("importlib.util.find_spec", side_effect=fake_find_spec, autospec=True):
            assert _is_paddleocr_available() is True
        assert seen == ["paddleocr"]


class TestModelZooEvictionFlags:
    """D4 — GAP:init-model-zoo-eviction-flags-strict (20). models.yml is the
    single source of truth; the pre-existing assert was an `or` form that None
    satisfies. priority/preload/never_evict feed VRAM eviction and the
    BACKEND_MODEL_PRELOAD startup pass — a dropped str()/bool() wrapper or
    damaged key read silently disables both.

    Probe row: face-detector-scrfd (R8 S2b retarget — the original probe was
    smoke-fire-yolov8n, whose row and loader were both retired). It pins both
    bool edges in one row: preload parses to True and never_evict to False, so
    a missing bool() leaves `is True`/`is False` red on None just as before.
    """

    def setup_method(self) -> None:
        reset_model_zoo()

    def teardown_method(self) -> None:
        reset_model_zoo()

    def test_face_row_eviction_fields_are_strictly_typed(self) -> None:
        config = get_model_config("face-detector-scrfd")
        assert config is not None
        assert type(config.priority) is str
        assert config.priority == "low"
        assert config.preload is True  # bool True, not None / not 'True'
        assert config.never_evict is False  # bool False, not None / not 'False'
        assert type(config.category) is str
        assert config.category == "detection"


class TestModelLoadTimeoutAndDuration:
    """D5 — GAP:load-model-timeout-constant-and-duration-metric (4)."""

    def setup_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_load_model_applies_20s_timeout_constant(self) -> None:
        """timeout=None silently removes the event-loop protection the
        L654-658 comment promises; must stay exactly 20.0 on BOTH wait_for
        call sites (pyroscope and no-pyroscope branches)."""
        import backend.services.model_zoo as mz

        captured: list[Any] = []

        async def spy_wait_for(awaitable: Any, timeout: float | None = None) -> Any:
            captured.append(timeout)
            awaitable.close()
            return MagicMock()

        manager = ModelManager()

        async def dummy_load(path: str) -> Any:
            return MagicMock()

        with (
            patch.object(mz.asyncio, "wait_for", spy_wait_for),
            patch.object(get_model_config("yolo11-license-plate"), "load_fn", dummy_load),
        ):
            async with manager.load("yolo11-license-plate"):
                pass

        assert captured and all(t == 20.0 for t in captured)

    @pytest.mark.asyncio
    async def test_load_duration_metric_is_a_realistic_duration(self) -> None:
        """MODEL_LOAD_DURATION must record a *duration* (perf_counter delta),
        not an absolute clock reading (the - -> + mutant records ~1e9 s;
        existing asserts are all >= lower bounds)."""
        from backend.core.metrics import MODEL_LOAD_DURATION

        manager = ModelManager()

        async def slowish_load(path: str) -> Any:
            await asyncio.sleep(0.01)
            return MagicMock()

        with patch.object(get_model_config("yolo11-face"), "load_fn", slowish_load):
            async with manager.load("yolo11-face"):
                pass

        value = MODEL_LOAD_DURATION.labels(model="yolo11-face")._value.get()
        assert 0.005 <= value < 10.0


class TestResolveModelPathContracts:
    """D6 — GAP:resolve-model-path-runtime-path-branch (4) + empty-local-
    prefix (1). runtime_path is priority 1 and the sentinel entries depend
    on it being used VERBATIM — damaged key lookups silently fall through to
    the base_path join and hand loaders a nonexistent directory."""

    def test_runtime_path_wins_verbatim(self) -> None:
        from backend.services.model_zoo import _resolve_model_path

        sentinel = {"runtime_path": "fast-alpr", "local_path": "model-zoo/fast-alpr"}
        assert _resolve_model_path(sentinel, "/models/model-zoo") == "fast-alpr"

    def test_empty_local_path_falls_back_to_base(self) -> None:
        from backend.services.model_zoo import _resolve_model_path

        assert _resolve_model_path({"local_path": None}, "/models/model-zoo") == (
            "/models/model-zoo"
        )
        assert _resolve_model_path({}, "/models/model-zoo") == "/models/model-zoo"

    def test_registry_sentinel_paths(self) -> None:
        """Tripwire for the whole branch against real models.yml data."""
        assert get_model_config("fast-alpr").path == "fast-alpr"


class TestModelZooBasePathEnv:
    """D7 — GAP:model-zoo-base-path-env-var-name (2). MODEL_ZOO_PATH is the
    container-mount override; a renamed lookup silently reverts every
    deployment to the baked-in default."""

    def test_env_var_name_is_exact(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.model_zoo import _get_model_zoo_base_path

        monkeypatch.setenv("MODEL_ZOO_PATH", "/mnt/custom-models")
        assert _get_model_zoo_base_path() == "/mnt/custom-models"

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.model_zoo import _get_model_zoo_base_path

        monkeypatch.delenv("MODEL_ZOO_PATH", raising=False)
        assert _get_model_zoo_base_path() == "/models/model-zoo"


class TestReloadContracts:
    """D9/D10/D11 — reload reference-count restore (2), stale-unload +
    CUDA clear (2), unload phantom load-count entry (1)."""

    def setup_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_reload_sets_single_reference_count(self) -> None:
        """After reload() the model is owned exactly once; get_status() is
        the public window onto _load_counts."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(get_model_config("yolo11-license-plate"), "load_fn", mock_load):
            await manager.preload("yolo11-license-plate")
            await manager.reload("yolo11-license-plate", "oom")
            assert manager.get_status()["load_counts"] == {"yolo11-license-plate": 1}

            await manager.unload("yolo11-license-plate")
            assert manager.get_status()["load_counts"] == {}
            assert not manager.is_loaded("yolo11-license-plate")

    @pytest.mark.asyncio
    async def test_reload_unloads_stale_model_and_clears_cuda_cache(self) -> None:
        """reload() must drop the stale instance (else VRAM double-allocates
        — the exact failure reload exists to fix) and clear the CUDA cache."""
        manager = ModelManager()
        models = iter([MagicMock(name="first-load"), MagicMock(name="second-load")])

        async def mock_load(path: str) -> Any:
            return next(models)

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with (
            patch.object(get_model_config("yolo11-face"), "load_fn", mock_load),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            await manager.preload("yolo11-face")
            mock_torch.cuda.empty_cache.assert_not_called()

            await manager.reload("yolo11-face", "crash")
            mock_torch.cuda.empty_cache.assert_called_once()
            assert manager.is_loaded("yolo11-face")

    @pytest.mark.asyncio
    async def test_unload_removes_load_count_entry(self) -> None:
        """D11: unload must POP the load-count entry (phantom entries make
        get_status lie and later `count - 1` TypeErrors possible)."""
        manager = ModelManager()
        mock_model = MagicMock()

        async def mock_load(path: str) -> Any:
            return mock_model

        with patch.object(get_model_config("yolo11-face"), "load_fn", mock_load):
            await manager.preload("yolo11-face")
            await manager.unload("yolo11-face")

        assert manager.get_status()["load_counts"] == {}


class TestLoadFnPathArgument:
    """D12 — GAP:load-fn-invocation-path-arg (1)."""

    def setup_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    def teardown_method(self) -> None:
        reset_model_zoo()
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_load_model_passes_configured_path_to_load_fn(self) -> None:
        manager = ModelManager()
        mock_model = MagicMock()
        seen_paths: list[Any] = []

        async def capture_load(path: Any) -> Any:
            seen_paths.append(path)
            return mock_model

        config = get_model_config("yolo11-license-plate")
        assert config is not None
        with patch.object(config, "load_fn", capture_load):
            async with manager.load("yolo11-license-plate"):
                pass

        assert seen_paths == [config.path]


class TestResidencyRowsAreDeclared:
    """Item 1 / F11 (owner ruling 2026-09-27): the sweep now honors cfg.preload,
    so the rows are the contract — a mechanism with no declared rows preloads
    nothing and leaves the legs answering "unavailable" on the target card.

    The three F11 rows below are the ones whose handles are read from the
    manager's registry by membership and never loaded on demand:
    osnet_loader.get_reid_handle, and face_recognizer_loader.get_face_leg_handles
    (which needs BOTH face rows or returns None). The plate leg is deliberately
    absent — it self-loads through fast_alpr_loader and the optional [alpr]
    extra, not the zoo registry.

    The set-equality pin DERIVES its expectation from the yaml rather than a
    hand-copied list: asserting a literal here silently overtook reality once
    already while this test was being written (found by running it, not by
    reading it). That is why the retirement of the smoke-fire row — the fourth
    preload row until R8 S2b — needed no edit here.
    """

    F11_ROWS = ("osnet-ain-x1-0", "face-detector-scrfd", "face-recognizer")

    def setup_method(self) -> None:
        reset_model_zoo()

    def teardown_method(self) -> None:
        reset_model_zoo()

    def test_f11_rows_declare_preload_true(self) -> None:
        for name in self.F11_ROWS:
            config = get_model_config(name)
            assert config is not None, name
            assert config.enabled is True, name
            assert config.preload is True, f"{name} must declare preload: true"

    def test_shipped_zoo_selects_every_declared_row(self) -> None:
        """End-to-end: the real models.yml through the real parser into the real
        selector. Flag on => the resident set is exactly the rows that opt in —
        nothing dropped by the predicate, nothing smuggled in."""
        from pathlib import Path

        import yaml

        from backend.main import select_preload_candidates

        entries = yaml.safe_load(Path("models.yml").read_text())["models"]
        declared = sorted(
            e["name"] for e in entries if e.get("preload") is True and e.get("enabled") is True
        )
        selected = select_preload_candidates(get_model_zoo(), preload_enabled=True)
        assert sorted(selected) == declared
        assert set(self.F11_ROWS) <= set(selected), (
            "F11's specialist rows must be in the boot-resident set"
        )
        # Declared-but-unregistered rows (a loader whose optional deps are absent
        # here) are the only allowed difference, and it must be small and named.
        missing = set(declared) - set(selected)
        assert not missing, f"declared rows the selector dropped: {sorted(missing)}"

    def test_flag_off_selects_nothing_on_the_shipped_zoo(self) -> None:
        """The CPU/sandbox posture stays honest: residency off => zero rows, the
        legs answer 'unavailable' rather than pretending."""
        from backend.main import select_preload_candidates

        assert select_preload_candidates(get_model_zoo(), preload_enabled=False) == []
