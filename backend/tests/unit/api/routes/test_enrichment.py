"""Unit tests for enrichment API routes.

Tests the detection and event enrichment endpoints for structured
vision model results.

TDD: These tests verify the enrichment transformation logic and schema validation.
"""

from datetime import UTC, datetime
from typing import Any

import pytest


@pytest.fixture
def sample_enrichment_data() -> dict[str, Any]:
    """Sample enrichment data as stored in the database."""
    return {
        "license_plates": [
            {
                "bbox": [100.0, 200.0, 300.0, 250.0],
                "text": "ABC-1234",
                "confidence": 0.92,
                "ocr_confidence": 0.88,
                "source_detection_id": 1,
            }
        ],
        "faces": [
            {
                "bbox": [150.0, 50.0, 200.0, 120.0],
                "confidence": 0.95,
                "source_detection_id": 1,
            }
        ],
        "violence_detection": {
            "is_violent": False,
            "confidence": 0.12,
            "predicted_class": "normal",
        },
        "vehicle_classifications": {
            "1": {
                "vehicle_type": "sedan",
                "confidence": 0.91,
                "display_name": "Sedan",
                "is_commercial": False,
                "all_scores": {"sedan": 0.91, "suv": 0.05},
            }
        },
        "vehicle_damage": {},
        "image_quality": {
            "quality_score": 85.0,
            "is_blurry": False,
            "is_low_quality": False,
            "is_good_quality": True,
            "quality_issues": [],
        },
        "quality_change_detected": False,
        "quality_change_description": "",
        "errors": [],
        "processing_time_ms": 125.5,
    }


@pytest.fixture
def sample_clothing_enrichment() -> dict[str, Any]:
    """Sample clothing classification enrichment data."""
    return {
        "clothing_classifications": {
            "1": {
                "top_category": "red t-shirt",
                "confidence": 0.87,
                "all_scores": {},
                "is_suspicious": False,
                "is_service_uniform": False,
                "raw_description": "red t-shirt, blue jeans",
            }
        },
        "clothing_segmentation": {
            "1": {
                "clothing_items": ["upper_clothes", "pants"],
                "has_face_covered": False,
                "has_bag": False,
            }
        },
    }


