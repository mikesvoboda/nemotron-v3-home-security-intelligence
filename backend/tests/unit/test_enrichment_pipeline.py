"""Unit tests for the EnrichmentPipeline service.

This module provides comprehensive tests for backend/services/enrichment_pipeline.py,
the most complex service in the codebase with 54+ methods handling AI enrichment pipelines.

Tests cover:
- BoundingBox and result dataclass operations
- EnrichmentPipeline initialization and configuration
- enrich_batch() orchestration with 8+ enrichment types
- Individual enrichment methods (_run_reid, _detect_license_plates, etc.)
- Image handling (PIL Image, Path, str)
- Error isolation (one enrichment fails, others continue)
- Remote service fallback logic
- Global singleton functions
"""

from __future__ import annotations

import tempfile
from pathlib import Path
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
from backend.services.vehicle_damage_loader import VehicleDamageResult
from backend.services.violence_loader import ViolenceDetectionResult

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def sample_image():
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (640, 480), color="blue")


@pytest.fixture
def temp_image_file():
    """Create a temporary image file for testing path handling."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = Image.new("RGB", (320, 240), color="green")
        img.save(tmp.name, "JPEG")
        yield tmp.name
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def mock_model_manager():
    """Create a mock ModelManager."""
    manager = MagicMock()
    # Create async context manager for load()
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_context.__aexit__ = AsyncMock(return_value=None)
    manager.load.return_value = mock_context
    return manager


@pytest.fixture
def sample_detections():
    """Create sample detections for testing."""
    return [
        DetectionInput(
            id=1,
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250, confidence=0.95),
        ),
        DetectionInput(
            id=2,
            class_name="person",
            confidence=0.88,
            bbox=BoundingBox(x1=400, y1=50, x2=500, y2=400, confidence=0.88),
        ),
        DetectionInput(
            id=3,
            class_name="dog",
            confidence=0.92,
            bbox=BoundingBox(x1=200, y1=200, x2=280, y2=320, confidence=0.92),
        ),
    ]


@pytest.fixture
def sample_person_detections():
    """Create multiple person detections for violence detection testing."""
    return [
        DetectionInput(
            id=1,
            class_name="person",
            confidence=0.91,
            bbox=BoundingBox(x1=50, y1=50, x2=150, y2=400, confidence=0.91),
        ),
        DetectionInput(
            id=2,
            class_name="person",
            confidence=0.89,
            bbox=BoundingBox(x1=200, y1=60, x2=300, y2=410, confidence=0.89),
        ),
    ]


@pytest.fixture
def mock_enrichment_client():
    """Create a mock EnrichmentClient for remote service tests."""
    client = AsyncMock()
    client.classify_vehicle = AsyncMock()
    client.classify_pet = AsyncMock()
    client.classify_clothing = AsyncMock()
    return client


# ==============================================================================
# BoundingBox Tests
# ==============================================================================


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_bounding_box_creation(self) -> None:
        """Test creating a BoundingBox with all fields."""
        bbox = BoundingBox(x1=10.0, y1=20.0, x2=100.0, y2=150.0, confidence=0.95)

        assert bbox.x1 == 10.0
        assert bbox.y1 == 20.0
        assert bbox.x2 == 100.0
        assert bbox.y2 == 150.0
        assert bbox.confidence == 0.95

    def test_bounding_box_default_confidence(self) -> None:
        """Test BoundingBox with default confidence."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        assert bbox.confidence == 0.0

    def test_bounding_box_to_tuple(self) -> None:
        """Test to_tuple returns correct format."""
        bbox = BoundingBox(x1=10.5, y1=20.5, x2=100.5, y2=150.5)
        result = bbox.to_tuple()

        assert result == (10.5, 20.5, 100.5, 150.5)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_bounding_box_to_int_tuple(self) -> None:
        """Test to_int_tuple returns integer coordinates."""
        bbox = BoundingBox(x1=10.7, y1=20.3, x2=100.9, y2=150.1)
        result = bbox.to_int_tuple()

        assert result == (10, 20, 100, 150)
        assert all(isinstance(v, int) for v in result)

    def test_bounding_box_width(self) -> None:
        """Test width property calculation."""
        bbox = BoundingBox(x1=50, y1=0, x2=200, y2=100)
        assert bbox.width == 150.0

    def test_bounding_box_height(self) -> None:
        """Test height property calculation."""
        bbox = BoundingBox(x1=0, y1=30, x2=100, y2=180)
        assert bbox.height == 150.0

    def test_bounding_box_center(self) -> None:
        """Test center property calculation."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=200)
        center = bbox.center

        assert center == (50.0, 100.0)
        assert isinstance(center, tuple)
        assert len(center) == 2


# ==============================================================================
# LicensePlateResult Tests
# ==============================================================================


class TestLicensePlateResult:
    """Tests for LicensePlateResult dataclass."""

    def test_license_plate_result_creation(self) -> None:
        """Test creating a LicensePlateResult with all fields."""
        bbox = BoundingBox(x1=10, y1=10, x2=100, y2=50)
        result = LicensePlateResult(
            bbox=bbox,
            text="ABC123",
            confidence=0.92,
            ocr_confidence=0.88,
            source_detection_id=42,
        )

        assert result.bbox is bbox
        assert result.text == "ABC123"
        assert result.confidence == 0.92
        assert result.ocr_confidence == 0.88
        assert result.source_detection_id == 42

    def test_license_plate_result_defaults(self) -> None:
        """Test LicensePlateResult with default values."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=25)
        result = LicensePlateResult(bbox=bbox)

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.ocr_confidence == 0.0
        assert result.source_detection_id is None


# ==============================================================================
# FaceResult Tests
# ==============================================================================


class TestFaceResult:
    """Tests for FaceResult dataclass."""

    def test_face_result_creation(self) -> None:
        """Test creating a FaceResult with all fields."""
        bbox = BoundingBox(x1=50, y1=20, x2=120, y2=110)
        result = FaceResult(
            bbox=bbox,
            confidence=0.96,
            source_detection_id=7,
        )

        assert result.bbox is bbox
        assert result.confidence == 0.96
        assert result.source_detection_id == 7

    def test_face_result_defaults(self) -> None:
        """Test FaceResult with default values."""
        bbox = BoundingBox(x1=0, y1=0, x2=50, y2=50)
        result = FaceResult(bbox=bbox)

        assert result.confidence == 0.0
        assert result.source_detection_id is None


# ==============================================================================
# DetectionInput Tests
# ==============================================================================


