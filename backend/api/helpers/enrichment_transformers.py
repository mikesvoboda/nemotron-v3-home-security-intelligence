"""Enrichment data transformation helpers.

This module provides helper classes for transforming raw enrichment data from the
database (JSONB format) into structured API response format.

Addresses:
- NEM-1349: Reduces code duplication by using a base extractor class
- NEM-1351: Validates enrichment_data schema before transformation
- NEM-1307: Breaks down transformation into smaller, focused helper classes

Design:
- BaseEnrichmentExtractor: Abstract base class defining the extraction interface
- Individual extractors for each enrichment type (license plate, face, vehicle, etc.)
- EnrichmentTransformer: Orchestrates all extractors and validates input

Usage:
    transformer = EnrichmentTransformer()
    result = transformer.transform(
        detection_id=1,
        enrichment_data=raw_data,
        detected_at=datetime.now(),
    )
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from backend.api.schemas.enrichment_data import validate_enrichment_data
from backend.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Error Sanitization (moved from detections.py for reuse)
# ============================================================================

# Known error categories that can be preserved in sanitized output
_ERROR_CATEGORIES = [
    "license plate detection",
    "face detection",
    "violence detection",
    "clothing classification",
    "clothing segmentation",
    "vehicle damage detection",
    "vehicle classification",
    "image quality assessment",
    "pet classification",
    "vision extraction",
    "re-identification",
    "scene change detection",
    "processing",
]


def sanitize_errors(errors: list[str]) -> list[str]:
    """Sanitize error messages to remove sensitive internal details.

    Security: This function removes file paths, IP addresses, stack traces,
    and other internal details from error messages before exposing them
    via the API.

    Args:
        errors: List of raw error messages from enrichment processing

    Returns:
        List of sanitized error messages safe for API exposure
    """
    if not errors:
        return []

    sanitized = []
    for error in errors:
        # Extract the error category (e.g., "License plate detection")
        category = None
        error_lower = error.lower()
        for cat in _ERROR_CATEGORIES:
            if cat in error_lower:
                category = cat.title()
                break

        # If we found a category, create a generic message
        if category:
            sanitized.append(f"{category} failed")
        else:
            # For unknown error types, use a completely generic message
            sanitized.append("Enrichment processing error")

    return sanitized


# ============================================================================
# Base Extractor Class (NEM-1349: Reduce duplication)
# ============================================================================


class BaseEnrichmentExtractor(ABC):
    """Abstract base class for enrichment data extractors.

    Each subclass handles extraction of a specific enrichment type from the
    raw database format to the API response format.
    """

    @property
    @abstractmethod
    def enrichment_key(self) -> str:
        """The key in enrichment_data to look for this enrichment type."""
        ...

    @property
    @abstractmethod
    def default_value(self) -> dict[str, Any] | None:
        """Default value to return when no enrichment data is found."""
        ...

    @abstractmethod
    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract and transform the enrichment data.

        Args:
            enrichment_data: Raw enrichment data from database

        Returns:
            Transformed data for API response, or None if not found
        """
        ...

    def _get_first_item_from_dict(
        self, data: dict[str, Any], key: str
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Get the first item from a dictionary-keyed collection.

        Many enrichment types store data keyed by detection ID. This helper
        extracts the first item for cases where we only need one result.

        Args:
            data: The enrichment data dictionary
            key: The key containing the collection

        Returns:
            Tuple of (detection_id, item_data) or (None, None) if not found
        """
        collection = data.get(key, {})
        if not collection or not isinstance(collection, dict):
            return None, None

        first_key = next(iter(collection), None)
        if first_key is None:
            return None, None

        return first_key, collection[first_key]


# ============================================================================
# Individual Extractors (NEM-1307: Smaller helper classes)
# ============================================================================


class LicensePlateExtractor(BaseEnrichmentExtractor):
    """Extract license plate data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "license_plates"

    @property
    def default_value(self) -> dict[str, Any]:
        return {"detected": False}

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any]:
        """Extract license plate data.

        Uses first detected plate if multiple exist.
        """
        license_plates = enrichment_data.get(self.enrichment_key, [])
        if not license_plates:
            return self.default_value

        plate = license_plates[0]  # Use first plate
        return {
            "detected": True,
            "confidence": plate.get("confidence"),
            "text": plate.get("text"),
            "ocr_confidence": plate.get("ocr_confidence"),
            "bbox": plate.get("bbox"),
        }


