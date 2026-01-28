"""Pydantic schemas for enrichment API endpoints.

These schemas provide structured access to the 18+ vision model results
that are run on each detection during the enrichment pipeline.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentModelInfo(BaseModel):
    """Information about the AI model that produced an enrichment result (NEM-3535).

    Exposes which model processed each enrichment, enabling model performance
    tracking and debugging.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model_name": "yolov11-face",
                "model_version": "1.0.0",
                "inference_time_ms": 25.3,
            }
        }
    )

    model_name: str = Field(..., description="Name of the AI model that produced this enrichment")
    model_version: str | None = Field(None, description="Version of the model (if available)")
    inference_time_ms: float | None = Field(
        None, ge=0.0, description="Time taken for model inference in milliseconds"
    )


class LicensePlateEnrichment(BaseModel):
    """License plate detection and OCR results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detected": True,
                "confidence": 0.92,
                "text": "ABC-1234",
                "ocr_confidence": 0.88,
                "bbox": [100.0, 200.0, 300.0, 250.0],
            }
        }
    )

    detected: bool = Field(False, description="Whether a license plate was detected")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    text: str | None = Field(None, description="OCR-extracted plate text")
    ocr_confidence: float | None = Field(None, ge=0.0, le=1.0, description="OCR confidence")
    bbox: list[float] | None = Field(None, description="Bounding box [x1, y1, x2, y2]")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class FaceEnrichment(BaseModel):
    """Face detection results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detected": True,
                "count": 1,
                "confidence": 0.88,
            }
        }
    )

    detected: bool = Field(False, description="Whether faces were detected")
    count: int = Field(0, ge=0, description="Number of faces detected")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Highest face confidence")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class VehicleEnrichment(BaseModel):
    """Vehicle classification results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "sedan",
                "color": "silver",
                "confidence": 0.91,
                "is_commercial": False,
            }
        }
    )

    type: str | None = Field(None, description="Vehicle type (sedan, suv, truck, etc.)")
    color: str | None = Field(None, description="Vehicle color (if detected)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    is_commercial: bool | None = Field(None, description="Whether vehicle is commercial/delivery")
    damage_detected: bool | None = Field(None, description="Whether vehicle damage was detected")
    damage_types: list[str] | None = Field(None, description="Types of damage detected")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class ClothingEnrichment(BaseModel):
    """Clothing classification and segmentation results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upper": "red t-shirt",
                "lower": "blue jeans",
                "is_suspicious": False,
                "is_service_uniform": False,
                "has_face_covered": False,
                "has_bag": True,
            }
        }
    )

    upper: str | None = Field(None, description="Upper body clothing description")
    lower: str | None = Field(None, description="Lower body clothing description")
    is_suspicious: bool | None = Field(
        None, description="Whether clothing is flagged as suspicious"
    )
    is_service_uniform: bool | None = Field(None, description="Whether wearing service uniform")
    has_face_covered: bool | None = Field(
        None, description="Whether face is covered (hat/sunglasses/mask)"
    )
    has_bag: bool | None = Field(None, description="Whether person is carrying a bag")
    clothing_items: list[str] | None = Field(None, description="List of detected clothing items")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class ViolenceEnrichment(BaseModel):
    """Violence detection results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detected": False,
                "score": 0.12,
                "confidence": 0.88,
            }
        }
    )

    detected: bool = Field(False, description="Whether violence was detected")
    score: float = Field(0.0, ge=0.0, le=1.0, description="Violence probability score")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Model confidence")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class WeatherEnrichment(BaseModel):
    """Weather classification results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "condition": "clear",
                "confidence": 0.95,
            }
        }
    )

    condition: str | None = Field(None, description="Weather condition (clear, rain, fog, etc.)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class PoseEnrichment(BaseModel):
    """Pose estimation results from ViTPose integration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "posture": "standing",
                "alerts": ["person_crouching"],
                "security_alerts": ["person_crouching"],
                "keypoints": [[100, 150, 0.9], [120, 160, 0.85]],
                "keypoint_count": 17,
                "confidence": 0.82,
            }
        }
    )

    posture: str | None = Field(None, description="Detected posture (standing, sitting, etc.)")
    alerts: list[str] = Field(default_factory=list, description="Pose-related security alerts")
    security_alerts: list[str] = Field(
        default_factory=list, description="Backward compatibility alias for alerts"
    )
    keypoints: list[list[float]] | None = Field(
        None, description="Body keypoints [[x, y, conf], ...]"
    )
    keypoint_count: int | None = Field(None, ge=0, description="Number of detected keypoints")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Pose estimation confidence")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class ActionEnrichment(BaseModel):
    """Action recognition results from X-CLIP temporal analysis.

    Provides detected actions from video frame sequences, identifying
    security-relevant activities like loitering, climbing, or delivering packages.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "delivering package",
                "confidence": 0.85,
                "is_suspicious": False,
                "all_scores": {
                    "delivering package": 0.85,
                    "walking normally": 0.10,
                    "loitering": 0.05,
                },
            }
        }
    )

    action: str | None = Field(
        None, description="Detected action (walking, running, delivering, loitering, etc.)"
    )
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score for detected action"
    )
    is_suspicious: bool | None = Field(
        None, description="Whether the detected action is flagged as security-relevant"
    )
    all_scores: dict[str, float] | None = Field(
        None, description="Confidence scores for all candidate actions"
    )
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class DepthEnrichment(BaseModel):
    """Depth estimation results (placeholder for future Depth Anything V2)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "estimated_distance_m": 4.2,
                "confidence": 0.78,
            }
        }
    )

    estimated_distance_m: float | None = Field(
        None, ge=0.0, description="Estimated distance in meters"
    )
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Estimation confidence")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class ImageQualityEnrichment(BaseModel):
    """Image quality assessment results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 0.85,
                "is_blurry": False,
                "is_low_quality": False,
                "quality_issues": [],
            }
        }
    )

    score: float | None = Field(None, ge=0.0, le=100.0, description="Quality score (0-100)")
    is_blurry: bool | None = Field(None, description="Whether image is blurry")
    is_low_quality: bool | None = Field(None, description="Whether image has low quality")
    quality_issues: list[str] | None = Field(None, description="List of detected quality issues")
    quality_change_detected: bool | None = Field(
        None, description="Whether sudden quality change was detected"
    )
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class PetEnrichment(BaseModel):
    """Pet classification results for false positive reduction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detected": True,
                "type": "dog",
                "confidence": 0.94,
                "is_household_pet": True,
            }
        }
    )

    detected: bool = Field(False, description="Whether a pet was detected")
    type: str | None = Field(None, description="Pet type (cat, dog)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    is_household_pet: bool | None = Field(None, description="Whether classified as household pet")
    model_info: EnrichmentModelInfo | None = Field(
        None, description="Model that produced this result"
    )


class EnrichmentResponse(BaseModel):
    """Structured enrichment data for a single detection.

    Contains results from all vision models run during the enrichment pipeline.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "detection_id": 12345,
                "enriched_at": "2026-01-03T10:30:00Z",
                "license_plate": {
                    "detected": True,
                    "confidence": 0.92,
                    "text": "ABC-1234",
                },
                "face": {"detected": True, "count": 1, "confidence": 0.88},
                "vehicle": {"type": "sedan", "color": "silver", "confidence": 0.91},
                "clothing": {"upper": "red t-shirt", "lower": "blue jeans"},
                "violence": {"detected": False, "score": 0.12},
                "weather": {"condition": "clear", "confidence": 0.95},
                "pose": None,
                "action": {
                    "action": "delivering package",
                    "confidence": 0.85,
                    "is_suspicious": False,
                },
                "depth": None,
                "image_quality": {"score": 0.85, "is_blurry": False},
                "pet": None,
                "processing_time_ms": 125.5,
                "errors": [],
            }
        },
    )

    detection_id: int = Field(..., description="Detection ID")
    enriched_at: datetime | None = Field(
        None, description="Timestamp when enrichment was performed"
    )
    license_plate: LicensePlateEnrichment | dict[str, Any] = Field(
        default_factory=lambda: LicensePlateEnrichment(),
        description="License plate detection results",
    )
    face: FaceEnrichment | dict[str, Any] = Field(
        default_factory=lambda: FaceEnrichment(),
        description="Face detection results",
    )
    vehicle: VehicleEnrichment | dict[str, Any] | None = Field(
        None, description="Vehicle classification results"
    )
    clothing: ClothingEnrichment | dict[str, Any] | None = Field(
        None, description="Clothing analysis results"
    )
    violence: ViolenceEnrichment | dict[str, Any] = Field(
        default_factory=lambda: ViolenceEnrichment(),
        description="Violence detection results",
    )
    weather: WeatherEnrichment | dict[str, Any] | None = Field(
        None, description="Weather classification results"
    )
    pose: PoseEnrichment | dict[str, Any] | None = Field(
        None, description="Pose estimation results"
    )
    action: ActionEnrichment | dict[str, Any] | None = Field(
        None, description="Action recognition results"
    )
    depth: DepthEnrichment | dict[str, Any] | None = Field(
        None, description="Depth estimation results"
    )
    image_quality: ImageQualityEnrichment | dict[str, Any] | None = Field(
        None, description="Image quality assessment"
    )
    pet: PetEnrichment | dict[str, Any] | None = Field(
        None, description="Pet classification results"
    )
    processing_time_ms: float | None = Field(
        None, ge=0.0, description="Enrichment processing time in milliseconds"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors encountered during enrichment"
    )


class EventEnrichmentsResponse(BaseModel):
    """Enrichment data for all detections in an event with pagination support."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 100,
                "enrichments": [
                    {
                        "detection_id": 1,
                        "enriched_at": "2026-01-03T10:30:00Z",
                        "license_plate": {"detected": True, "text": "ABC-1234"},
                        "face": {"detected": False, "count": 0},
                        "violence": {"detected": False, "score": 0.0},
                    },
                    {
                        "detection_id": 2,
                        "enriched_at": "2026-01-03T10:30:05Z",
                        "license_plate": {"detected": False},
                        "face": {"detected": True, "count": 1},
                        "violence": {"detected": False, "score": 0.0},
                    },
                ],
                "count": 2,
                "total": 10,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            }
        }
    )

    event_id: int = Field(..., description="Event ID")
    enrichments: list[EnrichmentResponse] = Field(..., description="Enrichment data per detection")
    count: int = Field(..., description="Number of enrichments in this response (page size)")
    total: int = Field(
        ..., description="Total number of detections with enrichment data for this event"
    )
    limit: int = Field(..., description="Maximum number of results requested")
    offset: int = Field(..., description="Number of results skipped")
    has_more: bool = Field(..., description="Whether there are more results available")
