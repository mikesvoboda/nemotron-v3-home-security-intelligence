"""Extended unit tests for enrichment_pipeline.py to increase coverage.

This file contains additional tests targeting uncovered lines:
- Service routing methods (_classify_vehicle_via_service, _classify_pets_via_service, _classify_clothing_via_service)
- OCR edge cases (_run_ocr with various failure modes)
- Model loading error paths (KeyError, RuntimeError)
- Helper method edge cases (_crop_to_bbox boundary conditions)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from backend.services.enrichment_client import EnrichmentUnavailableError
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def vehicle_detection() -> DetectionInput:
    """Create a vehicle detection for testing."""
    return DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=150, x2=300, y2=350),
    )


@pytest.fixture
def person_detection() -> DetectionInput:
    """Create a person detection for testing."""
    return DetectionInput(
        id=2,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400),
    )


@pytest.fixture
def dog_detection() -> DetectionInput:
    """Create a dog detection for testing."""
    return DetectionInput(
        id=3,
        class_name="dog",
        confidence=0.88,
        bbox=BoundingBox(x1=200, y1=300, x2=280, y2=400),
    )


class MockAsyncContextManager:
    """Mock async context manager for model loading."""

    def __init__(self, model: Any):
        self._model = model

    async def __aenter__(self) -> Any:
        return self._model

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock ModelManager."""
    manager = MagicMock()

    mock_models: dict[str, Any] = {
        "paddleocr": MagicMock(),
    }

    def mock_load(model_name: str) -> MockAsyncContextManager:
        if model_name in mock_models:
            return MockAsyncContextManager(mock_models[model_name])
        raise KeyError(f"Unknown model: {model_name}")

    manager.load = mock_load
    return manager


# =============================================================================
# Service Routing Tests (use_enrichment_service=True)
# =============================================================================


