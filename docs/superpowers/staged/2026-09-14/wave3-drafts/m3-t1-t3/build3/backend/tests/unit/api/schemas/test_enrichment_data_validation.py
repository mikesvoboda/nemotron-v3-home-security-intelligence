"""Unit tests for enrichment_data JSONB field schema validation.

Tests validate that the EnrichmentDataSchema correctly validates, coerces,
and handles legacy enrichment data formats from the database.

TDD: These tests verify schema validation behavior for the enrichment pipeline.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from backend.api.schemas.enrichment_data import (
    ClothingClassificationData,
    ClothingSegmentationData,
    EnrichmentDataSchema,
    FaceItem,
    ImageQualityData,
    LicensePlateItem,
    PetClassificationData,
    VehicleClassificationData,
    VehicleDamageData,
    ViolenceDetectionData,
    coerce_enrichment_data,
    validate_enrichment_data,
)


class TestLicensePlateItemSchema:
    """Tests for LicensePlateItem schema validation."""

    def test_valid_license_plate(self) -> None:
        """Test validation of valid license plate data."""
        data = {
            "bbox": [100.0, 200.0, 300.0, 250.0],
            "text": "ABC-1234",
            "confidence": 0.92,
            "ocr_confidence": 0.88,
            "source_detection_id": 1,
        }
        item = LicensePlateItem.model_validate(data)

        assert item.bbox == [100.0, 200.0, 300.0, 250.0]
        assert item.text == "ABC-1234"
        assert item.confidence == 0.92
        assert item.ocr_confidence == 0.88
        assert item.source_detection_id == 1

    def test_license_plate_confidence_clamping(self) -> None:
        """Test that confidence values are clamped to valid range."""
        # Value over 1.0 should be clamped
        data = {"confidence": 1.5, "ocr_confidence": 2.0}
        item = LicensePlateItem.model_validate(data)
        assert item.confidence == 1.0
        assert item.ocr_confidence == 1.0

        # Negative values should be clamped to 0
        data = {"confidence": -0.5, "ocr_confidence": -1.0}
        item = LicensePlateItem.model_validate(data)
        assert item.confidence == 0.0
        assert item.ocr_confidence == 0.0

    def test_license_plate_invalid_confidence_becomes_none(self) -> None:
        """Test that non-numeric confidence becomes None."""
        data = {"confidence": "invalid", "ocr_confidence": [1, 2, 3]}
        item = LicensePlateItem.model_validate(data)
        assert item.confidence is None
        assert item.ocr_confidence is None

    def test_license_plate_allows_extra_fields(self) -> None:
        """Test that extra fields are preserved for forward compatibility."""
        data = {
            "text": "XYZ-789",
            "confidence": 0.9,
            "future_field": "some_value",
            "another_new_field": 123,
        }
        item = LicensePlateItem.model_validate(data)
        assert item.text == "XYZ-789"
        # Extra fields are allowed due to model_config extra="allow"


class TestFaceItemSchema:
    """Tests for FaceItem schema validation."""

    def test_valid_face_item(self) -> None:
        """Test validation of valid face detection data."""
        data = {
            "bbox": [150.0, 50.0, 200.0, 120.0],
            "confidence": 0.95,
            "source_detection_id": 2,
        }
        item = FaceItem.model_validate(data)

        assert item.bbox == [150.0, 50.0, 200.0, 120.0]
        assert item.confidence == 0.95
        assert item.source_detection_id == 2

    def test_face_confidence_clamping(self) -> None:
        """Test that face confidence is clamped to valid range."""
        data = {"confidence": 1.1}
        item = FaceItem.model_validate(data)
        assert item.confidence == 1.0

        data = {"confidence": -0.1}
        item = FaceItem.model_validate(data)
        assert item.confidence == 0.0


class TestViolenceDetectionSchema:
    """Tests for ViolenceDetectionData schema validation."""

    def test_valid_violence_detection(self) -> None:
        """Test validation of valid violence detection data."""
        data = {
            "is_violent": False,
            "confidence": 0.12,
            "predicted_class": "normal",
        }
        result = ViolenceDetectionData.model_validate(data)

        assert result.is_violent is False
        assert result.confidence == 0.12
        assert result.predicted_class == "normal"

    def test_violence_is_violent_coercion(self) -> None:
        """Test that is_violent is coerced to boolean."""
        # String "true"
        data = {"is_violent": "true"}
        result = ViolenceDetectionData.model_validate(data)
        assert result.is_violent is True

        # String "false" (not in true values)
        data = {"is_violent": "false"}
        result = ViolenceDetectionData.model_validate(data)
        assert result.is_violent is False

        # Integer 1
        data = {"is_violent": 1}
        result = ViolenceDetectionData.model_validate(data)
        assert result.is_violent is True

        # None becomes False
        data = {"is_violent": None}
        result = ViolenceDetectionData.model_validate(data)
        assert result.is_violent is False


class TestVehicleClassificationSchema:
    """Tests for VehicleClassificationData schema validation."""

    def test_valid_vehicle_classification(self) -> None:
        """Test validation of valid vehicle classification data."""
        data = {
            "vehicle_type": "sedan",
            "confidence": 0.91,
            "display_name": "Sedan",
            "is_commercial": False,
            "all_scores": {"sedan": 0.91, "suv": 0.05, "truck": 0.02},
        }
        result = VehicleClassificationData.model_validate(data)

        assert result.vehicle_type == "sedan"
        assert result.confidence == 0.91
        assert result.display_name == "Sedan"
        assert result.is_commercial is False
        assert result.all_scores == {"sedan": 0.91, "suv": 0.05, "truck": 0.02}


class TestImageQualitySchema:
    """Tests for ImageQualityData schema validation."""

    def test_valid_image_quality(self) -> None:
        """Test validation of valid image quality data."""
        data = {
            "quality_score": 85.0,
            "is_blurry": False,
            "is_low_quality": False,
            "is_good_quality": True,
            "quality_issues": [],
        }
        result = ImageQualityData.model_validate(data)

        assert result.quality_score == 85.0
        assert result.is_blurry is False
        assert result.is_low_quality is False
        assert result.is_good_quality is True
        assert result.quality_issues == []

    def test_quality_score_clamping(self) -> None:
        """Test that quality score is clamped to 0-100."""
        # Over 100
        data = {"quality_score": 150.0}
        result = ImageQualityData.model_validate(data)
        assert result.quality_score == 100.0

        # Negative
        data = {"quality_score": -10.0}
        result = ImageQualityData.model_validate(data)
        assert result.quality_score == 0.0


class TestPetClassificationSchema:
    """Tests for PetClassificationData schema validation."""

    def test_valid_pet_classification(self) -> None:
        """Test validation of valid pet classification data."""
        data = {
            "animal_type": "dog",
            "confidence": 0.94,
            "is_household_pet": True,
        }
        result = PetClassificationData.model_validate(data)

        assert result.animal_type == "dog"
        assert result.confidence == 0.94
        assert result.is_household_pet is True


class TestEnrichmentDataSchema:
    """Tests for the complete EnrichmentDataSchema."""

    def test_valid_complete_enrichment_data(self) -> None:
        """Test validation of complete valid enrichment data."""
        data = {
            "license_plates": [
                {
                    "bbox": [100.0, 200.0, 300.0, 250.0],
                    "text": "ABC-1234",
                    "confidence": 0.92,
                    "ocr_confidence": 0.88,
                }
            ],
            "faces": [{"bbox": [150.0, 50.0, 200.0, 120.0], "confidence": 0.95}],
            "violence_detection": {
                "is_violent": False,
                "confidence": 0.12,
                "predicted_class": "normal",
            },
            "vehicle_classifications": {
                "1": {
                    "vehicle_type": "sedan",
                    "confidence": 0.91,
                    "is_commercial": False,
                }
            },
            "image_quality": {
                "quality_score": 85.0,
                "is_blurry": False,
                "is_low_quality": False,
            },
            "errors": [],
            "processing_time_ms": 125.5,
        }
        schema = EnrichmentDataSchema.model_validate(data)

        assert len(schema.license_plates) == 1
        assert schema.license_plates[0].text == "ABC-1234"
        assert len(schema.faces) == 1
        assert schema.faces[0].confidence == 0.95
        assert schema.violence_detection.is_violent is False
        assert "1" in schema.vehicle_classifications
        assert schema.vehicle_classifications["1"].vehicle_type == "sedan"
        assert schema.image_quality.quality_score == 85.0
        assert schema.errors == []
        assert schema.processing_time_ms == 125.5

    def test_empty_enrichment_data(self) -> None:
        """Test validation of empty enrichment data dict."""
        data: dict[str, Any] = {}
        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.license_plates is None
        assert schema.faces is None
        assert schema.violence_detection is None
        assert schema.processing_time_ms is None

    def test_partial_enrichment_data(self) -> None:
        """Test validation with only some fields present."""
        data = {
            "license_plates": [{"text": "XYZ-999", "confidence": 0.85}],
            "processing_time_ms": 50.0,
        }
        schema = EnrichmentDataSchema.model_validate(data)

        assert len(schema.license_plates) == 1
        assert schema.license_plates[0].text == "XYZ-999"
        assert schema.faces is None
        assert schema.processing_time_ms == 50.0

    def test_extra_fields_preserved(self) -> None:
        """Test that unknown extra fields are allowed."""
        data = {
            "license_plates": [],
            "future_model_output": {"new_field": "value"},
            "another_future_field": 123,
        }
        # Should not raise
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.license_plates == []


class TestLegacyDataHandling:
    """Tests for handling legacy enrichment data formats."""

    def test_legacy_vehicle_format_conversion(self) -> None:
        """Test conversion of legacy 'vehicle' dict to vehicle_classifications."""
        legacy_data = {
            "vehicle": {
                "type": "sedan",
                "color": "blue",
                "confidence": 0.92,
            }
        }
        schema = EnrichmentDataSchema.model_validate(legacy_data)

        assert schema.vehicle_classifications is not None
        assert "legacy" in schema.vehicle_classifications
        assert schema.vehicle_classifications["legacy"].vehicle_type == "sedan"
        assert schema.vehicle_classifications["legacy"].confidence == 0.92

    def test_legacy_pet_format_conversion(self) -> None:
        """Test conversion of legacy 'pet' dict to pet_classifications."""
        legacy_data = {
            "pet": {
                "type": "dog",
                "breed": "labrador",
                "confidence": 0.88,
            }
        }
        schema = EnrichmentDataSchema.model_validate(legacy_data)

        assert schema.pet_classifications is not None
        assert "legacy" in schema.pet_classifications
        assert schema.pet_classifications["legacy"].animal_type == "dog"
        assert schema.pet_classifications["legacy"].confidence == 0.88

    def test_legacy_license_plate_singular_conversion(self) -> None:
        """Test conversion of legacy singular 'license_plate' to list."""
        legacy_data = {
            "license_plate": {
                "text": "ABC123",
                "confidence": 0.91,
            }
        }
        schema = EnrichmentDataSchema.model_validate(legacy_data)

        assert schema.license_plates is not None
        assert len(schema.license_plates) == 1
        assert schema.license_plates[0].text == "ABC123"
        assert schema.license_plates[0].confidence == 0.91

    def test_mixed_legacy_and_new_format(self) -> None:
        """Test that new format takes precedence over legacy."""
        data = {
            # New format
            "vehicle_classifications": {"1": {"vehicle_type": "suv", "confidence": 0.95}},
            # Legacy format (should be ignored since new format exists)
            "vehicle": {"type": "sedan", "confidence": 0.80},
        }
        schema = EnrichmentDataSchema.model_validate(data)

        # New format should be used, not converted from legacy
        assert "1" in schema.vehicle_classifications
        assert schema.vehicle_classifications["1"].vehicle_type == "suv"


class TestValidateEnrichmentDataFunction:
    """Tests for the validate_enrichment_data helper function."""

    def test_validate_none_data(self) -> None:
        """Test validation of None data."""
        result = validate_enrichment_data(None)

        assert result.is_valid is True
        assert result.data is None
        assert result.warnings == []
        assert result.errors == []

    def test_validate_valid_data(self) -> None:
        """Test validation of valid data."""
        data = {
            "license_plates": [{"text": "ABC-123", "confidence": 0.9}],
            "processing_time_ms": 100.0,
        }
        result = validate_enrichment_data(data)

        assert result.is_valid is True
        assert result.data is not None
        assert "license_plates" in result.data
        assert result.errors == []

    def test_validate_non_dict_data(self) -> None:
        """Test validation of non-dict data returns error."""
        result = validate_enrichment_data("not a dict")  # type: ignore

        assert result.is_valid is False
        assert result.data is None
        assert "must be a dictionary" in result.errors[0]

    def test_validate_with_unknown_fields(self) -> None:
        """Test that unknown fields are preserved for forward compatibility."""
        data = {
            "license_plates": [],
            "completely_unknown_field": {"nested": "data"},
        }
        result = validate_enrichment_data(data)

        assert result.is_valid is True
        assert result.data is not None
        # Unknown field should be preserved (extra="allow" in schema)
        assert "completely_unknown_field" in result.data
        assert result.data["completely_unknown_field"] == {"nested": "data"}

    def test_validate_strict_mode(self) -> None:
        """Test strict mode validation."""
        # Valid data in strict mode
        valid_data = {"processing_time_ms": 100.0}
        result = validate_enrichment_data(valid_data, strict=True)
        assert result.is_valid is True

    def test_validate_non_strict_preserves_original(self) -> None:
        """Test non-strict mode preserves original data on validation errors."""
        # Even with some coercion issues, non-strict should return data
        data = {"processing_time_ms": "not_a_number"}  # Invalid but won't raise
        result = validate_enrichment_data(data, strict=False)

        # Should be valid in non-strict mode (original preserved)
        assert result.is_valid is True


class TestCoerceEnrichmentDataFunction:
    """Tests for the coerce_enrichment_data convenience function."""

    def test_coerce_none(self) -> None:
        """Test coercing None returns None."""
        result = coerce_enrichment_data(None)
        assert result is None

    def test_coerce_valid_data(self) -> None:
        """Test coercing valid data returns validated data."""
        data = {
            "license_plates": [{"text": "TEST-123", "confidence": 0.8}],
        }
        result = coerce_enrichment_data(data)

        assert result is not None
        assert "license_plates" in result

    def test_coerce_clamps_values(self) -> None:
        """Test that coercion clamps out-of-range values."""
        data = {
            "license_plates": [{"confidence": 1.5}],  # Should be clamped to 1.0
            "image_quality": {"quality_score": 150.0},  # Should be clamped to 100.0
        }
        result = coerce_enrichment_data(data)

        assert result is not None
        assert result["license_plates"][0]["confidence"] == 1.0
        assert result["image_quality"]["quality_score"] == 100.0


class TestDetectionModelValidation:
    """Tests for Detection model enrichment validation methods."""

    @pytest.mark.asyncio
    async def test_validate_enrichment_data_method(self) -> None:
        """Test Detection.validate_enrichment_data() method."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id="test-camera",
            file_path="/test/image.jpg",
            detected_at=datetime.now(UTC),
            enrichment_data={
                "license_plates": [{"text": "ABC-123", "confidence": 0.9}],
            },
        )

        is_valid, _messages = detection.validate_enrichment_data()
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_enrichment_data_with_none(self) -> None:
        """Test validation when enrichment_data is None."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id="test-camera",
            file_path="/test/image.jpg",
            detected_at=datetime.now(UTC),
            enrichment_data=None,
        )

        is_valid, messages = detection.validate_enrichment_data()
        assert is_valid is True
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_validated_enrichment_data(self) -> None:
        """Test Detection.get_validated_enrichment_data() method."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id="test-camera",
            file_path="/test/image.jpg",
            detected_at=datetime.now(UTC),
            enrichment_data={
                "license_plates": [{"text": "XYZ-789", "confidence": 1.2}],  # Out of range
            },
        )

        validated = detection.get_validated_enrichment_data()
        assert validated is not None
        # Confidence should be clamped to 1.0
        assert validated["license_plates"][0]["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_set_enrichment_data_validated(self) -> None:
        """Test Detection.set_enrichment_data_validated() method."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id="test-camera",
            file_path="/test/image.jpg",
            detected_at=datetime.now(UTC),
        )

        data = {
            "license_plates": [{"text": "NEW-123", "confidence": 0.95}],
        }
        success, _warnings = detection.set_enrichment_data_validated(data)

        assert success is True
        assert detection.enrichment_data is not None
        assert detection.enrichment_data["license_plates"][0]["text"] == "NEW-123"

    @pytest.mark.asyncio
    async def test_set_enrichment_data_validated_strict(self) -> None:
        """Test strict validation mode in set_enrichment_data_validated()."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id="test-camera",
            file_path="/test/image.jpg",
            detected_at=datetime.now(UTC),
        )

        # Valid data should succeed in strict mode
        valid_data = {"processing_time_ms": 50.0}
        success, _warnings = detection.set_enrichment_data_validated(valid_data, strict=True)
        assert success is True


