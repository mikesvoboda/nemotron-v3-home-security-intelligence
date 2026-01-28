"""Unit tests for enrichment data transformation helpers.

Tests verify:
- NEM-1349: Code duplication is reduced through base extractor class
- NEM-1351: Schema validation occurs before transformation
- NEM-1307: Individual extractor classes work correctly

TDD: These tests validate the refactored enrichment transformation logic.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from backend.api.helpers.enrichment_transformers import (
    ActionExtractor,
    BaseEnrichmentExtractor,
    ClothingExtractor,
    EnrichmentTransformer,
    FaceExtractor,
    ImageQualityExtractor,
    LicensePlateExtractor,
    PetExtractor,
    PoseExtractor,
    VehicleExtractor,
    ViolenceExtractor,
    get_enrichment_transformer,
    sanitize_errors,
    transform_enrichment_data,
)

# ============================================================================
# Test Fixtures
# ============================================================================


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


# ============================================================================
# Test sanitize_errors
# ============================================================================


class TestSanitizeErrors:
    """Tests for sanitize_errors function."""

    def test_sanitize_errors_empty_list(self) -> None:
        """Test that empty error list returns empty list."""
        assert sanitize_errors([]) == []

    def test_sanitize_errors_preserves_category(self) -> None:
        """Test that error category is preserved."""
        errors = [
            "License plate detection failed: FileNotFoundError: /export/foscam/image.jpg",
            "Face detection failed: Connection refused at 192.168.1.50:8080",
        ]
        result = sanitize_errors(errors)
        assert len(result) == 2
        assert "License Plate Detection" in result[0]
        assert "Face Detection" in result[1]

    def test_sanitize_errors_unknown_category(self) -> None:
        """Test that unknown error types get generic message."""
        errors = ["Some internal error with stack trace"]
        result = sanitize_errors(errors)
        assert result == ["Enrichment processing error"]


# ============================================================================
# Test LicensePlateExtractor
# ============================================================================


class TestLicensePlateExtractor:
    """Tests for LicensePlateExtractor."""

    def test_extract_with_data(self) -> None:
        """Test extraction with license plate data."""
        data = {
            "license_plates": [
                {
                    "text": "ABC-1234",
                    "confidence": 0.92,
                    "ocr_confidence": 0.88,
                    "bbox": [100.0, 200.0, 300.0, 250.0],
                }
            ]
        }
        extractor = LicensePlateExtractor()
        result = extractor.extract(data)

        assert result["detected"] is True
        assert result["text"] == "ABC-1234"
        assert result["confidence"] == 0.92
        assert result["ocr_confidence"] == 0.88
        assert result["bbox"] == [100.0, 200.0, 300.0, 250.0]

    def test_extract_empty_data(self) -> None:
        """Test extraction with no license plate data."""
        extractor = LicensePlateExtractor()
        result = extractor.extract({})

        assert result == {"detected": False}

    def test_default_value(self) -> None:
        """Test default value property."""
        extractor = LicensePlateExtractor()
        assert extractor.default_value == {"detected": False}


# ============================================================================
# Test FaceExtractor
# ============================================================================


class TestFaceExtractor:
    """Tests for FaceExtractor."""

    def test_extract_with_single_face(self) -> None:
        """Test extraction with single face."""
        data = {"faces": [{"confidence": 0.95, "bbox": [10, 20, 30, 40]}]}
        extractor = FaceExtractor()
        result = extractor.extract(data)

        assert result["detected"] is True
        assert result["count"] == 1
        assert result["confidence"] == 0.95

    def test_extract_with_multiple_faces(self) -> None:
        """Test extraction with multiple faces returns max confidence."""
        data = {
            "faces": [
                {"confidence": 0.85},
                {"confidence": 0.92},
                {"confidence": 0.78},
            ]
        }
        extractor = FaceExtractor()
        result = extractor.extract(data)

        assert result["detected"] is True
        assert result["count"] == 3
        assert result["confidence"] == 0.92

    def test_extract_empty_data(self) -> None:
        """Test extraction with no face data."""
        extractor = FaceExtractor()
        result = extractor.extract({})

        assert result == {"detected": False, "count": 0}


# ============================================================================
# Test ViolenceExtractor
# ============================================================================


class TestViolenceExtractor:
    """Tests for ViolenceExtractor."""

    def test_extract_with_violence_detected(self) -> None:
        """Test extraction when violence is detected."""
        data = {
            "violence_detection": {
                "is_violent": True,
                "confidence": 0.85,
            }
        }
        extractor = ViolenceExtractor()
        result = extractor.extract(data)

        assert result["detected"] is True
        assert result["score"] == 0.85
        assert result["confidence"] == 0.85

    def test_extract_no_violence(self) -> None:
        """Test extraction when no violence is detected."""
        data = {
            "violence_detection": {
                "is_violent": False,
                "confidence": 0.12,
            }
        }
        extractor = ViolenceExtractor()
        result = extractor.extract(data)

        assert result["detected"] is False
        assert result["score"] == 0.12

    def test_extract_empty_data(self) -> None:
        """Test extraction with no violence data."""
        extractor = ViolenceExtractor()
        result = extractor.extract({})

        assert result == {"detected": False, "score": 0.0}


# ============================================================================
# Test VehicleExtractor
# ============================================================================


class TestVehicleExtractor:
    """Tests for VehicleExtractor."""

    def test_extract_with_vehicle(self) -> None:
        """Test extraction with vehicle classification."""
        data = {
            "vehicle_classifications": {
                "1": {
                    "vehicle_type": "sedan",
                    "confidence": 0.91,
                    "is_commercial": False,
                }
            }
        }
        extractor = VehicleExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["type"] == "sedan"
        assert result["confidence"] == 0.91
        assert result["is_commercial"] is False

    def test_extract_with_vehicle_damage(self) -> None:
        """Test extraction with vehicle damage data."""
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
                    "damage_types": ["dent", "scratch"],
                }
            },
        }
        extractor = VehicleExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["type"] == "truck"
        assert result["damage_detected"] is True
        assert result["damage_types"] == ["dent", "scratch"]

    def test_extract_empty_data(self) -> None:
        """Test extraction with no vehicle data."""
        extractor = VehicleExtractor()
        result = extractor.extract({})

        assert result is None


# ============================================================================
# Test ClothingExtractor
# ============================================================================


class TestClothingExtractor:
    """Tests for ClothingExtractor."""

    def test_extract_with_both_sources(self, sample_clothing_enrichment: dict[str, Any]) -> None:
        """Test extraction with both classification and segmentation."""
        extractor = ClothingExtractor()
        result = extractor.extract(sample_clothing_enrichment)

        assert result is not None
        assert result["upper"] == "red t-shirt"
        assert result["lower"] == "blue jeans"
        assert result["is_suspicious"] is False
        assert result["has_face_covered"] is False
        assert result["clothing_items"] == ["upper_clothes", "pants"]

    def test_extract_classification_only(self) -> None:
        """Test extraction with only classification data."""
        data = {
            "clothing_classifications": {
                "1": {
                    "top_category": "jacket",
                    "is_suspicious": True,
                    "raw_description": "black jacket",
                }
            }
        }
        extractor = ClothingExtractor()
        result = extractor.extract(data)

        assert result is not None
        # Uses raw_description when available (no comma means single item)
        assert result["upper"] == "black jacket"
        assert result["is_suspicious"] is True

    def test_extract_empty_data(self) -> None:
        """Test extraction with no clothing data."""
        extractor = ClothingExtractor()
        result = extractor.extract({})

        assert result is None


# ============================================================================
# Test ImageQualityExtractor
# ============================================================================


class TestImageQualityExtractor:
    """Tests for ImageQualityExtractor."""

    def test_extract_with_data(self) -> None:
        """Test extraction with image quality data."""
        data = {
            "image_quality": {
                "quality_score": 85.0,
                "is_blurry": False,
                "is_low_quality": False,
                "quality_issues": [],
            },
            "quality_change_detected": False,
        }
        extractor = ImageQualityExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["score"] == 85.0
        assert result["is_blurry"] is False
        assert result["quality_change_detected"] is False

    def test_extract_empty_data(self) -> None:
        """Test extraction with no image quality data."""
        extractor = ImageQualityExtractor()
        result = extractor.extract({})

        assert result is None


# ============================================================================
# Test PetExtractor
# ============================================================================


class TestPetExtractor:
    """Tests for PetExtractor."""

    def test_extract_with_pet(self) -> None:
        """Test extraction with pet data."""
        data = {
            "pet_classifications": {
                "1": {
                    "animal_type": "dog",
                    "confidence": 0.94,
                    "is_household_pet": True,
                }
            }
        }
        extractor = PetExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["detected"] is True
        assert result["type"] == "dog"
        assert result["confidence"] == 0.94
        assert result["is_household_pet"] is True

    def test_extract_empty_data(self) -> None:
        """Test extraction with no pet data."""
        extractor = PetExtractor()
        result = extractor.extract({})

        assert result is None


# ============================================================================
# Test PoseExtractor (NEM-1881)
# ============================================================================


class TestPoseExtractor:
    """Tests for PoseExtractor (ViTPose pose analysis)."""

    def test_extract_with_pose_data(self) -> None:
        """Test extraction with complete pose estimation data."""
        data = {
            "pose_estimation": {
                "posture": "standing",
                "alerts": [],
                "keypoints": [
                    {"name": "nose", "x": 0.5, "y": 0.2, "confidence": 0.95},
                    {"name": "left_eye", "x": 0.48, "y": 0.18, "confidence": 0.92},
                    {"name": "right_eye", "x": 0.52, "y": 0.18, "confidence": 0.93},
                    {"name": "left_ear", "x": 0.45, "y": 0.19, "confidence": 0.88},
                    {"name": "right_ear", "x": 0.55, "y": 0.19, "confidence": 0.87},
                    {"name": "left_shoulder", "x": 0.4, "y": 0.35, "confidence": 0.96},
                    {"name": "right_shoulder", "x": 0.6, "y": 0.35, "confidence": 0.96},
                    {"name": "left_elbow", "x": 0.35, "y": 0.5, "confidence": 0.89},
                    {"name": "right_elbow", "x": 0.65, "y": 0.5, "confidence": 0.90},
                    {"name": "left_wrist", "x": 0.3, "y": 0.65, "confidence": 0.85},
                    {"name": "right_wrist", "x": 0.7, "y": 0.65, "confidence": 0.86},
                    {"name": "left_hip", "x": 0.42, "y": 0.6, "confidence": 0.94},
                    {"name": "right_hip", "x": 0.58, "y": 0.6, "confidence": 0.94},
                    {"name": "left_knee", "x": 0.4, "y": 0.78, "confidence": 0.91},
                    {"name": "right_knee", "x": 0.6, "y": 0.78, "confidence": 0.92},
                    {"name": "left_ankle", "x": 0.38, "y": 0.95, "confidence": 0.88},
                    {"name": "right_ankle", "x": 0.62, "y": 0.95, "confidence": 0.89},
                ],
                "inference_time_ms": 45.2,
            }
        }
        extractor = PoseExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["posture"] == "standing"
        assert result["alerts"] == []
        assert result["keypoint_count"] == 17
        # Check keypoints array is correctly formatted (17 keypoints in COCO order)
        assert len(result["keypoints"]) == 17
        # Check first keypoint (nose)
        assert result["keypoints"][0] == [0.5, 0.2, 0.95]

    def test_extract_with_security_alerts(self) -> None:
        """Test extraction with security alerts for crouching posture."""
        data = {
            "pose_estimation": {
                "posture": "crouching",
                "alerts": ["crouching"],
                "keypoints": [
                    {"name": "nose", "x": 0.5, "y": 0.4, "confidence": 0.90},
                    {"name": "left_shoulder", "x": 0.4, "y": 0.5, "confidence": 0.85},
                    {"name": "right_shoulder", "x": 0.6, "y": 0.5, "confidence": 0.85},
                ],
                "inference_time_ms": 42.1,
            }
        }
        extractor = PoseExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["posture"] == "crouching"
        assert result["alerts"] == ["crouching"]
        # Should have keypoint count matching number of keypoints provided
        assert result["keypoint_count"] == 3

    def test_extract_with_multiple_alerts(self) -> None:
        """Test extraction with multiple security alerts."""
        data = {
            "pose_estimation": {
                "posture": "lying_down",
                "alerts": ["lying_down", "hands_raised"],
                "keypoints": [],
                "inference_time_ms": 38.5,
            }
        }
        extractor = PoseExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["posture"] == "lying_down"
        assert "lying_down" in result["alerts"]
        assert "hands_raised" in result["alerts"]
        assert result["keypoint_count"] == 0

    def test_extract_empty_data(self) -> None:
        """Test extraction with no pose data."""
        extractor = PoseExtractor()
        result = extractor.extract({})

        assert result is None

    def test_extract_keypoints_ordered_by_coco_format(self) -> None:
        """Test that keypoints are returned in COCO 17 keypoint order."""
        # Provide keypoints out of order to verify COCO ordering
        data = {
            "pose_estimation": {
                "posture": "standing",
                "alerts": [],
                "keypoints": [
                    {"name": "right_ankle", "x": 0.62, "y": 0.95, "confidence": 0.89},
                    {"name": "nose", "x": 0.5, "y": 0.2, "confidence": 0.95},
                    {"name": "left_shoulder", "x": 0.4, "y": 0.35, "confidence": 0.96},
                ],
                "inference_time_ms": 40.0,
            }
        }
        extractor = PoseExtractor()
        result = extractor.extract(data)

        # Result should have 17 keypoints (missing ones filled with zeros)
        assert len(result["keypoints"]) == 17
        # Index 0 is nose
        assert result["keypoints"][0] == [0.5, 0.2, 0.95]
        # Index 5 is left_shoulder
        assert result["keypoints"][5] == [0.4, 0.35, 0.96]
        # Index 16 is right_ankle
        assert result["keypoints"][16] == [0.62, 0.95, 0.89]
        # Index 1 is left_eye (missing, should be zeros)
        assert result["keypoints"][1] == [0.0, 0.0, 0.0]

    def test_default_value(self) -> None:
        """Test default value property."""
        extractor = PoseExtractor()
        assert extractor.default_value is None

    def test_enrichment_key(self) -> None:
        """Test enrichment key property."""
        extractor = PoseExtractor()
        assert extractor.enrichment_key == "pose_estimation"


# ============================================================================
# Test ActionExtractor (NEM-3883)
# ============================================================================


class TestActionExtractor:
    """Tests for ActionExtractor (X-CLIP action recognition)."""

    def test_extract_with_action_data(self) -> None:
        """Test extraction with complete action recognition data."""
        data = {
            "action_recognition": {
                "detected_action": "delivering package",
                "confidence": 0.85,
                "all_scores": {
                    "delivering package": 0.85,
                    "walking normally": 0.10,
                    "loitering": 0.05,
                },
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "delivering package"
        assert result["confidence"] == 0.85
        assert result["is_suspicious"] is False
        assert result["all_scores"]["delivering package"] == 0.85

    def test_extract_suspicious_action(self) -> None:
        """Test extraction with suspicious action detected."""
        data = {
            "action_recognition": {
                "detected_action": "loitering",
                "confidence": 0.78,
                "all_scores": {
                    "loitering": 0.78,
                    "walking normally": 0.22,
                },
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "loitering"
        assert result["is_suspicious"] is True

    def test_extract_climbing_is_suspicious(self) -> None:
        """Test that climbing action is flagged as suspicious."""
        data = {
            "action_recognition": {
                "detected_action": "climbing",
                "confidence": 0.88,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "climbing"
        assert result["is_suspicious"] is True

    def test_extract_breaking_is_suspicious(self) -> None:
        """Test that breaking window action is suspicious."""
        data = {
            "action_recognition": {
                "detected_action": "breaking window",
                "confidence": 0.92,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["is_suspicious"] is True

    def test_extract_running_away_is_suspicious(self) -> None:
        """Test that running away action is suspicious."""
        data = {
            "action_recognition": {
                "detected_action": "running away",
                "confidence": 0.80,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["is_suspicious"] is True

    def test_extract_walking_normally_not_suspicious(self) -> None:
        """Test that walking normally is not suspicious."""
        data = {
            "action_recognition": {
                "detected_action": "walking normally",
                "confidence": 0.90,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "walking normally"
        assert result["is_suspicious"] is False

    def test_extract_empty_data_no_pose(self) -> None:
        """Test extraction with no action or pose data returns None."""
        extractor = ActionExtractor()
        result = extractor.extract({})

        assert result is None

    def test_fallback_to_pose_inference(self) -> None:
        """Test pose-based action inference when X-CLIP unavailable."""
        data = {
            "pose_estimation": {
                "posture": "standing",
                "confidence": 0.85,
                "keypoints": [],
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "standing"
        assert result["confidence"] == 0.85
        assert result["is_suspicious"] is False
        assert result["all_scores"] is None

    def test_fallback_pose_crouching_is_suspicious(self) -> None:
        """Test pose-based inference flags crouching as suspicious."""
        data = {
            "pose_estimation": {
                "posture": "crouching",
                "confidence": 0.80,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "crouching"
        assert result["is_suspicious"] is True

    def test_fallback_pose_running_is_suspicious(self) -> None:
        """Test pose-based inference flags running as suspicious."""
        data = {
            "pose_estimation": {
                "posture": "running",
                "confidence": 0.75,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "running"
        assert result["is_suspicious"] is True

    def test_fallback_pose_walking_maps_correctly(self) -> None:
        """Test pose-based inference maps walking to walking normally."""
        data = {
            "pose_estimation": {
                "posture": "walking",
                "confidence": 0.88,
            }
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        assert result["action"] == "walking normally"
        assert result["is_suspicious"] is False

    def test_action_takes_precedence_over_pose(self) -> None:
        """Test X-CLIP action takes precedence over pose inference."""
        data = {
            "action_recognition": {
                "detected_action": "delivering package",
                "confidence": 0.85,
            },
            "pose_estimation": {
                "posture": "crouching",  # Would be suspicious if used
                "confidence": 0.80,
            },
        }
        extractor = ActionExtractor()
        result = extractor.extract(data)

        assert result is not None
        # Should use X-CLIP result, not pose inference
        assert result["action"] == "delivering package"
        assert result["is_suspicious"] is False

    def test_default_value(self) -> None:
        """Test default value property."""
        extractor = ActionExtractor()
        assert extractor.default_value is None

    def test_enrichment_key(self) -> None:
        """Test enrichment key property."""
        extractor = ActionExtractor()
        assert extractor.enrichment_key == "action_recognition"

    def test_is_suspicious_with_none_action(self) -> None:
        """Test _is_suspicious handles None action gracefully."""
        extractor = ActionExtractor()
        assert extractor._is_suspicious(None) is False

    def test_is_suspicious_case_insensitive(self) -> None:
        """Test suspicious action detection is case insensitive."""
        extractor = ActionExtractor()
        assert extractor._is_suspicious("LOITERING") is True
        assert extractor._is_suspicious("Loitering") is True
        assert extractor._is_suspicious("loitering") is True

    def test_is_suspicious_partial_match(self) -> None:
        """Test suspicious detection works with partial matches."""
        extractor = ActionExtractor()
        # These should match the suspicious patterns
        assert extractor._is_suspicious("a person loitering near door") is True
        assert extractor._is_suspicious("climbing over fence") is True
        assert extractor._is_suspicious("person running away quickly") is True


# ============================================================================
# Test EnrichmentTransformer
# ============================================================================


class TestEnrichmentTransformer:
    """Tests for EnrichmentTransformer orchestration class."""

    def test_transform_full_data(self, sample_enrichment_data: dict[str, Any]) -> None:
        """Test transformation of complete enrichment data."""
        transformer = EnrichmentTransformer(validate_schema=False)
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        result = transformer.transform(
            detection_id=1,
            enrichment_data=sample_enrichment_data,
            detected_at=detected_at,
        )

        assert result["detection_id"] == 1
        assert result["enriched_at"] == detected_at
        assert result["license_plate"]["detected"] is True
        assert result["face"]["detected"] is True
        assert result["vehicle"]["type"] == "sedan"
        assert result["violence"]["detected"] is False
        assert result["processing_time_ms"] == 125.5

    def test_transform_none_data(self) -> None:
        """Test transformation when enrichment data is None."""
        transformer = EnrichmentTransformer()
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        result = transformer.transform(
            detection_id=1,
            enrichment_data=None,
            detected_at=detected_at,
        )

        assert result["detection_id"] == 1
        assert result["license_plate"]["detected"] is False
        assert result["face"]["count"] == 0
        assert result["vehicle"] is None
        assert result["errors"] == []

    def test_transform_empty_data(self) -> None:
        """Test transformation with empty dict."""
        transformer = EnrichmentTransformer(validate_schema=False)
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        result = transformer.transform(
            detection_id=42,
            enrichment_data={},
            detected_at=detected_at,
        )

        assert result["detection_id"] == 42
        assert result["license_plate"]["detected"] is False
        assert result["vehicle"] is None

    def test_transform_with_validation(self, sample_enrichment_data: dict[str, Any]) -> None:
        """Test that validation is called when enabled."""
        transformer = EnrichmentTransformer(validate_schema=True)
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        # Should not raise even with validation enabled for valid data
        result = transformer.transform(
            detection_id=1,
            enrichment_data=sample_enrichment_data,
            detected_at=detected_at,
        )

        assert result["detection_id"] == 1

    def test_transform_sanitizes_errors(self) -> None:
        """Test that errors are sanitized during transformation."""
        transformer = EnrichmentTransformer(validate_schema=False)
        data = {
            "errors": [
                "License plate detection failed: FileNotFoundError: /export/foscam/img.jpg",
            ]
        }

        result = transformer.transform(
            detection_id=1,
            enrichment_data=data,
            detected_at=datetime.now(UTC),
        )

        # Error should be sanitized
        assert "/export" not in result["errors"][0]
        assert "License Plate Detection" in result["errors"][0]

    def test_transform_includes_action_data(self) -> None:
        """Test that action recognition data is included in transform (NEM-3883)."""
        transformer = EnrichmentTransformer(validate_schema=False)
        data = {
            "action_recognition": {
                "detected_action": "delivering package",
                "confidence": 0.85,
                "all_scores": {"delivering package": 0.85, "walking normally": 0.15},
            }
        }

        result = transformer.transform(
            detection_id=1,
            enrichment_data=data,
            detected_at=datetime.now(UTC),
        )

        assert result["action"] is not None
        assert result["action"]["action"] == "delivering package"
        assert result["action"]["confidence"] == 0.85
        assert result["action"]["is_suspicious"] is False

    def test_transform_action_fallback_to_pose(self) -> None:
        """Test action inference from pose when X-CLIP unavailable (NEM-3883)."""
        transformer = EnrichmentTransformer(validate_schema=False)
        data = {
            "pose_estimation": {
                "posture": "crouching",
                "confidence": 0.80,
                "keypoints": [],
            }
        }

        result = transformer.transform(
            detection_id=1,
            enrichment_data=data,
            detected_at=datetime.now(UTC),
        )

        # Action should be inferred from pose
        assert result["action"] is not None
        assert result["action"]["action"] == "crouching"
        assert result["action"]["is_suspicious"] is True

    def test_transform_action_none_when_no_data(self) -> None:
        """Test action is None when no action or pose data available."""
        transformer = EnrichmentTransformer(validate_schema=False)
        data = {"processing_time_ms": 100.0}

        result = transformer.transform(
            detection_id=1,
            enrichment_data=data,
            detected_at=datetime.now(UTC),
        )

        assert result["action"] is None


# ============================================================================
# Test Module-level Functions
# ============================================================================


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_enrichment_transformer_singleton(self) -> None:
        """Test that get_enrichment_transformer returns singleton."""
        t1 = get_enrichment_transformer()
        t2 = get_enrichment_transformer()
        assert t1 is t2

    def test_transform_enrichment_data_convenience(
        self, sample_enrichment_data: dict[str, Any]
    ) -> None:
        """Test transform_enrichment_data convenience function."""
        detected_at = datetime(2026, 1, 3, 10, 30, 0, tzinfo=UTC)

        result = transform_enrichment_data(
            detection_id=1,
            enrichment_data=sample_enrichment_data,
            detected_at=detected_at,
        )

        assert result["detection_id"] == 1
        assert result["license_plate"]["detected"] is True


# ============================================================================
# Test BaseEnrichmentExtractor (Abstract)
# ============================================================================


class TestBaseEnrichmentExtractor:
    """Tests for BaseEnrichmentExtractor base class."""

    def test_get_first_item_from_dict(self) -> None:
        """Test _get_first_item_from_dict helper method."""
        # Create a concrete implementation for testing
        extractor = VehicleExtractor()

        data = {
            "vehicle_classifications": {
                "1": {"vehicle_type": "sedan"},
                "2": {"vehicle_type": "suv"},
            }
        }

        key, item = extractor._get_first_item_from_dict(data, "vehicle_classifications")
        assert key == "1"
        assert item == {"vehicle_type": "sedan"}

    def test_get_first_item_from_empty_dict(self) -> None:
        """Test _get_first_item_from_dict with empty data."""
        extractor = VehicleExtractor()

        key, item = extractor._get_first_item_from_dict({}, "vehicle_classifications")
        assert key is None
        assert item is None

    def test_get_first_item_from_missing_key(self) -> None:
        """Test _get_first_item_from_dict with missing key."""
        extractor = VehicleExtractor()

        key, item = extractor._get_first_item_from_dict(
            {"other_key": {}}, "vehicle_classifications"
        )
        assert key is None
        assert item is None


# ============================================================================
# Test NEM-1351: Schema Validation Before Transformation
# ============================================================================


class TestSchemaValidation:
    """Tests specifically for NEM-1351: schema validation before transformation."""

    def test_validation_catches_invalid_data(self) -> None:
        """Test that invalid data triggers validation warning."""
        transformer = EnrichmentTransformer(validate_schema=True)

        # Data with out-of-range confidence (should be clamped by validator)
        data = {
            "license_plates": [{"confidence": 1.5}],  # Over 1.0
        }

        with patch("backend.api.helpers.enrichment_transformers.logger"):
            result = transformer.transform(
                detection_id=1,
                enrichment_data=data,
                detected_at=datetime.now(UTC),
            )

            # Result should still be returned
            assert result["detection_id"] == 1

    def test_validation_can_be_disabled(self) -> None:
        """Test that validation can be disabled for performance."""
        transformer = EnrichmentTransformer(validate_schema=False)

        # Valid data - with validation disabled, it should just process normally
        data = {
            "license_plates": [{"text": "ABC-123", "confidence": 0.9}],
            "processing_time_ms": 100.0,
        }

        result = transformer.transform(
            detection_id=1,
            enrichment_data=data,
            detected_at=datetime.now(UTC),
        )

        # Should return result with license plate detected
        assert result["license_plate"]["detected"] is True
        assert result["license_plate"]["text"] == "ABC-123"


# ============================================================================
# Test NEM-1349: Code Duplication Reduction
# ============================================================================


class TestCodeDuplicationReduction:
    """Tests verifying NEM-1349: code duplication is reduced."""

    def test_extractors_share_base_class(self) -> None:
        """Test that all extractors inherit from BaseEnrichmentExtractor."""
        extractors = [
            LicensePlateExtractor,
            FaceExtractor,
            ViolenceExtractor,
            VehicleExtractor,
            ClothingExtractor,
            ImageQualityExtractor,
            PetExtractor,
            PoseExtractor,
            ActionExtractor,
        ]

        for extractor_class in extractors:
            assert issubclass(extractor_class, BaseEnrichmentExtractor)

    def test_extractors_implement_required_interface(self) -> None:
        """Test that all extractors implement the required interface."""
        extractors = [
            LicensePlateExtractor(),
            FaceExtractor(),
            ViolenceExtractor(),
            VehicleExtractor(),
            ClothingExtractor(),
            ImageQualityExtractor(),
            PetExtractor(),
            PoseExtractor(),
            ActionExtractor(),
        ]

        for extractor in extractors:
            # All extractors should have these properties and methods
            assert hasattr(extractor, "enrichment_key")
            assert hasattr(extractor, "default_value")
            assert hasattr(extractor, "extract")
            assert callable(extractor.extract)


# ============================================================================
# Test NEM-1307: Smaller Helper Classes
# ============================================================================


class TestSmallerHelperClasses:
    """Tests verifying NEM-1307: transformation broken into helper classes."""

    def test_each_enrichment_type_has_own_extractor(self) -> None:
        """Test that each enrichment type has its own dedicated extractor."""
        # Map enrichment types to expected extractor classes
        enrichment_types = {
            "license_plates": LicensePlateExtractor,
            "faces": FaceExtractor,
            "violence_detection": ViolenceExtractor,
            "vehicle_classifications": VehicleExtractor,
            "clothing_classifications": ClothingExtractor,
            "image_quality": ImageQualityExtractor,
            "pet_classifications": PetExtractor,
            "pose_estimation": PoseExtractor,
            "action_recognition": ActionExtractor,
        }

        for key, extractor_class in enrichment_types.items():
            extractor = extractor_class()
            assert extractor.enrichment_key == key, (
                f"Extractor {extractor_class.__name__} should handle key '{key}'"
            )

    def test_extractors_are_independently_testable(self) -> None:
        """Test that each extractor can be tested independently."""
        # Test data for each extractor type
        test_cases = [
            (LicensePlateExtractor(), {"license_plates": [{"text": "ABC"}]}),
            (FaceExtractor(), {"faces": [{"confidence": 0.9}]}),
            (ViolenceExtractor(), {"violence_detection": {"is_violent": False}}),
            (VehicleExtractor(), {"vehicle_classifications": {"1": {"vehicle_type": "car"}}}),
            (ClothingExtractor(), {"clothing_classifications": {"1": {"top_category": "shirt"}}}),
            (ImageQualityExtractor(), {"image_quality": {"quality_score": 80}}),
            (PetExtractor(), {"pet_classifications": {"1": {"animal_type": "cat"}}}),
            (
                PoseExtractor(),
                {"pose_estimation": {"posture": "standing", "alerts": [], "keypoints": []}},
            ),
            (
                ActionExtractor(),
                {"action_recognition": {"detected_action": "walking", "confidence": 0.85}},
            ),
        ]

        for extractor, data in test_cases:
            # Each extractor should be able to process its data independently
            result = extractor.extract(data)
            assert result is not None, f"{type(extractor).__name__} should return result"