class TestEnrichmentServiceRouting:
    """Tests for enrichment service routing methods."""

    async def test_classify_vehicle_via_service_success(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test successful vehicle classification via enrichment service."""
        mock_client = AsyncMock()
        mock_remote_result = MagicMock()
        mock_remote_result.vehicle_type = "sedan"
        mock_remote_result.confidence = 0.92
        mock_remote_result.display_name = "Sedan"
        mock_remote_result.is_commercial = False
        mock_remote_result.all_scores = {"sedan": 0.92}
        mock_client.classify_vehicle.return_value = mock_remote_result

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_vehicle_via_service([vehicle_detection], test_image)

        assert "1" in result
        assert result["1"].vehicle_type == "sedan"
        assert result["1"].confidence == 0.92
        mock_client.classify_vehicle.assert_called_once()

    async def test_classify_vehicle_via_service_unavailable(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle classification handles service unavailable gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_vehicle.side_effect = EnrichmentUnavailableError("Service unavailable")

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_vehicle_via_service([vehicle_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_vehicle_via_service_generic_error(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle classification handles generic errors gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_vehicle.side_effect = RuntimeError("Unexpected error")

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_vehicle_via_service([vehicle_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_vehicle_via_service_no_crop(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle classification skips detection when crop fails."""
        # Detection with invalid bbox that will fail cropping
        invalid_detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.92,
            bbox=BoundingBox(x1=700, y1=500, x2=800, y2=600),  # Outside image bounds
        )

        mock_client = AsyncMock()
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_vehicle_via_service([invalid_detection], test_image)

        # Should skip and return empty
        assert result == {}
        mock_client.classify_vehicle.assert_not_called()

    async def test_classify_pets_via_service_success(
        self,
        dog_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test successful pet classification via enrichment service."""
        mock_client = AsyncMock()
        mock_remote_result = MagicMock()
        mock_remote_result.pet_type = "dog"
        mock_remote_result.confidence = 0.95
        mock_remote_result.is_household_pet = True
        mock_client.classify_pet.return_value = mock_remote_result

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_pets_via_service([dog_detection], test_image)

        assert "3" in result
        assert result["3"].animal_type == "dog"
        assert result["3"].confidence == 0.95
        assert result["3"].is_household_pet is True
        mock_client.classify_pet.assert_called_once()

    async def test_classify_pets_via_service_unavailable(
        self,
        dog_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet classification handles service unavailable gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_pet.side_effect = EnrichmentUnavailableError("Service unavailable")

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_pets_via_service([dog_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_pets_via_service_generic_error(
        self,
        dog_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet classification handles generic errors gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_pet.side_effect = RuntimeError("Unexpected error")

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_pets_via_service([dog_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_pets_via_service_no_crop(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet classification skips detection when crop fails."""
        # Detection with invalid bbox
        invalid_detection = DetectionInput(
            id=3,
            class_name="dog",
            confidence=0.88,
            bbox=BoundingBox(x1=700, y1=500, x2=800, y2=600),  # Outside bounds
        )

        mock_client = AsyncMock()
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_pets_via_service([invalid_detection], test_image)

        # Should skip and return empty
        assert result == {}
        mock_client.classify_pet.assert_not_called()

    async def test_classify_clothing_via_service_success(
        self,
        person_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test successful clothing classification via enrichment service."""
        mock_client = AsyncMock()
        mock_remote_result = MagicMock()
        mock_remote_result.top_category = "hoodie"
        mock_remote_result.confidence = 0.88
        mock_remote_result.description = "dark hoodie"
        mock_remote_result.is_suspicious = True
        mock_remote_result.is_service_uniform = False
        mock_client.classify_clothing.return_value = mock_remote_result

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_clothing_via_service([person_detection], test_image)

        assert "2" in result
        assert result["2"].top_category == "hoodie"
        assert result["2"].confidence == 0.88
        assert result["2"].is_suspicious is True
        mock_client.classify_clothing.assert_called_once()

    async def test_classify_clothing_via_service_unavailable(
        self,
        person_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test clothing classification handles service unavailable gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_clothing.side_effect = EnrichmentUnavailableError(
            "Service unavailable"
        )

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_clothing_via_service([person_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_clothing_via_service_generic_error(
        self,
        person_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test clothing classification handles generic errors gracefully."""
        mock_client = AsyncMock()
        mock_client.classify_clothing.side_effect = RuntimeError("Unexpected error")

        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_clothing_via_service([person_detection], test_image)

        # Should return empty dict, not raise
        assert result == {}

    async def test_classify_clothing_via_service_no_crop(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test clothing classification skips detection when crop fails."""
        # Detection with invalid bbox
        invalid_detection = DetectionInput(
            id=2,
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(x1=700, y1=500, x2=800, y2=600),  # Outside bounds
        )

        mock_client = AsyncMock()
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        result = await pipeline._classify_clothing_via_service([invalid_detection], test_image)

        # Should skip and return empty
        assert result == {}
        mock_client.classify_clothing.assert_not_called()


# =============================================================================
# OCR Edge Cases Tests
# =============================================================================


class TestOCREdgeCases:
    """Tests for _run_ocr edge cases."""

    async def test_run_ocr_empty_result(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _run_ocr handles empty OCR results."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None  # No results

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0

    async def test_run_ocr_empty_first_result(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _run_ocr handles empty first OCR result."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]  # Empty first result

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0

    async def test_run_ocr_malformed_line_data(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _run_ocr handles malformed line data gracefully."""
        mock_ocr = MagicMock()
        # Malformed: line without proper text_info tuple
        mock_ocr.ocr.return_value = [
            [
                None,  # Malformed line
                ("ABC", 0.9),  # Incomplete line (missing bbox)
            ]
        ]

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        # Should return empty for malformed data
        assert text == ""
        assert confidence == 0.0

    async def test_run_ocr_exception_handling(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _run_ocr handles exceptions gracefully."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.side_effect = RuntimeError("OCR failed")

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0


# =============================================================================
# Crop Edge Cases Tests
# =============================================================================


class TestCropEdgeCases:
    """Tests for _crop_to_bbox edge cases."""

    async def test_crop_to_bbox_negative_coordinates(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles negative coordinates."""
        bbox = BoundingBox(x1=-10, y1=-20, x2=100, y2=100)

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(test_image, bbox)

        # Should clamp to 0 and succeed
        assert result is not None
        assert result.size == (100, 100)  # (x2-0, y2-0)

    async def test_crop_to_bbox_exceeds_image_bounds(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles coordinates exceeding image bounds."""
        bbox = BoundingBox(x1=500, y1=400, x2=1000, y2=800)

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(test_image, bbox)

        # Should clamp to image size (640x480) and succeed
        assert result is not None
        # Width: min(1000, 640) - 500 = 140
        # Height: min(800, 480) - 400 = 80
        assert result.size == (140, 80)

    async def test_crop_to_bbox_inverted_coordinates(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles inverted coordinates (x2 < x1)."""
        bbox = BoundingBox(x1=200, y1=200, x2=100, y2=100)  # Inverted

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(test_image, bbox)

        # Should return None for invalid bbox
        assert result is None

    async def test_crop_to_bbox_zero_width(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles zero-width bbox."""
        bbox = BoundingBox(x1=100, y1=100, x2=100, y2=200)  # Zero width

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(test_image, bbox)

        # Should return None for zero-dimension bbox
        assert result is None

    async def test_crop_to_bbox_zero_height(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles zero-height bbox."""
        bbox = BoundingBox(x1=100, y1=100, x2=200, y2=100)  # Zero height

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(test_image, bbox)

        # Should return None for zero-dimension bbox
        assert result is None

    async def test_crop_to_bbox_exception_handling(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox handles exceptions gracefully."""
        # Create a mock image that raises on crop
        mock_image = MagicMock(spec=Image.Image)
        mock_image.size = (640, 480)
        mock_image.crop.side_effect = RuntimeError("Crop failed")

        bbox = BoundingBox(x1=100, y1=100, x2=200, y2=200)

        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = await pipeline._crop_to_bbox(mock_image, bbox)

        # Should return None on exception
        assert result is None