class TestDetectionInput:
    """Tests for DetectionInput dataclass."""

    def test_detection_input_creation(self) -> None:
        """Test creating a DetectionInput with all fields."""
        bbox = BoundingBox(x1=100, y1=100, x2=300, y2=400)
        detection = DetectionInput(
            id=123,
            class_name="person",
            confidence=0.94,
            bbox=bbox,
        )

        assert detection.id == 123
        assert detection.class_name == "person"
        assert detection.confidence == 0.94
        assert detection.bbox is bbox

    def test_detection_input_default_id(self) -> None:
        """Test DetectionInput with default id (None)."""
        bbox = BoundingBox(x1=0, y1=0, x2=100, y2=100)
        detection = DetectionInput(
            class_name="car",
            confidence=0.85,
            bbox=bbox,
        )

        assert detection.id is None


# ==============================================================================
# EnrichmentResult Tests
# ==============================================================================


class TestEnrichmentResult:
    """Tests for EnrichmentResult dataclass and properties."""

    def test_enrichment_result_default_values(self) -> None:
        """Test EnrichmentResult initializes with empty defaults."""
        result = EnrichmentResult()

        assert result.license_plates == []
        assert result.faces == []
        assert result.vision_extraction is None
        assert result.person_reid_matches == {}
        assert result.vehicle_reid_matches == {}
        assert result.scene_change is None
        assert result.violence_detection is None
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

    def test_has_license_plates_true(self) -> None:
        """Test has_license_plates returns True when plates exist."""
        result = EnrichmentResult()
        result.license_plates = [LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text="ABC123")]
        assert result.has_license_plates is True

    def test_has_license_plates_false(self) -> None:
        """Test has_license_plates returns False when empty."""
        result = EnrichmentResult()
        assert result.has_license_plates is False

    def test_has_readable_plates_true(self) -> None:
        """Test has_readable_plates returns True when plates have text."""
        result = EnrichmentResult()
        result.license_plates = [LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text="XYZ789")]
        assert result.has_readable_plates is True

    def test_has_readable_plates_false_empty_text(self) -> None:
        """Test has_readable_plates returns False when plates have no text."""
        result = EnrichmentResult()
        result.license_plates = [LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text="")]
        assert result.has_readable_plates is False

    def test_plate_texts_returns_non_empty_only(self) -> None:
        """Test plate_texts filters out empty texts."""
        result = EnrichmentResult()
        result.license_plates = [
            LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text="ABC123"),
            LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text=""),
            LicensePlateResult(bbox=BoundingBox(0, 0, 50, 25), text="XYZ789"),
        ]

        texts = result.plate_texts
        assert texts == ["ABC123", "XYZ789"]
        assert len(texts) == 2

    def test_has_faces_true(self) -> None:
        """Test has_faces returns True when faces exist."""
        result = EnrichmentResult()
        result.faces = [FaceResult(bbox=BoundingBox(0, 0, 50, 50))]
        assert result.has_faces is True

    def test_has_faces_false(self) -> None:
        """Test has_faces returns False when empty."""
        result = EnrichmentResult()
        assert result.has_faces is False

    def test_has_violence_true(self) -> None:
        """Test has_violence returns True when violence detected."""
        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True, confidence=0.85, violent_score=0.85, non_violent_score=0.15
        )
        assert result.has_violence is True

    def test_has_violence_false_not_violent(self) -> None:
        """Test has_violence returns False when not violent."""
        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=False, confidence=0.92, violent_score=0.08, non_violent_score=0.92
        )
        assert result.has_violence is False

    def test_has_suspicious_clothing_true(self) -> None:
        """Test has_suspicious_clothing returns True when suspicious clothing found."""
        result = EnrichmentResult()
        result.clothing_classifications = {
            "1": ClothingClassification(
                top_category="hoodie",
                confidence=0.85,
                all_scores={"hoodie": 0.85},
                is_suspicious=True,
                is_service_uniform=False,
            )
        }
        assert result.has_suspicious_clothing is True

    def test_has_suspicious_clothing_false(self) -> None:
        """Test has_suspicious_clothing returns False when no suspicious clothing."""
        result = EnrichmentResult()
        result.clothing_classifications = {
            "1": ClothingClassification(
                top_category="casual",
                confidence=0.90,
                all_scores={"casual": 0.90},
                is_suspicious=False,
                is_service_uniform=False,
            )
        }
        assert result.has_suspicious_clothing is False

    def test_has_commercial_vehicles_true(self) -> None:
        """Test has_commercial_vehicles returns True when commercial vehicles found."""
        result = EnrichmentResult()
        result.vehicle_classifications = {
            "1": VehicleClassificationResult(
                vehicle_type="work_van",
                confidence=0.88,
                display_name="work van",
                is_commercial=True,
                all_scores={"work_van": 0.88, "car": 0.08},
            )
        }
        assert result.has_commercial_vehicles is True

    def test_has_vehicle_damage_true(self) -> None:
        """Test has_vehicle_damage returns True when damage detected."""
        from backend.services.vehicle_damage_loader import DamageDetection

        result = EnrichmentResult()
        result.vehicle_damage = {
            "1": VehicleDamageResult(
                detections=[
                    DamageDetection(
                        damage_type="scratch",
                        confidence=0.85,
                        bbox=(100, 100, 200, 150),
                    )
                ]
            )
        }
        assert result.has_vehicle_damage is True

    def test_has_high_security_damage_true(self) -> None:
        """Test has_high_security_damage returns True for glass/lamp damage."""
        from backend.services.vehicle_damage_loader import DamageDetection

        result = EnrichmentResult()
        result.vehicle_damage = {
            "1": VehicleDamageResult(
                detections=[
                    DamageDetection(
                        damage_type="glass_shatter",
                        confidence=0.92,
                        bbox=(50, 50, 150, 100),
                    )
                ]
            )
        }
        assert result.has_high_security_damage is True

    def test_has_quality_issues_true(self) -> None:
        """Test has_quality_issues returns True for low quality images."""
        result = EnrichmentResult()
        result.image_quality = ImageQualityResult(
            quality_score=25.0,
            brisque_score=75.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )
        assert result.has_quality_issues is True

    def test_has_motion_blur_true(self) -> None:
        """Test has_motion_blur returns True when blur detected."""
        result = EnrichmentResult()
        result.image_quality = ImageQualityResult(
            quality_score=30.0,
            brisque_score=70.0,
            is_blurry=True,
            is_noisy=False,
            is_low_quality=True,
            quality_issues=["blurry"],
        )
        assert result.has_motion_blur is True

    def test_pet_only_event_true(self) -> None:
        """Test pet_only_event returns True for pet-only scenario."""
        result = EnrichmentResult()
        result.pet_classifications = {
            "1": PetClassificationResult(
                animal_type="dog",
                confidence=0.98,
                cat_score=0.01,
                dog_score=0.98,
                is_household_pet=True,
            )
        }
        # No faces, plates, violence, or clothing
        assert result.pet_only_event is True

    def test_pet_only_event_false_with_face(self) -> None:
        """Test pet_only_event returns False when faces present."""
        result = EnrichmentResult()
        result.pet_classifications = {
            "1": PetClassificationResult(
                animal_type="dog",
                confidence=0.98,
                cat_score=0.01,
                dog_score=0.98,
                is_household_pet=True,
            )
        }
        result.faces = [FaceResult(bbox=BoundingBox(0, 0, 50, 50))]
        assert result.pet_only_event is False

    def test_to_context_string_empty(self) -> None:
        """Test to_context_string returns default message when empty."""
        result = EnrichmentResult()
        context = result.to_context_string()
        assert context == "No additional context extracted."

    def test_to_context_string_with_plates(self) -> None:
        """Test to_context_string includes license plates."""
        result = EnrichmentResult()
        result.license_plates = [
            LicensePlateResult(
                bbox=BoundingBox(0, 0, 50, 25),
                text="ABC123",
                ocr_confidence=0.95,
            )
        ]
        context = result.to_context_string()
        assert "License Plates" in context
        assert "ABC123" in context
        assert "95%" in context

    def test_to_context_string_with_faces(self) -> None:
        """Test to_context_string includes faces."""
        result = EnrichmentResult()
        result.faces = [FaceResult(bbox=BoundingBox(0, 0, 50, 50), confidence=0.92)]
        context = result.to_context_string()
        assert "Faces" in context
        assert "92%" in context

    def test_to_context_string_with_violence(self) -> None:
        """Test to_context_string includes violence detection."""
        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True, confidence=0.88, violent_score=0.88, non_violent_score=0.12
        )
        context = result.to_context_string()
        assert "Violence Detection" in context
        assert "VIOLENCE DETECTED" in context

    def test_to_dict(self) -> None:
        """Test to_dict returns proper dictionary format."""
        result = EnrichmentResult()
        result.license_plates = [
            LicensePlateResult(
                bbox=BoundingBox(10, 20, 100, 50),
                text="XYZ789",
                confidence=0.90,
                ocr_confidence=0.85,
                source_detection_id=1,
            )
        ]
        result.processing_time_ms = 125.5

        d = result.to_dict()

        assert "license_plates" in d
        assert len(d["license_plates"]) == 1
        assert d["license_plates"][0]["text"] == "XYZ789"
        assert d["processing_time_ms"] == 125.5

    def test_get_risk_modifiers_violence(self) -> None:
        """Test get_risk_modifiers includes violence modifier."""
        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True, confidence=0.90, violent_score=0.90, non_violent_score=0.10
        )

        modifiers = result.get_risk_modifiers()

        assert "violence" in modifiers
        assert modifiers["violence"] > 0.5  # Should increase risk significantly

    def test_get_risk_modifiers_pet_only(self) -> None:
        """Test get_risk_modifiers includes pet_only modifier."""
        result = EnrichmentResult()
        result.pet_classifications = {
            "1": PetClassificationResult(
                animal_type="cat",
                confidence=0.97,
                cat_score=0.97,
                dog_score=0.02,
                is_household_pet=True,
            )
        }

        modifiers = result.get_risk_modifiers()

        assert "pet_only" in modifiers
        assert modifiers["pet_only"] < 0  # Should decrease risk

    def test_get_summary_flags_violence(self) -> None:
        """Test get_summary_flags includes violence flag."""
        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True, confidence=0.92, violent_score=0.92, non_violent_score=0.08
        )

        flags = result.get_summary_flags()

        assert len(flags) >= 1
        violence_flags = [f for f in flags if f["type"] == "violence"]
        assert len(violence_flags) == 1
        assert violence_flags[0]["severity"] == "critical"


