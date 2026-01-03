"""Unit tests for enrichment data storage on Detection model.

Tests the storage and retrieval of AI-computed enrichment data
(vehicle classification, pet detection, person attributes, license plates, etc.)
on Detection records.
"""

import json
from datetime import UTC, datetime

from backend.models.detection import Detection


class TestDetectionEnrichmentData:
    """Tests for Detection.enrichment_data field."""

    def test_detection_has_enrichment_data_field(self):
        """Test that Detection model has enrichment_data attribute."""
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
        )
        # The field should exist and default to None
        assert hasattr(detection, "enrichment_data")
        assert detection.enrichment_data is None

    def test_detection_enrichment_data_stores_dict(self):
        """Test that enrichment_data can store dictionary data."""
        enrichment = {
            "vehicle_classification": {
                "vehicle_type": "sedan",
                "confidence": 0.92,
                "is_commercial": False,
            },
            "license_plates": [
                {
                    "text": "ABC123",
                    "confidence": 0.88,
                    "bbox": [100, 200, 150, 220],
                }
            ],
        }
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="car",
            confidence=0.95,
            enrichment_data=enrichment,
        )
        assert detection.enrichment_data == enrichment
        assert detection.enrichment_data["vehicle_classification"]["vehicle_type"] == "sedan"
        assert len(detection.enrichment_data["license_plates"]) == 1

    def test_detection_enrichment_data_stores_pet_classification(self):
        """Test that enrichment_data stores pet classification results."""
        enrichment = {
            "pet_classification": {
                "animal_type": "dog",
                "confidence": 0.97,
                "is_household_pet": True,
            }
        }
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="dog",
            confidence=0.88,
            enrichment_data=enrichment,
        )
        assert detection.enrichment_data["pet_classification"]["animal_type"] == "dog"
        assert detection.enrichment_data["pet_classification"]["is_household_pet"] is True

    def test_detection_enrichment_data_stores_person_attributes(self):
        """Test that enrichment_data stores person attribute analysis."""
        enrichment = {
            "clothing_classification": {
                "top_category": "t-shirt",
                "confidence": 0.85,
                "is_suspicious": False,
                "is_service_uniform": False,
            },
            "face_detected": True,
            "face_bbox": [120, 50, 180, 130],
        }
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            enrichment_data=enrichment,
        )
        assert detection.enrichment_data["clothing_classification"]["top_category"] == "t-shirt"
        assert detection.enrichment_data["face_detected"] is True

    def test_detection_enrichment_data_stores_vehicle_damage(self):
        """Test that enrichment_data stores vehicle damage detection results."""
        enrichment = {
            "vehicle_damage": {
                "has_damage": True,
                "damage_types": ["scratch", "dent"],
                "has_high_security_damage": False,
                "total_damage_count": 2,
            }
        }
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="car",
            confidence=0.92,
            enrichment_data=enrichment,
        )
        assert detection.enrichment_data["vehicle_damage"]["has_damage"] is True
        assert "scratch" in detection.enrichment_data["vehicle_damage"]["damage_types"]

    def test_detection_enrichment_data_empty_dict(self):
        """Test that enrichment_data can be an empty dict (enrichment ran but found nothing)."""
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.88,
            enrichment_data={},
        )
        assert detection.enrichment_data == {}

    def test_detection_enrichment_data_complex_nested(self):
        """Test that enrichment_data handles complex nested structures."""
        enrichment = {
            "vision_extraction": {
                "person_attributes": {
                    "det_1": {
                        "clothing": "blue jacket, jeans",
                        "carrying": "backpack",
                        "hair": "short brown",
                    }
                },
                "vehicle_attributes": {},
                "scene_analysis": {
                    "description": "Residential driveway",
                    "time_of_day": "afternoon",
                },
            },
            "reid_matches": {
                "person_matches": [
                    {
                        "entity_id": "person_abc123",
                        "similarity": 0.89,
                        "camera_id": "back_door",
                        "timestamp": "2025-12-23T10:00:00Z",
                    }
                ]
            },
        }
        detection = Detection(
            camera_id="test-camera",
            file_path="/test/path.jpg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            enrichment_data=enrichment,
        )
        assert (
            detection.enrichment_data["vision_extraction"]["person_attributes"]["det_1"]["clothing"]
            == "blue jacket, jeans"
        )
        assert len(detection.enrichment_data["reid_matches"]["person_matches"]) == 1


class TestEnrichmentResultToDetection:
    """Tests for converting EnrichmentResult to per-detection enrichment data."""

    def test_enrichment_result_to_dict_format(self):
        """Test that EnrichmentResult.to_dict() produces storable format."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult(
            license_plates=[],
            faces=[],
            errors=[],
            processing_time_ms=150.0,
        )
        result_dict = result.to_dict()

        # Verify it's a serializable dict
        assert isinstance(result_dict, dict)
        # Should be JSON serializable
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)

    def test_extract_enrichment_for_detection_id(self):
        """Test extracting enrichment data for a specific detection ID."""
        from backend.services.enrichment_pipeline import (
            BoundingBox,
            EnrichmentResult,
            LicensePlateResult,
        )
        from backend.services.nemotron_analyzer import extract_detection_enrichment
        from backend.services.vehicle_classifier_loader import VehicleClassificationResult

        # Create enrichment result with data for multiple detections
        result = EnrichmentResult(
            license_plates=[
                LicensePlateResult(
                    bbox=BoundingBox(100, 200, 150, 220),
                    text="ABC123",
                    confidence=0.88,
                    ocr_confidence=0.75,
                    source_detection_id=1,
                ),
            ],
            vehicle_classifications={
                "1": VehicleClassificationResult(
                    vehicle_type="sedan",
                    confidence=0.92,
                    display_name="Sedan",
                    is_commercial=False,
                    all_scores={"sedan": 0.92, "suv": 0.05},
                ),
            },
        )

        # Extract enrichment for detection 1
        det_enrichment = extract_detection_enrichment(result, detection_id=1)

        assert det_enrichment is not None
        assert "license_plates" in det_enrichment
        assert len(det_enrichment["license_plates"]) == 1
        assert det_enrichment["license_plates"][0]["text"] == "ABC123"
        assert "vehicle_classification" in det_enrichment
        assert det_enrichment["vehicle_classification"]["vehicle_type"] == "sedan"

    def test_extract_enrichment_returns_none_for_empty(self):
        """Test that extract_detection_enrichment returns None when no data for detection."""
        from backend.services.enrichment_pipeline import EnrichmentResult
        from backend.services.nemotron_analyzer import extract_detection_enrichment

        # Create enrichment result with no data for detection 99
        result = EnrichmentResult(
            license_plates=[],
            faces=[],
            errors=[],
            processing_time_ms=100.0,
        )

        det_enrichment = extract_detection_enrichment(result, detection_id=99)
        assert det_enrichment is None

    def test_extract_enrichment_returns_none_for_none_input(self):
        """Test that extract_detection_enrichment handles None input."""
        from backend.services.nemotron_analyzer import extract_detection_enrichment

        det_enrichment = extract_detection_enrichment(None, detection_id=1)
        assert det_enrichment is None