class TestClothingEnrichmentSchemas:
    """Tests for clothing enrichment data schemas."""

    def test_valid_clothing_classification(self) -> None:
        """Test validation of clothing classification data."""
        data = {
            "top_category": "red t-shirt",
            "confidence": 0.87,
            "all_scores": {},
            "is_suspicious": False,
            "is_service_uniform": False,
            "raw_description": "red t-shirt, blue jeans",
        }
        result = ClothingClassificationData.model_validate(data)

        assert result.top_category == "red t-shirt"
        assert result.confidence == 0.87
        assert result.is_suspicious is False
        assert result.raw_description == "red t-shirt, blue jeans"

    def test_valid_clothing_segmentation(self) -> None:
        """Test validation of clothing segmentation data."""
        data = {
            "clothing_items": ["upper_clothes", "pants"],
            "has_face_covered": False,
            "has_bag": True,
        }
        result = ClothingSegmentationData.model_validate(data)

        assert result.clothing_items == ["upper_clothes", "pants"]
        assert result.has_face_covered is False
        assert result.has_bag is True


class TestVehicleDamageSchema:
    """Tests for vehicle damage enrichment data schema."""

    def test_valid_vehicle_damage(self) -> None:
        """Test validation of vehicle damage data."""
        data = {
            "has_damage": True,
            "damage_types": ["dent", "scratch"],
            "confidence": 0.85,
        }
        result = VehicleDamageData.model_validate(data)

        assert result.has_damage is True
        assert result.damage_types == ["dent", "scratch"]
        assert result.confidence == 0.85

    def test_vehicle_damage_has_damage_coercion(self) -> None:
        """Test that has_damage is coerced to boolean."""
        data = {"has_damage": "yes"}
        result = VehicleDamageData.model_validate(data)
        assert result.has_damage is True

        data = {"has_damage": 0}
        result = VehicleDamageData.model_validate(data)
        assert result.has_damage is False