class TestTransformEnrichmentData:
    """Tests for _transform_enrichment_data helper function."""

    def test_transform_enrichment_data_full(self, sample_enrichment_data: dict[str, Any]) -> None:
        """Test transformation of full enrichment data."""
        from backend.api.routes.detections import _transform_enrichment_data

        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)
        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=sample_enrichment_data,
            detected_at=detected_at,
        )

        # Verify structure
        assert result["detection_id"] == 1
        assert result["enriched_at"] == detected_at

        # Verify license plate data
        assert result["license_plate"]["detected"] is True
        assert result["license_plate"]["text"] == "ABC-1234"
        assert result["license_plate"]["confidence"] == 0.92
        assert result["license_plate"]["ocr_confidence"] == 0.88
        assert result["license_plate"]["bbox"] == [100.0, 200.0, 300.0, 250.0]

        # Verify face data
        assert result["face"]["detected"] is True
        assert result["face"]["count"] == 1
        assert result["face"]["confidence"] == 0.95

        # Verify violence data
        assert result["violence"]["detected"] is False
        assert result["violence"]["score"] == 0.12

        # Verify vehicle data
        assert result["vehicle"]["type"] == "sedan"
        assert result["vehicle"]["confidence"] == 0.91
        assert result["vehicle"]["is_commercial"] is False

        # Verify image quality
        assert result["image_quality"]["score"] == 85.0
        assert result["image_quality"]["is_blurry"] is False

        # Verify processing metadata
        assert result["processing_time_ms"] == 125.5
        assert result["errors"] == []

    def test_transform_enrichment_data_none(self) -> None:
        """Test transformation when enrichment data is None."""
        from backend.api.routes.detections import _transform_enrichment_data

        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)
        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=None,
            detected_at=detected_at,
        )

        assert result["detection_id"] == 1
        assert result["enriched_at"] == detected_at
        assert result["license_plate"]["detected"] is False
        assert result["face"]["detected"] is False
        assert result["face"]["count"] == 0
        assert result["violence"]["detected"] is False
        assert result["violence"]["score"] == 0.0
        assert result["vehicle"] is None
        assert result["clothing"] is None
        assert result["image_quality"] is None
        assert result["processing_time_ms"] is None
        assert result["errors"] == []

    def test_transform_enrichment_data_empty(self) -> None:
        """Test transformation when enrichment data is empty dict."""
        from backend.api.routes.detections import _transform_enrichment_data

        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)
        result = _transform_enrichment_data(
            detection_id=42,
            enrichment_data={},
            detected_at=detected_at,
        )

        assert result["detection_id"] == 42
        assert result["license_plate"]["detected"] is False
        assert result["face"]["detected"] is False
        assert result["vehicle"] is None
        assert result["clothing"] is None

    def test_transform_enrichment_data_with_clothing(
        self,
        sample_enrichment_data: dict[str, Any],
        sample_clothing_enrichment: dict[str, Any],
    ) -> None:
        """Test transformation with clothing data."""
        from backend.api.routes.detections import _transform_enrichment_data

        combined_data = {**sample_enrichment_data, **sample_clothing_enrichment}
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=combined_data,
            detected_at=detected_at,
        )

        assert result["clothing"] is not None
        assert result["clothing"]["upper"] == "red t-shirt"
        assert result["clothing"]["lower"] == "blue jeans"
        assert result["clothing"]["is_suspicious"] is False
        assert result["clothing"]["has_face_covered"] is False
        assert result["clothing"]["has_bag"] is False
        assert result["clothing"]["clothing_items"] == ["upper_clothes", "pants"]

    def test_transform_enrichment_data_with_vehicle_damage(self) -> None:
        """Test transformation with vehicle damage data."""
        from backend.api.routes.detections import _transform_enrichment_data

        enrichment_data = {
            "vehicle_classifications": {
                "1": {
                    "vehicle_type": "sedan",
                    "confidence": 0.91,
                    "is_commercial": False,
                }
            },
            "vehicle_damage": {
                "1": {
                    "has_damage": True,
                    "damage_types": ["dent", "scratch"],
                }
            },
        }

        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=enrichment_data,
            detected_at=datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC),
        )

        assert result["vehicle"]["type"] == "sedan"
        assert result["vehicle"]["damage_detected"] is True
        assert result["vehicle"]["damage_types"] == ["dent", "scratch"]

    def test_transform_enrichment_data_with_multiple_faces(self) -> None:
        """Test transformation with multiple faces."""
        from backend.api.routes.detections import _transform_enrichment_data

        enrichment_data = {
            "faces": [
                {"confidence": 0.85, "bbox": [10, 20, 30, 40]},
                {"confidence": 0.92, "bbox": [50, 60, 70, 80]},
                {"confidence": 0.78, "bbox": [90, 100, 110, 120]},
            ]
        }

        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=enrichment_data,
            detected_at=datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC),
        )

        assert result["face"]["detected"] is True
        assert result["face"]["count"] == 3
        assert result["face"]["confidence"] == 0.92  # Max confidence

    def test_transform_enrichment_data_with_pet(self) -> None:
        """Test transformation with pet data."""
        from backend.api.routes.detections import _transform_enrichment_data

        enrichment_data = {
            "pet_classifications": {
                "1": {
                    "animal_type": "dog",
                    "confidence": 0.94,
                    "is_household_pet": True,
                }
            }
        }

        result = _transform_enrichment_data(
            detection_id=1,
            enrichment_data=enrichment_data,
            detected_at=datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC),
        )

        assert result["pet"]["detected"] is True
        assert result["pet"]["type"] == "dog"
        assert result["pet"]["confidence"] == 0.94
        assert result["pet"]["is_household_pet"] is True


