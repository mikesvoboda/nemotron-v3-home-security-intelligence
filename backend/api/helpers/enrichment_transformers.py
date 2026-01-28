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
    from datetime import UTC, datetime
    transformer = EnrichmentTransformer()
    result = transformer.transform(
        detection_id=1,
        enrichment_data=raw_data,
        detected_at=datetime.now(UTC),
    )
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, override

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
    @override
    def enrichment_key(self) -> str:
        return "license_plates"

    @property
    @override
    def default_value(self) -> dict[str, Any]:
        return {"detected": False}

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "faces"

    @property
    @override
    def default_value(self) -> dict[str, Any]:
        return {"detected": False, "count": 0}

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "violence_detection"

    @property
    @override
    def default_value(self) -> dict[str, Any]:
        return {"detected": False, "score": 0.0}

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "vehicle_classifications"

    @property
    @override
    def default_value(self) -> None:
        return None

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "clothing_classifications"

    @property
    @override
    def default_value(self) -> None:
        return None

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "image_quality"

    @property
    @override
    def default_value(self) -> None:
        return None

    @override
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
    @override
    def enrichment_key(self) -> str:
        return "pet_classifications"

    @property
    @override
    def default_value(self) -> None:
        return None

    @override
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


class PoseExtractor(BaseEnrichmentExtractor):
    """Extract pose analysis data from enrichment.

    Extracts ViTPose+ pose estimation data including:
    - keypoints: COCO 17 keypoints with normalized coordinates
    - posture: Classified posture (standing, walking, sitting, crouching, lying_down, running)
    - alerts: Security-relevant pose alerts (crouching, lying_down, hands_raised, fighting_stance)
    """

    @property
    @override
    def enrichment_key(self) -> str:
        return "pose_estimation"

    @property
    @override
    def default_value(self) -> None:
        return None

    @override
    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract pose analysis data.

        Returns a structured response with:
        - posture: The classified posture type
        - alerts: List of security-relevant alerts
        - keypoints: Array of [x, y, confidence] for skeleton overlay
        - keypoint_count: Number of detected keypoints
        """
        # Check for pose_estimation key (from ViTPose analysis)
        pose_data = enrichment_data.get(self.enrichment_key)
        if not pose_data:
            return self.default_value

        # Extract keypoints as array format for frontend skeleton overlay
        # Format: [[x, y, confidence], ...] matching COCO 17 keypoint order
        keypoints_list = pose_data.get("keypoints", [])
        keypoints_array: list[list[float]] = []

        # Map keypoint names to COCO indices for proper ordering
        coco_keypoint_order = [
            "nose",
            "left_eye",
            "right_eye",
            "left_ear",
            "right_ear",
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_ankle",
            "right_ankle",
        ]

        # Build keypoint dict for lookup
        keypoint_dict = {kp.get("name"): kp for kp in keypoints_list if kp.get("name")}

        # Create ordered keypoints array
        for name in coco_keypoint_order:
            kp = keypoint_dict.get(name)
            if kp:
                keypoints_array.append(
                    [
                        kp.get("x", 0.0),
                        kp.get("y", 0.0),
                        kp.get("confidence", 0.0),
                    ]
                )
            else:
                # Missing keypoint - add placeholder with zero confidence
                keypoints_array.append([0.0, 0.0, 0.0])

        return {
            "posture": pose_data.get("posture", "unknown"),
            "alerts": pose_data.get("alerts", []),
            "keypoints": keypoints_array,
            "keypoint_count": len(keypoints_list),
        }


class ActionExtractor(BaseEnrichmentExtractor):
    """Extract action recognition data from enrichment.

    Extracts X-CLIP temporal action recognition data including:
    - action: Detected action (walking, running, delivering, loitering, etc.)
    - confidence: Confidence score for the detected action
    - is_suspicious: Whether the action is security-relevant
    - all_scores: Confidence scores for all candidate actions

    The action recognition system uses pose-based inference when X-CLIP
    video frames are not available, mapping posture to likely actions.
    """

    # Suspicious actions that indicate potential security concerns
    SUSPICIOUS_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {
            "loitering",
            "climbing",
            "hiding",
            "breaking",
            "vandalizing",
            "picking lock",
            "looking around suspiciously",
            "running away",
            "trying door handle",
            "checking windows",
            "taking photos",
        }
    )

    # Mapping from pose postures to likely actions for pose-based inference
    POSE_TO_ACTION_MAP: ClassVar[dict[str, str]] = {
        "standing": "standing",
        "walking": "walking normally",
        "sitting": "sitting",
        "crouching": "crouching",
        "running": "running",
        "lying_down": "lying down",
        "bending_over": "bending over",
        "arms_raised": "arms raised",
    }

    @property
    @override
    def enrichment_key(self) -> str:
        return "action_recognition"

    @property
    @override
    def default_value(self) -> None:
        return None

    def _is_suspicious(self, action: str | None) -> bool:
        """Check if an action is considered suspicious.

        Args:
            action: The detected action string

        Returns:
            True if the action is security-relevant
        """
        if not action:
            return False
        action_lower = action.lower()
        return any(suspicious in action_lower for suspicious in self.SUSPICIOUS_ACTIONS)

    def _infer_action_from_pose(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Infer action from pose data when X-CLIP results are unavailable.

        This provides a lightweight fallback using pose estimation results
        to infer likely actions based on body posture.

        Args:
            enrichment_data: The enrichment data dictionary

        Returns:
            Inferred action data or None if pose data unavailable
        """
        pose_data = enrichment_data.get("pose_estimation")
        if not pose_data:
            return None

        posture = pose_data.get("posture", "unknown")
        confidence = pose_data.get("confidence", 0.5)

        # Map posture to action
        action = self.POSE_TO_ACTION_MAP.get(posture, "unknown")

        # Determine if suspicious based on posture
        is_suspicious = posture in {"crouching", "running"}

        return {
            "action": action,
            "confidence": confidence,
            "is_suspicious": is_suspicious,
            "all_scores": None,  # No scores available from pose inference
        }

    @override
    def extract(self, enrichment_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract action recognition data.

        Returns a structured response with:
        - action: The detected action type
        - confidence: Confidence score for the action
        - is_suspicious: Whether the action is security-relevant
        - all_scores: Scores for all candidate actions (if available)

        Falls back to pose-based inference if X-CLIP results are unavailable.
        """
        # Check for action_recognition key (from X-CLIP analysis)
        action_data = enrichment_data.get(self.enrichment_key)

        if not action_data:
            # Fall back to pose-based inference
            return self._infer_action_from_pose(enrichment_data)

        # Extract action recognition results
        action = action_data.get("detected_action")
        confidence = action_data.get("confidence")
        all_scores = action_data.get("all_scores")

        # Determine if suspicious
        is_suspicious = self._is_suspicious(action)

        return {
            "action": action,
            "confidence": confidence,
            "is_suspicious": is_suspicious,
            "all_scores": all_scores,
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
        self._pose_extractor = PoseExtractor()
        self._action_extractor = ActionExtractor()

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
            "pose": self._pose_extractor.extract(enrichment_data),
            "action": self._action_extractor.extract(enrichment_data),
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
            "pose": self._pose_extractor.default_value,
            "action": self._action_extractor.default_value,
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
