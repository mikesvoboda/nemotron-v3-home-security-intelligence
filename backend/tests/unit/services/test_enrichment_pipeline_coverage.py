"""Additional unit tests for enrichment_pipeline.py to increase coverage to 85%+.

This test file focuses on previously untested code paths:
- get_enrichment_for_detection() method with all enrichment types
- _run_reid() error handling and attribute extraction paths
- _run_ocr() inner function branches (empty results, no texts)
- Error handling in classification methods
- Image quality disabled path
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    FaceResult,
    LicensePlateResult,
)
from backend.services.fashion_clip_loader import ClothingClassification
from backend.services.image_quality_loader import ImageQualityResult
from backend.services.pet_classifier_loader import PetClassificationResult
from backend.services.segformer_loader import ClothingSegmentationResult
from backend.services.vehicle_classifier_loader import VehicleClassificationResult
from backend.services.vehicle_damage_loader import DamageDetection, VehicleDamageResult
from backend.services.weather_loader import WeatherResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def enrichment_result_with_data() -> EnrichmentResult:
    """Create an EnrichmentResult with various enrichment data populated."""
    result = EnrichmentResult()

    # Add vehicle classification
    result.vehicle_classifications["1"] = VehicleClassificationResult(
        vehicle_type="sedan",
        confidence=0.92,
        display_name="Sedan",
        is_commercial=False,
        all_scores={"sedan": 0.92, "suv": 0.05},
    )

    # Add vehicle damage
    result.vehicle_damage["2"] = VehicleDamageResult(
        detections=[
            DamageDetection(
                damage_type="glass_shatter",
                confidence=0.88,
                bbox=(100, 100, 200, 200),
                has_mask=False,
                mask_area=0,
            )
        ]
    )

    # Add pet classification
    result.pet_classifications["3"] = PetClassificationResult(
        animal_type="dog",
        confidence=0.95,
        cat_score=0.02,
        dog_score=0.95,
        is_household_pet=True,
    )

    # Add clothing classification
    result.clothing_classifications["4"] = ClothingClassification(
        top_category="hoodie",
        confidence=0.87,
        all_scores={"hoodie": 0.87, "jacket": 0.10},
        is_suspicious=True,
        is_service_uniform=False,
        raw_description="dark hoodie",
    )

    # Add clothing segmentation
    result.clothing_segmentation["5"] = ClothingSegmentationResult(
        clothing_items={"hat", "sunglasses"},
        has_face_covered=True,
        has_bag=False,
        coverage_percentages={"hat": 15.0, "sunglasses": 5.0},
        raw_mask=None,
    )

    # Add license plates
    result.license_plates.append(
        LicensePlateResult(
            bbox=BoundingBox(x1=10, y1=20, x2=30, y2=40),
            text="ABC123",
            confidence=0.90,
            ocr_confidence=0.85,
            source_detection_id=6,
        )
    )

    # Add faces
    result.faces.append(
        FaceResult(
            bbox=BoundingBox(x1=50, y1=60, x2=70, y2=80),
            confidence=0.93,
            source_detection_id=7,
        )
    )

    # Add weather classification
    result.weather_classification = WeatherResult(
        condition="rainy",
        simple_condition="rain",
        confidence=0.82,
        all_scores={"rainy": 0.82, "cloudy": 0.15, "sunny": 0.03},
    )

    # Add image quality
    result.image_quality = ImageQualityResult(
        quality_score=45.0,
        brisque_score=55.0,
        is_blurry=True,
        is_noisy=True,
        is_low_quality=True,
        quality_issues=["blur", "noise"],
    )

    return result


# =============================================================================
# Tests for get_enrichment_for_detection()
# =============================================================================


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_vehicle_classification(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with vehicle classification only."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(1)

    assert enrichment is not None
    assert "vehicle" in enrichment
    assert enrichment["vehicle"]["type"] == "sedan"
    assert enrichment["vehicle"]["confidence"] == 0.92
    assert enrichment["vehicle"]["damage"] == []
    assert enrichment["vehicle"]["color"] is None


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_vehicle_damage_only(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with vehicle damage but no classification."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(2)

    assert enrichment is not None
    assert "vehicle" in enrichment
    assert enrichment["vehicle"]["type"] is None
    assert enrichment["vehicle"]["confidence"] is None
    assert len(enrichment["vehicle"]["damage"]) == 1
    assert enrichment["vehicle"]["damage"][0]["type"] == "glass_shatter"


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_pet_classification(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with pet classification."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(3)

    assert enrichment is not None
    assert "pet" in enrichment
    assert enrichment["pet"]["type"] == "dog"
    assert enrichment["pet"]["confidence"] == 0.95
    assert enrichment["pet"]["breed"] is None


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_clothing_classification(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with clothing classification."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(4)

    assert enrichment is not None
    assert "person" in enrichment
    assert enrichment["person"]["clothing"] == "hoodie"
    assert enrichment["person"]["confidence"] == 0.87
    assert enrichment["person"]["action"] is None
    assert enrichment["person"]["carrying"] is None


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_clothing_segmentation_only(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with clothing segmentation but no classification."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(5)

    assert enrichment is not None
    assert "person" in enrichment
    assert enrichment["person"]["face_covered"] is True
    assert enrichment["person"]["clothing"] is None
    assert enrichment["person"]["confidence"] is None


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_license_plate(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with license plate."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(6)

    assert enrichment is not None
    assert "license_plate" in enrichment
    assert enrichment["license_plate"]["text"] == "ABC123"
    assert enrichment["license_plate"]["confidence"] == 0.85


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_faces(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection with faces."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(7)

    assert enrichment is not None
    assert enrichment["face_detected"] is True
    assert enrichment["face_count"] == 1


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_shared_weather(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection includes shared weather data."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(1)

    assert enrichment is not None
    assert "weather" in enrichment
    assert enrichment["weather"]["condition"] == "rainy"
    assert enrichment["weather"]["confidence"] == 0.82


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_shared_image_quality(
    enrichment_result_with_data: EnrichmentResult,
) -> None:
    """Test get_enrichment_for_detection includes shared image quality data."""
    enrichment = enrichment_result_with_data.get_enrichment_for_detection(1)

    assert enrichment is not None
    assert "image_quality" in enrichment
    assert enrichment["image_quality"]["score"] == 45.0
    assert "blur" in enrichment["image_quality"]["issues"]
    assert "noise" in enrichment["image_quality"]["issues"]


@pytest.mark.asyncio
async def test_get_enrichment_for_detection_no_data() -> None:
    """Test get_enrichment_for_detection returns None when no data available."""
    result = EnrichmentResult()
    enrichment = result.get_enrichment_for_detection(999)

    assert enrichment is None


# =============================================================================
# Tests for _run_reid() error handling and attribute extraction
# =============================================================================


@pytest.mark.asyncio
async def test_run_reid_with_person_attributes() -> None:
    """Test _run_reid extracts person attributes from vision extraction."""
    from backend.services.vision_extractor import BatchExtractionResult, PersonAttributes

    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock()
    mock_model_manager.load.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_model_manager.load.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_redis = AsyncMock()
    mock_reid_service = AsyncMock()
    mock_reid_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_reid_service.find_matching_entities = AsyncMock(return_value=[])
    mock_reid_service.store_embedding = AsyncMock()

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        redis_client=mock_redis,
        reid_enabled=True,
    )
    pipeline._reid_service = mock_reid_service

    # Create result with vision extraction person attributes
    result = EnrichmentResult()
    result.vision_extraction = BatchExtractionResult(
        person_attributes={
            "1": PersonAttributes(
                clothing="black jacket",
                carrying="backpack",
                is_service_worker=False,
                action="walking",
                caption="Person wearing black jacket carrying backpack",
            )
        },
        vehicle_attributes={},
    )

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    await pipeline._run_reid([person_det], image, "front_door", result)

    # Verify store_embedding was called with person attributes
    mock_reid_service.store_embedding.assert_called_once()
    call_args = mock_reid_service.store_embedding.call_args
    entity_embedding = call_args[0][1]
    assert entity_embedding.attributes["clothing"] == "black jacket"
    assert entity_embedding.attributes["carrying"] == "backpack"


@pytest.mark.asyncio
async def test_run_reid_with_vehicle_attributes() -> None:
    """Test _run_reid extracts vehicle attributes from vision extraction."""
    from backend.services.vision_extractor import BatchExtractionResult, VehicleAttributes

    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock()
    mock_model_manager.load.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_model_manager.load.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_redis = AsyncMock()
    mock_reid_service = AsyncMock()
    mock_reid_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_reid_service.find_matching_entities = AsyncMock(return_value=[])
    mock_reid_service.store_embedding = AsyncMock()

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        redis_client=mock_redis,
        reid_enabled=True,
    )
    pipeline._reid_service = mock_reid_service

    # Create result with vision extraction vehicle attributes
    result = EnrichmentResult()
    result.vision_extraction = BatchExtractionResult(
        person_attributes={},
        vehicle_attributes={
            "1": VehicleAttributes(
                vehicle_type="sedan",
                color="blue",
                is_commercial=False,
                commercial_text=None,
                caption="Blue sedan parked",
            )
        },
    )

    vehicle_det = DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
    )

    image = Image.new("RGB", (640, 480))

    await pipeline._run_reid([vehicle_det], image, "driveway", result)

    # Verify store_embedding was called with vehicle attributes
    mock_reid_service.store_embedding.assert_called_once()
    call_args = mock_reid_service.store_embedding.call_args
    entity_embedding = call_args[0][1]
    assert entity_embedding.attributes["color"] == "blue"
    assert entity_embedding.attributes["vehicle_type"] == "sedan"


@pytest.mark.asyncio
async def test_run_reid_error_handling() -> None:
    """Test _run_reid continues on error for individual detections."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock()
    mock_model_manager.load.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_model_manager.load.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_redis = AsyncMock()
    mock_reid_service = AsyncMock()
    mock_reid_service.generate_embedding = AsyncMock(side_effect=RuntimeError("Embedding failed"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        redis_client=mock_redis,
        reid_enabled=True,
    )
    pipeline._reid_service = mock_reid_service

    result = EnrichmentResult()

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    # Should not raise exception, just log warning
    await pipeline._run_reid([person_det], image, "front_door", result)

    # Result should be empty since embedding failed
    assert not result.person_reid_matches
    assert not result.vehicle_reid_matches


# =============================================================================
# Tests for _run_ocr() inner function branches
# =============================================================================


@pytest.mark.asyncio
async def test_run_ocr_empty_result() -> None:
    """Test _run_ocr handles empty OCR result."""
    mock_model_manager = MagicMock()

    pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

    # Mock OCR that returns empty result
    mock_ocr = MagicMock()
    mock_ocr.ocr = MagicMock(return_value=None)

    image = Image.new("RGB", (100, 50))

    text, confidence = await pipeline._run_ocr(mock_ocr, image)

    assert text == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_run_ocr_result_with_no_lines() -> None:
    """Test _run_ocr handles OCR result with empty lines."""
    mock_model_manager = MagicMock()

    pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

    # Mock OCR that returns result with no lines
    mock_ocr = MagicMock()
    mock_ocr.ocr = MagicMock(return_value=[[]])

    image = Image.new("RGB", (100, 50))

    text, confidence = await pipeline._run_ocr(mock_ocr, image)

    assert text == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_run_ocr_result_with_invalid_lines() -> None:
    """Test _run_ocr handles OCR result with invalid line format."""
    mock_model_manager = MagicMock()

    pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

    # Mock OCR that returns result with invalid lines (no text_info tuple)
    mock_ocr = MagicMock()
    mock_ocr.ocr = MagicMock(return_value=[[None, None]])

    image = Image.new("RGB", (100, 50))

    text, confidence = await pipeline._run_ocr(mock_ocr, image)

    assert text == ""
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_run_ocr_exception_handling() -> None:
    """Test _run_ocr handles exceptions gracefully."""
    mock_model_manager = MagicMock()

    pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

    # Mock OCR that raises exception
    mock_ocr = MagicMock()
    mock_ocr.ocr = MagicMock(side_effect=RuntimeError("OCR failed"))

    image = Image.new("RGB", (100, 50))

    text, confidence = await pipeline._run_ocr(mock_ocr, image)

    assert text == ""
    assert confidence == 0.0


# =============================================================================
# Tests for error handling in classification methods
# =============================================================================


@pytest.mark.asyncio
async def test_classify_weather_model_not_available() -> None:
    """Test _classify_weather handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("weather-classification"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        weather_classification_enabled=True,
    )

    image = Image.new("RGB", (640, 480))

    with pytest.raises(RuntimeError, match="weather-classification model not configured"):
        await pipeline._classify_weather(image)


@pytest.mark.asyncio
async def test_detect_violence_model_not_available() -> None:
    """Test _detect_violence handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("violence-detection"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        violence_detection_enabled=True,
    )

    image = Image.new("RGB", (640, 480))

    with pytest.raises(RuntimeError, match="violence-detection model not configured"):
        await pipeline._detect_violence(image)


@pytest.mark.asyncio
async def test_assess_image_quality_model_not_available() -> None:
    """Test _assess_image_quality handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("brisque-quality"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        image_quality_enabled=True,
    )

    image = Image.new("RGB", (640, 480))

    with pytest.raises(RuntimeError, match="brisque-quality model not configured"):
        await pipeline._assess_image_quality(image, camera_id="front_door")


@pytest.mark.asyncio
async def test_assess_image_quality_model_disabled() -> None:
    """Test _assess_image_quality handles disabled model (pyiqa incompatibility)."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(
        side_effect=RuntimeError("Model disabled due to pyiqa incompatibility")
    )

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        image_quality_enabled=True,
    )

    image = Image.new("RGB", (640, 480))

    # Should raise but with disabled message
    with pytest.raises(RuntimeError, match="disabled"):
        await pipeline._assess_image_quality(image, camera_id="front_door")


