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
    async def test_load_paddle_ocr_import_error(self) -> None:
        """Test that load_paddle_ocr raises ImportError when paddleocr missing."""
        from backend.services.model_zoo import load_paddle_ocr

        with patch.dict("sys.modules", {"paddleocr": None}):
            import sys

            if "paddleocr" in sys.modules:
                del sys.modules["paddleocr"]

            with (
                patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'paddleocr'"),
                ),
                pytest.raises(ImportError),
            ):
                await load_paddle_ocr("test/config")

    @pytest.mark.asyncio
    async def test_load_paddle_ocr_runtime_error(self) -> None:
        """Test that load_paddle_ocr raises RuntimeError on load failure."""
        from backend.services.model_zoo import load_paddle_ocr

        mock_paddleocr = MagicMock()
        mock_paddleocr.side_effect = ValueError("PaddleOCR initialization failed")

        with (
            patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddleocr)}),
            pytest.raises(RuntimeError, match="Failed to load PaddleOCR"),
        ):
            await load_paddle_ocr("config/path")


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