class TestProcessingTimeValidation:
    """Tests for processing_time_ms field validation."""

    def test_valid_processing_time(self) -> None:
        """Test validation of valid processing time."""
        data = {"processing_time_ms": 125.5}
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.processing_time_ms == 125.5

    def test_negative_processing_time_clamped(self) -> None:
        """Test that negative processing time is clamped to 0."""
        data = {"processing_time_ms": -50.0}
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.processing_time_ms == 0.0

    def test_invalid_processing_time_becomes_none(self) -> None:
        """Test that invalid processing time becomes None."""
        data = {"processing_time_ms": "invalid"}
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.processing_time_ms is None


class TestErrorsFieldValidation:
    """Tests for errors field validation."""

    def test_valid_errors_list(self) -> None:
        """Test validation of valid errors list."""
        data = {"errors": ["Error 1", "Error 2"]}
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.errors == ["Error 1", "Error 2"]

    def test_errors_coerced_to_strings(self) -> None:
        """Test that error items are coerced to strings."""
        data = {"errors": [123, {"key": "value"}, None]}
        schema = EnrichmentDataSchema.model_validate(data)
        assert all(isinstance(e, str) for e in schema.errors)

    def test_single_error_becomes_list(self) -> None:
        """Test that single error value becomes list."""
        data = {"errors": "Single error message"}
        schema = EnrichmentDataSchema.model_validate(data)
        assert schema.errors == ["Single error message"]


class TestQualityChangeFields:
    """Tests for quality change detection fields."""

    def test_quality_change_fields(self) -> None:
        """Test validation of quality change detection fields."""
        data = {
            "quality_change_detected": True,
            "quality_change_description": "Camera moved or obstructed",
        }
        schema = EnrichmentDataSchema.model_validate(data)

        assert schema.quality_change_detected is True
        assert schema.quality_change_description == "Camera moved or obstructed"