@pytest.mark.asyncio
async def test_classify_person_clothing_model_not_available() -> None:
    """Test _classify_person_clothing handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("fashion-clip"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        clothing_classification_enabled=True,
    )

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_person_clothing([person_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_classify_person_clothing_individual_failure() -> None:
    """Test _classify_person_clothing continues on individual person failure."""

    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock()
    mock_model_manager.load.return_value.__aenter__ = AsyncMock(return_value=("model", "processor"))
    mock_model_manager.load.return_value.__aexit__ = AsyncMock(return_value=None)

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        clothing_classification_enabled=True,
    )

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    with patch(
        "backend.services.enrichment_pipeline.classify_clothing",
        side_effect=RuntimeError("Classification failed"),
    ):
        # Should return empty dict, not raise
        result = await pipeline._classify_person_clothing([person_det], image)

        assert result == {}


@pytest.mark.asyncio
async def test_segment_person_clothing_model_not_available() -> None:
    """Test _segment_person_clothing handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("segformer-b2-clothes"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        clothing_segmentation_enabled=True,
    )

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._segment_person_clothing([person_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_classify_vehicle_types_model_not_available() -> None:
    """Test _classify_vehicle_types handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("vehicle-segment-classification"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        vehicle_classification_enabled=True,
    )

    vehicle_det = DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_vehicle_types([vehicle_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_detect_vehicle_damage_model_not_available() -> None:
    """Test _detect_vehicle_damage handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("vehicle-damage-detection"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        vehicle_damage_detection_enabled=True,
    )

    vehicle_det = DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._detect_vehicle_damage([vehicle_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_classify_pets_model_not_available() -> None:
    """Test _classify_pets handles missing model gracefully."""
    mock_model_manager = MagicMock()
    mock_model_manager.load = MagicMock(side_effect=KeyError("pet-classifier"))

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        pet_classification_enabled=True,
    )

    dog_det = DetectionInput(
        id=1,
        class_name="dog",
        confidence=0.88,
        bbox=BoundingBox(x1=200, y1=300, x2=280, y2=400),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_pets([dog_det], image)

    assert result == {}


# =============================================================================
# Tests for enrichment service error handling
# =============================================================================


@pytest.mark.asyncio
async def test_classify_vehicle_via_service_enrichment_unavailable() -> None:
    """Test _classify_vehicle_via_service handles EnrichmentUnavailableError."""
    from backend.services.enrichment_client import EnrichmentUnavailableError

    mock_model_manager = MagicMock()
    mock_enrichment_client = AsyncMock()
    mock_enrichment_client.classify_vehicle = AsyncMock(
        side_effect=EnrichmentUnavailableError("Service unavailable")
    )

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        use_enrichment_service=True,
        enrichment_client=mock_enrichment_client,
    )

    vehicle_det = DetectionInput(
        id=1,
        class_name="car",
        confidence=0.92,
        bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_vehicle_via_service([vehicle_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_classify_pets_via_service_enrichment_unavailable() -> None:
    """Test _classify_pets_via_service handles EnrichmentUnavailableError."""
    from backend.services.enrichment_client import EnrichmentUnavailableError

    mock_model_manager = MagicMock()
    mock_enrichment_client = AsyncMock()
    mock_enrichment_client.classify_pet = AsyncMock(
        side_effect=EnrichmentUnavailableError("Service unavailable")
    )

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        use_enrichment_service=True,
        enrichment_client=mock_enrichment_client,
    )

    dog_det = DetectionInput(
        id=1,
        class_name="dog",
        confidence=0.88,
        bbox=BoundingBox(x1=200, y1=300, x2=280, y2=400),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_pets_via_service([dog_det], image)

    assert result == {}


@pytest.mark.asyncio
async def test_classify_clothing_via_service_enrichment_unavailable() -> None:
    """Test _classify_clothing_via_service handles EnrichmentUnavailableError."""
    from backend.services.enrichment_client import EnrichmentUnavailableError

    mock_model_manager = MagicMock()
    mock_enrichment_client = AsyncMock()
    mock_enrichment_client.classify_clothing = AsyncMock(
        side_effect=EnrichmentUnavailableError("Service unavailable")
    )

    pipeline = EnrichmentPipeline(
        model_manager=mock_model_manager,
        use_enrichment_service=True,
        enrichment_client=mock_enrichment_client,
    )

    person_det = DetectionInput(
        id=1,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
    )

    image = Image.new("RGB", (640, 480))

    # Should return empty dict, not raise
    result = await pipeline._classify_clothing_via_service([person_det], image)

    assert result == {}
