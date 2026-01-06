"""Pydantic schemas for validating enrichment_data JSONB field.

These schemas define the structure of the raw enrichment data stored in the
Detection model's enrichment_data JSONB column. They provide validation for
data coming from 18+ vision models in the enrichment pipeline.

IMPORTANT: These schemas are designed to gracefully handle legacy data that
may not match the current schema. Validation is permissive - it coerces data
where possible and logs warnings for invalid data rather than raising errors.

Schema corresponds to the raw database format, NOT the transformed API response
format (see enrichment.py for API response schemas).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Individual enrichment data schemas (matching raw database storage format)
# ============================================================================


class LicensePlateItem(BaseModel):
    """Schema for a single license plate detection."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields from legacy data

    bbox: list[float] | None = Field(None, description="Bounding box [x1, y1, x2, y2]")
    text: str | None = Field(None, description="OCR-extracted plate text")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    ocr_confidence: float | None = Field(None, ge=0.0, le=1.0, description="OCR confidence score")
    source_detection_id: int | None = Field(None, description="Source detection ID")

    @field_validator("confidence", "ocr_confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            # Clamp to valid range rather than reject
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None


class FaceItem(BaseModel):
    """Schema for a single face detection."""

    model_config = ConfigDict(extra="allow")

    bbox: list[float] | None = Field(None, description="Bounding box [x1, y1, x2, y2]")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    source_detection_id: int | None = Field(None, description="Source detection ID")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None


class ViolenceDetectionData(BaseModel):
    """Schema for violence detection results."""

    model_config = ConfigDict(extra="allow")

    is_violent: bool = Field(False, description="Whether violence was detected")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Model confidence")
    predicted_class: str | None = Field(None, description="Predicted class label")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None

    @field_validator("is_violent", mode="before")
    @classmethod
    def coerce_is_violent(cls, v: Any) -> bool:
        """Coerce is_violent to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v) if v is not None else False


class VehicleClassificationData(BaseModel):
    """Schema for vehicle classification results (per-detection)."""

    model_config = ConfigDict(extra="allow")

    vehicle_type: str | None = Field(None, description="Vehicle type (sedan, suv, etc.)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    display_name: str | None = Field(None, description="Human-readable display name")
    is_commercial: bool | None = Field(None, description="Whether vehicle is commercial")
    all_scores: dict[str, float] | None = Field(None, description="All classification scores")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None


class VehicleDamageData(BaseModel):
    """Schema for vehicle damage detection results (per-detection)."""

    model_config = ConfigDict(extra="allow")

    has_damage: bool = Field(False, description="Whether damage was detected")
    damage_types: list[str] | None = Field(None, description="Types of damage detected")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence")

    @field_validator("has_damage", mode="before")
    @classmethod
    def coerce_has_damage(cls, v: Any) -> bool:
        """Coerce has_damage to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v) if v is not None else False


class ClothingClassificationData(BaseModel):
    """Schema for clothing classification results (per-detection)."""

    model_config = ConfigDict(extra="allow")

    top_category: str | None = Field(None, description="Top clothing category")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    all_scores: dict[str, float] | None = Field(None, description="All classification scores")
    is_suspicious: bool | None = Field(None, description="Whether clothing is suspicious")
    is_service_uniform: bool | None = Field(None, description="Whether wearing service uniform")
    raw_description: str | None = Field(None, description="Raw description from model")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None


class ClothingSegmentationData(BaseModel):
    """Schema for clothing segmentation results (per-detection)."""

    model_config = ConfigDict(extra="allow")

    clothing_items: list[str] | None = Field(None, description="List of detected clothing items")
    has_face_covered: bool | None = Field(None, description="Whether face is covered")
    has_bag: bool | None = Field(None, description="Whether person has a bag")