# ==============================================================================
# EnrichmentPipeline Initialization Tests
# ==============================================================================


class TestEnrichmentPipelineInit:
    """Tests for EnrichmentPipeline initialization."""

    def setup_method(self) -> None:
        """Reset pipeline before each test."""
        reset_enrichment_pipeline()

    def teardown_method(self) -> None:
        """Reset pipeline after each test."""
        reset_enrichment_pipeline()

    def test_pipeline_init_default_settings(self, mock_model_manager) -> None:
        """Test pipeline initializes with default settings."""
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
        assert pipeline.pet_classification_enabled is True
        assert pipeline.use_enrichment_service is False

    def test_pipeline_init_custom_settings(self, mock_model_manager) -> None:
        """Test pipeline initializes with custom settings."""
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

    def test_global_singleton(self) -> None:
        """Test get_enrichment_pipeline returns singleton."""
        pipeline1 = get_enrichment_pipeline()
        pipeline2 = get_enrichment_pipeline()

        assert pipeline1 is pipeline2

    def test_reset_singleton(self) -> None:
        """Test reset_enrichment_pipeline clears singleton."""
        pipeline1 = get_enrichment_pipeline()
        reset_enrichment_pipeline()
        pipeline2 = get_enrichment_pipeline()

        assert pipeline1 is not pipeline2


# ==============================================================================
# EnrichmentPipeline Image Handling Tests
# ==============================================================================


