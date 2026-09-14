"""Unit tests for enrichment API schemas (NEM-3535).

Tests validate the enrichment API schemas including the new EnrichmentModelInfo
schema that exposes which AI model produced each enrichment result.
"""

import pytest

from backend.api.schemas.enrichment import (
    ClothingEnrichment,
    DepthEnrichment,
    EnrichmentModelInfo,
    EnrichmentResponse,
    FaceEnrichment,
    ImageQualityEnrichment,
    LicensePlateEnrichment,
    PetEnrichment,
    PoseEnrichment,
    VehicleEnrichment,
    ViolenceEnrichment,
    WeatherEnrichment,
)


class TestEnrichmentModelInfo:
    """Tests for EnrichmentModelInfo schema (NEM-3535)."""

    def test_valid_model_info_full(self) -> None:
        """Test validation of complete model info."""
        data = {
            "model_name": "yolov8n-pose",
            "model_version": "1.0.0",
            "inference_time_ms": 45.2,
        }
        info = EnrichmentModelInfo.model_validate(data)

        assert info.model_name == "yolov8n-pose"
        assert info.model_version == "1.0.0"
        assert info.inference_time_ms == 45.2

    def test_valid_model_info_minimal(self) -> None:
        """Test validation with only required field."""
        data = {"model_name": "vitpose"}
        info = EnrichmentModelInfo.model_validate(data)

        assert info.model_name == "vitpose"
        assert info.model_version is None
        assert info.inference_time_ms is None

    def test_model_info_inference_time_positive(self) -> None:
        """Test that inference_time_ms must be non-negative."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            EnrichmentModelInfo.model_validate({"model_name": "test", "inference_time_ms": -1.0})

    def test_model_info_serialization(self) -> None:
        """Test that model info serializes correctly to dict."""
        info = EnrichmentModelInfo(
            model_name="fashionclip",
            model_version="2.0.1",
            inference_time_ms=32.5,
        )
        data = info.model_dump()

        assert data["model_name"] == "fashionclip"
        assert data["model_version"] == "2.0.1"
        assert data["inference_time_ms"] == 32.5


class TestLicensePlateEnrichmentWithModelInfo:
    """Tests for LicensePlateEnrichment with model_info field."""

    def test_license_plate_with_model_info(self) -> None:
        """Test license plate enrichment includes model info."""
        data = {
            "detected": True,
            "confidence": 0.92,
            "text": "ABC-1234",
            "ocr_confidence": 0.88,
            "model_info": {
                "model_name": "yolov11-license-plate",
                "inference_time_ms": 25.3,
            },
        }
        enrichment = LicensePlateEnrichment.model_validate(data)

        assert enrichment.detected is True
        assert enrichment.text == "ABC-1234"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "yolov11-license-plate"
        assert enrichment.model_info.inference_time_ms == 25.3

    def test_license_plate_without_model_info(self) -> None:
        """Test backward compatibility - model_info is optional."""
        data = {
            "detected": True,
            "confidence": 0.85,
            "text": "XYZ-789",
        }
        enrichment = LicensePlateEnrichment.model_validate(data)

        assert enrichment.detected is True
        assert enrichment.model_info is None


class TestFaceEnrichmentWithModelInfo:
    """Tests for FaceEnrichment with model_info field."""

    def test_face_with_model_info(self) -> None:
        """Test face enrichment includes model info."""
        data = {
            "detected": True,
            "count": 2,
            "confidence": 0.95,
            "model_info": {
                "model_name": "yolov11-face",
                "model_version": "1.0.0",
                "inference_time_ms": 18.5,
            },
        }
        enrichment = FaceEnrichment.model_validate(data)

        assert enrichment.detected is True
        assert enrichment.count == 2
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "yolov11-face"


class TestVehicleEnrichmentWithModelInfo:
    """Tests for VehicleEnrichment with model_info field."""

    def test_vehicle_with_model_info(self) -> None:
        """Test vehicle enrichment includes model info."""
        data = {
            "type": "sedan",
            "color": "silver",
            "confidence": 0.91,
            "is_commercial": False,
            "model_info": {
                "model_name": "vehicle-classifier",
                "inference_time_ms": 32.1,
            },
        }
        enrichment = VehicleEnrichment.model_validate(data)

        assert enrichment.type == "sedan"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "vehicle-classifier"


class TestClothingEnrichmentWithModelInfo:
    """Tests for ClothingEnrichment with model_info field."""

    def test_clothing_with_model_info(self) -> None:
        """Test clothing enrichment includes model info."""
        data = {
            "upper": "red t-shirt",
            "lower": "blue jeans",
            "is_suspicious": False,
            "model_info": {
                "model_name": "fashionclip",
                "inference_time_ms": 45.2,
            },
        }
        enrichment = ClothingEnrichment.model_validate(data)

        assert enrichment.upper == "red t-shirt"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "fashionclip"


class TestViolenceEnrichmentWithModelInfo:
    """Tests for ViolenceEnrichment with model_info field."""

    def test_violence_with_model_info(self) -> None:
        """Test violence enrichment includes model info."""
        data = {
            "detected": False,
            "score": 0.12,
            "confidence": 0.88,
            "model_info": {
                "model_name": "violence-detection",
                "inference_time_ms": 28.7,
            },
        }
        enrichment = ViolenceEnrichment.model_validate(data)

        assert enrichment.detected is False
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "violence-detection"


class TestWeatherEnrichmentWithModelInfo:
    """Tests for WeatherEnrichment with model_info field."""

    def test_weather_with_model_info(self) -> None:
        """Test weather enrichment includes model info."""
        data = {
            "condition": "clear",
            "confidence": 0.95,
            "model_info": {
                "model_name": "weather-classifier",
                "inference_time_ms": 15.3,
            },
        }
        enrichment = WeatherEnrichment.model_validate(data)

        assert enrichment.condition == "clear"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "weather-classifier"


class TestPoseEnrichmentWithModelInfo:
    """Tests for PoseEnrichment with model_info field."""

    def test_pose_with_model_info(self) -> None:
        """Test pose enrichment includes model info."""
        data = {
            "posture": "standing",
            "alerts": [],
            "keypoints": [[100, 150, 0.9], [120, 160, 0.85]],
            "keypoint_count": 17,
            "confidence": 0.82,
            "model_info": {
                "model_name": "vitpose",
                "inference_time_ms": 52.8,
            },
        }
        enrichment = PoseEnrichment.model_validate(data)

        assert enrichment.posture == "standing"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "vitpose"


class TestDepthEnrichmentWithModelInfo:
    """Tests for DepthEnrichment with model_info field."""

    def test_depth_with_model_info(self) -> None:
        """Test depth enrichment includes model info."""
        data = {
            "estimated_distance_m": 4.2,
            "confidence": 0.78,
            "model_info": {
                "model_name": "depth-anything-v2",
                "inference_time_ms": 38.5,
            },
        }
        enrichment = DepthEnrichment.model_validate(data)

        assert enrichment.estimated_distance_m == 4.2
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "depth-anything-v2"


class TestImageQualityEnrichmentWithModelInfo:
    """Tests for ImageQualityEnrichment with model_info field."""

    def test_image_quality_with_model_info(self) -> None:
        """Test image quality enrichment includes model info."""
        data = {
            "score": 85.0,
            "is_blurry": False,
            "is_low_quality": False,
            "quality_issues": [],
            "model_info": {
                "model_name": "brisque-quality",
                "inference_time_ms": 12.4,
            },
        }
        enrichment = ImageQualityEnrichment.model_validate(data)

        assert enrichment.score == 85.0
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "brisque-quality"


class TestPetEnrichmentWithModelInfo:
    """Tests for PetEnrichment with model_info field."""

    def test_pet_with_model_info(self) -> None:
        """Test pet enrichment includes model info."""
        data = {
            "detected": True,
            "type": "dog",
            "confidence": 0.94,
            "is_household_pet": True,
            "model_info": {
                "model_name": "pet-classifier",
                "inference_time_ms": 22.1,
            },
        }
        enrichment = PetEnrichment.model_validate(data)

        assert enrichment.detected is True
        assert enrichment.type == "dog"
        assert enrichment.model_info is not None
        assert enrichment.model_info.model_name == "pet-classifier"


class TestEnrichmentResponseWithModelInfo:
    """Tests for EnrichmentResponse with nested model_info fields."""

    def test_enrichment_response_with_all_model_info(self) -> None:
        """Test complete enrichment response with model info in all fields."""
        from datetime import UTC, datetime

        data = {
            "detection_id": 12345,
            "enriched_at": datetime.now(UTC).isoformat(),
            "license_plate": {
                "detected": True,
                "text": "ABC-1234",
                "confidence": 0.92,
                "model_info": {"model_name": "yolov11-license-plate"},
            },
            "face": {
                "detected": True,
                "count": 1,
                "confidence": 0.88,
                "model_info": {"model_name": "yolov11-face"},
            },
            "vehicle": {
                "type": "sedan",
                "confidence": 0.91,
                "model_info": {"model_name": "vehicle-classifier"},
            },
            "pose": {
                "posture": "standing",
                "alerts": [],
                "model_info": {"model_name": "vitpose"},
            },
            "processing_time_ms": 125.5,
            "errors": [],
        }
        response = EnrichmentResponse.model_validate(data)

        assert response.detection_id == 12345
        # Access nested model_info through dicts since response allows dict | Type
        lp = response.license_plate
        if isinstance(lp, dict):
            assert lp.get("model_info", {}).get("model_name") == "yolov11-license-plate"
        else:
            assert lp.model_info is not None
            assert lp.model_info.model_name == "yolov11-license-plate"

    def test_enrichment_response_backward_compatible(self) -> None:
        """Test enrichment response works without model_info (backward compat)."""
        data = {
            "detection_id": 12345,
            "license_plate": {"detected": False},
            "face": {"detected": False, "count": 0},
            "violence": {"detected": False, "score": 0.0},
        }
        response = EnrichmentResponse.model_validate(data)

        assert response.detection_id == 12345