class FaceExtractor(BaseEnrichmentExtractor):
    """Extract face detection data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "faces"

    @property
    def default_value(self) -> dict[str, Any]:
        return {"detected": False, "count": 0}

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any]:
        """Extract face detection data.

        Returns count and max confidence across all detected faces.
        """
        faces = enrichment_data.get(self.enrichment_key, [])
        if not faces:
            return self.default_value

        return {
            "detected": True,
            "count": len(faces),
            "confidence": max(f.get("confidence", 0) for f in faces),
        }


class ViolenceExtractor(BaseEnrichmentExtractor):
    """Extract violence detection data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "violence_detection"

    @property
    def default_value(self) -> dict[str, Any]:
        return {"detected": False, "score": 0.0}

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any]:
        """Extract violence detection data."""
        violence_data = enrichment_data.get(self.enrichment_key)
        if not violence_data:
            return self.default_value

        return {
            "detected": violence_data.get("is_violent", False),
            "score": violence_data.get("confidence", 0.0),
            "confidence": violence_data.get("confidence"),
        }


class VehicleExtractor(BaseEnrichmentExtractor):
    """Extract vehicle classification and damage data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "vehicle_classifications"

    @property
    def default_value(self) -> None:
        return None

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract vehicle classification data with damage info if present."""
        first_key, vc = self._get_first_item_from_dict(enrichment_data, self.enrichment_key)
        if not first_key or not vc:
            return self.default_value

        vehicle_response = {
            "type": vc.get("vehicle_type"),
            "color": None,  # Color not currently captured in enrichment
            "confidence": vc.get("confidence"),
            "is_commercial": vc.get("is_commercial"),
            "damage_detected": None,
            "damage_types": None,
        }

        # Add damage info if present for same detection
        vehicle_damage = enrichment_data.get("vehicle_damage", {})
        if first_key in vehicle_damage:
            vd = vehicle_damage[first_key]
            vehicle_response["damage_detected"] = vd.get("has_damage", False)
            vehicle_response["damage_types"] = vd.get("damage_types", [])

        return vehicle_response


class ClothingExtractor(BaseEnrichmentExtractor):
    """Extract clothing classification and segmentation data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "clothing_classifications"

    @property
    def default_value(self) -> None:
        return None

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract clothing data from both classification and segmentation."""
        clothing_classifications = enrichment_data.get(self.enrichment_key, {})
        clothing_segmentation = enrichment_data.get("clothing_segmentation", {})

        if not clothing_classifications and not clothing_segmentation:
            return self.default_value

        clothing_response: dict[str, Any] = {}

        # Extract from classifications
        if clothing_classifications:
            first_key = next(iter(clothing_classifications), None)
            if first_key:
                cc = clothing_classifications[first_key]
                # Parse raw description to extract upper/lower
                raw_desc = cc.get("raw_description", "")
                if ", " in raw_desc:
                    parts = raw_desc.split(", ")
                elif raw_desc:
                    parts = [raw_desc]  # Single-item description without comma
                else:
                    parts = [cc.get("top_category")]  # Fallback to top_category
                clothing_response["upper"] = parts[0] if parts else None
                clothing_response["lower"] = parts[1] if len(parts) > 1 else None
                clothing_response["is_suspicious"] = cc.get("is_suspicious")
                clothing_response["is_service_uniform"] = cc.get("is_service_uniform")

        # Extract from segmentation
        if clothing_segmentation:
            first_key = next(iter(clothing_segmentation), None)
            if first_key:
                cs = clothing_segmentation[first_key]
                clothing_response["has_face_covered"] = cs.get("has_face_covered")
                clothing_response["has_bag"] = cs.get("has_bag")
                clothing_response["clothing_items"] = cs.get("clothing_items")

        return clothing_response if clothing_response else self.default_value


class ImageQualityExtractor(BaseEnrichmentExtractor):
    """Extract image quality assessment data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "image_quality"

    @property
    def default_value(self) -> None:
        return None

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract image quality data."""
        iq = enrichment_data.get(self.enrichment_key)
        if not iq:
            return self.default_value

        return {
            "score": iq.get("quality_score"),
            "is_blurry": iq.get("is_blurry"),
            "is_low_quality": iq.get("is_low_quality"),
            "quality_issues": iq.get("quality_issues", []),
            "quality_change_detected": enrichment_data.get("quality_change_detected"),
        }