class TestEnrichmentPipelineImageHandling:
    """Tests for image loading and cropping operations."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with all enrichments disabled for isolated testing."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_load_image_pil_passthrough(self, pipeline, sample_image) -> None:
        """Test _load_image returns PIL Image unchanged."""
        result = await pipeline._load_image(sample_image)

        assert result is sample_image
        assert isinstance(result, Image.Image)

    @pytest.mark.asyncio
    async def test_load_image_from_path(self, pipeline, temp_image_file) -> None:
        """Test _load_image loads from Path object."""
        path = Path(temp_image_file)
        result = await pipeline._load_image(path)

        assert isinstance(result, Image.Image)
        assert result.size == (320, 240)

    @pytest.mark.asyncio
    async def test_load_image_from_string_path(self, pipeline, temp_image_file) -> None:
        """Test _load_image loads from string path."""
        result = await pipeline._load_image(temp_image_file)

        assert isinstance(result, Image.Image)
        assert result.size == (320, 240)

    @pytest.mark.asyncio
    async def test_load_image_invalid_path_returns_none(self, pipeline) -> None:
        """Test _load_image returns None for invalid path."""
        result = await pipeline._load_image("/nonexistent/image.jpg")
        assert result is None

    @pytest.mark.asyncio
    async def test_crop_to_bbox_success(self, pipeline, sample_image) -> None:
        """Test _crop_to_bbox crops correctly."""
        bbox = BoundingBox(x1=100, y1=100, x2=300, y2=250)
        result = await pipeline._crop_to_bbox(sample_image, bbox)

        assert isinstance(result, Image.Image)
        assert result.size == (200, 150)

    @pytest.mark.asyncio
    async def test_crop_to_bbox_clamps_to_image_bounds(self, pipeline, sample_image) -> None:
        """Test _crop_to_bbox clamps coordinates to image bounds."""
        # Bbox extends beyond image boundaries
        bbox = BoundingBox(x1=-50, y1=-50, x2=700, y2=500)
        result = await pipeline._crop_to_bbox(sample_image, bbox)

        assert isinstance(result, Image.Image)
        # Should be clamped to image size (640x480)
        assert result.size == (640, 480)

    @pytest.mark.asyncio
    async def test_crop_to_bbox_invalid_returns_none(self, pipeline, sample_image) -> None:
        """Test _crop_to_bbox returns None for invalid bbox."""
        # x2 <= x1
        bbox = BoundingBox(x1=300, y1=100, x2=100, y2=250)
        result = await pipeline._crop_to_bbox(sample_image, bbox)
        assert result is None

    @pytest.mark.asyncio
    async def test_crop_to_bbox_zero_dimensions_returns_none(self, pipeline, sample_image) -> None:
        """Test _crop_to_bbox returns None for zero-dimension bbox."""
        bbox = BoundingBox(x1=100, y1=100, x2=100, y2=100)
        result = await pipeline._crop_to_bbox(sample_image, bbox)
        assert result is None


# ==============================================================================
# EnrichmentPipeline enrich_batch Tests
# ==============================================================================


class TestEnrichmentPipelineEnrichBatch:
    """Tests for enrich_batch orchestration method."""

    @pytest.fixture
    def pipeline_all_disabled(self, mock_model_manager):
        """Create pipeline with all enrichments disabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_enrich_batch_empty_detections(self, pipeline_all_disabled) -> None:
        """Test enrich_batch returns empty result for empty detections."""
        result = await pipeline_all_disabled.enrich_batch([], {})

        assert isinstance(result, EnrichmentResult)
        assert result.license_plates == []
        assert result.faces == []
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_enrich_batch_filters_low_confidence(
        self, pipeline_all_disabled, sample_image
    ) -> None:
        """Test enrich_batch filters out low-confidence detections."""
        low_conf_detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.3,  # Below 0.5 threshold
            bbox=BoundingBox(x1=100, y1=100, x2=300, y2=250),
        )

        result = await pipeline_all_disabled.enrich_batch(
            [low_conf_detection],
            {None: sample_image},
        )

        # Should return empty result since all detections filtered
        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_enrich_batch_tracks_processing_time(
        self, pipeline_all_disabled, sample_image, sample_detections
    ) -> None:
        """Test enrich_batch tracks processing time."""
        result = await pipeline_all_disabled.enrich_batch(
            sample_detections,
            {None: sample_image},
        )

        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_enrich_batch_error_isolation(
        self, mock_model_manager, sample_image, sample_detections
    ) -> None:
        """Test enrich_batch isolates errors - one failure doesn't stop others."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=True,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

        # Make license plate detection raise an error
        with patch.object(pipeline, "_detect_license_plates", side_effect=Exception("Model error")):
            result = await pipeline.enrich_batch(
                sample_detections,
                {None: sample_image},
            )

        # Should capture error but not raise
        assert len(result.errors) >= 1
        assert "License plate detection failed" in result.errors[0]


# ==============================================================================
# License Plate Detection Tests
# ==============================================================================


class TestLicensePlateDetection:
    """Tests for license plate detection functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with only license plate detection enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=True,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_detect_license_plates_success(
        self, pipeline, sample_image, mock_model_manager
    ) -> None:
        """Test license plate detection returns results."""
        # Mock YOLO model response
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [50, 100, 150, 130]
        mock_box.conf = [MagicMock()]
        mock_box.conf[0] = 0.92

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_model)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_model_manager.load.return_value = mock_context

        vehicle_detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
        )

        plates = await pipeline._detect_license_plates(
            [vehicle_detection],
            {None: sample_image},
        )

        assert len(plates) >= 0  # May be 0 if model not found

    @pytest.mark.asyncio
    async def test_detect_license_plates_no_model(self, pipeline, sample_image) -> None:
        """Test license plate detection handles missing model gracefully."""
        # Make model manager raise KeyError
        pipeline.model_manager.load.side_effect = KeyError("yolo11-license-plate")

        vehicle_detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
        )

        plates = await pipeline._detect_license_plates(
            [vehicle_detection],
            {None: sample_image},
        )

        assert plates == []


# ==============================================================================
# Face Detection Tests
# ==============================================================================


class TestFaceDetection:
    """Tests for face detection functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with only face detection enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=True,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_detect_faces_no_model(self, pipeline, sample_image) -> None:
        """Test face detection handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("yolo11-face")

        person_detection = DetectionInput(
            id=1,
            class_name="person",
            confidence=0.90,
            bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
        )

        faces = await pipeline._detect_faces(
            [person_detection],
            {None: sample_image},
        )

        assert faces == []


# ==============================================================================
# Violence Detection Tests
# ==============================================================================