class TestExtractClothingFromEnrichment:
    """Tests for _extract_clothing_from_enrichment helper function."""

    def test_extract_clothing_with_both_sources(
        self, sample_clothing_enrichment: dict[str, Any]
    ) -> None:
        """Test clothing extraction with both classification and segmentation."""
        from backend.api.routes.detections import _extract_clothing_from_enrichment

        result = _extract_clothing_from_enrichment(sample_clothing_enrichment)

        assert result is not None
        assert result["upper"] == "red t-shirt"
        assert result["lower"] == "blue jeans"
        assert result["is_suspicious"] is False
        assert result["is_service_uniform"] is False
        assert result["has_face_covered"] is False
        assert result["has_bag"] is False
        assert result["clothing_items"] == ["upper_clothes", "pants"]

    def test_extract_clothing_empty_data(self) -> None:
        """Test clothing extraction with no clothing data."""
        from backend.api.routes.detections import _extract_clothing_from_enrichment

        result = _extract_clothing_from_enrichment({})

        assert result is None

    def test_extract_clothing_classification_only(self) -> None:
        """Test clothing extraction with only classification data."""
        from backend.api.routes.detections import _extract_clothing_from_enrichment

        data = {
            "clothing_classifications": {
                "1": {
                    "top_category": "jacket",
                    "is_suspicious": True,
                    "is_service_uniform": False,
                    "raw_description": "black jacket",  # No comma, uses top_category
                }
            }
        }

        result = _extract_clothing_from_enrichment(data)

        assert result is not None
        # When raw_description has no comma, we use top_category as upper
        assert result["upper"] == "jacket"
        assert result["lower"] is None
        assert result["is_suspicious"] is True


class TestExtractVehicleFromEnrichment:
    """Tests for _extract_vehicle_from_enrichment helper function."""

    def test_extract_vehicle_with_damage(self) -> None:
        """Test vehicle extraction with damage data."""
        from backend.api.routes.detections import _extract_vehicle_from_enrichment

        data = {
            "vehicle_classifications": {
                "1": {
                    "vehicle_type": "truck",
                    "confidence": 0.88,
                    "is_commercial": True,
                }
            },
            "vehicle_damage": {
                "1": {
                    "has_damage": True,
                    "damage_types": ["cracked_windshield"],
                }
            },
        }

        result = _extract_vehicle_from_enrichment(data)

        assert result is not None
        assert result["type"] == "truck"
        assert result["confidence"] == 0.88
        assert result["is_commercial"] is True
        assert result["damage_detected"] is True
        assert result["damage_types"] == ["cracked_windshield"]

    def test_extract_vehicle_empty_data(self) -> None:
        """Test vehicle extraction with no vehicle data."""
        from backend.api.routes.detections import _extract_vehicle_from_enrichment

        result = _extract_vehicle_from_enrichment({})

        assert result is None