class PetExtractor(BaseEnrichmentExtractor):
    """Extract pet classification data from enrichment."""

    @property
    def enrichment_key(self) -> str:
        return "pet_classifications"

    @property
    def default_value(self) -> None:
        return None

    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract pet classification data."""
        first_key, pc = self._get_first_item_from_dict(enrichment_data, self.enrichment_key)
        if not first_key or not pc:
            return self.default_value

        return {
            "detected": True,
            "type": pc.get("animal_type"),
            "confidence": pc.get("confidence"),
            "is_household_pet": pc.get("is_household_pet"),
        }


# ============================================================================
# Main Transformer Class (NEM-1351: Validates before transformation)
# ============================================================================


class EnrichmentTransformer:
    """Orchestrates enrichment data transformation from database to API format.

    This class:
    1. Validates the enrichment data schema (NEM-1351)
    2. Uses individual extractors to transform each enrichment type (NEM-1307)
    3. Reduces code duplication through shared base class (NEM-1349)
    """

    def __init__(self, validate_schema: bool = True) -> None:
        """Initialize the transformer.

        Args:
            validate_schema: Whether to validate enrichment data before transformation.
                            Set to False for performance-critical paths where data
                            is known to be valid.
        """
        self.validate_schema = validate_schema

        # Initialize extractors
        self._license_plate_extractor = LicensePlateExtractor()
        self._face_extractor = FaceExtractor()
        self._violence_extractor = ViolenceExtractor()
        self._vehicle_extractor = VehicleExtractor()
        self._clothing_extractor = ClothingExtractor()
        self._image_quality_extractor = ImageQualityExtractor()
        self._pet_extractor = PetExtractor()

    def transform(
        self,
        detection_id: int,
        enrichment_data: dict[str, Any] | None,
        detected_at: datetime | None,
    ) -> dict[str, Any]:
        """Transform raw enrichment data from database to structured API response.

        Args:
            detection_id: Detection ID
            enrichment_data: Raw JSONB data from the detection
            detected_at: Detection timestamp (used as fallback for enriched_at)

        Returns:
            Dictionary matching EnrichmentResponse schema
        """
        empty_response = self._get_empty_response(detection_id, detected_at)

        if enrichment_data is None:
            return empty_response

        # NEM-1351: Validate schema before transformation
        if self.validate_schema:
            validation_result = validate_enrichment_data(enrichment_data)
            if not validation_result.is_valid:
                logger.warning(
                    f"Enrichment data validation failed for detection {detection_id}: "
                    f"{validation_result.errors}"
                )
                # Use validated/coerced data if available, otherwise original
                if validation_result.data is not None:
                    enrichment_data = validation_result.data
            elif validation_result.warnings:
                logger.debug(
                    f"Enrichment data validation warnings for detection {detection_id}: "
                    f"{validation_result.warnings}"
                )
                # Use coerced data with warnings
                if validation_result.data is not None:
                    enrichment_data = validation_result.data

        return {
            "detection_id": detection_id,
            "enriched_at": detected_at,
            "license_plate": self._license_plate_extractor.extract(enrichment_data),
            "face": self._face_extractor.extract(enrichment_data),
            "vehicle": self._vehicle_extractor.extract(enrichment_data),
            "clothing": self._clothing_extractor.extract(enrichment_data),
            "violence": self._violence_extractor.extract(enrichment_data),
            "weather": None,  # Placeholder - not currently in enrichment pipeline
            "pose": None,  # Placeholder for future ViTPose
            "depth": None,  # Placeholder for future Depth Anything V2
            "image_quality": self._image_quality_extractor.extract(enrichment_data),
            "pet": self._pet_extractor.extract(enrichment_data),
            "processing_time_ms": enrichment_data.get("processing_time_ms"),
            # Security: Sanitize error messages to remove sensitive internal details
            "errors": sanitize_errors(enrichment_data.get("errors", [])),
        }

    def _get_empty_response(
        self, detection_id: int, detected_at: datetime | None
    ) -> dict[str, Any]:
        """Get the default empty response structure."""
        return {
            "detection_id": detection_id,
            "enriched_at": detected_at,
            "license_plate": self._license_plate_extractor.default_value,
            "face": self._face_extractor.default_value,
            "vehicle": self._vehicle_extractor.default_value,
            "clothing": self._clothing_extractor.default_value,
            "violence": self._violence_extractor.default_value,
            "weather": None,
            "pose": None,
            "depth": None,
            "image_quality": self._image_quality_extractor.default_value,
            "pet": self._pet_extractor.default_value,
            "processing_time_ms": None,
            "errors": [],
        }


# Module-level singleton for convenience
class _TransformerHolder:
    """Holds the default transformer instance to avoid global statement."""

    instance: EnrichmentTransformer | None = None


def get_enrichment_transformer() -> EnrichmentTransformer:
    """Get the default EnrichmentTransformer instance."""
    if _TransformerHolder.instance is None:
        _TransformerHolder.instance = EnrichmentTransformer()
    return _TransformerHolder.instance


def transform_enrichment_data(
    detection_id: int,
    enrichment_data: dict[str, Any] | None,
    detected_at: datetime | None,
) -> dict[str, Any]:
    """Convenience function to transform enrichment data using the default transformer.

    This is the main entry point for transforming enrichment data throughout the API.

    Args:
        detection_id: Detection ID
        enrichment_data: Raw JSONB data from the detection
        detected_at: Detection timestamp (used as fallback for enriched_at)

    Returns:
        Dictionary matching EnrichmentResponse schema
    """
    return get_enrichment_transformer().transform(
        detection_id=detection_id,
        enrichment_data=enrichment_data,
        detected_at=detected_at,
    )