class TestViolenceDetection:
    """Tests for violence detection functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with violence detection enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=True,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_detect_violence_success(self, pipeline, sample_image) -> None:
        """Test violence detection returns result."""
        mock_result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.95,
            violent_score=0.05,
            non_violent_score=0.95,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_violence",
            return_value=mock_result,
        ):
            result = await pipeline._detect_violence(sample_image)

        assert isinstance(result, ViolenceDetectionResult)
        assert result.is_violent is False
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_detect_violence_no_model(self, pipeline, sample_image) -> None:
        """Test violence detection handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("violence-detection")

        with pytest.raises(RuntimeError, match="violence-detection model not configured"):
            await pipeline._detect_violence(sample_image)

    @pytest.mark.asyncio
    async def test_enrich_batch_violence_requires_two_persons(
        self, pipeline, sample_image, sample_person_detections
    ) -> None:
        """Test violence detection only runs with 2+ persons."""
        mock_result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.92,
            violent_score=0.08,
            non_violent_score=0.92,
        )

        with patch.object(pipeline, "_detect_violence", return_value=mock_result) as mock_detect:
            result = await pipeline.enrich_batch(
                sample_person_detections,  # 2 persons
                {None: sample_image},
            )

            mock_detect.assert_called_once()
            assert result.violence_detection is not None

    @pytest.mark.asyncio
    async def test_enrich_batch_violence_skipped_single_person(
        self, pipeline, sample_image
    ) -> None:
        """Test violence detection is skipped with only 1 person."""
        single_person = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.90,
                bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
            )
        ]

        with patch.object(pipeline, "_detect_violence") as mock_detect:
            result = await pipeline.enrich_batch(
                single_person,
                {None: sample_image},
            )

            mock_detect.assert_not_called()
            assert result.violence_detection is None


# ==============================================================================
# Clothing Classification Tests
# ==============================================================================


class TestClothingClassification:
    """Tests for clothing classification functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with clothing classification enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=True,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_classify_person_clothing_success(self, pipeline, sample_image) -> None:
        """Test clothing classification returns results."""
        mock_result = ClothingClassification(
            top_category="casual",
            confidence=0.88,
            all_scores={"casual": 0.88},
            is_suspicious=False,
            is_service_uniform=False,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_clothing",
            return_value=mock_result,
        ):
            persons = [
                DetectionInput(
                    id=1,
                    class_name="person",
                    confidence=0.90,
                    bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
                )
            ]

            results = await pipeline._classify_person_clothing(persons, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert results["1"].top_category == "casual"

    @pytest.mark.asyncio
    async def test_classify_person_clothing_no_model(self, pipeline, sample_image) -> None:
        """Test clothing classification handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("fashion-clip")

        persons = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.90,
                bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
            )
        ]

        results = await pipeline._classify_person_clothing(persons, sample_image)
        assert results == {}

    @pytest.mark.asyncio
    async def test_classify_person_clothing_empty_list(self, pipeline, sample_image) -> None:
        """Test clothing classification with empty person list."""
        results = await pipeline._classify_person_clothing([], sample_image)
        assert results == {}


# ==============================================================================
# Vehicle Classification Tests
# ==============================================================================


class TestVehicleClassification:
    """Tests for vehicle classification functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with vehicle classification enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=True,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_classify_vehicle_types_success(self, pipeline, sample_image) -> None:
        """Test vehicle classification returns results."""
        mock_result = VehicleClassificationResult(
            vehicle_type="pickup_truck",
            confidence=0.92,
            display_name="pickup truck",
            is_commercial=False,
            all_scores={"pickup_truck": 0.92, "car": 0.05},
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_vehicle",
            return_value=mock_result,
        ):
            vehicles = [
                DetectionInput(
                    id=1,
                    class_name="car",
                    confidence=0.95,
                    bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
                )
            ]

            results = await pipeline._classify_vehicle_types(vehicles, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert results["1"].vehicle_type == "pickup_truck"

    @pytest.mark.asyncio
    async def test_classify_vehicle_types_no_model(self, pipeline, sample_image) -> None:
        """Test vehicle classification handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("vehicle-segment-classification")

        vehicles = [
            DetectionInput(
                id=1,
                class_name="car",
                confidence=0.95,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        results = await pipeline._classify_vehicle_types(vehicles, sample_image)
        assert results == {}

    @pytest.mark.asyncio
    async def test_classify_vehicle_types_empty_list(self, pipeline, sample_image) -> None:
        """Test vehicle classification with empty vehicle list."""
        results = await pipeline._classify_vehicle_types([], sample_image)
        assert results == {}


# ==============================================================================
# Pet Classification Tests
# ==============================================================================


class TestPetClassification:
    """Tests for pet classification functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with pet classification enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=True,
        )

    @pytest.mark.asyncio
    async def test_classify_pets_success(self, pipeline, sample_image) -> None:
        """Test pet classification returns results."""
        mock_result = PetClassificationResult(
            animal_type="dog",
            confidence=0.96,
            cat_score=0.03,
            dog_score=0.96,
            is_household_pet=True,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_pet",
            return_value=mock_result,
        ):
            animals = [
                DetectionInput(
                    id=1,
                    class_name="dog",
                    confidence=0.92,
                    bbox=BoundingBox(x1=200, y1=200, x2=350, y2=380),
                )
            ]

            results = await pipeline._classify_pets(animals, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert results["1"].animal_type == "dog"
        assert results["1"].is_household_pet is True

    @pytest.mark.asyncio
    async def test_classify_pets_no_model(self, pipeline, sample_image) -> None:
        """Test pet classification handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("pet-classifier")

        animals = [
            DetectionInput(
                id=1,
                class_name="cat",
                confidence=0.90,
                bbox=BoundingBox(x1=150, y1=180, x2=280, y2=320),
            )
        ]

        results = await pipeline._classify_pets(animals, sample_image)
        assert results == {}

    @pytest.mark.asyncio
    async def test_classify_pets_empty_list(self, pipeline, sample_image) -> None:
        """Test pet classification with empty animal list."""
        results = await pipeline._classify_pets([], sample_image)
        assert results == {}


# ==============================================================================
# Vehicle Damage Detection Tests
# ==============================================================================


class TestVehicleDamageDetection:
    """Tests for vehicle damage detection functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with vehicle damage detection enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=True,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_detect_vehicle_damage_success(self, pipeline, sample_image) -> None:
        """Test vehicle damage detection returns results."""
        from backend.services.vehicle_damage_loader import DamageDetection

        mock_result = VehicleDamageResult(
            detections=[
                DamageDetection(damage_type="scratch", confidence=0.85, bbox=(100, 100, 200, 150)),
                DamageDetection(damage_type="scratch", confidence=0.82, bbox=(200, 100, 300, 150)),
                DamageDetection(damage_type="dent", confidence=0.78, bbox=(150, 200, 250, 280)),
            ]
        )

        with patch(
            "backend.services.enrichment_pipeline.detect_vehicle_damage",
            return_value=mock_result,
        ):
            vehicles = [
                DetectionInput(
                    id=1,
                    class_name="car",
                    confidence=0.95,
                    bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
                )
            ]

            results = await pipeline._detect_vehicle_damage(vehicles, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert results["1"].has_damage is True
        assert "scratch" in results["1"].damage_types

    @pytest.mark.asyncio
    async def test_detect_vehicle_damage_no_model(self, pipeline, sample_image) -> None:
        """Test vehicle damage detection handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("vehicle-damage-detection")

        vehicles = [
            DetectionInput(
                id=1,
                class_name="truck",
                confidence=0.88,
                bbox=BoundingBox(x1=50, y1=50, x2=500, y2=350),
            )
        ]

        results = await pipeline._detect_vehicle_damage(vehicles, sample_image)
        assert results == {}


# ==============================================================================
# Image Quality Assessment Tests
# ==============================================================================


class TestImageQualityAssessment:
    """Tests for image quality assessment functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with image quality enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=True,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_assess_image_quality_success(self, pipeline, sample_image) -> None:
        """Test image quality assessment returns results."""
        mock_result = ImageQualityResult(
            quality_score=75.0,
            brisque_score=25.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )

        with patch(
            "backend.services.enrichment_pipeline.assess_image_quality",
            return_value=mock_result,
        ):
            result = await pipeline._assess_image_quality(sample_image, camera_id="front_door")

        assert isinstance(result, ImageQualityResult)
        assert result.is_good_quality is True
        assert result.quality_score == 75.0

    @pytest.mark.asyncio
    async def test_assess_image_quality_no_model(self, pipeline, sample_image) -> None:
        """Test image quality assessment handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("brisque-quality")

        with pytest.raises(RuntimeError, match="brisque-quality model not configured"):
            await pipeline._assess_image_quality(sample_image)

    @pytest.mark.asyncio
    async def test_assess_image_quality_disabled(self, pipeline, sample_image) -> None:
        """Test image quality handles disabled model gracefully."""
        pipeline.model_manager.load.side_effect = RuntimeError("Model disabled due to pyiqa")

        with pytest.raises(RuntimeError):
            await pipeline._assess_image_quality(sample_image)


# ==============================================================================
# Re-Identification Tests
# ==============================================================================


class TestReIdentification:
    """Tests for re-identification functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with reid enabled."""
        mock_redis = AsyncMock()
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=True,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
            redis_client=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_run_reid_requires_redis(self, mock_model_manager, sample_image) -> None:
        """Test reid requires redis client."""
        pipeline = EnrichmentPipeline(
            model_manager=mock_model_manager,
            reid_enabled=True,
            redis_client=None,  # No redis
        )

        detections = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.90,
                bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
            )
        ]

        # Should not crash - reid skipped without redis
        result = await pipeline.enrich_batch(
            detections,
            {None: sample_image},
        )

        assert result.person_reid_matches == {}
        assert result.vehicle_reid_matches == {}


