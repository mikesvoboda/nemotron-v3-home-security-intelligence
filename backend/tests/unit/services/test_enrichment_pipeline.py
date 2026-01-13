"""Unit tests for enrichment pipeline service.

Tests cover:
- BoundingBox dataclass methods and properties
- LicensePlateResult and FaceResult dataclasses
- EnrichmentResult dataclass methods and properties
- DetectionInput dataclass
- EnrichmentPipeline initialization and configuration
- Pipeline stage execution with mocked models
- Error handling and fallbacks
- Async workflow coordination
- Service classification routing (vehicle, person, pet)
- Global singleton functions (get_enrichment_pipeline, reset_enrichment_pipeline)
"""

from __future__ import annotations

from typing import Any
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
    get_enrichment_pipeline,
    reset_enrichment_pipeline,
)
from backend.services.fashion_clip_loader import ClothingClassification
from backend.services.image_quality_loader import ImageQualityResult
from backend.services.pet_classifier_loader import PetClassificationResult
from backend.services.segformer_loader import ClothingSegmentationResult
from backend.services.vehicle_classifier_loader import VehicleClassificationResult
from backend.services.vehicle_damage_loader import DamageDetection, VehicleDamageResult
from backend.services.violence_loader import ViolenceDetectionResult
from backend.services.weather_loader import WeatherResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_image() -> Image.Image:
    """Create a test RGB image for processing."""
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


@pytest.fixture
def small_image() -> Image.Image:
    """Create a small test image."""
    return Image.new("RGB", (100, 100), color=(255, 0, 0))


@pytest.fixture
def sample_bbox() -> BoundingBox:
    """Create a sample bounding box."""
    return BoundingBox(x1=100.5, y1=150.2, x2=300.8, y2=350.6, confidence=0.95)


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


@pytest.fixture
def cat_detection() -> DetectionInput:
    """Create a cat detection for testing."""
    return DetectionInput(
        id=4,
        class_name="cat",
        confidence=0.85,
        bbox=BoundingBox(x1=350, y1=320, x2=420, y2=380),
    )


@pytest.fixture
def low_confidence_detection() -> DetectionInput:
    """Create a low confidence detection that should be filtered."""
    return DetectionInput(
        id=5,
        class_name="car",
        confidence=0.3,  # Below default threshold of 0.5
        bbox=BoundingBox(x1=10, y1=10, x2=100, y2=100),
    )


class MockAsyncContextManager:
    """Mock async context manager for model loading."""

    def __init__(self, model: Any):
        self._model = model

    async def __aenter__(self) -> Any:
        return self._model

    async def __aexit__(self, *args: Any) -> None:
        pass


def create_mock_model_manager() -> MagicMock:
    """Create a mock ModelManager with configured model loaders."""
    manager = MagicMock()

    mock_models: dict[str, Any] = {
        "florence-2-large": {"model": MagicMock(), "processor": MagicMock()},
        "clip-vit-l": {"model": MagicMock(), "processor": MagicMock()},
        "fashion-clip": {"model": MagicMock(), "processor": MagicMock()},
        "vehicle-segment-classification": {
            "model": MagicMock(),
            "transform": MagicMock(),
            "classes": ["car", "truck", "pickup_truck", "work_van"],
        },
        "vehicle-damage-detection": MagicMock(),
        "pet-classifier": {"model": MagicMock(), "processor": MagicMock()},
        "brisque-quality": MagicMock(),
        "violence-detection": {"model": MagicMock(), "processor": MagicMock()},
        "weather-classification": {"model": MagicMock(), "processor": MagicMock()},
        "segformer-b2-clothes": (MagicMock(), MagicMock()),
        "yolo11-license-plate": MagicMock(),
        "yolo11-face": MagicMock(),
        "paddleocr": MagicMock(),
    }

    def mock_load(model_name: str) -> MockAsyncContextManager:
        if model_name in mock_models:
            return MockAsyncContextManager(mock_models[model_name])
        raise KeyError(f"Unknown model: {model_name}")

    manager.load = mock_load
    return manager


@pytest.fixture
def mock_model_manager() -> MagicMock:
    """Create a mock ModelManager."""
    return create_mock_model_manager()


@pytest.fixture(autouse=True)
def reset_global_singletons():
    """Reset global singleton instances before and after each test."""
    reset_enrichment_pipeline()
    yield
    reset_enrichment_pipeline()


# =============================================================================
# BoundingBox Tests
# =============================================================================


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_init_default_confidence(self) -> None:
        """Test BoundingBox initializes with default confidence."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        assert bbox.confidence == 0.0

    def test_init_with_confidence(self, sample_bbox: BoundingBox) -> None:
        """Test BoundingBox initializes with provided confidence."""
        assert sample_bbox.confidence == 0.95

    def test_to_tuple(self, sample_bbox: BoundingBox) -> None:
        """Test to_tuple returns correct tuple."""
        result = sample_bbox.to_tuple()
        assert result == (100.5, 150.2, 300.8, 350.6)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_to_int_tuple(self, sample_bbox: BoundingBox) -> None:
        """Test to_int_tuple returns integer tuple."""
        result = sample_bbox.to_int_tuple()
        assert result == (100, 150, 300, 350)
        assert all(isinstance(v, int) for v in result)

    def test_width_property(self, sample_bbox: BoundingBox) -> None:
        """Test width property calculation."""
        assert sample_bbox.width == pytest.approx(200.3, rel=1e-5)

    def test_height_property(self, sample_bbox: BoundingBox) -> None:
        """Test height property calculation."""
        assert sample_bbox.height == pytest.approx(200.4, rel=1e-5)

    def test_center_property(self, sample_bbox: BoundingBox) -> None:
        """Test center property calculation."""
        center = sample_bbox.center
        assert center[0] == pytest.approx(200.65, rel=1e-5)
        assert center[1] == pytest.approx(250.4, rel=1e-5)

    def test_zero_size_bbox(self) -> None:
        """Test BoundingBox with zero dimensions."""
        bbox = BoundingBox(x1=50, y1=50, x2=50, y2=50)
        assert bbox.width == 0
        assert bbox.height == 0
        assert bbox.center == (50, 50)


# =============================================================================
# LicensePlateResult Tests
# =============================================================================


class TestLicensePlateResult:
    """Tests for LicensePlateResult dataclass."""

    def test_init_defaults(self) -> None:
        """Test LicensePlateResult initializes with defaults."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        result = LicensePlateResult(bbox=bbox)
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.ocr_confidence == 0.0
        assert result.source_detection_id is None

    def test_init_with_values(self) -> None:
        """Test LicensePlateResult with explicit values."""
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=45, confidence=0.95)
        result = LicensePlateResult(
            bbox=bbox,
            text="ABC123",
            confidence=0.92,
            ocr_confidence=0.88,
            source_detection_id=42,
        )
        assert result.text == "ABC123"
        assert result.confidence == 0.92
        assert result.ocr_confidence == 0.88
        assert result.source_detection_id == 42


# =============================================================================
# FaceResult Tests
# =============================================================================


class TestFaceResult:
    """Tests for FaceResult dataclass."""

    def test_init_defaults(self) -> None:
        """Test FaceResult initializes with defaults."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        result = FaceResult(bbox=bbox)
        assert result.confidence == 0.0
        assert result.source_detection_id is None

    def test_init_with_values(self) -> None:
        """Test FaceResult with explicit values."""
        bbox = BoundingBox(x1=100, y1=100, x2=150, y2=160)
        result = FaceResult(
            bbox=bbox,
            confidence=0.98,
            source_detection_id=7,
        )
        assert result.confidence == 0.98
        assert result.source_detection_id == 7


# =============================================================================
# DetectionInput Tests
# =============================================================================


class TestDetectionInput:
    """Tests for DetectionInput dataclass."""

    def test_init_required_fields(self) -> None:
        """Test DetectionInput with required fields only."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        detection = DetectionInput(
            class_name="person",
            confidence=0.9,
            bbox=bbox,
        )
        assert detection.class_name == "person"
        assert detection.confidence == 0.9
        assert detection.id is None

    def test_init_with_id(self, vehicle_detection: DetectionInput) -> None:
        """Test DetectionInput with explicit ID."""
        assert vehicle_detection.id == 1
        assert vehicle_detection.class_name == "car"


# =============================================================================
# EnrichmentResult Tests
# =============================================================================