class PetClassificationData(BaseModel):
    """Schema for pet classification results (per-detection)."""

    model_config = ConfigDict(extra="allow")

    animal_type: str | None = Field(None, description="Animal type (cat, dog, etc.)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence")
    is_household_pet: bool | None = Field(None, description="Whether classified as household pet")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        """Coerce confidence values to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return None


class ImageQualityData(BaseModel):
    """Schema for image quality assessment results."""

    model_config = ConfigDict(extra="allow")

    quality_score: float | None = Field(None, ge=0.0, le=100.0, description="Quality score (0-100)")
    is_blurry: bool | None = Field(None, description="Whether image is blurry")
    is_low_quality: bool | None = Field(None, description="Whether image has low quality")
    is_good_quality: bool | None = Field(None, description="Whether image has good quality")
    quality_issues: list[str] | None = Field(None, description="List of quality issues")

    @field_validator("quality_score", mode="before")
    @classmethod
    def coerce_quality_score(cls, v: Any) -> float | None:
        """Coerce quality score to valid range or None."""
        if v is None:
            return None
        try:
            val = float(v)
            # Clamp to valid range
            return max(0.0, min(100.0, val))
        except (TypeError, ValueError):
            return None


# ============================================================================
# Main enrichment data schema
# ============================================================================


class EnrichmentDataSchema(BaseModel):
    """Schema for validating the complete enrichment_data JSONB field.

    This schema validates the raw enrichment data as stored in the database.
    It is permissive and handles legacy data gracefully:
    - Extra fields are allowed (for forward compatibility)
    - Invalid values are coerced where possible
    - Missing fields use sensible defaults

    Usage:
        # Validate enrichment data
        result = validate_enrichment_data(raw_data)
        if result.is_valid:
            validated_data = result.data
        else:
            # Log warnings, use original data
            logger.warning(f"Enrichment validation warnings: {result.warnings}")
    """

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for forward compatibility
        json_schema_extra={
            "example": {
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
        },
    )

    # License plate detections
    license_plates: list[LicensePlateItem] | None = Field(
        None, description="List of detected license plates"
    )

    # Face detections
    faces: list[FaceItem] | None = Field(None, description="List of detected faces")

    # Violence detection
    violence_detection: ViolenceDetectionData | None = Field(
        None, description="Violence detection results"
    )

    # Per-detection classifications (keyed by detection ID as string)
    vehicle_classifications: dict[str, VehicleClassificationData] | None = Field(
        None, description="Vehicle classification results by detection ID"
    )
    vehicle_damage: dict[str, VehicleDamageData] | None = Field(
        None, description="Vehicle damage results by detection ID"
    )
    clothing_classifications: dict[str, ClothingClassificationData] | None = Field(
        None, description="Clothing classification results by detection ID"
    )
    clothing_segmentation: dict[str, ClothingSegmentationData] | None = Field(
        None, description="Clothing segmentation results by detection ID"
    )
    pet_classifications: dict[str, PetClassificationData] | None = Field(
        None, description="Pet classification results by detection ID"
    )

    # Image quality assessment
    image_quality: ImageQualityData | None = Field(
        None, description="Image quality assessment results"
    )

    # Quality change detection
    quality_change_detected: bool | None = Field(
        None, description="Whether sudden quality change was detected"
    )
    quality_change_description: str | None = Field(
        None, description="Description of quality change"
    )

    # Processing metadata
    processing_time_ms: float | None = Field(
        None, ge=0.0, description="Total processing time in milliseconds"
    )
    errors: list[str] | None = Field(None, description="Errors encountered during enrichment")

    @field_validator("processing_time_ms", mode="before")
    @classmethod
    def coerce_processing_time(cls, v: Any) -> float | None:
        """Coerce processing time to valid float or None."""
        if v is None:
            return None
        try:
            val = float(v)
            return max(0.0, val)  # Can't be negative
        except (TypeError, ValueError):
            return None

    @field_validator("errors", mode="before")
    @classmethod
    def coerce_errors(cls, v: Any) -> list[str] | None:
        """Coerce errors to list of strings."""
        if v is None:
            return None
        if isinstance(v, list):
            return [str(e) for e in v]
        return [str(v)]

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_formats(cls, data: Any) -> Any:
        """Handle legacy data formats for backward compatibility.

        This validator handles various legacy formats that may exist in the database:
        - Old field names that have been renamed
        - Different data structures from earlier versions
        """
        if not isinstance(data, dict):
            return data

        # Handle legacy "vehicle" field (older format used dict, not nested by detection ID)
        if "vehicle" in data and "vehicle_classifications" not in data:
            vehicle_data = data.get("vehicle")
            if isinstance(vehicle_data, dict) and "type" in vehicle_data:
                # Convert legacy format to new format
                data["vehicle_classifications"] = {
                    "legacy": {
                        "vehicle_type": vehicle_data.get("type"),
                        "confidence": vehicle_data.get("confidence"),
                        "is_commercial": None,
                    }
                }

        # Handle legacy "pet" field
        if "pet" in data and "pet_classifications" not in data:
            pet_data = data.get("pet")
            if isinstance(pet_data, dict) and "type" in pet_data:
                data["pet_classifications"] = {
                    "legacy": {
                        "animal_type": pet_data.get("type"),
                        "confidence": pet_data.get("confidence"),
                        "is_household_pet": None,
                    }
                }

        # Handle legacy "license_plate" singular field
        if "license_plate" in data and "license_plates" not in data:
            lp_data = data.get("license_plate")
            if isinstance(lp_data, dict):
                data["license_plates"] = [
                    {
                        "text": lp_data.get("text"),
                        "confidence": lp_data.get("confidence"),
                    }
                ]

        return data


# ============================================================================
# Validation result and helper functions
# ============================================================================


class EnrichmentValidationResult:
    """Result of enrichment data validation.

    Attributes:
        is_valid: Whether the data passed validation
        data: The validated/coerced data (or original if invalid)
        warnings: List of warning messages for non-critical issues
        errors: List of error messages if validation failed
    """

    __slots__ = ("data", "errors", "is_valid", "warnings")

    def __init__(
        self,
        is_valid: bool,
        data: dict[str, Any] | None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.is_valid = is_valid
        self.data = data
        self.warnings = warnings or []
        self.errors = errors or []


def validate_enrichment_data(
    data: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> EnrichmentValidationResult:
    """Validate enrichment data from the database.

    This function validates enrichment data gracefully:
    - Returns validated/coerced data when possible
    - Logs warnings for non-critical issues
    - Only fails in strict mode for critical errors

    Args:
        data: The raw enrichment data dict from the database
        strict: If True, raise on validation errors. If False (default),
                return original data with warnings.

    Returns:
        EnrichmentValidationResult with validation status and data

    Examples:
        # Normal usage - graceful validation
        result = validate_enrichment_data(raw_data)
        if result.warnings:
            logger.warning(f"Enrichment validation: {result.warnings}")
        use_data = result.data

        # Strict mode - for new data being written
        result = validate_enrichment_data(new_data, strict=True)
        if not result.is_valid:
            raise ValueError(f"Invalid enrichment data: {result.errors}")
    """
    if data is None:
        return EnrichmentValidationResult(is_valid=True, data=None)

    if not isinstance(data, dict):
        return EnrichmentValidationResult(
            is_valid=False,
            data=None,
            errors=["enrichment_data must be a dictionary"],
        )

    warnings: list[str] = []
    errors: list[str] = []

    try:
        # Validate with Pydantic
        validated = EnrichmentDataSchema.model_validate(data)
        validated_dict = validated.model_dump(exclude_none=False, exclude_unset=False)

        # Extra fields are automatically preserved by Pydantic's extra="allow"
        # No warnings needed since this is intentional for forward compatibility

        return EnrichmentValidationResult(
            is_valid=True,
            data=validated_dict,
            warnings=warnings,
        )

    except ValidationError as e:
        error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        errors.extend(error_messages)

        if strict:
            return EnrichmentValidationResult(
                is_valid=False,
                data=data,  # Return original on failure
                errors=errors,
            )

        # In non-strict mode, return original data with warnings
        logger.warning(
            "Enrichment data validation failed, using original data",
            extra={"errors": error_messages},
        )
        return EnrichmentValidationResult(
            is_valid=True,  # Still considered valid for non-strict
            data=data,
            warnings=[f"Validation error (data preserved): {e}" for e in error_messages],
        )


def coerce_enrichment_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Coerce enrichment data to valid schema, returning validated data.

    This is a convenience function that validates and returns the coerced data.
    For detailed validation results, use validate_enrichment_data() instead.

    Args:
        data: The raw enrichment data dict

    Returns:
        Validated/coerced data dict, or original data if validation failed
    """
    result = validate_enrichment_data(data)
    return result.data