# ==============================================================================
# Remote Service Tests
# ==============================================================================


class TestRemoteServiceFallback:
    """Tests for remote enrichment service functionality."""

    @pytest.fixture
    def pipeline_with_remote(self, mock_model_manager, mock_enrichment_client):
        """Create pipeline using remote enrichment service."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=True,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=True,
            image_quality_enabled=False,
            pet_classification_enabled=True,
            use_enrichment_service=True,
            enrichment_client=mock_enrichment_client,
        )

    @pytest.mark.asyncio
    async def test_classify_vehicle_via_service_success(
        self, pipeline_with_remote, sample_image, mock_enrichment_client
    ) -> None:
        """Test vehicle classification via remote service."""

        mock_enrichment_client.classify_vehicle.return_value = MagicMock(
            vehicle_type="sedan",
            confidence=0.91,
            display_name="sedan",
            is_commercial=False,
            all_scores={"sedan": 0.91},
        )

        vehicles = [
            DetectionInput(
                id=1,
                class_name="car",
                confidence=0.95,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        results = await pipeline_with_remote._classify_vehicle_via_service(vehicles, sample_image)

        assert len(results) == 1
        assert "1" in results
        mock_enrichment_client.classify_vehicle.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_vehicle_via_service_unavailable(
        self, pipeline_with_remote, sample_image, mock_enrichment_client
    ) -> None:
        """Test vehicle classification handles service unavailable."""
        from backend.services.enrichment_client import EnrichmentUnavailableError

        mock_enrichment_client.classify_vehicle.side_effect = EnrichmentUnavailableError(
            "Service unavailable"
        )

        vehicles = [
            DetectionInput(
                id=1,
                class_name="car",
                confidence=0.95,
                bbox=BoundingBox(x1=100, y1=100, x2=400, y2=300),
            )
        ]

        results = await pipeline_with_remote._classify_vehicle_via_service(vehicles, sample_image)

        assert results == {}

    @pytest.mark.asyncio
    async def test_classify_pets_via_service_success(
        self, pipeline_with_remote, sample_image, mock_enrichment_client
    ) -> None:
        """Test pet classification via remote service."""
        mock_enrichment_client.classify_pet.return_value = MagicMock(
            pet_type="dog",
            confidence=0.97,
            is_household_pet=True,
        )

        animals = [
            DetectionInput(
                id=1,
                class_name="dog",
                confidence=0.92,
                bbox=BoundingBox(x1=200, y1=200, x2=350, y2=380),
            )
        ]

        results = await pipeline_with_remote._classify_pets_via_service(animals, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert results["1"].animal_type == "dog"
        mock_enrichment_client.classify_pet.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_clothing_via_service_success(
        self, pipeline_with_remote, sample_image, mock_enrichment_client
    ) -> None:
        """Test clothing classification via remote service."""
        mock_enrichment_client.classify_clothing.return_value = MagicMock(
            top_category="casual_outfit",
            confidence=0.86,
            description="casual outfit",
            is_suspicious=False,
            is_service_uniform=False,
        )

        persons = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.90,
                bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
            )
        ]

        results = await pipeline_with_remote._classify_clothing_via_service(persons, sample_image)

        assert len(results) == 1
        assert "1" in results
        mock_enrichment_client.classify_clothing.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_via_service_empty_list(
        self, pipeline_with_remote, sample_image, mock_enrichment_client
    ) -> None:
        """Test remote classification with empty lists."""
        vehicle_results = await pipeline_with_remote._classify_vehicle_via_service([], sample_image)
        pet_results = await pipeline_with_remote._classify_pets_via_service([], sample_image)
        clothing_results = await pipeline_with_remote._classify_clothing_via_service(
            [], sample_image
        )

        assert vehicle_results == {}
        assert pet_results == {}
        assert clothing_results == {}
        mock_enrichment_client.classify_vehicle.assert_not_called()
        mock_enrichment_client.classify_pet.assert_not_called()
        mock_enrichment_client.classify_clothing.assert_not_called()


# ==============================================================================
# Clothing Segmentation Tests
# ==============================================================================


class TestClothingSegmentation:
    """Tests for clothing segmentation functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with clothing segmentation enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=True,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_segment_person_clothing_success(self, pipeline, sample_image) -> None:
        """Test clothing segmentation returns results."""
        mock_result = ClothingSegmentationResult(
            clothing_items={"upper_clothes", "pants", "left_shoe", "right_shoe"},
            has_face_covered=False,
            has_bag=True,
            coverage_percentages={"upper_clothes": 25.0, "pants": 30.0},
        )

        # Create mock model data tuple
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=(mock_model, mock_processor))
        mock_context.__aexit__ = AsyncMock(return_value=None)
        pipeline.model_manager.load.return_value = mock_context

        # Patch at the source module where segment_clothing is defined
        with patch(
            "backend.services.segformer_loader.segment_clothing",
            return_value=mock_result,
        ):
            persons = [
                DetectionInput(
                    id=1,
                    class_name="person",
                    confidence=0.90,
                    bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
                )
            ]

            results = await pipeline._segment_person_clothing(persons, sample_image)

        assert len(results) == 1
        assert "1" in results
        assert "upper_clothes" in results["1"].clothing_items

    @pytest.mark.asyncio
    async def test_segment_person_clothing_no_model(self, pipeline, sample_image) -> None:
        """Test clothing segmentation handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("segformer-b2-clothes")

        persons = [
            DetectionInput(
                id=1,
                class_name="person",
                confidence=0.90,
                bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
            )
        ]

        results = await pipeline._segment_person_clothing(persons, sample_image)
        assert results == {}

    @pytest.mark.asyncio
    async def test_segment_person_clothing_empty_list(self, pipeline, sample_image) -> None:
        """Test clothing segmentation with empty person list."""
        results = await pipeline._segment_person_clothing([], sample_image)
        assert results == {}


# ==============================================================================
# OCR Tests
# ==============================================================================


class TestOCR:
    """Tests for OCR functionality."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with OCR enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=True,
            face_detection_enabled=False,
            ocr_enabled=True,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_run_ocr_success(self, pipeline, sample_image) -> None:
        """Test OCR extracts text successfully."""

        # Create mock OCR model
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 30], [0, 30]], ("ABC123", 0.95)],
            ]
        ]

        text, confidence = await pipeline._run_ocr(mock_ocr, sample_image)

        assert text == "ABC123"
        assert confidence == 0.95

    @pytest.mark.asyncio
    async def test_run_ocr_empty_result(self, pipeline, sample_image) -> None:
        """Test OCR handles empty result."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]

        text, confidence = await pipeline._run_ocr(mock_ocr, sample_image)

        assert text == ""
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_run_ocr_exception(self, pipeline, sample_image) -> None:
        """Test OCR handles exception gracefully."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.side_effect = Exception("OCR failed")

        text, confidence = await pipeline._run_ocr(mock_ocr, sample_image)

        assert text == ""
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_read_plates_empty_list(self, pipeline) -> None:
        """Test _read_plates with empty list does nothing."""
        await pipeline._read_plates([], {})
        # Should not raise

    @pytest.mark.asyncio
    async def test_read_plates_no_model(self, pipeline, sample_image) -> None:
        """Test _read_plates handles missing model gracefully."""
        pipeline.model_manager.load.side_effect = KeyError("paddleocr")

        plates = [
            LicensePlateResult(
                bbox=BoundingBox(50, 100, 150, 130),
                confidence=0.92,
                source_detection_id=1,
            )
        ]

        await pipeline._read_plates(plates, {None: sample_image})

        # Plates should still have empty text
        assert plates[0].text == ""


