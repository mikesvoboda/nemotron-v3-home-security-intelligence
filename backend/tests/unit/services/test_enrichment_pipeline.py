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
            assert pipeline.clothing_classification_enabled is True
            assert pipeline.clothing_segmentation_enabled is True
            assert pipeline.vehicle_damage_detection_enabled is True
            assert pipeline.vehicle_classification_enabled is True
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