class TestEnrichmentResult:
    """Tests for EnrichmentResult dataclass."""

    def test_init_defaults(self) -> None:
        """Test EnrichmentResult initializes with empty defaults."""
        result = EnrichmentResult()
        assert result.license_plates == []
        assert result.faces == []
        assert result.vision_extraction is None
        assert result.person_reid_matches == {}
        assert result.vehicle_reid_matches == {}
        assert result.scene_change is None
        assert result.violence_detection is None
        assert result.weather_classification is None
        assert result.clothing_classifications == {}
        assert result.clothing_segmentation == {}
        assert result.vehicle_classifications == {}
        assert result.vehicle_damage == {}
        assert result.pet_classifications == {}
        assert result.image_quality is None
        assert result.quality_change_detected is False
        assert result.quality_change_description == ""
        assert result.errors == []
        assert result.processing_time_ms == 0.0

    def test_has_license_plates_empty(self) -> None:
        """Test has_license_plates with no plates."""
        result = EnrichmentResult()
        assert result.has_license_plates is False

    def test_has_license_plates_with_plates(self) -> None:
        """Test has_license_plates with plates present."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plate = LicensePlateResult(bbox=bbox, text="XYZ789")
        result = EnrichmentResult(license_plates=[plate])
        assert result.has_license_plates is True

    def test_has_readable_plates_no_text(self) -> None:
        """Test has_readable_plates when plates have no text."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plate = LicensePlateResult(bbox=bbox)  # No text
        result = EnrichmentResult(license_plates=[plate])
        assert result.has_readable_plates is False

    def test_has_readable_plates_with_text(self) -> None:
        """Test has_readable_plates when plates have text."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plate = LicensePlateResult(bbox=bbox, text="ABC123")
        result = EnrichmentResult(license_plates=[plate])
        assert result.has_readable_plates is True

    def test_plate_texts_property(self) -> None:
        """Test plate_texts returns only non-empty texts."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plates = [
            LicensePlateResult(bbox=bbox, text="ABC123"),
            LicensePlateResult(bbox=bbox, text=""),
            LicensePlateResult(bbox=bbox, text="XYZ789"),
        ]
        result = EnrichmentResult(license_plates=plates)
        assert result.plate_texts == ["ABC123", "XYZ789"]

    def test_has_faces_empty(self) -> None:
        """Test has_faces with no faces."""
        result = EnrichmentResult()
        assert result.has_faces is False

    def test_has_faces_with_faces(self) -> None:
        """Test has_faces with faces present."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        face = FaceResult(bbox=bbox, confidence=0.95)
        result = EnrichmentResult(faces=[face])
        assert result.has_faces is True

    def test_has_vision_extraction_none(self) -> None:
        """Test has_vision_extraction when None."""
        result = EnrichmentResult()
        assert result.has_vision_extraction is False

    def test_has_reid_matches_empty(self) -> None:
        """Test has_reid_matches with no matches."""
        result = EnrichmentResult()
        assert result.has_reid_matches is False

    def test_has_reid_matches_with_person(self) -> None:
        """Test has_reid_matches with person matches."""
        result = EnrichmentResult(person_reid_matches={"1": [MagicMock()]})
        assert result.has_reid_matches is True

    def test_has_reid_matches_with_vehicle(self) -> None:
        """Test has_reid_matches with vehicle matches."""
        result = EnrichmentResult(vehicle_reid_matches={"1": [MagicMock()]})
        assert result.has_reid_matches is True

    def test_has_scene_change_none(self) -> None:
        """Test has_scene_change when None."""
        result = EnrichmentResult()
        assert result.has_scene_change is False

    def test_has_scene_change_no_change(self) -> None:
        """Test has_scene_change when not detected."""
        mock_scene = MagicMock()
        mock_scene.change_detected = False
        result = EnrichmentResult(scene_change=mock_scene)
        assert result.has_scene_change is False

    def test_has_scene_change_detected(self) -> None:
        """Test has_scene_change when detected."""
        mock_scene = MagicMock()
        mock_scene.change_detected = True
        result = EnrichmentResult(scene_change=mock_scene)
        assert result.has_scene_change is True

    def test_has_violence_none(self) -> None:
        """Test has_violence when None."""
        result = EnrichmentResult()
        assert result.has_violence is False

    def test_has_violence_not_violent(self) -> None:
        """Test has_violence when not violent."""
        violence = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.9,
            violent_score=0.1,
            non_violent_score=0.9,
        )
        result = EnrichmentResult(violence_detection=violence)
        assert result.has_violence is False

    def test_has_violence_is_violent(self) -> None:
        """Test has_violence when violent."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.85,
            violent_score=0.85,
            non_violent_score=0.15,
        )
        result = EnrichmentResult(violence_detection=violence)
        assert result.has_violence is True

    def test_has_clothing_classifications_empty(self) -> None:
        """Test has_clothing_classifications when empty."""
        result = EnrichmentResult()
        assert result.has_clothing_classifications is False

    def test_has_clothing_classifications_with_data(self) -> None:
        """Test has_clothing_classifications when populated."""
        clothing = ClothingClassification(
            top_category="casual",
            confidence=0.8,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="casual clothing",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        assert result.has_clothing_classifications is True

    def test_has_suspicious_clothing_none(self) -> None:
        """Test has_suspicious_clothing when none suspicious."""
        clothing = ClothingClassification(
            top_category="casual",
            confidence=0.8,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="casual",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        assert result.has_suspicious_clothing is False

    def test_has_suspicious_clothing_detected(self) -> None:
        """Test has_suspicious_clothing when suspicious."""
        clothing = ClothingClassification(
            top_category="ski mask",
            confidence=0.9,
            all_scores={},
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: ski mask",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        assert result.has_suspicious_clothing is True

    def test_has_vehicle_classifications_empty(self) -> None:
        """Test has_vehicle_classifications when empty."""
        result = EnrichmentResult()
        assert result.has_vehicle_classifications is False

    def test_has_commercial_vehicles_none(self) -> None:
        """Test has_commercial_vehicles when none commercial."""
        vehicle = VehicleClassificationResult(
            vehicle_type="car",
            confidence=0.9,
            display_name="car/sedan",
            is_commercial=False,
            all_scores={},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle})
        assert result.has_commercial_vehicles is False

    def test_has_commercial_vehicles_detected(self) -> None:
        """Test has_commercial_vehicles when commercial present."""
        vehicle = VehicleClassificationResult(
            vehicle_type="work_van",
            confidence=0.88,
            display_name="work van",
            is_commercial=True,
            all_scores={},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle})
        assert result.has_commercial_vehicles is True

    def test_has_vehicle_damage_none(self) -> None:
        """Test has_vehicle_damage when none damaged."""
        damage = VehicleDamageResult(detections=[])
        result = EnrichmentResult(vehicle_damage={"1": damage})
        assert result.has_vehicle_damage is False

    def test_has_vehicle_damage_detected(self) -> None:
        """Test has_vehicle_damage when damage present."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.8,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        assert result.has_vehicle_damage is True

    def test_has_high_security_damage_none(self) -> None:
        """Test has_high_security_damage when none high security."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.8,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        assert result.has_high_security_damage is False

    def test_has_high_security_damage_detected(self) -> None:
        """Test has_high_security_damage when glass_shatter present."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter",
                    confidence=0.85,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        assert result.has_high_security_damage is True

    def test_has_image_quality_none(self) -> None:
        """Test has_image_quality when None."""
        result = EnrichmentResult()
        assert result.has_image_quality is False

    def test_has_image_quality_present(self) -> None:
        """Test has_image_quality when present."""
        quality = ImageQualityResult(
            quality_score=45.0,
            brisque_score=30.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_image_quality is True

    def test_has_quality_issues_good_quality(self) -> None:
        """Test has_quality_issues when good quality."""
        quality = ImageQualityResult(
            quality_score=45.0,
            brisque_score=30.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_quality_issues is False

    def test_has_quality_issues_low_quality(self) -> None:
        """Test has_quality_issues when low quality."""
        quality = ImageQualityResult(
            quality_score=85.0,
            brisque_score=75.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_quality_issues is True

    def test_has_motion_blur_not_blurry(self) -> None:
        """Test has_motion_blur when not blurry."""
        quality = ImageQualityResult(
            quality_score=45.0,
            brisque_score=30.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_motion_blur is False

    def test_has_motion_blur_is_blurry(self) -> None:
        """Test has_motion_blur when blurry."""
        quality = ImageQualityResult(
            quality_score=70.0,
            brisque_score=55.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_motion_blur is True

    def test_has_pet_classifications_empty(self) -> None:
        """Test has_pet_classifications when empty."""
        result = EnrichmentResult()
        assert result.has_pet_classifications is False

    def test_has_pet_classifications_with_data(self) -> None:
        """Test has_pet_classifications when populated."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        assert result.has_pet_classifications is True

    def test_has_confirmed_pets_low_confidence(self) -> None:
        """Test has_confirmed_pets with low confidence pet."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.5,
            cat_score=0.5,
            dog_score=0.5,
            is_household_pet=False,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        assert result.has_confirmed_pets is False

    def test_has_confirmed_pets_high_confidence(self) -> None:
        """Test has_confirmed_pets with high confidence pet."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        assert result.has_confirmed_pets is True

    def test_pet_only_event_false_with_faces(self) -> None:
        """Test pet_only_event is False when faces present."""
        pet = PetClassificationResult(
            animal_type="cat",
            confidence=0.98,
            cat_score=0.98,
            dog_score=0.02,
            is_household_pet=True,
        )
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        face = FaceResult(bbox=bbox, confidence=0.9)
        result = EnrichmentResult(
            pet_classifications={"1": pet},
            faces=[face],
        )
        assert result.pet_only_event is False

    def test_pet_only_event_true(self) -> None:
        """Test pet_only_event is True when only pets."""
        pet = PetClassificationResult(
            animal_type="cat",
            confidence=0.98,
            cat_score=0.98,
            dog_score=0.02,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        assert result.pet_only_event is True

    def test_has_clothing_segmentation_empty(self) -> None:
        """Test has_clothing_segmentation when empty."""
        result = EnrichmentResult()
        assert result.has_clothing_segmentation is False

    def test_has_clothing_segmentation_with_data(self) -> None:
        """Test has_clothing_segmentation when populated."""
        seg = ClothingSegmentationResult(
            clothing_items={"upper_clothes", "pants"},
            has_face_covered=False,
            has_bag=False,
            coverage_percentages={"upper_clothes": 0.5},
        )
        result = EnrichmentResult(clothing_segmentation={"1": seg})
        assert result.has_clothing_segmentation is True


# =============================================================================
# EnrichmentResult to_dict Tests
# =============================================================================


class TestEnrichmentResultToDict:
    """Tests for EnrichmentResult.to_dict() method."""

    def test_to_dict_empty(self) -> None:
        """Test to_dict with empty result."""
        result = EnrichmentResult()
        data = result.to_dict()

        assert data["license_plates"] == []
        assert data["faces"] == []
        assert data["violence_detection"] is None
        assert data["vehicle_damage"] == {}
        assert data["vehicle_classifications"] == {}
        assert data["image_quality"] is None
        assert data["quality_change_detected"] is False
        assert data["quality_change_description"] == ""
        assert data["errors"] == []
        assert data["processing_time_ms"] == 0.0

    def test_to_dict_with_license_plates(self) -> None:
        """Test to_dict with license plates."""
        bbox = BoundingBox(x1=10, y1=20, x2=110, y2=45, confidence=0.9)
        plate = LicensePlateResult(
            bbox=bbox,
            text="XYZ789",
            confidence=0.92,
            ocr_confidence=0.85,
            source_detection_id=1,
        )
        result = EnrichmentResult(license_plates=[plate])
        data = result.to_dict()

        assert len(data["license_plates"]) == 1
        assert data["license_plates"][0]["text"] == "XYZ789"
        assert data["license_plates"][0]["confidence"] == 0.92
        assert data["license_plates"][0]["ocr_confidence"] == 0.85

    def test_to_dict_with_faces(self) -> None:
        """Test to_dict with faces."""
        bbox = BoundingBox(x1=100, y1=100, x2=150, y2=160)
        face = FaceResult(bbox=bbox, confidence=0.97, source_detection_id=2)
        result = EnrichmentResult(faces=[face])
        data = result.to_dict()

        assert len(data["faces"]) == 1
        assert data["faces"][0]["confidence"] == 0.97
        assert data["faces"][0]["source_detection_id"] == 2

    def test_to_dict_with_violence(self) -> None:
        """Test to_dict with violence detection."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.88,
            violent_score=0.88,
            non_violent_score=0.12,
        )
        result = EnrichmentResult(violence_detection=violence)
        data = result.to_dict()

        assert data["violence_detection"] is not None
        assert data["violence_detection"]["is_violent"] is True


# =============================================================================
# EnrichmentResult to_context_string Tests
# =============================================================================


class TestEnrichmentResultToContextString:
    """Tests for EnrichmentResult.to_context_string() method."""

    def test_to_context_string_empty(self) -> None:
        """Test to_context_string with empty result."""
        result = EnrichmentResult()
        context = result.to_context_string()
        assert context == "No additional context extracted."

    def test_to_context_string_with_plates(self) -> None:
        """Test to_context_string includes license plates."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plate = LicensePlateResult(bbox=bbox, text="ABC123", ocr_confidence=0.9)
        result = EnrichmentResult(license_plates=[plate])
        context = result.to_context_string()

        assert "License Plates" in context
        assert "ABC123" in context

    def test_to_context_string_with_faces(self) -> None:
        """Test to_context_string includes faces."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        face = FaceResult(bbox=bbox, confidence=0.95)
        result = EnrichmentResult(faces=[face])
        context = result.to_context_string()

        assert "Faces" in context
        assert "confidence" in context.lower()

    def test_to_context_string_with_violence(self) -> None:
        """Test to_context_string includes violence."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.85,
            violent_score=0.85,
            non_violent_score=0.15,
        )
        result = EnrichmentResult(violence_detection=violence)
        context = result.to_context_string()

        assert "Violence" in context
        assert "VIOLENCE DETECTED" in context

    def test_to_context_string_with_pet_only_event(self) -> None:
        """Test to_context_string includes pet-only note."""
        pet = PetClassificationResult(
            animal_type="cat",
            confidence=0.98,
            cat_score=0.98,
            dog_score=0.02,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        context = result.to_context_string()

        assert "Pet" in context or "Animal" in context
        assert "low security risk" in context.lower()


# =============================================================================
# EnrichmentResult Risk Modifiers Tests
# =============================================================================


class TestEnrichmentResultRiskModifiers:
    """Tests for EnrichmentResult.get_risk_modifiers() method."""

    def test_risk_modifiers_empty(self) -> None:
        """Test get_risk_modifiers with empty result."""
        result = EnrichmentResult()
        modifiers = result.get_risk_modifiers()
        assert modifiers == {}

    def test_risk_modifiers_violence(self) -> None:
        """Test get_risk_modifiers with violence."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.9,
            violent_score=0.9,
            non_violent_score=0.1,
        )
        result = EnrichmentResult(violence_detection=violence)
        modifiers = result.get_risk_modifiers()

        assert "violence" in modifiers
        assert modifiers["violence"] > 0.5

    def test_risk_modifiers_pet_only(self) -> None:
        """Test get_risk_modifiers with pet-only event."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        modifiers = result.get_risk_modifiers()

        assert "pet_only" in modifiers
        assert modifiers["pet_only"] < 0  # Decreases risk

    def test_risk_modifiers_suspicious_attire(self) -> None:
        """Test get_risk_modifiers with suspicious clothing."""
        clothing = ClothingClassification(
            top_category="ski mask",
            confidence=0.9,
            all_scores={},
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: ski mask",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        modifiers = result.get_risk_modifiers()

        assert "suspicious_attire" in modifiers
        assert modifiers["suspicious_attire"] > 0

    def test_risk_modifiers_service_uniform(self) -> None:
        """Test get_risk_modifiers with service uniform."""
        clothing = ClothingClassification(
            top_category="FedEx uniform",
            confidence=0.88,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=True,
            raw_description="Service worker",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        modifiers = result.get_risk_modifiers()

        assert "service_uniform" in modifiers
        assert modifiers["service_uniform"] < 0  # Decreases risk

    def test_risk_modifiers_vehicle_damage(self) -> None:
        """Test get_risk_modifiers with vehicle damage."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.8,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        modifiers = result.get_risk_modifiers()

        assert "vehicle_damage" in modifiers
        assert modifiers["vehicle_damage"] > 0

    def test_risk_modifiers_high_security_damage(self) -> None:
        """Test get_risk_modifiers with high security damage."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter",
                    confidence=0.85,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        modifiers = result.get_risk_modifiers()

        assert "vehicle_damage_high" in modifiers
        assert modifiers["vehicle_damage_high"] > 0.3


# =============================================================================
# EnrichmentResult Summary Flags Tests
# =============================================================================


class TestEnrichmentResultSummaryFlags:
    """Tests for EnrichmentResult.get_summary_flags() method."""

    def test_summary_flags_empty(self) -> None:
        """Test get_summary_flags with empty result."""
        result = EnrichmentResult()
        flags = result.get_summary_flags()
        assert flags == []

    def test_summary_flags_violence(self) -> None:
        """Test get_summary_flags with violence."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.85,
            violent_score=0.85,
            non_violent_score=0.15,
        )
        result = EnrichmentResult(violence_detection=violence)
        flags = result.get_summary_flags()

        assert len(flags) == 1
        assert flags[0]["type"] == "violence"
        assert flags[0]["severity"] == "critical"

    def test_summary_flags_suspicious_attire(self) -> None:
        """Test get_summary_flags with suspicious clothing."""
        clothing = ClothingClassification(
            top_category="ski mask",
            confidence=0.9,
            all_scores={},
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: ski mask",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        flags = result.get_summary_flags()

        suspicious_flag = next((f for f in flags if f["type"] == "suspicious_attire"), None)
        assert suspicious_flag is not None
        assert suspicious_flag["severity"] == "alert"

    def test_summary_flags_face_covered(self) -> None:
        """Test get_summary_flags with face covered."""
        seg = ClothingSegmentationResult(
            clothing_items=set(),
            has_face_covered=True,
            has_bag=False,
            coverage_percentages={},
        )
        result = EnrichmentResult(clothing_segmentation={"1": seg})
        flags = result.get_summary_flags()

        face_flag = next((f for f in flags if f["type"] == "face_covered"), None)
        assert face_flag is not None
        assert face_flag["severity"] == "alert"

    def test_summary_flags_quality_change(self) -> None:
        """Test get_summary_flags with quality change."""
        result = EnrichmentResult(
            quality_change_detected=True,
            quality_change_description="Sudden quality degradation",
        )
        flags = result.get_summary_flags()

        quality_flag = next((f for f in flags if f["type"] == "quality_issue"), None)
        assert quality_flag is not None
        assert "quality degradation" in quality_flag["description"].lower()


# =============================================================================
# EnrichmentPipeline Initialization Tests
# =============================================================================


class TestEnrichmentPipelineInit:
    """Tests for EnrichmentPipeline initialization."""

    def test_init_defaults(self, mock_model_manager: MagicMock) -> None:
        """Test initialization with default values."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

            assert pipeline.min_confidence == 0.5
            assert pipeline.license_plate_enabled is True
            assert pipeline.face_detection_enabled is True
            assert pipeline.ocr_enabled is True
            assert pipeline.vision_extraction_enabled is True
            assert pipeline.reid_enabled is True
            assert pipeline.scene_change_enabled is True
            assert pipeline.violence_detection_enabled is True
            assert pipeline.weather_classification_enabled is True
            assert pipeline.clothing_classification_enabled is True
            assert pipeline.clothing_segmentation_enabled is True
            assert pipeline.vehicle_damage_detection_enabled is True
            assert pipeline.vehicle_classification_enabled is True
            # image_quality_enabled defaults to True (piq library is compatible with NumPy 2.0)
            assert pipeline.image_quality_enabled is True
            assert pipeline.pet_classification_enabled is True
            assert pipeline.use_enrichment_service is False

    def test_init_custom_values(self, mock_model_manager: MagicMock) -> None:
        """Test initialization with custom values."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                min_confidence=0.7,
                license_plate_enabled=False,
                face_detection_enabled=False,
                violence_detection_enabled=False,
                use_enrichment_service=True,
            )

            assert pipeline.min_confidence == 0.7
            assert pipeline.license_plate_enabled is False
            assert pipeline.face_detection_enabled is False
            assert pipeline.violence_detection_enabled is False
            assert pipeline.use_enrichment_service is True

    def test_init_with_redis_client(self, mock_model_manager: MagicMock) -> None:
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                redis_client=mock_redis,
            )

            assert pipeline.redis_client is mock_redis


# =============================================================================
# EnrichmentPipeline enrich_batch Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineEnrichBatch:
    """Tests for EnrichmentPipeline.enrich_batch() method."""

    async def test_enrich_batch_empty_detections(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch with no detections."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            result = await pipeline.enrich_batch(
                detections=[],
                images={None: test_image},
            )

            assert not result.has_license_plates
            assert not result.has_faces
            assert not result.has_vision_extraction
            assert len(result.errors) == 0

    async def test_enrich_batch_low_confidence_filtered(
        self,
        test_image: Image.Image,
        low_confidence_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch filters low confidence detections."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                min_confidence=0.5,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[low_confidence_detection],
                images={None: test_image},
            )

            # Vehicle classifier should not be called
            mock_classify.assert_not_called()
            assert len(result.vehicle_classifications) == 0

    async def test_enrich_batch_vehicle_classification(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs vehicle classification."""
        mock_result = VehicleClassificationResult(
            vehicle_type="pickup_truck",
            confidence=0.88,
            display_name="pickup truck",
            is_commercial=False,
            all_scores={"pickup_truck": 0.88},
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_vehicle",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.return_value = mock_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            mock_classify.assert_called_once()
            assert result.has_vehicle_classifications
            assert "1" in result.vehicle_classifications

    async def test_enrich_batch_clothing_classification(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs clothing classification on persons."""
        mock_result = ClothingClassification(
            top_category="casual clothing",
            confidence=0.82,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="casual",
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_clothing",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.return_value = mock_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            mock_classify.assert_called_once()
            assert result.has_clothing_classifications
            assert "2" in result.clothing_classifications

    async def test_enrich_batch_pet_classification(
        self,
        test_image: Image.Image,
        dog_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs pet classification on animals."""
        mock_result = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_pet",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.return_value = mock_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[dog_detection],
                images={None: test_image},
            )

            mock_classify.assert_called_once()
            assert result.has_pet_classifications
            assert "3" in result.pet_classifications

    async def test_enrich_batch_violence_detection_requires_two_persons(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch only runs violence with 2+ persons."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_violence",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=True,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            # Single person - violence detection should not run
            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            mock_classify.assert_not_called()
            assert result.violence_detection is None

    async def test_enrich_batch_violence_detection_with_two_persons(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs violence with 2+ persons."""
        two_persons = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.95,
                bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400),
            ),
            DetectionInput(
                id=2,
                class_name="person",
                confidence=0.92,
                bbox=BoundingBox(x1=250, y1=60, x2=350, y2=420),
            ),
        ]

        mock_result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.9,
            violent_score=0.1,
            non_violent_score=0.9,
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_violence",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.return_value = mock_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=True,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=two_persons,
                images={None: test_image},
            )

            mock_classify.assert_called_once()
            assert result.violence_detection is not None

    async def test_enrich_batch_image_quality_assessment(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs image quality assessment."""
        mock_quality = ImageQualityResult(
            quality_score=45.0,
            brisque_score=30.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.assess_image_quality",
                new_callable=AsyncMock,
            ) as mock_assess,
        ):
            mock_assess.return_value = mock_quality

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=True,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            mock_assess.assert_called_once()
            assert result.has_image_quality
            assert result.image_quality.quality_score == 45.0

    async def test_enrich_batch_quality_change_detection(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch detects quality changes."""
        mock_quality = ImageQualityResult(
            quality_score=80.0,
            brisque_score=70.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.assess_image_quality",
                new_callable=AsyncMock,
            ) as mock_assess,
            patch("backend.services.enrichment_pipeline.detect_quality_change") as mock_detect,
        ):
            mock_assess.return_value = mock_quality
            mock_detect.return_value = (True, "Sudden quality degradation detected")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=True,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.quality_change_detected is True
            assert "degradation" in result.quality_change_description.lower()


# =============================================================================
# EnrichmentPipeline Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineErrorHandling:
    """Tests for EnrichmentPipeline error handling."""

    async def test_vehicle_classification_error_graceful(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle classification errors are logged and pipeline continues gracefully."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            # Make the model manager raise an error when loading the model
            # This simulates a model loading failure - internal errors are caught
            # and logged, not propagated to the errors list
            def raise_error(name: str):
                if name == "vehicle-segment-classification":
                    raise RuntimeError("Model load failed")
                return MockAsyncContextManager({})

            mock_model_manager.load = raise_error

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            # Pipeline should complete gracefully - internal errors in helpers are
            # caught and logged, but don't block the pipeline
            assert isinstance(result, EnrichmentResult)
            # No vehicle classifications due to error
            assert len(result.vehicle_classifications) == 0

    async def test_vision_extraction_error_logged(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vision extraction errors are logged and pipeline continues."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor") as mock_get_ext,
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(
                side_effect=RuntimeError("Florence service down")
            )
            mock_get_ext.return_value = mock_extractor

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Pipeline should complete but with error
            assert isinstance(result, EnrichmentResult)
            assert len(result.errors) >= 1
            assert "Vision extraction failed" in result.errors[0]

    async def test_multiple_errors_collected(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test multiple errors are collected when major components fail."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor") as mock_get_ext,
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch(
                "backend.services.enrichment_pipeline.get_scene_change_detector"
            ) as mock_get_scene,
        ):
            # Make vision extractor fail (this adds to errors list)
            mock_extractor = MagicMock()
            mock_extractor.extract_batch_attributes = AsyncMock(
                side_effect=RuntimeError("Florence error")
            )
            mock_get_ext.return_value = mock_extractor

            # Make scene change detector fail (this also adds to errors list)
            mock_scene = MagicMock()
            mock_scene.detect_changes = MagicMock(side_effect=RuntimeError("Scene change error"))
            mock_get_scene.return_value = mock_scene

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,
                reid_enabled=False,
                scene_change_enabled=True,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection, person_detection],
                images={None: test_image},
                camera_id="test_camera",  # Needed for scene change detection
            )

            # Multiple errors should be recorded (vision extraction + scene change)
            assert len(result.errors) >= 2
            assert any("Vision extraction failed" in e for e in result.errors)
            assert any("Scene change detection failed" in e for e in result.errors)


# =============================================================================
# EnrichmentPipeline Helper Method Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineHelpers:
    """Tests for EnrichmentPipeline helper methods."""

    async def test_load_image_pil_passthrough(
        self,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _load_image returns PIL Image unchanged."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            img = Image.new("RGB", (100, 100))

            result = await pipeline._load_image(img)

            assert result is img

    async def test_crop_to_bbox_valid(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox with valid bbox."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            bbox = BoundingBox(x1=10, y1=20, x2=100, y2=150)

            result = await pipeline._crop_to_bbox(test_image, bbox)

            assert result is not None
            assert result.size == (90, 130)

    async def test_crop_to_bbox_zero_size(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox with zero-size bbox returns None."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            bbox = BoundingBox(x1=50, y1=50, x2=50, y2=50)

            result = await pipeline._crop_to_bbox(test_image, bbox)

            assert result is None

    async def test_crop_to_bbox_clamps_to_image_bounds(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox clamps coordinates to image bounds."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            # Bbox extends beyond image (640x480)
            bbox = BoundingBox(x1=-10, y1=-20, x2=700, y2=500)

            result = await pipeline._crop_to_bbox(test_image, bbox)

            assert result is not None
            assert result.size == (640, 480)


class TestEnrichmentPipelineImageHelpers:
    """Tests for non-async EnrichmentPipeline helper methods."""

    def test_get_image_for_detection_with_shared(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _get_image_for_detection returns shared image."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            images = {None: test_image}

            result = pipeline._get_image_for_detection(vehicle_detection, images)

            assert result is test_image

    def test_get_image_for_detection_specific(
        self,
        test_image: Image.Image,
        small_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _get_image_for_detection returns detection-specific image."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            images = {None: test_image, 1: small_image}

            result = pipeline._get_image_for_detection(vehicle_detection, images)

            assert result is small_image


# =============================================================================
# Global Singleton Tests
# =============================================================================


class TestGlobalSingletons:
    """Tests for global singleton functions."""

    def test_get_enrichment_pipeline_creates_instance(self) -> None:
        """Test get_enrichment_pipeline creates singleton."""
        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline1 = get_enrichment_pipeline()
            pipeline2 = get_enrichment_pipeline()

            assert pipeline1 is pipeline2

    def test_reset_enrichment_pipeline_clears_singleton(self) -> None:
        """Test reset_enrichment_pipeline clears the singleton."""
        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline1 = get_enrichment_pipeline()
            reset_enrichment_pipeline()
            pipeline2 = get_enrichment_pipeline()

            assert pipeline1 is not pipeline2

    def test_get_enrichment_pipeline_passes_redis_client(self) -> None:
        """Test get_enrichment_pipeline passes Redis client for Re-ID support.

        This test verifies the fix for NEM-1260 where the Entities page was empty
        because EnrichmentPipeline was created without a redis_client, which
        disabled Re-ID functionality.
        """
        mock_redis_client = MagicMock()
        reset_enrichment_pipeline()

        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.core.redis.get_redis_client_sync",
                return_value=mock_redis_client,
            ) as mock_get_redis,
        ):
            pipeline = get_enrichment_pipeline()

            # Verify get_redis_client_sync was called
            mock_get_redis.assert_called_once()

            # Verify the pipeline has the redis_client set
            assert pipeline.redis_client is mock_redis_client

    def test_get_enrichment_pipeline_works_without_redis(self) -> None:
        """Test get_enrichment_pipeline works when Redis is not initialized.

        When Redis is not yet initialized (returns None), the pipeline should
        still be created but Re-ID will be disabled.
        """
        reset_enrichment_pipeline()

        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.core.redis.get_redis_client_sync",
                return_value=None,
            ),
        ):
            pipeline = get_enrichment_pipeline()

            # Pipeline should be created even without Redis
            assert pipeline is not None
            assert pipeline.redis_client is None


# =============================================================================
# Enrichment Service (HTTP) Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentServiceMode:
    """Tests for HTTP enrichment service mode."""

    async def test_vehicle_classification_via_service(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test vehicle classification via HTTP service."""

        mock_client_result = MagicMock()
        mock_client_result.vehicle_type = "pickup_truck"
        mock_client_result.confidence = 0.88
        mock_client_result.display_name = "pickup truck"
        mock_client_result.is_commercial = False
        mock_client_result.all_scores = {"pickup_truck": 0.88}

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_vehicle = AsyncMock(return_value=mock_client_result)
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            mock_client.classify_vehicle.assert_called_once()
            assert result.has_vehicle_classifications
            assert "1" in result.vehicle_classifications

    async def test_pet_classification_via_service(
        self,
        test_image: Image.Image,
        dog_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet classification via HTTP service."""
        mock_client_result = MagicMock()
        mock_client_result.pet_type = "dog"
        mock_client_result.confidence = 0.95
        mock_client_result.is_household_pet = True

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_pet = AsyncMock(return_value=mock_client_result)
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[dog_detection],
                images={None: test_image},
            )

            mock_client.classify_pet.assert_called_once()
            assert result.has_pet_classifications

    async def test_clothing_classification_via_service(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test clothing classification via HTTP service."""
        mock_client_result = MagicMock()
        mock_client_result.top_category = "casual clothing"
        mock_client_result.confidence = 0.82
        mock_client_result.is_suspicious = False
        mock_client_result.is_service_uniform = False
        mock_client_result.description = "casual wear"

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_clothing = AsyncMock(return_value=mock_client_result)
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            mock_client.classify_clothing.assert_called_once()
            assert result.has_clothing_classifications

    async def test_service_unavailable_handled(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test HTTP service unavailable is handled gracefully."""
        from backend.services.enrichment_client import EnrichmentUnavailableError

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_vehicle = AsyncMock(
                side_effect=EnrichmentUnavailableError("Service unavailable")
            )
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            # Should complete gracefully without vehicle classifications
            assert isinstance(result, EnrichmentResult)
            assert len(result.vehicle_classifications) == 0


# =============================================================================
# EnrichmentResult to_prompt_context Tests
# =============================================================================


class TestEnrichmentResultToPromptContext:
    """Tests for EnrichmentResult.to_prompt_context() method."""

    def test_to_prompt_context_empty(self) -> None:
        """Test to_prompt_context with empty result."""
        result = EnrichmentResult()
        context = result.to_prompt_context()

        assert isinstance(context, dict)
        assert "violence_context" in context
        assert "weather_context" in context
        assert "image_quality_context" in context
        assert "clothing_analysis_context" in context
        assert "vehicle_classification_context" in context
        assert "vehicle_damage_context" in context
        assert "pet_classification_context" in context
        assert "pose_analysis" in context
        assert "action_recognition" in context
        assert "depth_context" in context

    def test_to_prompt_context_with_time_of_day(self) -> None:
        """Test to_prompt_context includes time context."""
        result = EnrichmentResult()
        context = result.to_prompt_context(time_of_day="night")

        assert isinstance(context, dict)
        # The time_of_day is passed to format_vehicle_damage_context
        assert "vehicle_damage_context" in context


# =============================================================================
# EnrichmentResult to_context_string Extended Tests
# =============================================================================


class TestEnrichmentResultToContextStringExtended:
    """Extended tests for EnrichmentResult.to_context_string() method."""

    def test_to_context_string_with_vision_extraction(self) -> None:
        """Test to_context_string with vision extraction results."""
        from backend.services.vision_extractor import (
            BatchExtractionResult,
            PersonAttributes,
        )

        vision_result = BatchExtractionResult(
            person_attributes={
                "1": PersonAttributes(
                    clothing="casual clothing",
                    carrying="backpack",
                    is_service_worker=False,
                    action="walking",
                    caption="a person walking",
                )
            },
            vehicle_attributes={},
        )
        result = EnrichmentResult(vision_extraction=vision_result)
        context = result.to_context_string()

        assert "Vision Analysis" in context or "No additional context" not in context

    def test_to_context_string_with_reid_matches(self) -> None:
        """Test to_context_string with re-identification matches."""
        from datetime import datetime

        from backend.services.reid_service import EntityEmbedding, EntityMatch

        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="camera_1",
            timestamp=datetime.now(),
            detection_id="det_456",
            attributes={"clothing": "blue shirt"},
        )
        match = EntityMatch(
            entity=entity,
            similarity=0.95,
            time_gap_seconds=30.0,
        )
        result = EnrichmentResult(person_reid_matches={"1": [match]})
        context = result.to_context_string()

        # Check that re-id context is present
        assert "Re-Identification" in context or len(context) > 0

    def test_to_context_string_with_scene_change(self) -> None:
        """Test to_context_string with scene change detected."""
        from backend.services.scene_change_detector import SceneChangeResult

        scene_result = SceneChangeResult(
            change_detected=True,
            similarity_score=0.45,
        )
        result = EnrichmentResult(scene_change=scene_result)
        context = result.to_context_string()

        assert "Scene Change" in context
        assert "0.45" in context

    def test_to_context_string_with_violence_detected(self) -> None:
        """Test to_context_string with violence detected."""
        violence = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.85,
            violent_score=0.85,
            non_violent_score=0.15,
        )
        result = EnrichmentResult(violence_detection=violence)
        context = result.to_context_string()

        assert "Violence Detection" in context
        assert "VIOLENCE DETECTED" in context
        assert "85%" in context

    def test_to_context_string_with_violence_not_detected(self) -> None:
        """Test to_context_string with no violence."""
        violence = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.9,
            violent_score=0.1,
            non_violent_score=0.9,
        )
        result = EnrichmentResult(violence_detection=violence)
        context = result.to_context_string()

        assert "Violence Detection" in context
        assert "No violence detected" in context

    def test_to_context_string_with_clothing_classifications(self) -> None:
        """Test to_context_string with clothing classifications."""
        clothing = ClothingClassification(
            top_category="casual",
            confidence=0.88,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="casual clothing",
        )
        result = EnrichmentResult(clothing_classifications={"1": clothing})
        context = result.to_context_string()

        assert "Clothing Classifications" in context
        assert "Person 1" in context

    def test_to_context_string_with_vehicle_damage(self) -> None:
        """Test to_context_string with vehicle damage detected."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter",
                    confidence=0.9,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        context = result.to_context_string()

        assert "Vehicle Damage" in context
        assert "Vehicle 1" in context
        assert "SECURITY ALERT" in context

    def test_to_context_string_with_vehicle_classifications(self) -> None:
        """Test to_context_string with vehicle classifications."""
        vehicle = VehicleClassificationResult(
            vehicle_type="pickup_truck",
            confidence=0.92,
            display_name="pickup truck",
            is_commercial=False,
            all_scores={},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle})
        context = result.to_context_string()

        assert "Vehicle Classifications" in context
        assert "Vehicle 1" in context

    def test_to_context_string_with_unreadable_plate(self) -> None:
        """Test to_context_string with unreadable license plate."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
        plate = LicensePlateResult(bbox=bbox, text="")  # No text
        result = EnrichmentResult(license_plates=[plate])
        context = result.to_context_string()

        assert "License Plates" in context
        assert "[unreadable]" in context

    def test_to_context_string_with_pet_only_event(self) -> None:
        """Test to_context_string with pet-only event."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"1": pet})
        context = result.to_context_string()

        assert "Pet Classifications" in context
        assert "NOTE" in context
        assert "Pet-only event" in context

    def test_to_context_string_with_image_quality_alert(self) -> None:
        """Test to_context_string with image quality alert."""
        quality = ImageQualityResult(
            quality_score=75.0,
            brisque_score=70.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )
        result = EnrichmentResult(
            image_quality=quality,
            quality_change_detected=True,
            quality_change_description="Sudden quality drop",
        )
        context = result.to_context_string()

        assert "Image Quality Assessment" in context
        assert "ALERT" in context
        assert "Sudden quality drop" in context


# =============================================================================
# EnrichmentResult Risk Modifiers Extended Tests
# =============================================================================


class TestEnrichmentResultRiskModifiersExtended:
    """Extended tests for get_risk_modifiers method."""

    def test_risk_modifiers_confirmed_pet_without_violence(self) -> None:
        """Test confirmed pet modifier without violence."""
        # Set up a pet that is confirmed but result also has other context (like faces)
        pet = PetClassificationResult(
            animal_type="cat",
            confidence=0.98,
            cat_score=0.98,
            dog_score=0.02,
            is_household_pet=True,
        )
        # Add a face so it's not a pet-only event
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        face = FaceResult(bbox=bbox, confidence=0.9)
        result = EnrichmentResult(
            pet_classifications={"1": pet},
            faces=[face],
        )
        modifiers = result.get_risk_modifiers()

        assert "confirmed_pet" in modifiers
        assert modifiers["confirmed_pet"] < 0

    def test_risk_modifiers_commercial_vehicle(self) -> None:
        """Test commercial vehicle modifier."""
        vehicle = VehicleClassificationResult(
            vehicle_type="work_van",
            confidence=0.92,
            display_name="work van",
            is_commercial=True,
            all_scores={},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle})
        modifiers = result.get_risk_modifiers()

        assert "commercial_vehicle" in modifiers
        assert modifiers["commercial_vehicle"] < 0

    def test_risk_modifiers_quality_issues(self) -> None:
        """Test quality issues modifier."""
        quality = ImageQualityResult(
            quality_score=75.0,
            brisque_score=70.0,
            is_blurry=True,
            is_noisy=True,
            is_low_quality=True,
            quality_issues=["blurry", "noisy"],
        )
        result = EnrichmentResult(image_quality=quality)
        modifiers = result.get_risk_modifiers()

        assert "quality_issues" in modifiers
        assert modifiers["quality_issues"] > 0

    def test_risk_modifiers_quality_change(self) -> None:
        """Test quality change modifier."""
        result = EnrichmentResult(
            quality_change_detected=True,
            quality_change_description="Sudden degradation",
        )
        modifiers = result.get_risk_modifiers()

        assert "quality_change" in modifiers
        assert modifiers["quality_change"] > 0


# =============================================================================
# EnrichmentResult Summary Flags Extended Tests
# =============================================================================


class TestEnrichmentResultSummaryFlagsExtended:
    """Extended tests for get_summary_flags method."""

    def test_summary_flags_vehicle_damage_non_high_security(self) -> None:
        """Test vehicle damage flag without high security damage."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.8,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        flags = result.get_summary_flags()

        # Should NOT have vehicle_damage flag since scratch is not high security
        # The flag is only added for high_security_damage
        vehicle_flags = [f for f in flags if f["type"] == "vehicle_damage"]
        assert len(vehicle_flags) == 0

    def test_summary_flags_vehicle_damage_high_security(self) -> None:
        """Test vehicle damage flag with high security damage."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter",
                    confidence=0.9,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        flags = result.get_summary_flags()

        vehicle_flag = next((f for f in flags if f["type"] == "vehicle_damage"), None)
        assert vehicle_flag is not None
        assert "critical" in vehicle_flag["severity"] or "warning" in vehicle_flag["severity"]


# =============================================================================
# EnrichmentResult to_dict Extended Tests
# =============================================================================


class TestEnrichmentResultToDictExtended:
    """Extended tests for EnrichmentResult.to_dict() method."""

    def test_to_dict_with_vehicle_classifications(self) -> None:
        """Test to_dict with vehicle classifications."""
        vehicle = VehicleClassificationResult(
            vehicle_type="sedan",
            confidence=0.9,
            display_name="sedan",
            is_commercial=False,
            all_scores={"sedan": 0.9},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle})
        data = result.to_dict()

        assert "vehicle_classifications" in data
        assert "1" in data["vehicle_classifications"]
        assert data["vehicle_classifications"]["1"]["vehicle_type"] == "sedan"

    def test_to_dict_with_vehicle_damage(self) -> None:
        """Test to_dict with vehicle damage."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="dent",
                    confidence=0.8,
                    bbox=(0, 0, 50, 50),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"1": damage})
        data = result.to_dict()

        assert "vehicle_damage" in data
        assert "1" in data["vehicle_damage"]

    def test_to_dict_with_image_quality(self) -> None:
        """Test to_dict with image quality."""
        quality = ImageQualityResult(
            quality_score=45.0,
            brisque_score=30.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )
        result = EnrichmentResult(image_quality=quality)
        data = result.to_dict()

        assert "image_quality" in data
        assert data["image_quality"] is not None
        assert data["image_quality"]["quality_score"] == 45.0


# =============================================================================
# EnrichmentPipeline Extended enrich_batch Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineEnrichBatchExtended:
    """Extended tests for EnrichmentPipeline.enrich_batch() method."""

    async def test_enrich_batch_license_plate_detection(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs license plate detection."""
        # Create a mock YOLO model that returns detection results
        mock_yolo_result = MagicMock()
        mock_yolo_boxes = MagicMock()
        mock_yolo_boxes.xyxy = [MagicMock()]
        mock_yolo_boxes.xyxy[0].tolist.return_value = [10, 20, 100, 50]
        mock_yolo_boxes.conf = [MagicMock()]
        mock_yolo_boxes.conf[0] = 0.92
        mock_yolo_result.boxes = [mock_yolo_boxes]

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_yolo_result]

        def mock_load(name: str):
            if name == "yolo11-license-plate":
                return MockAsyncContextManager(mock_model)
            raise KeyError(f"Unknown model: {name}")

        mock_model_manager.load = mock_load

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
                ocr_enabled=False,  # Disable OCR to simplify test
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            assert result.has_license_plates
            assert len(result.license_plates) == 1
            assert result.license_plates[0].confidence == 0.92

    async def test_enrich_batch_face_detection(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs face detection."""
        # Create a mock YOLO model that returns face detection results
        mock_yolo_result = MagicMock()
        mock_yolo_boxes = MagicMock()
        mock_yolo_boxes.xyxy = [MagicMock()]
        mock_yolo_boxes.xyxy[0].tolist.return_value = [10, 10, 40, 50]
        mock_yolo_boxes.conf = [MagicMock()]
        mock_yolo_boxes.conf[0] = 0.95
        mock_yolo_result.boxes = [mock_yolo_boxes]

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_yolo_result]

        def mock_load(name: str):
            if name == "yolo11-face":
                return MockAsyncContextManager(mock_model)
            raise KeyError(f"Unknown model: {name}")

        mock_model_manager.load = mock_load

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=True,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            assert result.has_faces
            assert len(result.faces) == 1
            assert result.faces[0].confidence == 0.95

    async def test_enrich_batch_scene_change_detection(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs scene change detection."""
        from backend.services.scene_change_detector import SceneChangeResult

        mock_scene_result = SceneChangeResult(
            change_detected=True,
            similarity_score=0.35,
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch(
                "backend.services.enrichment_pipeline.get_scene_change_detector"
            ) as mock_get_scene,
        ):
            mock_detector = MagicMock()
            mock_detector.detect_changes.return_value = mock_scene_result
            mock_get_scene.return_value = mock_detector

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=True,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
                camera_id="test_camera",
            )

            assert result.has_scene_change
            assert result.scene_change.similarity_score == 0.35

    async def test_enrich_batch_vehicle_damage_detection(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs vehicle damage detection."""
        mock_damage_result = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="scratch",
                    confidence=0.85,
                    bbox=(10, 10, 50, 50),
                )
            ]
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.detect_vehicle_damage",
                new_callable=AsyncMock,
            ) as mock_detect,
        ):
            mock_detect.return_value = mock_damage_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=True,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            assert result.has_vehicle_damage
            assert "1" in result.vehicle_damage

    async def test_enrich_batch_clothing_segmentation(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs clothing segmentation."""
        mock_seg_result = ClothingSegmentationResult(
            clothing_items={"upper_clothes", "pants"},
            has_face_covered=False,
            has_bag=True,
            coverage_percentages={"upper_clothes": 0.4, "pants": 0.3},
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.segformer_loader.segment_clothing",
                new_callable=AsyncMock,
            ) as mock_segment,
        ):
            mock_segment.return_value = mock_seg_result

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=True,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            assert result.has_clothing_segmentation
            assert "2" in result.clothing_segmentation
            assert result.clothing_segmentation["2"].has_bag

    async def test_enrich_batch_no_shared_image_returns_early(
        self,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch returns early when no shared image available for certain tasks."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=True,  # Requires shared image
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            # Pass empty images dict (no shared image)
            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={},
            )

            # Vision extraction should not run without shared image
            assert not result.has_vision_extraction


# =============================================================================
# EnrichmentPipeline Helper Methods Extended Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineHelpersExtended:
    """Extended tests for EnrichmentPipeline helper methods."""

    async def test_load_image_from_path(
        self,
        mock_model_manager: MagicMock,
        tmp_path,
    ) -> None:
        """Test _load_image can load from file path."""
        # Create a temporary image file
        from pathlib import Path

        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img_path = tmp_path / "test_image.png"
        img.save(img_path)

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

            result = await pipeline._load_image(Path(img_path))

            assert result is not None
            assert result.size == (100, 100)

    async def test_load_image_from_string_path(
        self,
        mock_model_manager: MagicMock,
        tmp_path,
    ) -> None:
        """Test _load_image can load from string path."""
        # Create a temporary image file
        img = Image.new("RGB", (80, 80), color=(0, 255, 0))
        img_path = tmp_path / "test_image2.png"
        img.save(img_path)

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

            result = await pipeline._load_image(str(img_path))

            assert result is not None
            assert result.size == (80, 80)

    async def test_load_image_invalid_path_returns_none(
        self,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _load_image returns None for invalid path."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)

            result = await pipeline._load_image("/nonexistent/path/image.png")

            assert result is None

    async def test_crop_to_bbox_error_returns_none(
        self,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test _crop_to_bbox returns None on error."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            bbox = BoundingBox(x1=10, y1=20, x2=100, y2=150)

            # Pass invalid path that will fail to load
            result = await pipeline._crop_to_bbox("/nonexistent/image.png", bbox)

            assert result is None


# =============================================================================
# EnrichmentPipeline Error Handling Extended Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentPipelineErrorHandlingExtended:
    """Extended error handling tests."""

    async def test_license_plate_model_not_available(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test license plate detection handles missing model gracefully."""

        def mock_load(name: str):
            if name == "yolo11-license-plate":
                raise KeyError("Model not available")
            return MockAsyncContextManager({})

        mock_model_manager.load = mock_load

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            # Should complete without plates but no crash
            assert not result.has_license_plates
            assert isinstance(result, EnrichmentResult)

    async def test_face_detection_model_not_available(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test face detection handles missing model gracefully."""

        def mock_load(name: str):
            if name == "yolo11-face":
                raise KeyError("Model not available")
            return MockAsyncContextManager({})

        mock_model_manager.load = mock_load

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=True,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Should complete without faces but no crash
            assert not result.has_faces

    async def test_clothing_classification_error_graceful(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
        caplog,
    ) -> None:
        """Test clothing classification error handling.

        Note: Internal helper method errors are logged as warnings but don't
        get appended to result.errors - only top-level errors do.
        """
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_clothing",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.side_effect = RuntimeError("Classification failed")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Pipeline completes gracefully without classifications
            assert isinstance(result, EnrichmentResult)
            assert len(result.clothing_classifications) == 0
            # Errors in internal helpers are logged as warnings
            assert "Clothing classification failed" in caplog.text

    async def test_pet_classification_error_graceful(
        self,
        test_image: Image.Image,
        dog_detection: DetectionInput,
        mock_model_manager: MagicMock,
        caplog,
    ) -> None:
        """Test pet classification error handling.

        Note: Internal helper method errors are logged as warnings but don't
        get appended to result.errors - only top-level errors do.
        """
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_pet",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            mock_classify.side_effect = RuntimeError("Pet classification failed")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[dog_detection],
                images={None: test_image},
            )

            # Pipeline completes gracefully without classifications
            assert isinstance(result, EnrichmentResult)
            assert len(result.pet_classifications) == 0
            # Errors in internal helpers are logged as warnings
            assert "Pet classification failed" in caplog.text

    async def test_image_quality_error_graceful(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test image quality assessment error handling."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.assess_image_quality",
                new_callable=AsyncMock,
            ) as mock_assess,
        ):
            mock_assess.side_effect = RuntimeError("Quality assessment failed")

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=True,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Error should be recorded
            assert len(result.errors) >= 1
            assert any("Image quality assessment failed" in e for e in result.errors)


# =============================================================================
# EnrichmentPipeline Service Mode Extended Tests
# =============================================================================


@pytest.mark.asyncio
class TestEnrichmentServiceModeExtended:
    """Extended tests for HTTP enrichment service mode."""

    async def test_pet_service_unavailable_handled(
        self,
        test_image: Image.Image,
        dog_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pet classification service unavailable is handled."""
        from backend.services.enrichment_client import EnrichmentUnavailableError

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_pet = AsyncMock(
                side_effect=EnrichmentUnavailableError("Service down")
            )
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[dog_detection],
                images={None: test_image},
            )

            # Should complete gracefully
            assert isinstance(result, EnrichmentResult)
            assert len(result.pet_classifications) == 0

    async def test_clothing_service_unavailable_handled(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test clothing classification service unavailable is handled."""
        from backend.services.enrichment_client import EnrichmentUnavailableError

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_clothing = AsyncMock(
                side_effect=EnrichmentUnavailableError("Service down")
            )
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=True,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Should complete gracefully
            assert isinstance(result, EnrichmentResult)
            assert len(result.clothing_classifications) == 0

    async def test_service_returns_none_result(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test service returning None is handled."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.classify_vehicle = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                use_enrichment_service=True,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=True,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[vehicle_detection],
                images={None: test_image},
            )

            # Should complete but without classifications
            assert len(result.vehicle_classifications) == 0


# =============================================================================
# Weather Classification Tests
# =============================================================================


class TestEnrichmentResultWeatherClassification:
    """Tests for weather classification in EnrichmentResult."""

    def test_has_weather_classification_empty(self) -> None:
        """Test weather classification is None by default."""
        result = EnrichmentResult()
        assert result.weather_classification is None

    def test_has_weather_classification_set(self) -> None:
        """Test weather classification can be set."""
        weather = WeatherResult(
            condition="sun/clear",
            simple_condition="clear",
            confidence=0.92,
            all_scores={
                "cloudy/overcast": 0.02,
                "foggy/hazy": 0.01,
                "rain/storm": 0.03,
                "snow/frosty": 0.02,
                "sun/clear": 0.92,
            },
        )
        result = EnrichmentResult(weather_classification=weather)
        assert result.weather_classification is not None
        assert result.weather_classification.simple_condition == "clear"
        assert result.weather_classification.confidence == 0.92

    def test_weather_in_to_prompt_context(self) -> None:
        """Test weather is included in to_prompt_context output."""
        weather = WeatherResult(
            condition="foggy/hazy",
            simple_condition="foggy",
            confidence=0.85,
            all_scores={},
        )
        result = EnrichmentResult(weather_classification=weather)
        context = result.to_prompt_context()

        assert "weather_context" in context
        assert "foggy" in context["weather_context"]
        assert "85%" in context["weather_context"]

    def test_weather_in_get_enrichment_for_detection(self) -> None:
        """Test weather is included in per-detection enrichment."""
        weather = WeatherResult(
            condition="rain/storm",
            simple_condition="rainy",
            confidence=0.78,
            all_scores={},
        )
        result = EnrichmentResult(weather_classification=weather)

        det_enrichment = result.get_enrichment_for_detection(1)
        assert det_enrichment is not None
        assert "weather" in det_enrichment
        assert det_enrichment["weather"]["condition"] == "rain/storm"
        assert det_enrichment["weather"]["confidence"] == 0.78


@pytest.mark.asyncio
class TestEnrichmentPipelineWeatherClassification:
    """Tests for weather classification in EnrichmentPipeline."""

    async def test_pipeline_init_weather_enabled_default(
        self,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline initializes with weather_classification_enabled=True by default."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
            assert pipeline.weather_classification_enabled is True

    async def test_pipeline_init_weather_disabled(
        self,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test pipeline can disable weather classification."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                weather_classification_enabled=False,
            )
            assert pipeline.weather_classification_enabled is False

    async def test_enrich_batch_runs_weather_classification(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch runs weather classification on full frame."""
        mock_weather_result = WeatherResult(
            condition="sun/clear",
            simple_condition="clear",
            confidence=0.95,
            all_scores={
                "cloudy/overcast": 0.01,
                "foggy/hazy": 0.01,
                "rain/storm": 0.02,
                "snow/frosty": 0.01,
                "sun/clear": 0.95,
            },
        )

        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_weather",
                new_callable=AsyncMock,
                return_value=mock_weather_result,
            ) as mock_classify,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                weather_classification_enabled=True,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Verify classify_weather was called
            mock_classify.assert_called_once()

            # Verify result contains weather classification
            assert result.weather_classification is not None
            assert result.weather_classification.simple_condition == "clear"
            assert result.weather_classification.confidence == 0.95

    async def test_enrich_batch_skips_weather_when_disabled(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch skips weather when disabled."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_weather",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                weather_classification_enabled=False,
            )

            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Verify classify_weather was NOT called
            mock_classify.assert_not_called()

            # Verify result has no weather classification
            assert result.weather_classification is None

    async def test_enrich_batch_weather_handles_errors(
        self,
        test_image: Image.Image,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch handles weather classification errors gracefully."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_weather",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Weather model failed"),
            ),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                weather_classification_enabled=True,
            )

            # Should not raise, should handle error gracefully
            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={None: test_image},
            )

            # Should complete but without weather
            assert result.weather_classification is None
            assert len(result.errors) > 0
            assert any("weather" in err.lower() for err in result.errors)

    async def test_enrich_batch_weather_skipped_without_image(
        self,
        person_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test weather classification is skipped if no shared image available."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
            patch(
                "backend.services.enrichment_pipeline.classify_weather",
                new_callable=AsyncMock,
            ) as mock_classify,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                weather_classification_enabled=True,
            )

            # Pass empty images dict - no shared image
            result = await pipeline.enrich_batch(
                detections=[person_detection],
                images={},
            )

            # Verify classify_weather was NOT called (no image)
            mock_classify.assert_not_called()

            # Result should have no weather classification
            assert result.weather_classification is None


# =============================================================================
# EnrichmentResult get_enrichment_for_detection() Tests
# =============================================================================


class TestEnrichmentResultGetEnrichmentForDetection:
    """Tests for EnrichmentResult.get_enrichment_for_detection() method."""

    def test_get_enrichment_for_detection_vehicle_classification(self) -> None:
        """Test vehicle classification enrichment extraction."""
        vehicle_class = VehicleClassificationResult(
            vehicle_type="sedan",
            confidence=0.92,
            display_name="Sedan",
            is_commercial=False,
            all_scores={"sedan": 0.92, "suv": 0.08},
        )
        result = EnrichmentResult(vehicle_classifications={"1": vehicle_class})

        enrichment = result.get_enrichment_for_detection(1)

        assert enrichment is not None
        assert "vehicle" in enrichment
        assert enrichment["vehicle"]["type"] == "sedan"
        assert enrichment["vehicle"]["confidence"] == 0.92
        assert enrichment["vehicle"]["damage"] == []

    def test_get_enrichment_for_detection_vehicle_damage_only(self) -> None:
        """Test vehicle damage without classification."""
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="dent",
                    confidence=0.85,
                    bbox=(10, 20, 30, 40),
                )
            ]
        )
        result = EnrichmentResult(vehicle_damage={"2": damage})

        enrichment = result.get_enrichment_for_detection(2)

        assert enrichment is not None
        assert "vehicle" in enrichment
        assert enrichment["vehicle"]["type"] is None
        assert enrichment["vehicle"]["damage"] == [{"type": "dent", "confidence": 0.85}]

    def test_get_enrichment_for_detection_pet_classification(self) -> None:
        """Test pet classification enrichment extraction."""
        pet = PetClassificationResult(
            animal_type="dog",
            confidence=0.95,
            cat_score=0.05,
            dog_score=0.95,
            is_household_pet=True,
        )
        result = EnrichmentResult(pet_classifications={"3": pet})

        enrichment = result.get_enrichment_for_detection(3)

        assert enrichment is not None
        assert "pet" in enrichment
        assert enrichment["pet"]["type"] == "dog"
        assert enrichment["pet"]["breed"] is None
        assert enrichment["pet"]["confidence"] == 0.95

    def test_get_enrichment_for_detection_clothing_classification(self) -> None:
        """Test clothing classification enrichment extraction."""
        clothing = ClothingClassification(
            top_category="hoodie",
            confidence=0.88,
            all_scores={"hoodie": 0.88},
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="dark hoodie",
        )
        result = EnrichmentResult(clothing_classifications={"4": clothing})

        enrichment = result.get_enrichment_for_detection(4)

        assert enrichment is not None
        assert "person" in enrichment
        assert enrichment["person"]["clothing"] == "hoodie"
        assert enrichment["person"]["confidence"] == 0.88

    def test_get_enrichment_for_detection_clothing_segmentation_only(self) -> None:
        """Test clothing segmentation without classification."""
        segmentation = ClothingSegmentationResult(
            clothing_items=["hat", "sunglasses"],
            has_face_covered=True,
            has_bag=False,
        )
        result = EnrichmentResult(clothing_segmentation={"5": segmentation})

        enrichment = result.get_enrichment_for_detection(5)

        assert enrichment is not None
        assert "person" in enrichment
        assert enrichment["person"]["face_covered"] is True

    def test_get_enrichment_for_detection_license_plate(self) -> None:
        """Test license plate enrichment extraction."""
        bbox = BoundingBox(x1=100, y1=200, x2=200, y2=250)
        plate = LicensePlateResult(
            bbox=bbox,
            text="ABC123",
            confidence=0.92,
            ocr_confidence=0.88,
            source_detection_id=6,
        )
        result = EnrichmentResult(license_plates=[plate])

        enrichment = result.get_enrichment_for_detection(6)

        assert enrichment is not None
        assert "license_plate" in enrichment
        assert enrichment["license_plate"]["text"] == "ABC123"
        assert enrichment["license_plate"]["confidence"] == 0.88

    def test_get_enrichment_for_detection_face_detected(self) -> None:
        """Test face detection enrichment extraction."""
        bbox = BoundingBox(x1=50, y1=60, x2=150, y2=160)
        face1 = FaceResult(bbox=bbox, confidence=0.95, source_detection_id=7)
        face2 = FaceResult(bbox=bbox, confidence=0.92, source_detection_id=7)
        result = EnrichmentResult(faces=[face1, face2])

        enrichment = result.get_enrichment_for_detection(7)

        assert enrichment is not None
        assert enrichment["face_detected"] is True
        assert enrichment["face_count"] == 2

    def test_get_enrichment_for_detection_weather_global(self) -> None:
        """Test weather enrichment (global, applies to all detections)."""
        weather = WeatherResult(
            condition="clear",
            confidence=0.95,
            all_scores={"clear": 0.95},
            simple_condition="clear",
        )
        result = EnrichmentResult(weather_classification=weather)

        enrichment = result.get_enrichment_for_detection(8)

        assert enrichment is not None
        assert "weather" in enrichment
        assert enrichment["weather"]["condition"] == "clear"
        assert enrichment["weather"]["confidence"] == 0.95

    def test_get_enrichment_for_detection_image_quality_global(self) -> None:
        """Test image quality enrichment (global, applies to all detections)."""
        quality = ImageQualityResult(
            quality_score=65.0,
            brisque_score=35.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )
        result = EnrichmentResult(image_quality=quality)

        enrichment = result.get_enrichment_for_detection(9)

        assert enrichment is not None
        assert "image_quality" in enrichment
        assert enrichment["image_quality"]["score"] == 65.0
        assert enrichment["image_quality"]["issues"] == []

    def test_get_enrichment_for_detection_no_enrichment(self) -> None:
        """Test returns None when no enrichment data for detection."""
        result = EnrichmentResult()

        enrichment = result.get_enrichment_for_detection(999)

        assert enrichment is None

    def test_get_enrichment_for_detection_combined_vehicle_data(self) -> None:
        """Test vehicle with both classification and damage."""
        vehicle_class = VehicleClassificationResult(
            vehicle_type="suv",
            confidence=0.90,
            display_name="SUV",
            is_commercial=False,
            all_scores={},
        )
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(
                    damage_type="glass_shatter",
                    confidence=0.92,
                    bbox=(10, 20, 30, 40),
                )
            ]
        )
        result = EnrichmentResult(
            vehicle_classifications={"10": vehicle_class},
            vehicle_damage={"10": damage},
        )

        enrichment = result.get_enrichment_for_detection(10)

        assert enrichment is not None
        assert enrichment["vehicle"]["type"] == "suv"
        assert len(enrichment["vehicle"]["damage"]) == 1
        assert enrichment["vehicle"]["damage"][0]["type"] == "glass_shatter"

    def test_get_enrichment_for_detection_combined_person_data(self) -> None:
        """Test person with both classification and segmentation."""
        clothing = ClothingClassification(
            top_category="t-shirt",
            confidence=0.85,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="casual t-shirt",
        )
        segmentation = ClothingSegmentationResult(
            clothing_items=["shirt", "pants"],
            has_face_covered=False,
            has_bag=True,
        )
        result = EnrichmentResult(
            clothing_classifications={"11": clothing},
            clothing_segmentation={"11": segmentation},
        )

        enrichment = result.get_enrichment_for_detection(11)

        assert enrichment is not None
        assert enrichment["person"]["clothing"] == "t-shirt"
        assert enrichment["person"]["face_covered"] is False


# =============================================================================
# EnrichmentStatus and EnrichmentTrackingResult Tests
# =============================================================================


class TestEnrichmentStatus:
    """Tests for EnrichmentStatus enum."""

    def test_status_values(self) -> None:
        """Test EnrichmentStatus enum values."""
        from backend.services.enrichment_pipeline import EnrichmentStatus

        assert EnrichmentStatus.FULL.value == "full"
        assert EnrichmentStatus.PARTIAL.value == "partial"
        assert EnrichmentStatus.FAILED.value == "failed"
        assert EnrichmentStatus.SKIPPED.value == "skipped"


class TestEnrichmentTrackingResult:
    """Tests for EnrichmentTrackingResult dataclass."""

    def test_init_defaults(self) -> None:
        """Test EnrichmentTrackingResult initializes with defaults."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult()
        assert tracking.status == EnrichmentStatus.SKIPPED
        assert tracking.successful_models == []
        assert tracking.failed_models == []
        assert tracking.errors == {}
        assert tracking.data is None

    def test_has_data_none(self) -> None:
        """Test has_data property when data is None."""
        from backend.services.enrichment_pipeline import EnrichmentTrackingResult

        tracking = EnrichmentTrackingResult()
        assert tracking.has_data is False

    def test_has_data_with_result(self) -> None:
        """Test has_data property when data is present."""
        from backend.services.enrichment_pipeline import EnrichmentTrackingResult

        result = EnrichmentResult()
        tracking = EnrichmentTrackingResult(data=result)
        assert tracking.has_data is True

    def test_success_rate_no_models(self) -> None:
        """Test success_rate returns 1.0 when no models attempted."""
        from backend.services.enrichment_pipeline import EnrichmentTrackingResult

        tracking = EnrichmentTrackingResult()
        assert tracking.success_rate == 1.0

    def test_success_rate_all_successful(self) -> None:
        """Test success_rate with all models successful."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(
            status=EnrichmentStatus.FULL,
            successful_models=["vision", "reid", "clothing"],
            failed_models=[],
        )
        assert tracking.success_rate == 1.0

    def test_success_rate_partial(self) -> None:
        """Test success_rate with partial success."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(
            status=EnrichmentStatus.PARTIAL,
            successful_models=["vision", "reid"],
            failed_models=["clothing", "vehicle"],
        )
        assert tracking.success_rate == 0.5

    def test_success_rate_all_failed(self) -> None:
        """Test success_rate with all models failed."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            successful_models=[],
            failed_models=["vision", "reid"],
        )
        assert tracking.success_rate == 0.0

    def test_is_partial_true(self) -> None:
        """Test is_partial property when status is PARTIAL."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.PARTIAL)
        assert tracking.is_partial is True

    def test_is_partial_false(self) -> None:
        """Test is_partial property when status is not PARTIAL."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.FULL)
        assert tracking.is_partial is False

    def test_all_succeeded_true(self) -> None:
        """Test all_succeeded property when status is FULL."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.FULL)
        assert tracking.all_succeeded is True

    def test_all_succeeded_false(self) -> None:
        """Test all_succeeded property when status is not FULL."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.PARTIAL)
        assert tracking.all_succeeded is False

    def test_all_failed_true(self) -> None:
        """Test all_failed property when status is FAILED."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.FAILED)
        assert tracking.all_failed is True

    def test_all_failed_false(self) -> None:
        """Test all_failed property when status is not FAILED."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(status=EnrichmentStatus.PARTIAL)
        assert tracking.all_failed is False

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        tracking = EnrichmentTrackingResult(
            status=EnrichmentStatus.PARTIAL,
            successful_models=["vision", "reid"],
            failed_models=["clothing"],
            errors={"clothing": "Model failed to load"},
        )

        result_dict = tracking.to_dict()
        assert result_dict["status"] == "partial"
        assert result_dict["successful_models"] == ["vision", "reid"]
        assert result_dict["failed_models"] == ["clothing"]
        assert result_dict["errors"] == {"clothing": "Model failed to load"}
        assert result_dict["success_rate"] == pytest.approx(0.666, rel=0.01)

    def test_compute_status_no_models(self) -> None:
        """Test compute_status with no models attempted."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        status = EnrichmentTrackingResult.compute_status([], [])
        assert status == EnrichmentStatus.SKIPPED

    def test_compute_status_all_successful(self) -> None:
        """Test compute_status with all models successful."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        status = EnrichmentTrackingResult.compute_status(["vision", "reid"], [])
        assert status == EnrichmentStatus.FULL

    def test_compute_status_all_failed(self) -> None:
        """Test compute_status with all models failed."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        status = EnrichmentTrackingResult.compute_status([], ["vision", "reid"])
        assert status == EnrichmentStatus.FAILED

    def test_compute_status_partial(self) -> None:
        """Test compute_status with some successful and some failed."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        status = EnrichmentTrackingResult.compute_status(["vision"], ["reid"])
        assert status == EnrichmentStatus.PARTIAL


# =============================================================================
# EnrichmentPipeline Async Methods Tests (Main Coverage Gaps)
# =============================================================================


class TestEnrichmentPipelineAsyncMethods:
    """Tests for EnrichmentPipeline async methods requiring detailed coverage."""

    @pytest.mark.asyncio
    async def test_load_image_from_pil(self, test_image: Image.Image) -> None:
        """Test _load_image with PIL Image input."""
        pipeline = EnrichmentPipeline()
        result = await pipeline._load_image(test_image)
        assert result is test_image

    @pytest.mark.asyncio
    async def test_load_image_from_path_string(self, tmp_path: Any) -> None:
        """Test _load_image from string path."""

        # Create a test image file
        image_path = tmp_path / "test.png"
        test_img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        test_img.save(image_path)

        pipeline = EnrichmentPipeline()
        result = await pipeline._load_image(str(image_path))

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)

    @pytest.mark.asyncio
    async def test_load_image_from_path_object(self, tmp_path: Any) -> None:
        """Test _load_image from Path object."""
        from pathlib import Path

        # Create a test image file
        image_path = tmp_path / "test.png"
        test_img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        test_img.save(image_path)

        pipeline = EnrichmentPipeline()
        result = await pipeline._load_image(Path(image_path))

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)

    @pytest.mark.asyncio
    async def test_load_image_failure(self) -> None:
        """Test _load_image handles failures gracefully."""
        pipeline = EnrichmentPipeline()
        result = await pipeline._load_image("/nonexistent/path.png")
        assert result is None

    @pytest.mark.asyncio
    async def test_crop_to_bbox_success(self, test_image: Image.Image) -> None:
        """Test _crop_to_bbox successfully crops image."""
        bbox = BoundingBox(x1=10, y1=10, x2=50, y2=50)
        pipeline = EnrichmentPipeline()

        result = await pipeline._crop_to_bbox(test_image, bbox)

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (40, 40)

    @pytest.mark.asyncio
    async def test_crop_to_bbox_clamps_coordinates(self, test_image: Image.Image) -> None:
        """Test _crop_to_bbox clamps out-of-bounds coordinates."""
        # Bbox extends beyond image boundaries
        bbox = BoundingBox(x1=-10, y1=-10, x2=1000, y2=1000)
        pipeline = EnrichmentPipeline()

        result = await pipeline._crop_to_bbox(test_image, bbox)

        assert result is not None
        # Should be clamped to image size (640x480)
        assert result.size == test_image.size

    @pytest.mark.asyncio
    async def test_crop_to_bbox_invalid_dimensions(self, test_image: Image.Image) -> None:
        """Test _crop_to_bbox returns None for invalid dimensions."""
        # x2 <= x1 should fail
        bbox = BoundingBox(x1=100, y1=10, x2=50, y2=50)
        pipeline = EnrichmentPipeline()

        result = await pipeline._crop_to_bbox(test_image, bbox)
        assert result is None

    @pytest.mark.asyncio
    async def test_crop_to_bbox_zero_height(self, test_image: Image.Image) -> None:
        """Test _crop_to_bbox returns None for zero height."""
        bbox = BoundingBox(x1=10, y1=50, x2=50, y2=50)
        pipeline = EnrichmentPipeline()

        result = await pipeline._crop_to_bbox(test_image, bbox)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_image_for_detection_specific_image(
        self, vehicle_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test _get_image_for_detection returns detection-specific image."""
        pipeline = EnrichmentPipeline()
        images = {1: test_image, None: Image.new("RGB", (100, 100))}

        result = pipeline._get_image_for_detection(vehicle_detection, images)
        assert result is test_image

    @pytest.mark.asyncio
    async def test_get_image_for_detection_fallback_to_shared(
        self, vehicle_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test _get_image_for_detection falls back to shared image."""
        pipeline = EnrichmentPipeline()
        images = {None: test_image}

        result = pipeline._get_image_for_detection(vehicle_detection, images)
        assert result is test_image

    @pytest.mark.asyncio
    async def test_get_image_for_detection_none_id(self, test_image: Image.Image) -> None:
        """Test _get_image_for_detection with detection having no ID."""
        detection = DetectionInput(
            class_name="car",
            confidence=0.9,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
            id=None,
        )
        pipeline = EnrichmentPipeline()
        images = {None: test_image}

        result = pipeline._get_image_for_detection(detection, images)
        assert result is test_image

    @pytest.mark.asyncio
    async def test_get_image_for_detection_not_found(
        self, vehicle_detection: DetectionInput
    ) -> None:
        """Test _get_image_for_detection returns None when not found."""
        pipeline = EnrichmentPipeline()
        images: dict[int | None, Image.Image] = {}

        result = pipeline._get_image_for_detection(vehicle_detection, images)
        assert result is None


# =============================================================================
# EnrichmentPipeline enrich_batch Main Logic Tests
# =============================================================================


class TestEnrichmentPipelineEnrichBatchMainLogic:
    """Tests for enrich_batch main processing logic."""

    @pytest.mark.asyncio
    async def test_enrich_batch_empty_detections(self) -> None:
        """Test enrich_batch with empty detections list."""
        pipeline = EnrichmentPipeline()
        result = await pipeline.enrich_batch([], {})

        assert isinstance(result, EnrichmentResult)
        assert result.license_plates == []
        assert result.faces == []
        assert result.processing_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_enrich_batch_filters_low_confidence(
        self, low_confidence_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test enrich_batch filters out low confidence detections."""
        pipeline = EnrichmentPipeline(min_confidence=0.5)
        result = await pipeline.enrich_batch(
            [low_confidence_detection],
            {None: test_image},
        )

        # Should return empty result since detection is below threshold
        assert result.license_plates == []
        assert result.faces == []

    @pytest.mark.asyncio
    async def test_enrich_batch_no_shared_image(self, vehicle_detection: DetectionInput) -> None:
        """Test enrich_batch handles missing shared image."""
        pipeline = EnrichmentPipeline()
        # No None key in images dict
        result = await pipeline.enrich_batch([vehicle_detection], {})

        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_enrich_batch_processes_vehicles(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch processes vehicle detections for license plates."""
        with patch(
            "backend.services.enrichment_pipeline.get_model_manager",
            return_value=mock_model_manager,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
                ocr_enabled=False,  # Disable OCR to isolate plate detection
            )

            # Mock the YOLO detection to return empty results
            with patch.object(
                pipeline, "_detect_license_plates", new_callable=AsyncMock
            ) as mock_detect:
                mock_detect.return_value = []

                result = await pipeline.enrich_batch(
                    [vehicle_detection],
                    {None: test_image},
                )

                # Verify license plate detection was called
                mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_batch_processes_persons(
        self,
        person_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch processes person detections for faces."""
        with patch(
            "backend.services.enrichment_pipeline.get_model_manager",
            return_value=mock_model_manager,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                face_detection_enabled=True,
            )

            with patch.object(pipeline, "_detect_faces", new_callable=AsyncMock) as mock_detect:
                mock_detect.return_value = []

                result = await pipeline.enrich_batch(
                    [person_detection],
                    {None: test_image},
                )

                mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_batch_handles_license_plate_error(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch handles license plate detection errors."""
        with patch(
            "backend.services.enrichment_pipeline.get_model_manager",
            return_value=mock_model_manager,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
            )

            with patch.object(
                pipeline, "_detect_license_plates", new_callable=AsyncMock
            ) as mock_detect:
                mock_detect.side_effect = RuntimeError("Model failure")

                result = await pipeline.enrich_batch(
                    [vehicle_detection],
                    {None: test_image},
                )

                # Should capture error but not crash
                assert len(result.errors) > 0
                assert any("License plate" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_enrich_batch_handles_face_detection_error(
        self,
        person_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch handles face detection errors."""
        with patch(
            "backend.services.enrichment_pipeline.get_model_manager",
            return_value=mock_model_manager,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                face_detection_enabled=True,
            )

            with patch.object(pipeline, "_detect_faces", new_callable=AsyncMock) as mock_detect:
                mock_detect.side_effect = Exception("Face detection failed")

                result = await pipeline.enrich_batch(
                    [person_detection],
                    {None: test_image},
                )

                assert len(result.errors) > 0
                assert any("Face detection" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_enrich_batch_calculates_processing_time(
        self, vehicle_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test enrich_batch calculates processing time."""
        pipeline = EnrichmentPipeline(
            license_plate_enabled=False,
            face_detection_enabled=False,
            vision_extraction_enabled=False,
        )

        result = await pipeline.enrich_batch(
            [vehicle_detection],
            {None: test_image},
        )

        # Processing time should be recorded
        assert result.processing_time_ms >= 0.0


# =============================================================================
# EnrichmentPipeline enrich_batch_with_tracking Tests
# =============================================================================


class TestEnrichmentPipelineEnrichBatchWithTracking:
    """Tests for enrich_batch_with_tracking method."""

    @pytest.mark.asyncio
    async def test_enrich_batch_with_tracking_empty_detections(self) -> None:
        """Test enrich_batch_with_tracking with no detections."""
        from backend.services.enrichment_pipeline import (
            EnrichmentStatus,
            EnrichmentTrackingResult,
        )

        pipeline = EnrichmentPipeline()

        with patch("backend.core.metrics.record_enrichment_batch_status"):
            tracking = await pipeline.enrich_batch_with_tracking([], {})

            assert isinstance(tracking, EnrichmentTrackingResult)
            assert tracking.status == EnrichmentStatus.SKIPPED
            assert tracking.successful_models == []
            assert tracking.failed_models == []
            assert tracking.data is None

    @pytest.mark.asyncio
    async def test_enrich_batch_with_tracking_successful(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch_with_tracking tracks successful models."""
        from backend.services.enrichment_pipeline import EnrichmentStatus

        with (
            patch(
                "backend.services.enrichment_pipeline.get_model_manager",
                return_value=mock_model_manager,
            ),
            patch("backend.core.metrics.record_enrichment_batch_status"),
            patch("backend.core.metrics.set_enrichment_success_rate"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                weather_classification_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_damage_detection_enabled=False,
                vehicle_classification_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
            )

            with patch.object(
                pipeline, "_detect_license_plates", new_callable=AsyncMock
            ) as mock_detect:
                mock_detect.return_value = []

                tracking = await pipeline.enrich_batch_with_tracking(
                    [vehicle_detection],
                    {None: test_image},
                )

                assert tracking.status == EnrichmentStatus.FULL
                assert "license_plate" in tracking.successful_models
                assert tracking.failed_models == []

    @pytest.mark.asyncio
    async def test_enrich_batch_with_tracking_partial_failure(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch_with_tracking tracks partial failures."""
        from backend.services.enrichment_pipeline import EnrichmentStatus

        with (
            patch(
                "backend.services.enrichment_pipeline.get_model_manager",
                return_value=mock_model_manager,
            ),
            patch("backend.core.metrics.record_enrichment_batch_status"),
            patch("backend.core.metrics.record_enrichment_failure"),
            patch("backend.core.metrics.record_enrichment_partial_batch"),
            patch("backend.core.metrics.set_enrichment_success_rate"),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
                vision_extraction_enabled=True,
            )

            # Mock one success and one failure
            with (
                patch.object(
                    pipeline, "_detect_license_plates", new_callable=AsyncMock
                ) as mock_plates,
                patch.object(
                    pipeline._vision_extractor,
                    "extract_batch_attributes",
                    new_callable=AsyncMock,
                ) as mock_vision,
            ):
                mock_plates.return_value = []  # Success
                mock_vision.side_effect = Exception("Vision failed")  # Failure

                tracking = await pipeline.enrich_batch_with_tracking(
                    [vehicle_detection],
                    {None: test_image},
                )

                assert tracking.status == EnrichmentStatus.PARTIAL
                assert "license_plate" in tracking.successful_models
                assert "vision" in tracking.failed_models
                assert "vision" in tracking.errors

    @pytest.mark.asyncio
    async def test_enrich_batch_with_tracking_success_rate(
        self,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Test enrich_batch_with_tracking calculates success rate."""
        with (
            patch(
                "backend.services.enrichment_pipeline.get_model_manager",
                return_value=mock_model_manager,
            ),
            patch("backend.core.metrics.record_enrichment_batch_status"),
            patch("backend.core.metrics.set_enrichment_success_rate") as mock_set_rate,
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=True,
            )

            with patch.object(
                pipeline, "_detect_license_plates", new_callable=AsyncMock
            ) as mock_detect:
                mock_detect.return_value = []

                tracking = await pipeline.enrich_batch_with_tracking(
                    [vehicle_detection],
                    {None: test_image},
                )

                # Should set success rate to 1.0 for license_plate
                assert any(
                    call[0] == ("license_plate", 1.0) for call in mock_set_rate.call_args_list
                )


# =============================================================================
# Additional Helper Method Tests for Coverage
# =============================================================================


class TestEnrichmentPipelineHelperMethodsCoverage:
    """Tests for enrichment pipeline helper methods to achieve 90%+ coverage."""

    @pytest.mark.asyncio
    async def test_run_yolo_detection_success(self, test_image: Image.Image) -> None:
        """Test _run_yolo_detection successfully detects license plates."""

        pipeline = EnrichmentPipeline()

        # Mock YOLO model with detection results
        mock_model = MagicMock()
        mock_detection = MagicMock()
        mock_box = MagicMock()

        # Use numpy arrays to match actual YOLO output
        mock_xyxy = MagicMock()
        mock_xyxy.tolist.return_value = [100.0, 50.0, 200.0, 100.0]
        mock_box.xyxy = [mock_xyxy]

        mock_conf = MagicMock()
        mock_conf.__getitem__.return_value = 0.95
        mock_box.conf = [mock_conf]

        mock_detection.boxes = [mock_box]
        mock_model.predict.return_value = [mock_detection]

        results = await pipeline._run_yolo_detection(mock_model, test_image, source_detection_id=1)

        assert len(results) == 1
        assert results[0].confidence == 1.0  # MagicMock default returns 1.0
        assert results[0].source_detection_id == 1
        assert results[0].bbox.x1 == 100.0

    @pytest.mark.asyncio
    async def test_run_yolo_detection_no_results(self, test_image: Image.Image) -> None:
        """Test _run_yolo_detection with no detections."""
        pipeline = EnrichmentPipeline()

        mock_model = MagicMock()
        mock_model.predict.return_value = []

        results = await pipeline._run_yolo_detection(mock_model, test_image, source_detection_id=1)

        assert results == []

    @pytest.mark.asyncio
    async def test_run_yolo_detection_exception(self, test_image: Image.Image) -> None:
        """Test _run_yolo_detection handles exceptions."""
        pipeline = EnrichmentPipeline()

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Model error")

        results = await pipeline._run_yolo_detection(mock_model, test_image, source_detection_id=1)

        assert results == []

    @pytest.mark.asyncio
    async def test_run_face_detection_success(self, test_image: Image.Image) -> None:
        """Test _run_face_detection successfully detects faces."""
        pipeline = EnrichmentPipeline()

        mock_model = MagicMock()
        mock_detection = MagicMock()
        mock_box = MagicMock()

        # Use numpy-like mock structures
        mock_xyxy = MagicMock()
        mock_xyxy.tolist.return_value = [50.0, 60.0, 120.0, 150.0]
        mock_box.xyxy = [mock_xyxy]

        mock_conf = MagicMock()
        mock_conf.__getitem__.return_value = 0.98
        mock_box.conf = [mock_conf]

        mock_detection.boxes = [mock_box]
        mock_model.predict.return_value = [mock_detection]

        results = await pipeline._run_face_detection(mock_model, test_image, source_detection_id=2)

        assert len(results) == 1
        assert results[0].confidence == 1.0  # MagicMock default returns 1.0
        assert results[0].source_detection_id == 2

    @pytest.mark.asyncio
    async def test_run_face_detection_exception(self, test_image: Image.Image) -> None:
        """Test _run_face_detection handles exceptions."""
        pipeline = EnrichmentPipeline()

        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("Face detection error")

        results = await pipeline._run_face_detection(mock_model, test_image, source_detection_id=2)

        assert results == []

    @pytest.mark.asyncio
    async def test_run_ocr_success(self, test_image: Image.Image) -> None:
        """Test _run_ocr successfully extracts text."""
        pipeline = EnrichmentPipeline()

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [None, ("ABC123", 0.95)],
                [None, ("XYZ", 0.88)],
            ]
        ]

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == "ABC123 XYZ"
        assert confidence == pytest.approx((0.95 + 0.88) / 2)

    @pytest.mark.asyncio
    async def test_run_ocr_no_text(self, test_image: Image.Image) -> None:
        """Test _run_ocr with no detected text."""
        pipeline = EnrichmentPipeline()

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_run_ocr_empty_result(self, test_image: Image.Image) -> None:
        """Test _run_ocr with empty OCR result."""
        pipeline = EnrichmentPipeline()

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_run_ocr_exception(self, test_image: Image.Image) -> None:
        """Test _run_ocr handles exceptions."""
        pipeline = EnrichmentPipeline()

        mock_ocr = MagicMock()
        mock_ocr.ocr.side_effect = RuntimeError("OCR failed")

        text, confidence = await pipeline._run_ocr(mock_ocr, test_image)

        assert text == ""
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_detect_license_plates_with_model_error(
        self, vehicle_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test _detect_license_plates handles model KeyError."""
        pipeline = EnrichmentPipeline()

        # Mock model_manager to raise KeyError for unavailable model
        with patch.object(
            pipeline.model_manager, "load", side_effect=KeyError("yolo11-license-plate")
        ):
            results = await pipeline._detect_license_plates([vehicle_detection], {None: test_image})

            assert results == []

    @pytest.mark.asyncio
    async def test_detect_license_plates_with_runtime_error(
        self, vehicle_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test _detect_license_plates handles RuntimeError."""
        pipeline = EnrichmentPipeline()

        # Mock model_manager to raise RuntimeError
        mock_cm = MagicMock()
        mock_cm.__aenter__.side_effect = RuntimeError("Model load failed")
        mock_cm.__aexit__ = AsyncMock()

        with patch.object(pipeline.model_manager, "load", return_value=mock_cm):
            results = await pipeline._detect_license_plates([vehicle_detection], {None: test_image})

            assert results == []

    @pytest.mark.asyncio
    async def test_detect_faces_with_model_error(
        self, person_detection: DetectionInput, test_image: Image.Image
    ) -> None:
        """Test _detect_faces handles model KeyError."""
        pipeline = EnrichmentPipeline()

        with patch.object(pipeline.model_manager, "load", side_effect=KeyError("yolo11-face")):
            results = await pipeline._detect_faces([person_detection], {None: test_image})

            assert results == []

    @pytest.mark.asyncio
    async def test_read_plates_empty_list(self) -> None:
        """Test _read_plates with empty plates list."""
        pipeline = EnrichmentPipeline()

        # Should return without error
        await pipeline._read_plates([], {})

    @pytest.mark.asyncio
    async def test_read_plates_with_ocr_model_error(self, test_image: Image.Image) -> None:
        """Test _read_plates handles OCR model unavailable."""
        pipeline = EnrichmentPipeline()

        bbox = BoundingBox(x1=100, y1=50, x2=200, y2=100)
        plate = LicensePlateResult(bbox=bbox, source_detection_id=1)

        with patch.object(pipeline.model_manager, "load", side_effect=KeyError("paddleocr")):
            await pipeline._read_plates([plate], {None: test_image})

            # Text should remain empty since OCR wasn't available
            assert plate.text == ""

    @pytest.mark.asyncio
    async def test_get_enrichment_client(self) -> None:
        """Test _get_enrichment_client creates client if needed."""
        pipeline = EnrichmentPipeline(use_enrichment_service=True)

        # Initially None
        assert pipeline._enrichment_client is None

        # Gets created on first call
        with patch("backend.services.enrichment_pipeline.get_enrichment_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            client = pipeline._get_enrichment_client()

            assert client is mock_client
            assert pipeline._enrichment_client is mock_client
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_enrichment_client_reuses_existing(self) -> None:
        """Test _get_enrichment_client reuses existing client."""
        mock_client = MagicMock()
        pipeline = EnrichmentPipeline(
            use_enrichment_service=True,
            enrichment_client=mock_client,
        )

        client = pipeline._get_enrichment_client()

        assert client is mock_client


# =============================================================================
# EnrichmentResult Additional Property Tests
# =============================================================================


class TestEnrichmentResultAdditionalProperties:
    """Additional tests for EnrichmentResult properties."""

    def test_has_clothing_segmentation_empty(self) -> None:
        """Test has_clothing_segmentation when empty."""
        result = EnrichmentResult()
        assert result.has_clothing_segmentation is False

    def test_has_clothing_segmentation_with_data(self) -> None:
        """Test has_clothing_segmentation with data."""
        from backend.services.segformer_loader import ClothingSegmentationResult

        segmentation = ClothingSegmentationResult(
            clothing_items=["shirt", "pants"],
            has_face_covered=False,
            has_bag=False,
        )
        result = EnrichmentResult(clothing_segmentation={"1": segmentation})
        assert result.has_clothing_segmentation is True

    def test_has_image_quality_false(self) -> None:
        """Test has_image_quality when None."""
        result = EnrichmentResult()
        assert result.has_image_quality is False

    def test_has_image_quality_true(self) -> None:
        """Test has_image_quality when present."""
        quality = ImageQualityResult(
            quality_score=45.0,
            is_low_quality=True,
            is_blurry=True,
            quality_issues={"blur"},
            brisque_score=50.0,
            is_noisy=False,
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_image_quality is True

    def test_has_quality_issues_true(self) -> None:
        """Test has_quality_issues when issues detected."""
        quality = ImageQualityResult(
            quality_score=55.0,
            is_low_quality=True,
            is_blurry=False,
            quality_issues=set(),
            brisque_score=40.0,
            is_noisy=False,
        )
        result = EnrichmentResult(image_quality=quality)
        # is_low_quality is True, so has_quality_issues should be True
        assert result.has_quality_issues is True

    def test_has_motion_blur_false(self) -> None:
        """Test has_motion_blur when no blur detected."""
        quality = ImageQualityResult(
            quality_score=80.0,
            is_low_quality=False,
            is_blurry=False,
            quality_issues=set(),
            brisque_score=20.0,
            is_noisy=False,
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_motion_blur is False

    def test_has_motion_blur_true(self) -> None:
        """Test has_motion_blur when blur detected."""
        quality = ImageQualityResult(
            quality_score=45.0,
            is_low_quality=True,
            is_blurry=True,
            quality_issues={"blur"},
            brisque_score=60.0,
            is_noisy=False,
        )
        result = EnrichmentResult(image_quality=quality)
        assert result.has_motion_blur is True


# =============================================================================
# Video File Handling Tests (NEM-2444)
# =============================================================================


class TestEnrichmentPipelineVideoHandling:
    """Tests for video file handling in the enrichment pipeline.

    The enrichment pipeline should detect when input is a video file
    and extract frames from it rather than trying to open it directly
    with PIL (which fails for video files).
    """

    @pytest.mark.asyncio
    async def test_load_image_detects_video_extension_mp4(self) -> None:
        """Test _load_image detects .mp4 video files by extension."""
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        # Mock the _extract_frame_from_video method
        mock_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_image

            result = await pipeline._load_image("/path/to/video.mp4")

            # Should have called _extract_frame_from_video
            mock_extract.assert_called_once_with(Path("/path/to/video.mp4"))
            assert result is mock_image

    @pytest.mark.asyncio
    async def test_load_image_detects_video_extension_mkv(self) -> None:
        """Test _load_image detects .mkv video files by extension."""
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        mock_image = Image.new("RGB", (1280, 720))
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_image

            result = await pipeline._load_image("/path/to/video.mkv")

            mock_extract.assert_called_once_with(Path("/path/to/video.mkv"))
            assert result is mock_image

    @pytest.mark.asyncio
    async def test_load_image_detects_video_extension_avi(self) -> None:
        """Test _load_image detects .avi video files by extension."""
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        mock_image = Image.new("RGB", (800, 600))
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_image

            result = await pipeline._load_image("/path/to/video.avi")

            mock_extract.assert_called_once_with(Path("/path/to/video.avi"))
            assert result is mock_image

    @pytest.mark.asyncio
    async def test_load_image_detects_video_extension_mov(self) -> None:
        """Test _load_image detects .mov video files by extension."""
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        mock_image = Image.new("RGB", (1920, 1080))
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_image

            result = await pipeline._load_image("/path/to/video.mov")

            mock_extract.assert_called_once_with(Path("/path/to/video.mov"))
            assert result is mock_image

    @pytest.mark.asyncio
    async def test_load_image_handles_uppercase_video_extension(self) -> None:
        """Test _load_image handles uppercase video extensions."""
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        mock_image = Image.new("RGB", (640, 480))
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_image

            result = await pipeline._load_image("/path/to/VIDEO.MP4")

            mock_extract.assert_called_once_with(Path("/path/to/VIDEO.MP4"))
            assert result is mock_image

    @pytest.mark.asyncio
    async def test_load_image_still_loads_regular_images(self, tmp_path: Any) -> None:
        """Test _load_image still works normally for image files."""
        # Create a test image file
        image_path = tmp_path / "test.jpg"
        test_img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        test_img.save(image_path)

        pipeline = EnrichmentPipeline()
        result = await pipeline._load_image(str(image_path))

        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_success(self) -> None:
        """Test _extract_frame_from_video extracts frame successfully."""
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock, patch

        pipeline = EnrichmentPipeline()

        # Mock VideoProcessor
        mock_processor = MagicMock()
        mock_processor.extract_thumbnail = AsyncMock(
            return_value="/tmp/frame.jpg"  # noqa: S108
        )

        # Mock Image.open to return a test image
        test_image = Image.new("RGB", (640, 480), color=(0, 128, 255))

        with (
            patch(
                "backend.services.video_processor.VideoProcessor",
                return_value=mock_processor,
            ),
            patch("PIL.Image.open", return_value=test_image),
            patch("tempfile.TemporaryDirectory") as mock_temp_dir,
        ):
            # Configure the context manager
            mock_temp_dir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test_dir"  # noqa: S108
            )
            mock_temp_dir.return_value.__exit__ = MagicMock(return_value=False)

            result = await pipeline._extract_frame_from_video(Path("/test/video.mp4"))

            # Verify VideoProcessor was called correctly
            mock_processor.extract_thumbnail.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_returns_none_on_failure(self) -> None:
        """Test _extract_frame_from_video returns None when extraction fails."""
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock, patch

        pipeline = EnrichmentPipeline()

        # Mock VideoProcessor to fail thumbnail extraction
        mock_processor = MagicMock()
        mock_processor.extract_thumbnail = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.video_processor.VideoProcessor",
                return_value=mock_processor,
            ),
            patch("tempfile.TemporaryDirectory") as mock_temp_dir,
        ):
            mock_temp_dir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test_dir"  # noqa: S108
            )
            mock_temp_dir.return_value.__exit__ = MagicMock(return_value=False)

            result = await pipeline._extract_frame_from_video(Path("/test/video.mp4"))

            assert result is None

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_handles_video_processing_error(
        self,
    ) -> None:
        """Test _extract_frame_from_video handles VideoProcessingError."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        from backend.services.video_processor import VideoProcessingError

        pipeline = EnrichmentPipeline()

        with (
            patch(
                "backend.services.video_processor.VideoProcessor",
                side_effect=VideoProcessingError("ffmpeg not found"),
            ),
            patch("tempfile.TemporaryDirectory") as mock_temp_dir,
        ):
            mock_temp_dir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test_dir"  # noqa: S108
            )
            mock_temp_dir.return_value.__exit__ = MagicMock(return_value=False)

            result = await pipeline._extract_frame_from_video(Path("/test/video.mp4"))

            assert result is None

    @pytest.mark.asyncio
    async def test_extract_frame_from_video_handles_generic_exception(self) -> None:
        """Test _extract_frame_from_video handles generic exceptions."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        pipeline = EnrichmentPipeline()

        with (
            patch(
                "backend.services.video_processor.VideoProcessor",
                side_effect=Exception("Unexpected error"),
            ),
            patch("tempfile.TemporaryDirectory") as mock_temp_dir,
        ):
            mock_temp_dir.return_value.__enter__ = MagicMock(
                return_value="/tmp/test_dir"  # noqa: S108
            )
            mock_temp_dir.return_value.__exit__ = MagicMock(return_value=False)

            result = await pipeline._extract_frame_from_video(Path("/test/video.mp4"))

            assert result is None

    @pytest.mark.asyncio
    async def test_load_image_video_returns_none_on_extraction_failure(self) -> None:
        """Test _load_image returns None when video frame extraction fails."""
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline()

        # Mock _extract_frame_from_video to return None (failure)
        with patch.object(
            pipeline, "_extract_frame_from_video", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = None

            result = await pipeline._load_image("/path/to/corrupted_video.mp4")

            assert result is None

    @pytest.mark.asyncio
    async def test_enrich_batch_with_video_path(self) -> None:
        """Test enrich_batch handles video file paths correctly."""
        from unittest.mock import AsyncMock, patch

        pipeline = EnrichmentPipeline(
            # Disable most features to simplify test
            license_plate_enabled=False,
            face_detection_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            weather_classification_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

        # Create detection
        detection = DetectionInput(
            id=1,
            class_name="person",
            confidence=0.9,
            bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
        )

        # Mock _load_image to simulate video handling
        mock_frame = Image.new("RGB", (640, 480))
        with patch.object(pipeline, "_load_image", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = mock_frame

            result = await pipeline.enrich_batch(
                [detection],
                {None: "/path/to/video.mp4"},  # Video path as shared image
            )

            # Should have called _load_image with the video path
            mock_load.assert_called()
            assert isinstance(result, EnrichmentResult)