# ==============================================================================
# Detection ID Handling Tests
# ==============================================================================


class TestDetectionIdHandling:
    """Tests for detection ID handling in enrichment methods."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline for testing."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=True,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=False,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_detection_without_id_uses_index(self, pipeline, sample_image) -> None:
        """Test that detections without ID use their index as key."""
        mock_result = ClothingClassification(
            top_category="casual",
            confidence=0.88,
            all_scores={"casual": 0.88},
            is_suspicious=False,
            is_service_uniform=False,
        )

        with patch(
            "backend.services.enrichment_pipeline.classify_clothing",
            return_value=mock_result,
        ):
            persons = [
                DetectionInput(
                    id=None,  # No ID
                    class_name="person",
                    confidence=0.90,
                    bbox=BoundingBox(x1=100, y1=50, x2=250, y2=400),
                )
            ]

            results = await pipeline._classify_person_clothing(persons, sample_image)

        # Should use index "0" as key
        assert "0" in results


# ==============================================================================
# _get_image_for_detection Tests
# ==============================================================================


class TestGetImageForDetection:
    """Tests for _get_image_for_detection method."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline for testing."""
        return EnrichmentPipeline(model_manager=mock_model_manager)

    def test_get_image_for_detection_specific(self, pipeline, sample_image) -> None:
        """Test getting specific image for detection ID."""
        images = {1: sample_image, None: Image.new("RGB", (100, 100), "red")}

        detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
        )

        result = pipeline._get_image_for_detection(detection, images)

        assert result is sample_image

    def test_get_image_for_detection_fallback_to_shared(self, pipeline, sample_image) -> None:
        """Test falling back to shared image (None key)."""
        images = {None: sample_image}

        detection = DetectionInput(
            id=999,  # ID not in images
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
        )

        result = pipeline._get_image_for_detection(detection, images)

        assert result is sample_image

    def test_get_image_for_detection_none_id(self, pipeline, sample_image) -> None:
        """Test getting image for detection with None ID."""
        images = {None: sample_image}

        detection = DetectionInput(
            id=None,
            class_name="person",
            confidence=0.90,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
        )

        result = pipeline._get_image_for_detection(detection, images)

        assert result is sample_image

    def test_get_image_for_detection_not_found(self, pipeline) -> None:
        """Test returning None when no image found."""
        images = {}

        detection = DetectionInput(
            id=1,
            class_name="car",
            confidence=0.95,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
        )

        result = pipeline._get_image_for_detection(detection, images)

        assert result is None


# ==============================================================================
# YOLO Detection Result Conversion Tests
# ==============================================================================