class TestEnrichmentSchemas:
    """Tests for enrichment Pydantic schemas."""

    def test_enrichment_response_schema_validation(self) -> None:
        """Test that EnrichmentResponse schema validates correctly."""
        from backend.api.schemas.enrichment import EnrichmentResponse

        # Create valid enrichment response
        enrichment = EnrichmentResponse(
            detection_id=1,
            enriched_at=datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC),
            license_plate={
                "detected": True,
                "confidence": 0.92,
                "text": "ABC-1234",
                "bbox": [100, 200, 300, 250],
            },
            face={"detected": True, "count": 1, "confidence": 0.88},
            vehicle={"type": "sedan", "color": None, "confidence": 0.91},
            clothing={"upper": "red t-shirt", "lower": "blue jeans"},
            violence={"detected": False, "score": 0.12},
            weather={"condition": "clear", "confidence": 0.95},
            pose=None,
            depth=None,
            image_quality={"score": 0.85, "is_blurry": False},
        )

        assert enrichment.detection_id == 1
        # Access using .model_dump() since the field may be a dict or Pydantic model
        lp = enrichment.model_dump()["license_plate"]
        assert lp["detected"] is True
        assert lp["text"] == "ABC-1234"

    def test_enrichment_response_optional_fields(self) -> None:
        """Test that EnrichmentResponse handles optional fields."""
        from backend.api.schemas.enrichment import EnrichmentResponse

        # Create enrichment with minimal data
        enrichment = EnrichmentResponse(
            detection_id=1,
            enriched_at=datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC),
            license_plate={"detected": False},
            face={"detected": False, "count": 0},
            vehicle=None,
            clothing=None,
            violence={"detected": False, "score": 0.0},
            weather=None,
            pose=None,
            depth=None,
            image_quality=None,
        )

        assert enrichment.vehicle is None
        assert enrichment.clothing is None

    def test_event_enrichments_response_schema(self) -> None:
        """Test EventEnrichmentsResponse schema."""
        from backend.api.schemas.enrichment import (
            EnrichmentResponse,
            EventEnrichmentsResponse,
        )

        enrichments = [
            EnrichmentResponse(
                detection_id=i,
                enriched_at=datetime(2026, 1, 3, 10, 30, i, tzinfo=UTC),
                license_plate={"detected": False},
                face={"detected": False, "count": 0},
                violence={"detected": False, "score": 0.0},
            )
            for i in range(3)
        ]

        response = EventEnrichmentsResponse(
            event_id=100,
            enrichments=enrichments,
            count=3,
        )

        assert response.event_id == 100
        assert response.count == 3
        assert len(response.enrichments) == 3

    def test_license_plate_enrichment_schema(self) -> None:
        """Test LicensePlateEnrichment schema."""
        from backend.api.schemas.enrichment import LicensePlateEnrichment

        lp = LicensePlateEnrichment(
            detected=True,
            confidence=0.92,
            text="ABC-1234",
            ocr_confidence=0.88,
            bbox=[100.0, 200.0, 300.0, 250.0],
        )

        assert lp.detected is True
        assert lp.text == "ABC-1234"
        assert lp.confidence == 0.92

    def test_face_enrichment_schema(self) -> None:
        """Test FaceEnrichment schema."""
        from backend.api.schemas.enrichment import FaceEnrichment

        face = FaceEnrichment(
            detected=True,
            count=3,
            confidence=0.95,
        )

        assert face.detected is True
        assert face.count == 3
        assert face.confidence == 0.95

    def test_vehicle_enrichment_schema(self) -> None:
        """Test VehicleEnrichment schema."""
        from backend.api.schemas.enrichment import VehicleEnrichment

        vehicle = VehicleEnrichment(
            type="sedan",
            color="silver",
            confidence=0.91,
            is_commercial=False,
            damage_detected=True,
            damage_types=["dent", "scratch"],
        )

        assert vehicle.type == "sedan"
        assert vehicle.color == "silver"
        assert vehicle.is_commercial is False
        assert vehicle.damage_detected is True
        assert vehicle.damage_types == ["dent", "scratch"]

    def test_clothing_enrichment_schema(self) -> None:
        """Test ClothingEnrichment schema."""
        from backend.api.schemas.enrichment import ClothingEnrichment

        clothing = ClothingEnrichment(
            upper="red t-shirt",
            lower="blue jeans",
            is_suspicious=False,
            is_service_uniform=False,
            has_face_covered=False,
            has_bag=True,
            clothing_items=["upper_clothes", "pants"],
        )

        assert clothing.upper == "red t-shirt"
        assert clothing.lower == "blue jeans"
        assert clothing.has_bag is True

    def test_violence_enrichment_schema(self) -> None:
        """Test ViolenceEnrichment schema."""
        from backend.api.schemas.enrichment import ViolenceEnrichment

        violence = ViolenceEnrichment(
            detected=False,
            score=0.12,
            confidence=0.88,
        )

        assert violence.detected is False
        assert violence.score == 0.12

    def test_image_quality_enrichment_schema(self) -> None:
        """Test ImageQualityEnrichment schema."""
        from backend.api.schemas.enrichment import ImageQualityEnrichment

        iq = ImageQualityEnrichment(
            score=85.0,
            is_blurry=False,
            is_low_quality=False,
            quality_issues=[],
            quality_change_detected=False,
        )

        assert iq.score == 85.0
        assert iq.is_blurry is False
        assert iq.quality_issues == []

    def test_pet_enrichment_schema(self) -> None:
        """Test PetEnrichment schema."""
        from backend.api.schemas.enrichment import PetEnrichment

        pet = PetEnrichment(
            detected=True,
            type="dog",
            confidence=0.94,
            is_household_pet=True,
        )

        assert pet.detected is True
        assert pet.type == "dog"
        assert pet.is_household_pet is True