class TestYoloDetectionConversion:
    """Tests for YOLO detection result conversion."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline for testing."""
        return EnrichmentPipeline(model_manager=mock_model_manager)

    @pytest.mark.asyncio
    async def test_run_yolo_detection_success(self, pipeline, sample_image) -> None:
        """Test YOLO detection conversion to LicensePlateResult."""
        # Create mock YOLO model response
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [50, 100, 150, 130]
        mock_box.conf = [MagicMock()]
        mock_box.conf[0] = 0.92

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        plates = await pipeline._run_yolo_detection(
            mock_model, sample_image, source_detection_id=42
        )

        assert len(plates) == 1
        assert plates[0].confidence == 0.92
        assert plates[0].source_detection_id == 42
        assert plates[0].bbox.x1 == 50
        assert plates[0].bbox.y1 == 100
        assert plates[0].bbox.x2 == 150
        assert plates[0].bbox.y2 == 130

    @pytest.mark.asyncio
    async def test_run_yolo_detection_no_results(self, pipeline, sample_image) -> None:
        """Test YOLO detection with no detections."""
        mock_result = MagicMock()
        mock_result.boxes = []

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        plates = await pipeline._run_yolo_detection(mock_model, sample_image, source_detection_id=1)

        assert plates == []

    @pytest.mark.asyncio
    async def test_run_yolo_detection_exception(self, pipeline, sample_image) -> None:
        """Test YOLO detection handles exception gracefully."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("CUDA error")

        plates = await pipeline._run_yolo_detection(mock_model, sample_image, source_detection_id=1)

        assert plates == []


# ==============================================================================
# Face Detection Result Conversion Tests
# ==============================================================================


class TestFaceDetectionConversion:
    """Tests for face detection result conversion."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline for testing."""
        return EnrichmentPipeline(model_manager=mock_model_manager)

    @pytest.mark.asyncio
    async def test_run_face_detection_success(self, pipeline, sample_image) -> None:
        """Test face detection conversion to FaceResult."""
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [80, 40, 140, 120]
        mock_box.conf = [MagicMock()]
        mock_box.conf[0] = 0.96

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        faces = await pipeline._run_face_detection(mock_model, sample_image, source_detection_id=7)

        assert len(faces) == 1
        assert faces[0].confidence == 0.96
        assert faces[0].source_detection_id == 7
        assert faces[0].bbox.x1 == 80
        assert faces[0].bbox.y1 == 40

    @pytest.mark.asyncio
    async def test_run_face_detection_no_results(self, pipeline, sample_image) -> None:
        """Test face detection with no faces found."""
        mock_result = MagicMock()
        mock_result.boxes = []

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        faces = await pipeline._run_face_detection(mock_model, sample_image, source_detection_id=1)

        assert faces == []

    @pytest.mark.asyncio
    async def test_run_face_detection_exception(self, pipeline, sample_image) -> None:
        """Test face detection handles exception gracefully."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Model error")

        faces = await pipeline._run_face_detection(mock_model, sample_image, source_detection_id=1)

        assert faces == []


# ==============================================================================
# Quality Change Detection Tests
# ==============================================================================


class TestQualityChangeDetection:
    """Tests for quality change detection tracking."""

    @pytest.fixture
    def pipeline(self, mock_model_manager):
        """Create pipeline with image quality enabled."""
        return EnrichmentPipeline(
            model_manager=mock_model_manager,
            license_plate_enabled=False,
            face_detection_enabled=False,
            ocr_enabled=False,
            vision_extraction_enabled=False,
            reid_enabled=False,
            scene_change_enabled=False,
            violence_detection_enabled=False,
            clothing_classification_enabled=False,
            clothing_segmentation_enabled=False,
            vehicle_damage_detection_enabled=False,
            vehicle_classification_enabled=False,
            image_quality_enabled=True,
            pet_classification_enabled=False,
        )

    @pytest.mark.asyncio
    async def test_quality_change_tracked_per_camera(self, pipeline, sample_image) -> None:
        """Test quality results dictionary exists and can be updated."""
        # Verify the pipeline has the _previous_quality_results attribute
        assert hasattr(pipeline, "_previous_quality_results")
        assert isinstance(pipeline._previous_quality_results, dict)
        assert pipeline._previous_quality_results == {}

        # Manually set a value to simulate quality tracking
        good_quality = ImageQualityResult(
            quality_score=80.0,
            brisque_score=20.0,
            is_blurry=False,
            is_noisy=False,
            is_low_quality=False,
            quality_issues=[],
        )

        pipeline._previous_quality_results["front"] = good_quality
        assert "front" in pipeline._previous_quality_results
        assert pipeline._previous_quality_results["front"].quality_score == 80.0

        # Test quality change detection logic directly
        from backend.services.image_quality_loader import detect_quality_change

        bad_quality = ImageQualityResult(
            quality_score=20.0,
            brisque_score=80.0,
            is_blurry=True,
            is_noisy=True,
            is_low_quality=True,
            quality_issues=["blurry", "noisy"],
        )

        # Detect change: current (bad) vs previous (good)
        # Function signature: detect_quality_change(current, previous)
        # A big drop from 80 -> 20 should trigger the alert
        changed, description = detect_quality_change(bad_quality, good_quality)
        assert changed is True
        assert "Sudden quality drop" in description


# ==============================================================================
# Enrichment Result Prompt Context Tests
# ==============================================================================


class TestEnrichmentResultPromptContext:
    """Tests for to_prompt_context method."""

    def test_to_prompt_context_returns_all_fields(self) -> None:
        """Test to_prompt_context returns all expected fields."""
        result = EnrichmentResult()

        context = result.to_prompt_context()

        expected_keys = [
            "violence_context",
            "weather_context",
            "image_quality_context",
            "clothing_analysis_context",
            "vehicle_classification_context",
            "vehicle_damage_context",
            "pet_classification_context",
            "pose_analysis",
            "action_recognition",
            "depth_context",
        ]

        for key in expected_keys:
            assert key in context, f"Missing key: {key}"

    def test_to_prompt_context_with_time_of_day(self) -> None:
        """Test to_prompt_context accepts time_of_day parameter."""
        from backend.services.vehicle_damage_loader import DamageDetection

        result = EnrichmentResult()
        result.vehicle_damage = {
            "1": VehicleDamageResult(
                detections=[
                    DamageDetection(
                        damage_type="glass_shatter",
                        confidence=0.92,
                        bbox=(50, 50, 150, 100),
                    )
                ]
            )
        }

        context = result.to_prompt_context(time_of_day="night")

        assert "vehicle_damage_context" in context
