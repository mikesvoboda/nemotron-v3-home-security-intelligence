"""Enrichment Pipeline for detection context enhancement.

This module provides the EnrichmentPipeline service that enriches detections
with additional context by running on-demand AI models:

1. License Plate Detection: Runs YOLO11 on vehicle detections
2. License Plate OCR: Runs PaddleOCR on detected plates
3. Face Detection: Runs YOLO11 on person detections
4. Image Quality Assessment: BRISQUE for blur/noise/tampering detection

The pipeline can use either:
- Local models via ModelManager (default, for single-process deployments)
- Remote HTTP service at ai-enrichment:8094 (for containerized deployments)

Set use_enrichment_service=True to use the HTTP service for vehicle, pet,
and clothing classification instead of loading models locally.
"""

from __future__ import annotations

__all__ = [
    "BoundingBox",
    "DetectionInput",
    "EnrichmentError",
    "EnrichmentPipeline",
    "EnrichmentResult",
    "EnrichmentStatus",
    "EnrichmentTrackingResult",
    "ErrorCategory",
    "FaceResult",
    "LicensePlateResult",
    "get_enrichment_pipeline",
    "get_enrichment_pipeline_with_session",
    "reset_enrichment_pipeline",
]

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC
from enum import Enum
from pathlib import Path

# Frame buffer is lazily imported to avoid circular imports
# Import type for annotation only
from typing import TYPE_CHECKING, Any

import httpx
from PIL import Image
from pydantic import ValidationError

from backend.core.exceptions import (
    AIServiceError,
    CLIPUnavailableError,
    EnrichmentUnavailableError,
    FlorenceUnavailableError,
)
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_enrichment_model_duration,
    record_enrichment_model_call,
    record_enrichment_model_error,
    record_pipeline_error,
)
from backend.core.mime_types import VIDEO_MIME_TYPES
from backend.core.telemetry import add_span_event
from backend.services.depth_anything_loader import (
    DepthAnalysisResult,
    analyze_depth,
)

# Import enrichment client for remote HTTP service
from backend.services.enrichment_client import (
    EnrichmentClient,
    get_enrichment_client,
)
from backend.services.fashion_clip_loader import (
    ClothingClassification,
    classify_clothing,
    format_clothing_context,
)
from backend.services.household_matcher import (
    HouseholdMatch,
    get_household_matcher,
)
from backend.services.image_quality_loader import (
    ImageQualityResult,
    assess_image_quality,
    detect_quality_change,
    interpret_blur_with_motion,
)
from backend.services.model_zoo import (
    ANIMAL_CLASSES,
    PERSON_CLASS,
    VEHICLE_CLASSES,
    ModelManager,
    get_model_manager,
)
from backend.services.pet_classifier_loader import (
    PetClassificationResult,
    classify_pet,
    format_pet_for_nemotron,
    is_likely_pet_false_positive,
)
from backend.services.reid_service import (
    EntityEmbedding,
    EntityMatch,
    get_reid_service,
)
from backend.services.scene_change_detector import (
    SceneChangeResult,
    get_scene_change_detector,
)
from backend.services.segformer_loader import (
    ClothingSegmentationResult,
)
from backend.services.vehicle_classifier_loader import (
    VehicleClassificationResult,
    classify_vehicle,
    format_vehicle_classification_context,
)
from backend.services.vehicle_damage_loader import (
    VehicleDamageResult,
    detect_vehicle_damage,
)
from backend.services.violence_loader import (
    ViolenceDetectionResult,
    classify_violence,
)
from backend.services.vision_extractor import (
    BatchExtractionResult,
    get_vision_extractor,
)
from backend.services.vitpose_loader import (
    PoseResult,
    extract_poses_batch,
)
from backend.services.weather_loader import (
    WeatherResult,
    classify_weather,
)
from backend.services.xclip_loader import (
    classify_actions,
    get_action_risk_weight,
    is_suspicious_action,
)

if TYPE_CHECKING:
    from backend.services.frame_buffer import FrameBuffer

logger = get_logger(__name__)


class EnrichmentStatus(str, Enum):
    """Status of enrichment pipeline execution.

    Tracks the overall success/failure state of enrichment operations:
    - FULL: All enabled enrichment models succeeded
    - PARTIAL: Some models succeeded, some failed (partial enrichment available)
    - FAILED: All models failed (no enrichment data available)
    - SKIPPED: Enrichment was not attempted (disabled or no applicable detections)
    """

    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorCategory(str, Enum):
    """Category of enrichment error for observability.

    Error categories help distinguish between transient failures that
    can be retried and permanent failures that indicate bugs.
    """

    # Transient errors (use fallback, retry later)
    SERVICE_UNAVAILABLE = "service_unavailable"  # Connection errors, service down
    TIMEOUT = "timeout"  # Request timed out
    RATE_LIMITED = "rate_limited"  # HTTP 429, back off
    SERVER_ERROR = "server_error"  # HTTP 5xx, transient issue

    # Permanent errors (likely a bug, requires investigation)
    CLIENT_ERROR = "client_error"  # HTTP 4xx, bad request
    PARSE_ERROR = "parse_error"  # JSON/response parsing failed
    VALIDATION_ERROR = "validation_error"  # Invalid input data

    # Unexpected errors (catch-all, needs investigation)
    UNEXPECTED = "unexpected"  # Unknown error type


@dataclass(slots=True)
class EnrichmentError:
    """Structured error information for enrichment failures.

    Provides detailed error context for observability and debugging,
    including the error category, reason, and original exception type.

    Attributes:
        operation: The operation that failed (e.g., "license_plate_detection")
        category: Error category for classification
        reason: Human-readable reason for the failure
        error_type: The type name of the original exception
        is_transient: Whether the error is transient (retry may succeed)
        details: Additional context-specific details
    """

    operation: str
    category: ErrorCategory
    reason: str
    error_type: str
    is_transient: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation": self.operation,
            "category": self.category.value,
            "reason": self.reason,
            "error_type": self.error_type,
            "is_transient": self.is_transient,
            "details": self.details,
        }

    @classmethod
    def from_exception(  # noqa: PLR0911
        cls,
        operation: str,
        exc: Exception,
        *,
        details: dict[str, Any] | None = None,
    ) -> EnrichmentError:
        """Create an EnrichmentError from an exception.

        Classifies the exception into the appropriate category and determines
        whether it is transient (retry may succeed) or permanent (likely a bug).

        Args:
            operation: The operation that failed
            exc: The exception that was raised
            details: Additional context-specific details

        Returns:
            EnrichmentError with appropriate category and reason
        """
        error_details = details or {}

        # Handle httpx connection errors (transient)
        if isinstance(exc, httpx.ConnectError):
            return cls(
                operation=operation,
                category=ErrorCategory.SERVICE_UNAVAILABLE,
                reason=f"Service connection failed: {sanitize_error(exc)}",
                error_type=type(exc).__name__,
                is_transient=True,
                details=error_details,
            )

        # Handle timeout errors (transient)
        if isinstance(exc, httpx.TimeoutException | TimeoutError | asyncio.TimeoutError):
            return cls(
                operation=operation,
                category=ErrorCategory.TIMEOUT,
                reason=f"Request timed out: {sanitize_error(exc)}",
                error_type=type(exc).__name__,
                is_transient=True,
                details=error_details,
            )

        # Handle HTTP status errors
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            error_details["status_code"] = status_code

            # Rate limiting (429)
            if status_code == 429:
                return cls(
                    operation=operation,
                    category=ErrorCategory.RATE_LIMITED,
                    reason=f"Rate limited (HTTP {status_code})",
                    error_type=type(exc).__name__,
                    is_transient=True,
                    details=error_details,
                )

            # Server errors (5xx) - transient
            if 500 <= status_code < 600:
                return cls(
                    operation=operation,
                    category=ErrorCategory.SERVER_ERROR,
                    reason=f"Server error (HTTP {status_code})",
                    error_type=type(exc).__name__,
                    is_transient=True,
                    details=error_details,
                )

            # Client errors (4xx) - permanent, likely a bug
            if 400 <= status_code < 500:
                return cls(
                    operation=operation,
                    category=ErrorCategory.CLIENT_ERROR,
                    reason=f"Client error (HTTP {status_code})",
                    error_type=type(exc).__name__,
                    is_transient=False,  # This is likely a bug!
                    details=error_details,
                )

        # Handle AI service unavailable errors (transient)
        if isinstance(
            exc,
            AIServiceError
            | EnrichmentUnavailableError
            | FlorenceUnavailableError
            | CLIPUnavailableError,
        ):
            return cls(
                operation=operation,
                category=ErrorCategory.SERVICE_UNAVAILABLE,
                reason=str(exc),
                error_type=type(exc).__name__,
                is_transient=True,
                details=error_details,
            )

        # Handle parsing errors (permanent)
        if isinstance(exc, ValueError | KeyError | TypeError | json.JSONDecodeError):
            return cls(
                operation=operation,
                category=ErrorCategory.PARSE_ERROR,
                reason=f"Response parsing failed: {sanitize_error(exc)}",
                error_type=type(exc).__name__,
                is_transient=False,
                details=error_details,
            )

        # Handle validation errors (permanent)
        if isinstance(exc, ValidationError | AttributeError):
            return cls(
                operation=operation,
                category=ErrorCategory.VALIDATION_ERROR,
                reason=f"Validation failed: {sanitize_error(exc)}",
                error_type=type(exc).__name__,
                is_transient=False,
                details=error_details,
            )

        # Unexpected errors (needs investigation)
        return cls(
            operation=operation,
            category=ErrorCategory.UNEXPECTED,
            reason=f"Unexpected error: {sanitize_error(exc)}",
            error_type=type(exc).__name__,
            is_transient=True,  # Assume transient unless proven otherwise
            details=error_details,
        )


@dataclass(slots=True)
class EnrichmentTrackingResult:
    """Tracks which enrichment models succeeded/failed for a batch.

    This provides visibility into partial failures instead of silently
    degrading when some enrichment models fail.

    Attributes:
        status: Overall enrichment status (full, partial, failed, skipped)
        successful_models: List of model names that succeeded
        failed_models: List of model names that failed
        errors: Dictionary mapping model names to error messages
        data: The actual EnrichmentResult data (if any models succeeded)
    """

    status: EnrichmentStatus = EnrichmentStatus.SKIPPED
    successful_models: list[str] = field(default_factory=list)
    failed_models: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    data: EnrichmentResult | None = None

    @property
    def has_data(self) -> bool:
        """Check if any enrichment data is available."""
        return self.data is not None

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of enrichment models.

        Returns:
            Float between 0.0 and 1.0 representing success rate.
            Returns 1.0 if no models were attempted.
        """
        total = len(self.successful_models) + len(self.failed_models)
        if total == 0:
            return 1.0
        return len(self.successful_models) / total

    @property
    def is_partial(self) -> bool:
        """Check if this is a partial result (some succeeded, some failed)."""
        return self.status == EnrichmentStatus.PARTIAL

    @property
    def all_succeeded(self) -> bool:
        """Check if all attempted models succeeded."""
        return self.status == EnrichmentStatus.FULL

    @property
    def all_failed(self) -> bool:
        """Check if all attempted models failed."""
        return self.status == EnrichmentStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of tracking result
        """
        return {
            "status": self.status.value,
            "successful_models": self.successful_models,
            "failed_models": self.failed_models,
            "errors": self.errors,
            "success_rate": self.success_rate,
        }

    @classmethod
    def compute_status(cls, successful: list[str], failed: list[str]) -> EnrichmentStatus:
        """Compute the appropriate status based on model results.

        Uses Python 3.10+ structural pattern matching with tuple unpacking
        for clear, exhaustive status determination based on list emptiness.

        Args:
            successful: List of models that succeeded
            failed: List of models that failed

        Returns:
            EnrichmentStatus enum value
        """
        match (bool(successful), bool(failed)):
            case (False, False):
                return EnrichmentStatus.SKIPPED
            case (True, False):
                return EnrichmentStatus.FULL
            case (False, True):
                return EnrichmentStatus.FAILED
            case (True, True):
                return EnrichmentStatus.PARTIAL
            case _:
                # Unreachable but required for exhaustiveness
                return EnrichmentStatus.SKIPPED


@dataclass(slots=True)
class BoundingBox:
    """Bounding box coordinates.

    Attributes:
        x1: Left coordinate
        y1: Top coordinate
        x2: Right coordinate
        y2: Bottom coordinate
        confidence: Detection confidence score (0-1)
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 0.0

    def to_tuple(self) -> tuple[float, float, float, float]:
        """Convert to (x1, y1, x2, y2) tuple."""
        return (self.x1, self.y1, self.x2, self.y2)

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        """Convert to integer (x1, y1, x2, y2) tuple for cropping."""
        return (int(self.x1), int(self.y1), int(self.x2), int(self.y2))

    @property
    def width(self) -> float:
        """Get bounding box width."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """Get bounding box height."""
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[float, float]:
        """Get center point (x, y)."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass(slots=True)
class LicensePlateResult:
    """Result from license plate detection and OCR.

    Attributes:
        bbox: Bounding box of the detected plate
        text: OCR text from the plate (may be empty)
        confidence: Detection confidence
        ocr_confidence: OCR confidence (0-1, may be 0 if OCR failed)
        source_detection_id: ID of the vehicle detection this came from
    """

    bbox: BoundingBox
    text: str = ""
    confidence: float = 0.0
    ocr_confidence: float = 0.0
    source_detection_id: int | None = None


@dataclass(slots=True)
class FaceResult:
    """Result from face detection.

    Attributes:
        bbox: Bounding box of the detected face
        confidence: Detection confidence
        source_detection_id: ID of the person detection this came from
    """

    bbox: BoundingBox
    confidence: float = 0.0
    source_detection_id: int | None = None


@dataclass(slots=True)
class EnrichmentResult:
    """Result from the enrichment pipeline.

    Contains all additional context extracted from detections
    for use in the Nemotron LLM prompt.

    Attributes:
        license_plates: Detected license plates with OCR text
        faces: Detected faces
        vision_extraction: Florence-2 attribute extraction results
        person_reid_matches: Re-identification matches for persons
        vehicle_reid_matches: Re-identification matches for vehicles
        person_household_matches: Household member matches for persons (NEM-3314)
        vehicle_household_matches: Registered vehicle matches (NEM-3314)
        scene_change: Scene change detection result
        errors: List of error messages during processing (deprecated, use structured_errors)
        structured_errors: List of structured error objects with category and reason
        processing_time_ms: Total processing time in milliseconds
    """

    license_plates: list[LicensePlateResult] = field(default_factory=list)
    faces: list[FaceResult] = field(default_factory=list)
    vision_extraction: BatchExtractionResult | None = None
    person_reid_matches: dict[str, list[EntityMatch]] = field(default_factory=dict)
    vehicle_reid_matches: dict[str, list[EntityMatch]] = field(default_factory=dict)
    # Household matching results (NEM-3314)
    person_household_matches: list[HouseholdMatch] = field(default_factory=list)
    vehicle_household_matches: list[HouseholdMatch] = field(default_factory=list)
    scene_change: SceneChangeResult | None = None
    violence_detection: ViolenceDetectionResult | None = None
    weather_classification: WeatherResult | None = None
    clothing_classifications: dict[str, ClothingClassification] = field(default_factory=dict)
    clothing_segmentation: dict[str, ClothingSegmentationResult] = field(default_factory=dict)
    vehicle_classifications: dict[str, VehicleClassificationResult] = field(default_factory=dict)
    vehicle_damage: dict[str, VehicleDamageResult] = field(default_factory=dict)
    pet_classifications: dict[str, PetClassificationResult] = field(default_factory=dict)
    pose_results: dict[str, PoseResult] = field(default_factory=dict)
    action_results: dict[str, Any] | None = None
    depth_analysis: DepthAnalysisResult | None = None
    image_quality: ImageQualityResult | None = None
    quality_change_detected: bool = False
    quality_change_description: str = ""
    # New model outputs
    threat_detection: Any | None = None  # ThreatDetectionResult
    age_classifications: dict[str, Any] = field(default_factory=dict)  # AgeClassificationResult
    gender_classifications: dict[str, Any] = field(
        default_factory=dict
    )  # GenderClassificationResult
    person_embeddings: dict[str, Any] = field(default_factory=dict)  # PersonEmbeddingResult (OSNet)
    errors: list[str] = field(default_factory=list)
    structured_errors: list[EnrichmentError] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def has_license_plates(self) -> bool:
        """Check if any license plates were detected."""
        return len(self.license_plates) > 0

    @property
    def has_clothing_segmentation(self) -> bool:
        """Check if any clothing segmentation results are available."""
        return bool(self.clothing_segmentation)

    @property
    def has_readable_plates(self) -> bool:
        """Check if any plates have readable text."""
        return any(plate.text for plate in self.license_plates)

    @property
    def has_faces(self) -> bool:
        """Check if any faces were detected."""
        return len(self.faces) > 0

    @property
    def plate_texts(self) -> list[str]:
        """Get list of all plate texts (non-empty only)."""
        return [plate.text for plate in self.license_plates if plate.text]

    @property
    def has_vision_extraction(self) -> bool:
        """Check if vision extraction results are available."""
        return self.vision_extraction is not None

    @property
    def has_reid_matches(self) -> bool:
        """Check if any re-identification matches were found."""
        return bool(self.person_reid_matches) or bool(self.vehicle_reid_matches)

    @property
    def has_person_household_matches(self) -> bool:
        """Check if any persons matched household members (NEM-3314)."""
        return bool(self.person_household_matches)

    @property
    def has_vehicle_household_matches(self) -> bool:
        """Check if any vehicles matched registered vehicles (NEM-3314)."""
        return bool(self.vehicle_household_matches)

    @property
    def has_household_matches(self) -> bool:
        """Check if any household matches were found (persons or vehicles) (NEM-3314)."""
        return self.has_person_household_matches or self.has_vehicle_household_matches

    @property
    def has_scene_change(self) -> bool:
        """Check if scene change was detected."""
        return self.scene_change is not None and self.scene_change.change_detected

    @property
    def has_violence(self) -> bool:
        """Check if violence was detected."""
        return self.violence_detection is not None and self.violence_detection.is_violent

    @property
    def has_clothing_classifications(self) -> bool:
        """Check if any clothing classifications are available."""
        return bool(self.clothing_classifications)

    @property
    def has_suspicious_clothing(self) -> bool:
        """Check if any suspicious clothing was detected."""
        return any(c.is_suspicious for c in self.clothing_classifications.values())

    @property
    def has_vehicle_classifications(self) -> bool:
        """Check if any vehicle classifications are available."""
        return bool(self.vehicle_classifications)

    @property
    def has_commercial_vehicles(self) -> bool:
        """Check if any commercial/delivery vehicles were detected."""
        return any(v.is_commercial for v in self.vehicle_classifications.values())

    @property
    def has_vehicle_damage(self) -> bool:
        """Check if any vehicle damage was detected."""
        return any(d.has_damage for d in self.vehicle_damage.values())

    @property
    def has_high_security_damage(self) -> bool:
        """Check if any high-security vehicle damage was detected (glass shatter, lamp broken)."""
        return any(d.has_high_security_damage for d in self.vehicle_damage.values())

    @property
    def has_image_quality(self) -> bool:
        """Check if image quality assessment is available."""
        return self.image_quality is not None

    @property
    def has_quality_issues(self) -> bool:
        """Check if any image quality issues were detected."""
        return self.image_quality is not None and not self.image_quality.is_good_quality

    @property
    def has_motion_blur(self) -> bool:
        """Check if motion blur was detected (possible fast movement)."""
        return self.image_quality is not None and self.image_quality.is_blurry

    @property
    def has_pet_classifications(self) -> bool:
        """Check if any pet classifications are available."""
        return bool(self.pet_classifications)

    @property
    def has_confirmed_pets(self) -> bool:
        """Check if any high-confidence household pets were detected."""
        return any(is_likely_pet_false_positive(p) for p in self.pet_classifications.values())

    @property
    def pet_only_event(self) -> bool:
        """Check if this is a pet-only event (can skip Nemotron analysis)."""
        return (
            self.has_confirmed_pets
            and not self.has_faces
            and not self.has_license_plates
            and not self.has_violence
            and not self.has_clothing_classifications
        )

    @property
    def has_pose_results(self) -> bool:
        """Check if any pose estimation results are available."""
        return bool(self.pose_results)

    @property
    def has_suspicious_poses(self) -> bool:
        """Check if any suspicious poses were detected (crouching, running)."""
        suspicious_poses = {"crouching", "running", "lying"}
        return any(
            p.pose_class in suspicious_poses
            for p in self.pose_results.values()
            if p.pose_confidence > 0.5
        )

    @property
    def has_action_results(self) -> bool:
        """Check if action recognition results are available."""
        return self.action_results is not None

    @property
    def has_suspicious_action(self) -> bool:
        """Check if a suspicious action was detected."""
        if not self.action_results:
            return False
        detected_action = self.action_results.get("detected_action", "")
        return is_suspicious_action(detected_action)

    @property
    def action_risk_weight(self) -> float:
        """Get the risk weight for the detected action."""
        if not self.action_results:
            return 0.5  # Neutral
        detected_action = self.action_results.get("detected_action", "")
        return get_action_risk_weight(detected_action)

    @property
    def has_depth_analysis(self) -> bool:
        """Check if depth analysis results are available."""
        return self.depth_analysis is not None and self.depth_analysis.has_detections

    @property
    def has_close_objects(self) -> bool:
        """Check if any objects are in close proximity (very close or close)."""
        return self.depth_analysis is not None and self.depth_analysis.has_close_objects

    @property
    def has_threat_detection(self) -> bool:
        """Check if threat detection results are available."""
        return self.threat_detection is not None

    @property
    def has_threats(self) -> bool:
        """Check if any threats/weapons were detected."""
        return (
            self.threat_detection is not None
            and hasattr(self.threat_detection, "has_threats")
            and self.threat_detection.has_threats
        )

    @property
    def has_high_priority_threats(self) -> bool:
        """Check if any high-priority threats (guns, knives) were detected."""
        return (
            self.threat_detection is not None
            and hasattr(self.threat_detection, "has_high_priority")
            and self.threat_detection.has_high_priority
        )

    @property
    def has_age_classifications(self) -> bool:
        """Check if any age classifications are available."""
        return bool(self.age_classifications)

    @property
    def has_minors(self) -> bool:
        """Check if any minors were detected."""
        return any(
            hasattr(age, "is_minor") and age.is_minor for age in self.age_classifications.values()
        )

    @property
    def has_gender_classifications(self) -> bool:
        """Check if any gender classifications are available."""
        return bool(self.gender_classifications)

    @property
    def has_person_embeddings(self) -> bool:
        """Check if any person embeddings (OSNet) are available."""
        return bool(self.person_embeddings)

    @property
    def has_structured_errors(self) -> bool:
        """Check if any structured errors were recorded."""
        return bool(self.structured_errors)

    @property
    def has_transient_errors(self) -> bool:
        """Check if any transient errors occurred (retry may succeed)."""
        return any(e.is_transient for e in self.structured_errors)

    @property
    def has_permanent_errors(self) -> bool:
        """Check if any permanent errors occurred (likely bugs)."""
        return any(not e.is_transient for e in self.structured_errors)

    @property
    def transient_error_count(self) -> int:
        """Count of transient errors."""
        return sum(1 for e in self.structured_errors if e.is_transient)

    @property
    def permanent_error_count(self) -> int:
        """Count of permanent errors (likely bugs)."""
        return sum(1 for e in self.structured_errors if not e.is_transient)

    def get_errors_by_category(self, category: ErrorCategory) -> list[EnrichmentError]:
        """Get all errors of a specific category.

        Args:
            category: The error category to filter by

        Returns:
            List of errors matching the category
        """
        return [e for e in self.structured_errors if e.category == category]

    def add_error(
        self,
        operation: str,
        exc: Exception,
        *,
        details: dict[str, Any] | None = None,
    ) -> EnrichmentError:
        """Add an error from an exception with structured tracking.

        Creates an EnrichmentError from the exception and adds it to both
        the structured_errors list (new) and errors list (legacy compatibility).

        Args:
            operation: The operation that failed
            exc: The exception that was raised
            details: Additional context-specific details

        Returns:
            The created EnrichmentError
        """
        error = EnrichmentError.from_exception(operation, exc, details=details)
        self.structured_errors.append(error)
        # Legacy compatibility: also add to errors list
        self.errors.append(f"{operation} failed: {error.reason}")
        return error

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Formatted string describing enrichment results
        """
        from backend.services.reid_service import format_full_reid_context
        from backend.services.vision_extractor import (
            format_batch_extraction_result,
        )

        lines = []

        # Vision extraction (Florence-2)
        if self.vision_extraction:
            vision_str = format_batch_extraction_result(self.vision_extraction)
            if vision_str and not vision_str.startswith("No vision"):
                lines.append("## Vision Analysis")
                lines.append(vision_str)

        # Re-identification
        if self.person_reid_matches or self.vehicle_reid_matches:
            reid_str = format_full_reid_context(self.person_reid_matches, self.vehicle_reid_matches)
            if reid_str and not reid_str.startswith("No entities"):
                lines.append("## Re-Identification")
                lines.append(reid_str)

        # Scene change
        if self.scene_change and self.scene_change.change_detected:
            lines.append("## Scene Change")
            lines.append(
                f"Scene change detected (similarity: {self.scene_change.similarity_score:.2f})"
            )

        # Violence detection
        if self.violence_detection:
            lines.append("## Violence Detection")
            if self.violence_detection.is_violent:
                lines.append(
                    f"**VIOLENCE DETECTED** (confidence: {self.violence_detection.confidence:.0%})"
                )
            else:
                lines.append(
                    f"No violence detected (confidence: {self.violence_detection.confidence:.0%})"
                )

        # Clothing Classifications (FashionCLIP)
        if self.clothing_classifications:
            lines.append(
                f"## Clothing Classifications ({len(self.clothing_classifications)} persons)"
            )
            for det_id, classification in self.clothing_classifications.items():
                lines.append(f"  Person {det_id}:")
                lines.append(f"    {format_clothing_context(classification)}")

        # Vehicle Damage Detection
        if self.vehicle_damage:
            damaged_vehicles = {k: v for k, v in self.vehicle_damage.items() if v.has_damage}
            if damaged_vehicles:
                lines.append(f"## Vehicle Damage ({len(damaged_vehicles)} vehicles with damage)")
                for det_id, damage_result in damaged_vehicles.items():
                    lines.append(f"  Vehicle {det_id}:")
                    lines.append(f"    {damage_result.to_context_string()}")
                    if damage_result.has_high_security_damage:
                        lines.append("    **SECURITY ALERT**: High-priority damage detected")

        # Vehicle Classifications (ResNet-50)
        if self.vehicle_classifications:
            lines.append(
                f"## Vehicle Classifications ({len(self.vehicle_classifications)} vehicles)"
            )
            for det_id, vehicle_class in self.vehicle_classifications.items():
                lines.append(f"  Vehicle {det_id}:")
                lines.append(f"    {format_vehicle_classification_context(vehicle_class)}")

        # License plates
        if self.license_plates:
            lines.append(f"## License Plates ({len(self.license_plates)} detected)")
            for i, plate in enumerate(self.license_plates, 1):
                if plate.text:
                    lines.append(
                        f"  - Plate {i}: {plate.text} (OCR confidence: {plate.ocr_confidence:.0%})"
                    )
                else:
                    lines.append(f"  - Plate {i}: [unreadable]")

        # Faces
        if self.faces:
            lines.append(f"## Faces ({len(self.faces)} detected)")
            for i, face in enumerate(self.faces, 1):
                lines.append(f"  - Face {i}: confidence {face.confidence:.0%}")

        # Pet Classifications (for false positive context)
        if self.pet_classifications:
            lines.append(f"## Pet Classifications ({len(self.pet_classifications)} animals)")
            for det_id, pet_result in self.pet_classifications.items():
                lines.append(f"  - Animal {det_id}: {format_pet_for_nemotron(pet_result)}")
            if self.pet_only_event:
                lines.append("  **NOTE**: Pet-only event - low security risk")

        # Pose Estimation Results (ViTPose)
        if self.pose_results:
            lines.append(f"## Pose Analysis ({len(self.pose_results)} persons)")
            suspicious_poses = {"crouching", "running", "lying"}
            for det_id, pose_result in self.pose_results.items():
                pose_class = pose_result.pose_class
                confidence = pose_result.pose_confidence
                risk_note = ""
                if pose_class in suspicious_poses and confidence > 0.5:
                    risk_note = " [SUSPICIOUS]"
                lines.append(f"  Person {det_id}: {pose_class} ({confidence:.0%}){risk_note}")

        # Action Recognition Results (X-CLIP)
        if self.action_results:
            lines.append("## Action Recognition")
            detected_action = self.action_results.get("detected_action", "unknown")
            confidence = self.action_results.get("confidence", 0.0)
            risk_weight = get_action_risk_weight(detected_action)
            risk_level = (
                "HIGH RISK"
                if risk_weight >= 0.7
                else "suspicious"
                if risk_weight >= 0.5
                else "normal"
            )
            lines.append(f"  Detected action: {detected_action} ({confidence:.0%})")
            if risk_weight >= 0.7:
                lines.append(
                    f"  **{risk_level}**: This action indicates potential security concern"
                )

        # Depth Analysis (Depth Anything V2)
        if self.depth_analysis and self.depth_analysis.has_detections:
            lines.append("## Spatial Depth Analysis")
            lines.append(self.depth_analysis.to_context_string())

        # Threat/Weapon Detection (YOLOv8n)
        if (
            self.threat_detection
            and hasattr(self.threat_detection, "has_threats")
            and self.threat_detection.has_threats
        ):
            lines.append("## **THREAT DETECTION**")
            if (
                hasattr(self.threat_detection, "has_high_priority")
                and self.threat_detection.has_high_priority
            ):
                lines.append("  **CRITICAL**: High-priority weapon detected!")
            if hasattr(self.threat_detection, "threat_summary"):
                lines.append(f"  Threats: {self.threat_detection.threat_summary}")
            if hasattr(self.threat_detection, "threats"):
                for threat in self.threat_detection.threats[:5]:
                    priority = " **HIGH PRIORITY**" if threat.is_high_priority else ""
                    lines.append(f"    - {threat.class_name} ({threat.confidence:.0%}){priority}")

        # Age Classifications (ViT)
        if self.age_classifications:
            lines.append(f"## Age Estimation ({len(self.age_classifications)} persons)")
            has_minors = False
            for det_id, age in self.age_classifications.items():
                display_name = (
                    age.display_name
                    if hasattr(age, "display_name")
                    else getattr(age, "age_group", "unknown")
                )
                confidence = getattr(age, "confidence", 0.0)
                is_minor = hasattr(age, "is_minor") and age.is_minor
                if is_minor:
                    has_minors = True
                minor_marker = " **MINOR**" if is_minor else ""
                lines.append(f"  Person {det_id}: {display_name} ({confidence:.0%}){minor_marker}")
            if has_minors:
                lines.append("  **NOTE**: Minor(s) detected - evaluate context carefully")

        # Gender Classifications (ViT)
        if self.gender_classifications:
            lines.append(f"## Gender Estimation ({len(self.gender_classifications)} persons)")
            for det_id, gender in self.gender_classifications.items():
                gender_val = getattr(gender, "gender", "unknown")
                confidence = getattr(gender, "confidence", 0.0)
                lines.append(f"  Person {det_id}: {gender_val} ({confidence:.0%})")

        # Person Embeddings (OSNet)
        if self.person_embeddings:
            lines.append(f"## Person Re-ID Embeddings ({len(self.person_embeddings)} persons)")
            lines.append("  Embeddings extracted for person tracking across cameras")

        # Image Quality Assessment
        if self.image_quality:
            lines.append("## Image Quality Assessment")
            lines.append(f"  {self.image_quality.format_context()}")
            if self.quality_change_detected:
                lines.append(f"  **ALERT**: {self.quality_change_description}")

        if not lines:
            return "No additional context extracted."

        return "\n\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of enrichment results
        """
        return {
            "license_plates": [
                {
                    "bbox": plate.bbox.to_tuple(),
                    "text": plate.text,
                    "confidence": plate.confidence,
                    "ocr_confidence": plate.ocr_confidence,
                    "source_detection_id": plate.source_detection_id,
                }
                for plate in self.license_plates
            ],
            "faces": [
                {
                    "bbox": face.bbox.to_tuple(),
                    "confidence": face.confidence,
                    "source_detection_id": face.source_detection_id,
                }
                for face in self.faces
            ],
            "violence_detection": (
                self.violence_detection.to_dict() if self.violence_detection else None
            ),
            "vehicle_damage": {
                det_id: result.to_dict() for det_id, result in self.vehicle_damage.items()
            },
            "vehicle_classifications": {
                det_id: result.to_dict() for det_id, result in self.vehicle_classifications.items()
            },
            "pose_results": {
                det_id: self._serialize_pose_result(pose)
                for det_id, pose in self.pose_results.items()
            },
            "image_quality": (self.image_quality.to_dict() if self.image_quality else None),
            "depth_analysis": (self.depth_analysis.to_dict() if self.depth_analysis else None),
            "quality_change_detected": self.quality_change_detected,
            "quality_change_description": self.quality_change_description,
            "threat_detection": (
                self.threat_detection.to_dict()
                if self.threat_detection and hasattr(self.threat_detection, "to_dict")
                else None
            ),
            "age_classifications": {
                det_id: result.to_dict() if hasattr(result, "to_dict") else {}
                for det_id, result in self.age_classifications.items()
            },
            "gender_classifications": {
                det_id: result.to_dict() if hasattr(result, "to_dict") else {}
                for det_id, result in self.gender_classifications.items()
            },
            "person_embeddings": {
                det_id: result.to_dict() if hasattr(result, "to_dict") else {}
                for det_id, result in self.person_embeddings.items()
            },
            # Household matching results (NEM-3314)
            "person_household_matches": [
                {
                    "member_id": match.member_id,
                    "member_name": match.member_name,
                    "similarity": match.similarity,
                    "match_type": match.match_type,
                }
                for match in self.person_household_matches
            ],
            "vehicle_household_matches": [
                {
                    "vehicle_id": match.vehicle_id,
                    "vehicle_description": match.vehicle_description,
                    "similarity": match.similarity,
                    "match_type": match.match_type,
                }
                for match in self.vehicle_household_matches
            ],
            "vision_extraction": (
                self.vision_extraction.to_dict() if self.vision_extraction else None
            ),
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
        }

    def _serialize_pose_result(self, pose: PoseResult) -> dict[str, Any]:
        """Serialize a PoseResult to the frontend-expected PoseEnrichment format.

        Converts the internal PoseResult dataclass to the schema expected by
        the frontend (PoseEnrichment), including:
        - posture: The classified pose type
        - alerts: Security alerts based on suspicious poses
        - security_alerts: Backward compatibility alias for alerts
        - keypoints: [[x, y, confidence], ...] format for visualization
        - keypoint_count: Number of detected keypoints
        - confidence: Pose classification confidence

        Args:
            pose: PoseResult from ViTPose estimation

        Returns:
            Dictionary matching the PoseEnrichment schema
        """
        # Suspicious poses that generate security alerts
        suspicious_poses = {"crouching", "running", "lying"}

        # Generate security alerts based on pose classification
        alerts: list[str] = []
        if pose.pose_class in suspicious_poses and pose.pose_confidence > 0.5:
            alerts.append(f"person_{pose.pose_class}")

        # Convert keypoints dict to [[x, y, confidence], ...] format
        # Use COCO keypoint order for consistent indexing
        keypoint_names = [
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

        keypoints: list[list[float]] = []
        for name in keypoint_names:
            if name in pose.keypoints:
                kp = pose.keypoints[name]
                keypoints.append([kp.x, kp.y, kp.confidence])
            else:
                # Missing keypoint - use zeros
                keypoints.append([0.0, 0.0, 0.0])

        return {
            "posture": pose.pose_class,
            "alerts": alerts,
            "security_alerts": alerts,  # Backward compatibility
            "keypoints": keypoints,
            "keypoint_count": len(pose.keypoints),
            "confidence": pose.pose_confidence,
        }

    def to_prompt_context(self, time_of_day: str | None = None) -> dict[str, str]:
        """Generate all prompt context sections for MODEL_ZOO_ENHANCED template.

        Returns a dictionary of formatted context strings for each enrichment
        category, suitable for direct insertion into the prompt template.

        Args:
            time_of_day: Optional time context for risk assessment

        Returns:
            Dictionary mapping prompt field names to formatted context strings
        """
        from backend.services.prompts import (
            format_action_recognition_context,
            format_clothing_analysis_context,
            format_depth_context,
            format_image_quality_context,
            format_pet_classification_context,
            format_pose_analysis_context,
            format_vehicle_classification_context,
            format_vehicle_damage_context,
            format_violence_context,
            format_weather_context,
        )

        return {
            # Violence analysis
            "violence_context": format_violence_context(self.violence_detection),
            # Weather context
            "weather_context": format_weather_context(self.weather_classification),
            # Image quality
            "image_quality_context": format_image_quality_context(
                self.image_quality,
                self.quality_change_detected,
                self.quality_change_description,
            ),
            # Clothing analysis
            "clothing_analysis_context": format_clothing_analysis_context(
                self.clothing_classifications,
                self.clothing_segmentation,
            ),
            # Vehicle classification
            "vehicle_classification_context": format_vehicle_classification_context(
                self.vehicle_classifications
            ),
            # Vehicle damage
            "vehicle_damage_context": format_vehicle_damage_context(
                self.vehicle_damage,
                time_of_day=time_of_day,
            ),
            # Pet classification
            "pet_classification_context": format_pet_classification_context(
                self.pet_classifications
            ),
            # Pose analysis (ViTPose) - convert PoseResult to dict format
            "pose_analysis": format_pose_analysis_context(
                {
                    det_id: {
                        "classification": pose.pose_class,
                        "confidence": pose.pose_confidence,
                    }
                    for det_id, pose in self.pose_results.items()
                }
                if self.pose_results
                else None
            ),
            # Action recognition (X-CLIP)
            "action_recognition": format_action_recognition_context(
                {"0": self.action_results} if self.action_results else None
            ),
            # Depth context (Depth Anything V2)
            "depth_context": format_depth_context(self.depth_analysis),
        }

    def get_risk_modifiers(self) -> dict[str, float]:
        """Calculate risk score modifiers based on enrichment results.

        Returns a dictionary of named risk modifiers that can be used to
        adjust the base risk score from Nemotron.

        Positive values increase risk, negative values decrease risk.

        Returns:
            Dictionary mapping modifier names to float values (-1.0 to 1.0)
        """
        modifiers: dict[str, float] = {}

        # Violence detection - major risk increase
        if self.has_violence:
            assert self.violence_detection is not None
            modifiers["violence"] = 0.5 + (0.5 * self.violence_detection.confidence)

        # Pet-only event - significant risk decrease
        if self.pet_only_event:
            modifiers["pet_only"] = -0.7

        # High-confidence pets without other threats - moderate risk decrease
        elif self.has_confirmed_pets and not self.has_violence:
            modifiers["confirmed_pet"] = -0.3

        # Suspicious clothing - moderate risk increase
        if self.has_suspicious_clothing:
            modifiers["suspicious_attire"] = 0.3

        # Service uniform - moderate risk decrease (legitimate presence)
        service_uniforms = [
            c for c in self.clothing_classifications.values() if c.is_service_uniform
        ]
        if service_uniforms:
            modifiers["service_uniform"] = -0.2

        # High-security vehicle damage - major risk increase
        if self.has_high_security_damage:
            modifiers["vehicle_damage_high"] = 0.4
        elif self.has_vehicle_damage:
            modifiers["vehicle_damage"] = 0.15

        # Commercial vehicles during day - slight risk decrease
        if self.has_commercial_vehicles:
            modifiers["commercial_vehicle"] = -0.1

        # Image quality issues - slight uncertainty increase
        if self.has_quality_issues:
            modifiers["quality_issues"] = 0.1
        if self.quality_change_detected:
            modifiers["quality_change"] = 0.2

        # Suspicious poses (crouching, running, lying) - moderate risk increase
        if self.has_suspicious_poses:
            modifiers["suspicious_pose"] = 0.25

        # Action recognition - risk based on detected action
        if self.action_results:
            action_weight = self.action_risk_weight
            if action_weight >= 0.7:
                # High risk action (breaking in, vandalizing, etc.)
                modifiers["suspicious_action"] = 0.4
            elif action_weight >= 0.5:
                # Medium risk action (loitering, etc.)
                modifiers["moderate_action"] = 0.2
            elif action_weight <= 0.3:
                # Low risk action (delivering, knocking, etc.)
                modifiers["benign_action"] = -0.15

        return modifiers

    def get_summary_flags(self) -> list[dict[str, str]]:
        """Generate summary flags for the risk assessment output.

        Creates a list of flag dictionaries suitable for inclusion in
        the Nemotron JSON output format.

        Returns:
            List of flag dictionaries with type, description, and severity
        """
        flags: list[dict[str, str]] = []

        # Violence flag
        if self.has_violence:
            assert self.violence_detection is not None
            flags.append(
                {
                    "type": "violence",
                    "description": f"Violence detected ({self.violence_detection.confidence:.0%} confidence)",
                    "severity": "critical",
                }
            )

        # Suspicious attire flags
        for det_id, clothing in self.clothing_classifications.items():
            if clothing.is_suspicious:
                flags.append(
                    {
                        "type": "suspicious_attire",
                        "description": f"Person {det_id}: {clothing.top_category}",
                        "severity": "alert",
                    }
                )

        # Face covering flags from SegFormer
        for det_id, seg in self.clothing_segmentation.items():
            if seg.has_face_covered:
                flags.append(
                    {
                        "type": "face_covered",
                        "description": f"Person {det_id}: Face obscured by hat/sunglasses/scarf",
                        "severity": "alert",
                    }
                )

        # Vehicle damage flags
        for det_id, damage in self.vehicle_damage.items():
            if damage.has_high_security_damage:
                flags.append(
                    {
                        "type": "vehicle_damage",
                        "description": f"Vehicle {det_id}: {', '.join(damage.damage_types)}",
                        "severity": "critical" if damage.has_high_security_damage else "warning",
                    }
                )

        # Quality change flag
        if self.quality_change_detected:
            flags.append(
                {
                    "type": "quality_issue",
                    "description": self.quality_change_description,
                    "severity": "alert",
                }
            )

        # Suspicious pose flags
        suspicious_poses = {"crouching", "running", "lying"}
        for det_id, pose in self.pose_results.items():
            if pose.pose_class in suspicious_poses and pose.pose_confidence > 0.5:
                flags.append(
                    {
                        "type": "suspicious_pose",
                        "description": f"Person {det_id}: {pose.pose_class} ({pose.pose_confidence:.0%} confidence)",
                        "severity": "alert" if pose.pose_class == "crouching" else "warning",
                    }
                )

        # Suspicious action flag
        if self.has_suspicious_action and self.action_results:
            detected_action = self.action_results.get("detected_action", "unknown")
            confidence = self.action_results.get("confidence", 0.0)
            risk_weight = self.action_risk_weight
            severity = (
                "critical" if risk_weight >= 0.9 else "alert" if risk_weight >= 0.7 else "warning"
            )
            flags.append(
                {
                    "type": "suspicious_action",
                    "description": f"{detected_action} ({confidence:.0%} confidence)",
                    "severity": severity,
                }
            )

        return flags

    def get_enrichment_for_detection(self, detection_id: int) -> dict[str, Any] | None:
        """Get enrichment data for a specific detection.

        Aggregates all enrichment results that apply to the given detection ID.
        Returns None if no enrichment data is available for this detection.

        Args:
            detection_id: The detection ID to get enrichment for

        Returns:
            Dictionary with detection-specific enrichment data, or None if no data
        """
        enrichment: dict[str, Any] = {}
        det_id_str = str(detection_id)

        # Vehicle classification
        if det_id_str in self.vehicle_classifications:
            vc = self.vehicle_classifications[det_id_str]
            enrichment["vehicle"] = {
                "type": vc.vehicle_type,
                "color": None,  # Color extraction not implemented in current classifier
                "damage": [],  # Will be filled from vehicle_damage if present
                "confidence": vc.confidence,
            }

        # Vehicle damage
        if det_id_str in self.vehicle_damage:
            vd = self.vehicle_damage[det_id_str]
            if "vehicle" not in enrichment:
                enrichment["vehicle"] = {
                    "type": None,
                    "color": None,
                    "damage": [],
                    "confidence": None,
                }
            enrichment["vehicle"]["damage"] = [
                {"type": d.damage_type, "confidence": d.confidence} for d in vd.detections
            ]

        # Pet classification
        if det_id_str in self.pet_classifications:
            pc = self.pet_classifications[det_id_str]
            enrichment["pet"] = {
                "type": pc.animal_type,
                "breed": None,  # Breed extraction not implemented in current classifier
                "confidence": pc.confidence,
            }

        # Person: clothing classification and segmentation
        if det_id_str in self.clothing_classifications:
            cc = self.clothing_classifications[det_id_str]
            detected_action = (
                self.action_results.get("detected_action") if self.action_results else None
            )
            enrichment["person"] = {
                "clothing": cc.top_category,
                "action": detected_action,
                "carrying": None,  # Future: from pose estimation
                "confidence": cc.confidence,
            }

        # Person: pose estimation (ViTPose)
        if det_id_str in self.pose_results:
            pose = self.pose_results[det_id_str]
            detected_action = (
                self.action_results.get("detected_action") if self.action_results else None
            )
            if "person" not in enrichment:
                enrichment["person"] = {
                    "clothing": None,
                    "action": detected_action,
                    "carrying": None,
                    "confidence": None,
                }
            # Basic pose info under person
            enrichment["person"]["pose"] = pose.pose_class
            enrichment["person"]["pose_confidence"] = pose.pose_confidence
            # Full pose enrichment data matching PoseEnrichment schema
            enrichment["pose"] = self._serialize_pose_result(pose)

        # Person: clothing segmentation (adds additional attributes)
        if det_id_str in self.clothing_segmentation:
            cs = self.clothing_segmentation[det_id_str]
            detected_action = (
                self.action_results.get("detected_action") if self.action_results else None
            )
            if "person" not in enrichment:
                enrichment["person"] = {
                    "clothing": None,
                    "action": detected_action,
                    "carrying": None,
                    "confidence": None,
                }
            enrichment["person"]["face_covered"] = cs.has_face_covered

        # License plates associated with this detection
        detection_plates = [
            lp for lp in self.license_plates if lp.source_detection_id == detection_id
        ]
        if detection_plates:
            # Take the highest confidence plate
            best_plate = max(detection_plates, key=lambda p: p.ocr_confidence or 0.0)
            enrichment["license_plate"] = {
                "text": best_plate.text,
                "confidence": best_plate.ocr_confidence or best_plate.confidence,
            }

        # Faces associated with this detection
        detection_faces = [f for f in self.faces if f.source_detection_id == detection_id]
        if detection_faces:
            enrichment["face_detected"] = True
            enrichment["face_count"] = len(detection_faces)

        # Shared/global enrichment data (applies to all detections in the batch)
        if self.weather_classification:
            enrichment["weather"] = {
                "condition": self.weather_classification.condition,
                "confidence": self.weather_classification.confidence,
            }

        if self.image_quality:
            enrichment["image_quality"] = {
                "score": self.image_quality.quality_score,
                "issues": list(self.image_quality.quality_issues)
                if self.image_quality.quality_issues
                else [],
            }

        # Return None if no enrichment data was collected
        return enrichment if enrichment else None


@dataclass(slots=True)
class DetectionInput:
    """Input detection for enrichment pipeline.

    Simplified detection representation for the enrichment pipeline.
    Maps from the Detection model or API schemas.

    Attributes:
        id: Detection ID (optional)
        class_name: Object class (e.g., "car", "person")
        confidence: Detection confidence
        bbox: Bounding box coordinates
        video_width: Original video/image width (for bbox scaling)
        video_height: Original video/image height (for bbox scaling)
    """

    class_name: str
    confidence: float
    bbox: BoundingBox
    id: int | None = None
    video_width: int | None = None
    video_height: int | None = None


class EnrichmentPipeline:
    """Pipeline for enriching detections with additional context.

    The EnrichmentPipeline orchestrates on-demand model loading to extract
    additional context from detections:

    1. Vehicle detections -> License plate detection -> OCR
    2. Person detections -> Face detection

    Models are loaded lazily via the ModelManager and unloaded after use
    to maximize VRAM availability for Nemotron and YOLO26v2.

    Usage:
        pipeline = EnrichmentPipeline()

        result = await pipeline.enrich_batch(detections, images)
        context = result.to_context_string()

    Attributes:
        model_manager: ModelManager instance for model loading
        min_confidence: Minimum detection confidence for enrichment
        license_plate_enabled: Whether to run license plate detection
        face_detection_enabled: Whether to run face detection
        ocr_enabled: Whether to run OCR on detected plates
    """

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        min_confidence: float = 0.5,
        license_plate_enabled: bool = True,
        face_detection_enabled: bool = True,
        ocr_enabled: bool = True,
        vision_extraction_enabled: bool = True,
        reid_enabled: bool = True,
        scene_change_enabled: bool = True,
        violence_detection_enabled: bool = True,
        weather_classification_enabled: bool = True,
        clothing_classification_enabled: bool = True,
        clothing_segmentation_enabled: bool = True,
        vehicle_damage_detection_enabled: bool = True,
        vehicle_classification_enabled: bool = True,
        image_quality_enabled: bool | None = None,
        pet_classification_enabled: bool = True,
        depth_estimation_enabled: bool = True,
        pose_estimation_enabled: bool = True,
        action_recognition_enabled: bool = True,
        household_matching_enabled: bool = False,
        frame_buffer: FrameBuffer | None = None,
        redis_client: Any | None = None,
        use_enrichment_service: bool = False,
        enrichment_client: EnrichmentClient | None = None,
        reid_service: Any | None = None,
    ) -> None:
        """Initialize the EnrichmentPipeline.

        Args:
            model_manager: ModelManager instance (uses global if not provided)
            min_confidence: Minimum confidence for detections to enrich
            license_plate_enabled: Enable license plate detection
            face_detection_enabled: Enable face detection
            ocr_enabled: Enable OCR on detected plates
            vision_extraction_enabled: Enable Florence-2 vision extraction
            reid_enabled: Enable CLIP re-identification
            scene_change_enabled: Enable scene change detection
            violence_detection_enabled: Enable violence detection (runs when 2+ persons)
            weather_classification_enabled: Enable SigLIP weather classification (runs on full frame)
            clothing_classification_enabled: Enable FashionCLIP clothing classification
            clothing_segmentation_enabled: Enable SegFormer clothing segmentation
            vehicle_damage_detection_enabled: Enable YOLOv11 vehicle damage detection
            vehicle_classification_enabled: Enable ResNet-50 vehicle type classification
            image_quality_enabled: Enable BRISQUE image quality assessment (CPU-based).
                                   Default None uses settings.image_quality_enabled (False by default
                                   due to pyiqa/NumPy 2.0 incompatibility).
            pet_classification_enabled: Enable pet classification for false positive reduction
            depth_estimation_enabled: Enable Depth Anything V2 depth estimation for spatial context
            pose_estimation_enabled: Enable ViTPose pose estimation for person detections
            action_recognition_enabled: Enable X-CLIP action recognition from frame sequences
            household_matching_enabled: Enable matching persons/vehicles against household database (NEM-3314).
                                       Disabled by default for backward compatibility.
            frame_buffer: FrameBuffer for accumulating frames for X-CLIP temporal action recognition.
                         If provided, frames are buffered per camera and X-CLIP runs on frame sequences
                         (8 frames) for better action recognition. If None, falls back to single-frame.
            redis_client: Redis client for re-id storage (optional)
            use_enrichment_service: Use HTTP service at ai-enrichment:8094 instead of local models
                                    for vehicle, pet, and clothing classification
            enrichment_client: Optional EnrichmentClient instance (uses global if not provided)
            reid_service: Optional ReIdentificationService instance with HybridEntityStorage
                         configured. When provided, entities will be persisted to PostgreSQL.
                         If not provided, uses global ReIdentificationService (Redis-only).
        """
        # Import settings to get image_quality_enabled default
        from backend.core.config import get_settings

        self.model_manager = model_manager or get_model_manager()
        self.min_confidence = min_confidence
        self.license_plate_enabled = license_plate_enabled
        self.face_detection_enabled = face_detection_enabled
        self.ocr_enabled = ocr_enabled
        self.vision_extraction_enabled = vision_extraction_enabled
        self.reid_enabled = reid_enabled
        self.scene_change_enabled = scene_change_enabled
        self.violence_detection_enabled = violence_detection_enabled
        self.weather_classification_enabled = weather_classification_enabled
        self.clothing_classification_enabled = clothing_classification_enabled
        self.clothing_segmentation_enabled = clothing_segmentation_enabled
        self.vehicle_damage_detection_enabled = vehicle_damage_detection_enabled
        self.vehicle_classification_enabled = vehicle_classification_enabled
        # Use config default if not explicitly set (disabled due to pyiqa/NumPy 2.0 incompatibility)
        if image_quality_enabled is None:
            settings = get_settings()
            self.image_quality_enabled = settings.image_quality_enabled
        else:
            self.image_quality_enabled = image_quality_enabled
        self.pet_classification_enabled = pet_classification_enabled
        self.depth_estimation_enabled = depth_estimation_enabled
        self.pose_estimation_enabled = pose_estimation_enabled
        self.action_recognition_enabled = action_recognition_enabled
        self.household_matching_enabled = household_matching_enabled
        self._previous_quality_results: dict[str, ImageQualityResult] = {}
        self.redis_client = redis_client

        # Frame buffer for X-CLIP temporal action recognition
        self._frame_buffer = frame_buffer

        # Enrichment service settings
        self.use_enrichment_service = use_enrichment_service
        self._enrichment_client = enrichment_client

        # Initialize services
        self._vision_extractor = get_vision_extractor()
        # Use provided reid_service (with HybridEntityStorage) or global (Redis-only)
        self._reid_service = reid_service if reid_service is not None else get_reid_service()
        self._scene_detector = get_scene_change_detector()

        logger.info(
            f"EnrichmentPipeline initialized: "
            f"license_plate={license_plate_enabled}, "
            f"face_detection={face_detection_enabled}, "
            f"ocr={ocr_enabled}, "
            f"vision_extraction={vision_extraction_enabled}, "
            f"reid={reid_enabled}, "
            f"scene_change={scene_change_enabled}, "
            f"household_matching={household_matching_enabled}, "
            f"use_enrichment_service={use_enrichment_service}"
        )

    def _get_enrichment_client(self) -> EnrichmentClient:
        """Get the enrichment client, creating if needed.

        Returns:
            EnrichmentClient instance
        """
        if self._enrichment_client is None:
            self._enrichment_client = get_enrichment_client()
        return self._enrichment_client

    def _handle_enrichment_error(
        self,
        operation: str,
        exc: Exception,
        result: EnrichmentResult,
    ) -> EnrichmentError:
        """Handle enrichment errors with structured logging and metrics.

        This helper function provides consistent error handling for all enrichment
        operations, including proper classification, structured logging, and metrics.

        Args:
            operation: The operation that failed (e.g., "face_detection")
            exc: The exception that was raised
            result: The EnrichmentResult to add the error to

        Returns:
            The created EnrichmentError
        """
        error = result.add_error(operation, exc)
        metric_name = f"{operation.replace('_', '_')}_error"

        # Log based on error category and transience
        match error.category:
            case ErrorCategory.SERVICE_UNAVAILABLE | ErrorCategory.TIMEOUT:
                record_pipeline_error(f"{metric_name}_transient")
                logger.warning(
                    f"{operation} service unavailable or timed out",
                    extra={"error": error.to_dict()},
                )
            case ErrorCategory.RATE_LIMITED:
                record_pipeline_error(f"{metric_name}_rate_limited")
                logger.warning(
                    f"{operation} rate limited - backing off",
                    extra={"error": error.to_dict()},
                )
            case ErrorCategory.SERVER_ERROR:
                record_pipeline_error(f"{metric_name}_server_error")
                logger.warning(
                    f"{operation} server error (transient)",
                    extra={"error": error.to_dict()},
                )
            case ErrorCategory.CLIENT_ERROR:
                # Client errors are likely bugs - log with full traceback
                record_pipeline_error(f"{metric_name}_client_error")
                logger.error(
                    f"{operation} client error (likely a bug)",
                    extra={"error": error.to_dict()},
                    exc_info=True,
                )
            case ErrorCategory.PARSE_ERROR:
                record_pipeline_error(f"{metric_name}_parse_error")
                logger.error(
                    f"{operation} response parsing failed",
                    extra={"error": error.to_dict()},
                    exc_info=True,
                )
            case ErrorCategory.VALIDATION_ERROR:
                record_pipeline_error(f"{metric_name}_validation_error")
                logger.error(
                    f"{operation} validation failed",
                    extra={"error": error.to_dict()},
                    exc_info=True,
                )
            case ErrorCategory.UNEXPECTED:
                record_pipeline_error(f"{metric_name}_unexpected")
                logger.error(
                    f"{operation} unexpected error: {sanitize_error(exc)}",
                    extra={"error": error.to_dict()},
                    exc_info=True,
                )

        return error

    async def _classify_vehicle_via_service(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleClassificationResult]:
        """Classify vehicles using the remote enrichment HTTP service.

        Args:
            vehicles: List of vehicle detections to classify
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleClassificationResult
        """
        results: dict[str, VehicleClassificationResult] = {}

        if not vehicles:
            return results

        client = self._get_enrichment_client()

        for i, vehicle in enumerate(vehicles):
            det_id = str(vehicle.id) if vehicle.id else str(i)

            try:
                # Crop vehicle from full frame
                vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                if vehicle_crop is None:
                    continue

                # Call remote service
                bbox_tuple = vehicle.bbox.to_tuple() if vehicle.bbox else None
                remote_result = await client.classify_vehicle(vehicle_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local VehicleClassificationResult

                    results[det_id] = VehicleClassificationResult(
                        vehicle_type=remote_result.vehicle_type,
                        confidence=remote_result.confidence,
                        display_name=remote_result.display_name,
                        is_commercial=remote_result.is_commercial,
                        all_scores=remote_result.all_scores,
                    )

                    logger.debug(
                        f"Vehicle {det_id} type (via service): {remote_result.vehicle_type} "
                        f"({remote_result.confidence:.0%})"
                    )

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                EnrichmentUnavailableError,
            ) as e:
                # Transient error - log warning, continue to next vehicle
                logger.warning(
                    f"Enrichment service unavailable for vehicle {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    # Client error - likely a bug, log with traceback
                    logger.error(
                        f"Vehicle classification client error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                        exc_info=True,
                    )
                else:
                    # Server error - transient, log warning
                    logger.warning(
                        f"Vehicle classification server error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                    )
            except (ValueError, KeyError, TypeError) as e:
                # Parse error - log with details
                logger.error(
                    f"Vehicle classification parse error for {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )
            except Exception as e:
                # Unexpected error - log with full details
                logger.error(
                    f"Vehicle classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )

        return results

    async def _classify_pets_via_service(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PetClassificationResult]:
        """Classify pets using the remote enrichment HTTP service.

        Args:
            animals: List of animal detections to classify
            image: Full frame image to crop animals from

        Returns:
            Dictionary mapping detection IDs to PetClassificationResult
        """
        results: dict[str, PetClassificationResult] = {}

        if not animals:
            return results

        client = self._get_enrichment_client()

        for i, animal in enumerate(animals):
            det_id = str(animal.id) if animal.id else str(i)

            try:
                # Crop animal from full frame
                animal_crop = await self._crop_to_bbox(image, animal.bbox)
                if animal_crop is None:
                    continue

                # Call remote service
                bbox_tuple = animal.bbox.to_tuple() if animal.bbox else None
                remote_result = await client.classify_pet(animal_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local PetClassificationResult
                    results[det_id] = PetClassificationResult(
                        animal_type=remote_result.pet_type,
                        confidence=remote_result.confidence,
                        cat_score=0.0,  # Remote service doesn't return raw scores
                        dog_score=0.0,
                        is_household_pet=remote_result.is_household_pet,
                    )

                    logger.debug(
                        f"Animal {det_id} classified (via service) as {remote_result.pet_type} "
                        f"({remote_result.confidence:.0%} confidence)"
                    )

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                EnrichmentUnavailableError,
            ) as e:
                # Transient error - log warning, continue to next animal
                logger.warning(
                    f"Enrichment service unavailable for animal {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    # Client error - likely a bug
                    logger.error(
                        f"Pet classification client error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                        exc_info=True,
                    )
                else:
                    # Server error - transient
                    logger.warning(
                        f"Pet classification server error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                    )
            except (ValueError, KeyError, TypeError) as e:
                # Parse error
                logger.error(
                    f"Pet classification parse error for {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )
            except Exception as e:
                # Unexpected error
                logger.error(
                    f"Pet classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )

        return results

    async def _analyze_depth(
        self,
        detections: list[DetectionInput],
        image: Image.Image,
    ) -> DepthAnalysisResult:
        """Analyze depth for all detections using Depth Anything V2.

        Runs monocular depth estimation on the full frame and extracts
        depth values at each detection bounding box. This provides spatial
        context for security analysis (how close objects are to camera).

        Args:
            detections: List of high-confidence detections with bounding boxes
            image: Full frame PIL Image

        Returns:
            DepthAnalysisResult with depth info for all detections
        """
        if not detections:
            return DepthAnalysisResult()

        # Convert DetectionInput to dict format for analyze_depth
        det_dicts = [
            {
                "detection_id": str(d.id) if d.id else str(i),
                "class_name": d.class_name,
                "bbox": d.bbox.to_tuple() if d.bbox else None,
            }
            for i, d in enumerate(detections)
        ]

        # Filter out detections without valid bboxes
        det_dicts = [d for d in det_dicts if d["bbox"] is not None]

        if not det_dicts:
            return DepthAnalysisResult()

        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("depth-anything-v2-small") as depth_pipeline:
                record_enrichment_model_call("depth")
                result = await analyze_depth(
                    depth_pipeline,
                    image,
                    det_dicts,
                    depth_sampling_method="center",
                )
                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("depth-anything-v2", duration)
                logger.debug(
                    f"Depth analysis complete: {result.detection_count} detections, "
                    f"closest={result.closest_detection_id}, "
                    f"close_objects={'yes' if result.has_close_objects else 'no'}"
                )
                return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("depth-anything-v2", duration)
            record_enrichment_model_error("depth-anything-v2")
            logger.error(
                f"Depth analysis failed: {sanitize_error(e)}",
                exc_info=True,
            )
            raise

    async def _estimate_poses(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PoseResult]:
        """Estimate poses for person detections using ViTPose.

        Runs pose estimation on each detected person to classify their body
        posture (standing, sitting, crouching, running, lying). This provides
        behavioral context for security analysis.

        Args:
            persons: List of person detections with bounding boxes
            image: Full frame PIL Image

        Returns:
            Dictionary mapping detection IDs to PoseResult
        """
        if not persons:
            return {}

        results: dict[str, PoseResult] = {}

        # Crop images for each person
        crops: list[Image.Image] = []
        bboxes: list[list[float]] = []
        det_ids: list[str] = []

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            if not person.bbox:
                continue

            # Crop person from full frame
            bbox = person.bbox.to_int_tuple()
            cropped = await self._crop_to_bbox(image, person.bbox)
            if cropped:
                crops.append(cropped)
                bboxes.append([float(x) for x in bbox])
                det_ids.append(det_id)

        if not crops:
            return {}

        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("vitpose-small") as (model, processor):
                record_enrichment_model_call("pose")
                pose_results = await extract_poses_batch(model, processor, crops, bboxes)

                for det_id, pose_result in zip(det_ids, pose_results, strict=True):
                    results[det_id] = pose_result

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("vitpose", duration)
                logger.debug(f"Pose estimation complete: {len(results)} persons analyzed")
                return results
        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("vitpose", duration)
            record_enrichment_model_error("vitpose")
            logger.error(
                f"Pose estimation failed: {sanitize_error(e)}",
                exc_info=True,
            )
            raise

    async def _get_action_frames(
        self,
        camera_id: str | None,
        current_frame: Image.Image,
        num_frames: int = 8,
    ) -> list[Image.Image]:
        """Get frames for X-CLIP action recognition.

        Retrieves a sequence of frames for temporal action recognition. If a
        FrameBuffer is configured and has enough frames for the camera, returns
        evenly sampled frames from the buffer converted to PIL Images.
        Otherwise, falls back to using just the current frame.

        X-CLIP works best with 8 frames spanning the action sequence.

        Args:
            camera_id: Camera identifier for looking up buffered frames
            current_frame: The current PIL Image (fallback if no buffer)
            num_frames: Number of frames to retrieve (default 8)

        Returns:
            List of PIL Images for action recognition (may be single-frame fallback)
        """
        import io

        # Try to get frames from buffer if available
        if self._frame_buffer is not None and camera_id is not None:
            frame_bytes_list = self._frame_buffer.get_sequence(camera_id, num_frames)
            if frame_bytes_list is not None:
                # Convert bytes to PIL Images
                pil_frames: list[Image.Image] = []
                for frame_bytes in frame_bytes_list:
                    try:
                        raw_img = Image.open(io.BytesIO(frame_bytes))
                        # Convert to RGB if needed (X-CLIP expects RGB)
                        # Always convert to ensure consistent Image type (not ImageFile)
                        img: Image.Image = raw_img.convert("RGB")
                        pil_frames.append(img)
                    except Exception as e:
                        logger.debug(f"Failed to decode buffered frame: {e}")
                        continue

                if len(pil_frames) >= num_frames:
                    logger.debug(
                        f"Using {len(pil_frames)} buffered frames for X-CLIP (camera: {camera_id})"
                    )
                    return pil_frames

        # Fallback to single current frame
        logger.debug(
            "Using single-frame fallback for X-CLIP "
            f"(camera: {camera_id}, buffer: {self._frame_buffer is not None})"
        )
        return [current_frame]

    async def _recognize_actions(
        self,
        frames: list[Image.Image],
    ) -> dict[str, Any] | None:
        """Recognize actions from frame sequence using X-CLIP.

        Runs action recognition on a sequence of frames to classify the
        activity being performed (walking, running, loitering, breaking in, etc.).
        This provides behavioral context for security analysis.

        Args:
            frames: List of PIL Images representing a temporal sequence
                   (ideally 8 frames for best results)

        Returns:
            Dictionary with detected_action, confidence, top_actions, all_scores
            or None if recognition fails
        """
        if not frames:
            return None

        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("xclip-base") as model_dict:
                record_enrichment_model_call("action")
                result = await classify_actions(model_dict, frames)

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("xclip", duration)
                logger.debug(
                    f"Action recognition complete: {result.get('detected_action')} "
                    f"({result.get('confidence', 0):.0%})"
                )
                return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("xclip", duration)
            record_enrichment_model_error("xclip")
            logger.error(
                f"Action recognition failed: {sanitize_error(e)}",
                exc_info=True,
            )
            raise

    async def _classify_clothing_via_service(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingClassification]:
        """Classify clothing using the remote enrichment HTTP service.

        Args:
            persons: List of person detections to classify
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingClassification
        """
        results: dict[str, ClothingClassification] = {}

        if not persons:
            return results

        client = self._get_enrichment_client()

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)

            try:
                # Crop person from full frame
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                # Call remote service
                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result = await client.classify_clothing(person_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local ClothingClassification
                    results[det_id] = ClothingClassification(
                        top_category=remote_result.top_category,
                        confidence=remote_result.confidence,
                        all_scores={},  # Remote service only returns top category
                        is_suspicious=remote_result.is_suspicious,
                        is_service_uniform=remote_result.is_service_uniform,
                        raw_description=remote_result.description,
                    )

                    logger.debug(
                        f"Person {det_id} clothing (via service): {remote_result.description} "
                        f"({remote_result.confidence:.0%})"
                    )

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                EnrichmentUnavailableError,
            ) as e:
                # Transient error - log warning, continue to next person
                logger.warning(
                    f"Enrichment service unavailable for person {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    # Client error - likely a bug
                    logger.error(
                        f"Clothing classification client error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                        exc_info=True,
                    )
                else:
                    # Server error - transient
                    logger.warning(
                        f"Clothing classification server error for {det_id} (HTTP {status_code})",
                        extra={"detection_id": det_id, "status_code": status_code},
                    )
            except (ValueError, KeyError, TypeError) as e:
                # Parse error
                logger.error(
                    f"Clothing classification parse error for {det_id}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )
            except Exception as e:
                # Unexpected error
                logger.error(
                    f"Clothing classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={"error_type": type(e).__name__, "detection_id": det_id},
                    exc_info=True,
                )

        return results

    async def enrich_batch(
        self,
        detections: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
        camera_id: str | None = None,
    ) -> EnrichmentResult:
        """Enrich a batch of detections with additional context.

        Processes detections through the enrichment pipeline:
        1. Filter vehicles -> run license plate detection -> run OCR
        2. Filter persons -> run face detection
        3. Run Florence-2 vision extraction for attributes
        4. Run CLIP re-identification
        5. Run scene change detection

        Args:
            detections: List of detections to enrich
            images: Dictionary mapping detection IDs to images (PIL Image, Path, or str)
                   Use None key for a single shared image
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentResult with all extracted context
        """
        import time

        start_time = time.monotonic()
        result = EnrichmentResult()

        # NEM-3797: Add span event for enrichment pipeline start
        add_span_event(
            "enrichment_pipeline.start",
            {
                "detection.count": len(detections),
                "camera.id": camera_id or "unknown",
                "license_plate.enabled": self.license_plate_enabled,
                "face_detection.enabled": self.face_detection_enabled,
                "vision_extraction.enabled": self.vision_extraction_enabled,
            },
        )

        if not detections:
            return result

        # Get the shared image for full-frame analysis
        shared_image = images.get(None)
        if shared_image:
            pil_image = await self._load_image(shared_image)
        else:
            pil_image = None

        # Filter detections by confidence
        high_conf_detections = [d for d in detections if d.confidence >= self.min_confidence]

        if not high_conf_detections:
            return result

        # Process vehicles for license plates
        if self.license_plate_enabled:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    plates = await self._detect_license_plates(vehicles, images)
                    result.license_plates.extend(plates)

                    # Run OCR on detected plates
                    if self.ocr_enabled and plates:
                        await self._read_plates(result.license_plates, images)

                except httpx.ConnectError as e:
                    error = result.add_error("license_plate_detection", e)
                    record_pipeline_error("license_plate_connection_error")
                    logger.warning(
                        "License plate detection service unavailable",
                        extra={"error": error.to_dict()},
                    )
                except httpx.TimeoutException as e:
                    error = result.add_error("license_plate_detection", e)
                    record_pipeline_error("license_plate_timeout")
                    logger.warning(
                        "License plate detection timed out",
                        extra={"error": error.to_dict()},
                    )
                except httpx.HTTPStatusError as e:
                    error = result.add_error("license_plate_detection", e)
                    record_pipeline_error("license_plate_http_error")
                    if not error.is_transient:
                        # Client errors (4xx) are likely bugs - log as error
                        logger.error(
                            f"License plate detection client error (HTTP {e.response.status_code})",
                            extra={"error": error.to_dict()},
                            exc_info=True,
                        )
                    else:
                        logger.warning(
                            f"License plate detection server error (HTTP {e.response.status_code})",
                            extra={"error": error.to_dict()},
                        )
                except (ValueError, KeyError, TypeError) as e:
                    error = result.add_error("license_plate_detection", e)
                    record_pipeline_error("license_plate_parse_error")
                    logger.error(
                        "License plate detection response parsing failed",
                        extra={"error": error.to_dict()},
                        exc_info=True,
                    )
                except Exception as e:
                    error = result.add_error("license_plate_detection", e)
                    record_pipeline_error("license_plate_unexpected_error")
                    logger.error(
                        f"License plate detection unexpected error: {sanitize_error(e)}",
                        extra={"error": error.to_dict()},
                        exc_info=True,
                    )

        # Process persons for faces
        if self.face_detection_enabled:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    faces = await self._detect_faces(persons, images)
                    result.faces.extend(faces)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("face_detection", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("face_detection", e, result)
                except Exception as e:
                    self._handle_enrichment_error("face_detection", e, result)

        # Run Florence-2 vision extraction
        if self.vision_extraction_enabled and pil_image:
            try:
                # Convert detections to dict format for VisionExtractor
                det_dicts = [
                    {
                        "class_name": d.class_name,
                        "confidence": d.confidence,
                        "bbox": d.bbox.to_tuple() if d.bbox else None,
                        "detection_id": str(d.id) if d.id else str(i),
                    }
                    for i, d in enumerate(high_conf_detections)
                ]
                result.vision_extraction = await self._vision_extractor.extract_batch_attributes(
                    pil_image, det_dicts
                )
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
                FlorenceUnavailableError,
                AIServiceError,
            ) as e:
                self._handle_enrichment_error("vision_extraction", e, result)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("vision_extraction", e, result)
            except Exception as e:
                self._handle_enrichment_error("vision_extraction", e, result)

        # Run CLIP re-identification
        if self.reid_enabled and self.redis_client and pil_image:
            try:
                await self._run_reid(high_conf_detections, pil_image, camera_id, result)
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
                CLIPUnavailableError,
                AIServiceError,
            ) as e:
                self._handle_enrichment_error("re_identification", e, result)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("re_identification", e, result)
            except Exception as e:
                self._handle_enrichment_error("re_identification", e, result)

        # Run scene change detection
        if self.scene_change_enabled and camera_id and pil_image:
            try:
                import numpy as np

                frame_array = np.array(pil_image)
                result.scene_change = self._scene_detector.detect_changes(camera_id, frame_array)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("scene_change_detection", e, result)
            except Exception as e:
                self._handle_enrichment_error("scene_change_detection", e, result)

        # Run violence detection when 2+ persons are detected (optimization)
        if self.violence_detection_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if len(persons) >= 2:
                try:
                    result.violence_detection = await self._detect_violence(pil_image)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("violence_detection", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("violence_detection", e, result)
                except Exception as e:
                    self._handle_enrichment_error("violence_detection", e, result)

        # Run weather classification on full frame (environmental context)
        if self.weather_classification_enabled and pil_image:
            try:
                result.weather_classification = await self._classify_weather(pil_image)
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
                AIServiceError,
            ) as e:
                self._handle_enrichment_error("weather_classification", e, result)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("weather_classification", e, result)
            except Exception as e:
                self._handle_enrichment_error("weather_classification", e, result)

        # Run clothing classification on person crops
        if self.clothing_classification_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    if self.use_enrichment_service:
                        result.clothing_classifications = await self._classify_clothing_via_service(
                            persons, pil_image
                        )
                    else:
                        result.clothing_classifications = await self._classify_person_clothing(
                            persons, pil_image
                        )
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    EnrichmentUnavailableError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("clothing_classification", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("clothing_classification", e, result)
                except Exception as e:
                    self._handle_enrichment_error("clothing_classification", e, result)

        # Run SegFormer clothing segmentation on person crops
        if self.clothing_segmentation_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    result.clothing_segmentation = await self._segment_person_clothing(
                        persons, pil_image
                    )
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("clothing_segmentation", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("clothing_segmentation", e, result)
                except Exception as e:
                    self._handle_enrichment_error("clothing_segmentation", e, result)

        # Run vehicle damage detection on vehicle crops
        if self.vehicle_damage_detection_enabled and pil_image:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    result.vehicle_damage = await self._detect_vehicle_damage(vehicles, pil_image)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("vehicle_damage_detection", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("vehicle_damage_detection", e, result)
                except Exception as e:
                    self._handle_enrichment_error("vehicle_damage_detection", e, result)

        # Run vehicle segment classification on vehicle crops
        if self.vehicle_classification_enabled and pil_image:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    if self.use_enrichment_service:
                        result.vehicle_classifications = await self._classify_vehicle_via_service(
                            vehicles, pil_image
                        )
                    else:
                        result.vehicle_classifications = await self._classify_vehicle_types(
                            vehicles, pil_image
                        )
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    EnrichmentUnavailableError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("vehicle_classification", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("vehicle_classification", e, result)
                except Exception as e:
                    self._handle_enrichment_error("vehicle_classification", e, result)

        # Run BRISQUE image quality assessment (CPU-based, no VRAM)
        if self.image_quality_enabled and pil_image:
            try:
                quality_result = await self._assess_image_quality(pil_image, camera_id)
                result.image_quality = quality_result

                # Check for sudden quality changes (possible tampering)
                if camera_id:
                    previous = self._previous_quality_results.get(camera_id)
                    change_detected, description = detect_quality_change(quality_result, previous)
                    result.quality_change_detected = change_detected
                    result.quality_change_description = description
                    if change_detected:
                        logger.warning(f"Camera {camera_id}: {description}")

                    # Update tracking
                    self._previous_quality_results[camera_id] = quality_result

                # Log if blur detected with person (possible running)
                persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
                if quality_result.is_blurry and persons:
                    blur_context = interpret_blur_with_motion(quality_result, has_person=True)
                    logger.info(f"Motion context: {blur_context}")

            except RuntimeError as e:
                # Model disabled is expected behavior when pyiqa is incompatible
                if "disabled" in str(e).lower():
                    logger.debug(f"Image quality assessment skipped (model disabled): {e}")
                else:
                    self._handle_enrichment_error("image_quality_assessment", e, result)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("image_quality_assessment", e, result)
            except Exception as e:
                # Check if model is disabled
                if "disabled" in str(e).lower():
                    logger.debug(f"Image quality assessment skipped (model disabled): {e}")
                else:
                    self._handle_enrichment_error("image_quality_assessment", e, result)

        # Run pet classification on dog/cat detections for false positive reduction
        if self.pet_classification_enabled and pil_image:
            animals = [d for d in high_conf_detections if d.class_name in ANIMAL_CLASSES]
            if animals:
                try:
                    if self.use_enrichment_service:
                        result.pet_classifications = await self._classify_pets_via_service(
                            animals, pil_image
                        )
                    else:
                        result.pet_classifications = await self._classify_pets(animals, pil_image)
                    if result.pet_only_event:
                        logger.info("Pet-only event detected - can skip Nemotron risk analysis")
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    EnrichmentUnavailableError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("pet_classification", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("pet_classification", e, result)
                except Exception as e:
                    self._handle_enrichment_error("pet_classification", e, result)

        # Run depth estimation for spatial context (Depth Anything V2)
        if self.depth_estimation_enabled and pil_image and high_conf_detections:
            try:
                result.depth_analysis = await self._analyze_depth(high_conf_detections, pil_image)
            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
                AIServiceError,
            ) as e:
                self._handle_enrichment_error("depth_estimation", e, result)
            except (ValueError, KeyError, TypeError) as e:
                self._handle_enrichment_error("depth_estimation", e, result)
            except Exception as e:
                self._handle_enrichment_error("depth_estimation", e, result)

        # Run pose estimation on person detections (ViTPose)
        if self.pose_estimation_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    result.pose_results = await self._estimate_poses(persons, pil_image)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("pose_estimation", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("pose_estimation", e, result)
                except Exception as e:
                    self._handle_enrichment_error("pose_estimation", e, result)

        # Run action recognition on frame sequence (X-CLIP)
        # X-CLIP performs best with 8 frames for temporal action recognition
        if self.action_recognition_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    # Get frames from buffer if available, otherwise fall back to single frame
                    frames = await self._get_action_frames(camera_id, pil_image)
                    if frames:
                        result.action_results = await self._recognize_actions(frames)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    AIServiceError,
                ) as e:
                    self._handle_enrichment_error("action_recognition", e, result)
                except (ValueError, KeyError, TypeError) as e:
                    self._handle_enrichment_error("action_recognition", e, result)
                except Exception as e:
                    self._handle_enrichment_error("action_recognition", e, result)

        # Run household matching against known persons and vehicles (NEM-3314)
        if self.household_matching_enabled:
            try:
                await self._run_household_matching(high_conf_detections, result)
            except Exception as e:
                self._handle_enrichment_error("household_matching", e, result)

        result.processing_time_ms = (time.monotonic() - start_time) * 1000

        # NEM-3797: Add span event for enrichment pipeline complete
        add_span_event(
            "enrichment_pipeline.complete",
            {
                "license_plate.count": len(result.license_plates),
                "face.count": len(result.faces),
                "vision_extraction.enabled": result.vision_extraction is not None,
                "reid.has_matches": result.has_reid_matches,
                "scene_change.detected": result.has_scene_change,
                "clothing_classification.count": len(result.clothing_classifications),
                "vehicle_classification.count": len(result.vehicle_classifications),
                "pet_classification.count": len(result.pet_classifications),
                "depth_analysis.enabled": result.depth_analysis is not None,
                "pose_result.count": len(result.pose_results),
                "action_recognition.enabled": result.action_results is not None,
                "image_quality.assessed": result.image_quality is not None,
                "household_person_match.count": len(result.person_household_matches),
                "household_vehicle_match.count": len(result.vehicle_household_matches),
                "error.count": len(result.errors),
                "processing.duration_ms": int(result.processing_time_ms),
            },
        )

        logger.info(
            f"Enrichment complete: {len(result.license_plates)} plates, "
            f"{len(result.faces)} faces, "
            f"vision={'yes' if result.vision_extraction else 'no'}, "
            f"reid={'yes' if result.has_reid_matches else 'no'}, "
            f"scene_change={'yes' if result.has_scene_change else 'no'}, "
            f"clothing_class={len(result.clothing_classifications)}, "
            f"clothing_seg={len(result.clothing_segmentation)}, "
            f"vehicle_damage={len(result.vehicle_damage)}, "
            f"vehicle_class={len(result.vehicle_classifications)}, "
            f"pets={len(result.pet_classifications)}, "
            f"depth={'yes' if result.depth_analysis else 'no'}, "
            f"pose={len(result.pose_results)}, "
            f"action={'yes' if result.action_results else 'no'}, "
            f"quality={'yes' if result.image_quality else 'no'}, "
            f"household_persons={len(result.person_household_matches)}, "
            f"household_vehicles={len(result.vehicle_household_matches)} "
            f"in {result.processing_time_ms:.1f}ms"
        )

        return result

    async def _run_reid(
        self,
        detections: list[DetectionInput],
        image: Image.Image,
        camera_id: str | None,
        result: EnrichmentResult,
    ) -> None:
        """Run re-identification on detections.

        Args:
            detections: List of detections
            image: Full frame image
            camera_id: Camera ID
            result: EnrichmentResult to update
        """
        from datetime import datetime

        from redis.asyncio import Redis

        # Ensure redis_client is available (caller should check before calling)
        assert self.redis_client is not None, "redis_client required for re-id"
        redis: Redis = self.redis_client  # type: ignore[assignment]

        # CLIP model is now accessed via HTTP service (ai-clip)
        # The context manager is kept for compatibility but model is unused
        async with self.model_manager.load("clip-vit-l"):
            for i, det in enumerate(detections):
                det_id = str(det.id) if det.id else str(i)

                # Use pattern matching for entity type classification
                # Only process person and vehicle detections for re-identification
                match det.class_name:
                    case _ if det.class_name == PERSON_CLASS:
                        entity_type = "person"
                    case _ if det.class_name in VEHICLE_CLASSES:
                        entity_type = "vehicle"
                    case _:
                        continue  # Skip non-person/vehicle detections

                try:
                    # Generate embedding using ai-clip HTTP service
                    # Scale bbox if image was resized (e.g., thumbnail vs original video)
                    bbox = None
                    if det.bbox:
                        bbox_tuple = det.bbox.to_int_tuple()
                        # Check if we need to scale the bbox
                        if det.video_width and det.video_height:
                            img_width, img_height = image.size
                            # Only scale if dimensions differ
                            if img_width != det.video_width or img_height != det.video_height:
                                scale_x = img_width / det.video_width
                                scale_y = img_height / det.video_height
                                bbox = (
                                    int(bbox_tuple[0] * scale_x),
                                    int(bbox_tuple[1] * scale_y),
                                    int(bbox_tuple[2] * scale_x),
                                    int(bbox_tuple[3] * scale_y),
                                )
                            else:
                                bbox = bbox_tuple
                        else:
                            bbox = bbox_tuple
                    embedding = await self._reid_service.generate_embedding(image, bbox=bbox)

                    # Find matches
                    matches = await self._reid_service.find_matching_entities(
                        redis,
                        embedding,
                        entity_type=entity_type,
                        exclude_detection_id=det_id,
                    )

                    if matches:
                        # Use pattern matching to route matches to appropriate storage
                        match entity_type:
                            case "person":
                                result.person_reid_matches[det_id] = matches
                            case "vehicle":
                                result.vehicle_reid_matches[det_id] = matches

                    # Store this embedding for future matching
                    attrs = {}
                    if result.vision_extraction:
                        if det_id in result.vision_extraction.person_attributes:
                            p_attrs = result.vision_extraction.person_attributes[det_id]
                            attrs = {
                                "clothing": p_attrs.clothing,
                                "carrying": p_attrs.carrying,
                            }
                        elif det_id in result.vision_extraction.vehicle_attributes:
                            v_attrs = result.vision_extraction.vehicle_attributes[det_id]
                            attrs = {
                                "color": v_attrs.color,
                                "vehicle_type": v_attrs.vehicle_type,
                            }

                    entity_embedding = EntityEmbedding(
                        entity_type=entity_type,
                        embedding=embedding,
                        camera_id=camera_id or "unknown",
                        timestamp=datetime.now(UTC),
                        detection_id=det_id,
                        attributes=attrs,
                    )
                    await self._reid_service.store_embedding(redis, entity_embedding)

                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    httpx.HTTPStatusError,
                    CLIPUnavailableError,
                    AIServiceError,
                ) as e:
                    # Transient error - log as warning, continue processing other detections
                    logger.warning(
                        f"Re-id failed for detection {det_id} (transient)",
                        extra={
                            "error_type": type(e).__name__,
                            "detection_id": det_id,
                            "entity_type": entity_type,
                        },
                    )
                except (ValueError, KeyError, TypeError) as e:
                    # Parse/validation error - log as error with traceback
                    logger.error(
                        f"Re-id failed for detection {det_id} (parse error)",
                        extra={
                            "error_type": type(e).__name__,
                            "detection_id": det_id,
                            "entity_type": entity_type,
                        },
                        exc_info=True,
                    )
                except Exception as e:
                    # Unexpected error - log with full details
                    logger.error(
                        f"Re-id failed for detection {det_id}: {sanitize_error(e)}",
                        extra={
                            "error_type": type(e).__name__,
                            "detection_id": det_id,
                            "entity_type": entity_type,
                        },
                        exc_info=True,
                    )

    async def _run_household_matching(
        self,
        detections: list[DetectionInput],
        result: EnrichmentResult,
    ) -> None:
        """Match persons and vehicles against known household members and vehicles (NEM-3314).

        This method performs household matching to identify known persons and
        registered vehicles in the current detections. Matches are stored in
        the EnrichmentResult for use by the NemotronAnalyzer to reduce risk
        scores for recognized household members.

        Matching Flow:
        1. For person detections: Extract embeddings from person_embeddings field
           and match against HouseholdMember embeddings via cosine similarity
        2. For vehicles: Match by license plate text from detected plates

        Args:
            detections: List of high-confidence detections
            result: EnrichmentResult to update with household matches

        Note:
            This method accesses the database via a session and should not fail
            the entire enrichment pipeline if matching fails.
        """
        import numpy as np

        from backend.core.database import get_session

        matcher = get_household_matcher()

        # Extract persons for matching (vehicles matched by plate below)
        persons = [d for d in detections if d.class_name == PERSON_CLASS]

        async with get_session() as session:
            # Match persons by embedding similarity
            for i, person in enumerate(persons):
                det_id = str(person.id) if person.id else str(i)

                # Get person embedding from the result if available
                # Person embeddings come from OSNet or other re-ID models
                if det_id in result.person_embeddings:
                    embedding_result = result.person_embeddings[det_id]
                    # Extract the actual embedding array from the result
                    if hasattr(embedding_result, "embedding"):
                        embedding = embedding_result.embedding
                    elif isinstance(embedding_result, dict) and "embedding" in embedding_result:
                        embedding = embedding_result["embedding"]
                    else:
                        continue

                    # Convert to numpy array if needed
                    if not isinstance(embedding, np.ndarray):
                        try:
                            embedding = np.array(embedding, dtype=np.float32)
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Could not convert embedding to numpy array for person {det_id}"
                            )
                            continue

                    try:
                        match = await matcher.match_person(embedding, session)
                        if match:
                            result.person_household_matches.append(match)
                            logger.debug(
                                "Person matched to household member",
                                extra={
                                    "detection_id": det_id,
                                    "member_name": match.member_name,
                                    "similarity": match.similarity,
                                },
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to match person {det_id} against household: {sanitize_error(e)}",
                            extra={"detection_id": det_id, "error_type": type(e).__name__},
                        )

            # Match vehicles by license plate
            if result.has_readable_plates:
                for plate_result in result.license_plates:
                    if plate_result.text:
                        try:
                            match = await matcher.match_vehicle(
                                license_plate=plate_result.text,
                                vehicle_embedding=None,  # Visual matching not yet implemented
                                vehicle_type="car",  # Default type
                                color=None,
                                session=session,
                            )
                            if match:
                                result.vehicle_household_matches.append(match)
                                logger.debug(
                                    "Vehicle matched by license plate",
                                    extra={
                                        "plate": plate_result.text,
                                        "vehicle_description": match.vehicle_description,
                                    },
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to match vehicle plate {plate_result.text}: {sanitize_error(e)}",
                                extra={
                                    "plate": plate_result.text,
                                    "error_type": type(e).__name__,
                                },
                            )

    async def _detect_license_plates(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Detect license plates in vehicle detections.

        Args:
            vehicles: List of vehicle detections
            images: Dictionary mapping detection IDs to images

        Returns:
            List of detected license plates
        """
        results: list[LicensePlateResult] = []

        try:
            async with self.model_manager.load("yolo11-license-plate") as model:
                for vehicle in vehicles:
                    image = self._get_image_for_detection(vehicle, images)
                    if image is None:
                        continue

                    # Crop to vehicle bounding box for more accurate plate detection
                    cropped = await self._crop_to_bbox(image, vehicle.bbox)
                    if cropped is None:
                        continue

                    # Run plate detection
                    plates = await self._run_yolo_detection(model, cropped, vehicle.id)
                    results.extend(plates)

        except KeyError:
            logger.warning("yolo11-license-plate model not available")
        except RuntimeError:
            logger.error("License plate detection error", exc_info=True)

        return results

    async def _read_plates(
        self,
        plates: list[LicensePlateResult],
        images: dict[int | None, Image.Image | Path | str],
    ) -> None:
        """Run OCR on detected license plates to extract text.

        Updates the plates in-place with OCR results.

        Args:
            plates: List of detected plates to OCR
            images: Dictionary mapping detection IDs to images
        """
        if not plates:
            return

        try:
            async with self.model_manager.load("paddleocr") as ocr:
                for plate in plates:
                    # Get the original image
                    image = images.get(plate.source_detection_id) or images.get(None)
                    if image is None:
                        continue

                    # Load image if path
                    pil_image = await self._load_image(image)
                    if pil_image is None:
                        continue

                    # Crop to plate bounding box
                    cropped = await self._crop_to_bbox(pil_image, plate.bbox)
                    if cropped is None:
                        continue

                    # Run OCR
                    text, confidence = await self._run_ocr(ocr, cropped)
                    plate.text = text
                    plate.ocr_confidence = confidence

        except KeyError:
            logger.warning("paddleocr model not available")
        except RuntimeError:
            logger.error("OCR error", exc_info=True)

    async def _detect_faces(
        self,
        persons: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[FaceResult]:
        """Detect faces in person detections.

        Args:
            persons: List of person detections
            images: Dictionary mapping detection IDs to images

        Returns:
            List of detected faces
        """
        results: list[FaceResult] = []

        try:
            async with self.model_manager.load("yolo11-face") as model:
                for person in persons:
                    image = self._get_image_for_detection(person, images)
                    if image is None:
                        continue

                    # Crop to person bounding box for more accurate face detection
                    cropped = await self._crop_to_bbox(image, person.bbox)
                    if cropped is None:
                        continue

                    # Run face detection
                    faces = await self._run_face_detection(model, cropped, person.id)
                    results.extend(faces)

        except KeyError:
            logger.warning("yolo11-face model not available")
        except RuntimeError:
            logger.error("Face detection error", exc_info=True)

        return results

    def _get_image_for_detection(
        self,
        detection: DetectionInput,
        images: dict[int | None, Image.Image | Path | str],
    ) -> Image.Image | Path | str | None:
        """Get image for a specific detection.

        Args:
            detection: Detection to get image for
            images: Dictionary mapping detection IDs to images

        Returns:
            Image for the detection, or None if not found
        """
        # Try detection-specific image first
        if detection.id is not None and detection.id in images:
            return images[detection.id]

        # Fall back to shared image (None key)
        return images.get(None)

    async def _load_image(self, image: Image.Image | Path | str) -> Image.Image | None:
        """Load image from path or return if already PIL Image.

        Handles both image and video files. For video files, extracts
        a frame at 10% into the video (or 1 second, whichever is smaller).

        Args:
            image: PIL Image, Path, or string path

        Returns:
            PIL Image or None if loading fails
        """
        if isinstance(image, Image.Image):
            return image

        try:
            path = Path(image) if isinstance(image, str) else image

            # Check if this is a video file by extension
            if path.suffix.lower() in VIDEO_MIME_TYPES:
                return await self._extract_frame_from_video(path)

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: Image.open(path))
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")
            return None

    async def _extract_frame_from_video(self, video_path: Path) -> Image.Image | None:
        """Extract a single frame from a video file for enrichment processing.

        Uses ffmpeg to extract a frame at 10% into the video or 1 second,
        whichever is smaller. This avoids black frames at the start.

        Args:
            video_path: Path to the video file

        Returns:
            PIL Image of the extracted frame, or None if extraction fails
        """
        import tempfile

        from backend.services.video_processor import VideoProcessingError, VideoProcessor

        try:
            # Create a temporary VideoProcessor for frame extraction
            # Use a temp directory for the extracted frame
            with tempfile.TemporaryDirectory() as temp_dir:
                processor = VideoProcessor(output_dir=temp_dir)

                # Extract thumbnail (uses smart timestamp selection)
                output_path = Path(temp_dir) / f"{video_path.stem}_enrichment_frame.jpg"
                thumbnail_path = await processor.extract_thumbnail(
                    str(video_path),
                    output_path=str(output_path),
                )

                if thumbnail_path is None:
                    logger.warning(f"Failed to extract frame from video: {video_path}")
                    return None

                # Load the extracted frame as PIL Image
                loop = asyncio.get_event_loop()
                pil_image = await loop.run_in_executor(
                    None, lambda: Image.open(thumbnail_path).copy()
                )
                return pil_image

        except VideoProcessingError as e:
            logger.warning(f"Video processing error extracting frame from {video_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to extract frame from video {video_path}: {e}")
            return None

    async def _crop_to_bbox(
        self, image: Image.Image | Path | str, bbox: BoundingBox
    ) -> Image.Image | None:
        """Crop image to bounding box.

        Args:
            image: Image to crop
            bbox: Bounding box coordinates

        Returns:
            Cropped PIL Image or None if cropping fails
        """
        pil_image = await self._load_image(image)
        if pil_image is None:
            return None

        try:
            # Ensure coordinates are within image bounds
            width, height = pil_image.size
            x1 = int(bbox.x1)
            y1 = int(bbox.y1)
            x2 = int(bbox.x2)
            y2 = int(bbox.y2)

            # Validate and fix inverted coordinates
            if x2 < x1:
                logger.warning(
                    f"Invalid bounding box: x2 ({x2}) < x1 ({x1}). Swapping coordinates."
                )
                x1, x2 = x2, x1

            if y2 < y1:
                logger.warning(
                    f"Invalid bounding box: y2 ({y2}) < y1 ({y1}). Swapping coordinates."
                )
                y1, y2 = y2, y1

            # Clamp to image bounds after fixing inverted coordinates
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width, x2)
            y2 = min(height, y2)

            if x2 <= x1 or y2 <= y1:
                logger.warning(
                    f"Bounding box has zero or negative dimensions after clamping: "
                    f"({x1}, {y1}, {x2}, {y2}). Skipping crop."
                )
                return None

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: pil_image.crop((x1, y1, x2, y2)))
        except Exception as e:
            logger.warning(f"Failed to crop image: {e}")
            return None

    async def _run_yolo_detection(
        self, model: Any, image: Image.Image, source_detection_id: int | None
    ) -> list[LicensePlateResult]:
        """Run YOLO detection and convert results to LicensePlateResult.

        Args:
            model: Loaded YOLO model
            image: Image to run detection on
            source_detection_id: ID of the source vehicle detection

        Returns:
            List of detected license plates
        """
        results: list[LicensePlateResult] = []

        try:
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(
                None, lambda: model.predict(image, verbose=False)
            )

            if detections and len(detections) > 0:
                for det in detections[0].boxes:
                    bbox_data = det.xyxy[0].tolist()
                    conf = float(det.conf[0])

                    results.append(
                        LicensePlateResult(
                            bbox=BoundingBox(
                                x1=bbox_data[0],
                                y1=bbox_data[1],
                                x2=bbox_data[2],
                                y2=bbox_data[3],
                                confidence=conf,
                            ),
                            confidence=conf,
                            source_detection_id=source_detection_id,
                        )
                    )

        except Exception as e:
            logger.warning(f"YOLO detection failed: {e}")

        return results

    async def _run_face_detection(
        self, model: Any, image: Image.Image, source_detection_id: int | None
    ) -> list[FaceResult]:
        """Run face detection and convert results to FaceResult.

        Args:
            model: Loaded YOLO face model
            image: Image to run detection on
            source_detection_id: ID of the source person detection

        Returns:
            List of detected faces
        """
        results: list[FaceResult] = []

        try:
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(
                None, lambda: model.predict(image, verbose=False)
            )

            if detections and len(detections) > 0:
                for det in detections[0].boxes:
                    bbox_data = det.xyxy[0].tolist()
                    conf = float(det.conf[0])

                    results.append(
                        FaceResult(
                            bbox=BoundingBox(
                                x1=bbox_data[0],
                                y1=bbox_data[1],
                                x2=bbox_data[2],
                                y2=bbox_data[3],
                                confidence=conf,
                            ),
                            confidence=conf,
                            source_detection_id=source_detection_id,
                        )
                    )

        except Exception as e:
            logger.warning(f"Face detection failed: {e}")

        return results

    async def _run_ocr(self, ocr: Any, image: Image.Image) -> tuple[str, float]:
        """Run OCR on an image and extract text.

        Args:
            ocr: Loaded PaddleOCR instance
            image: Image to OCR

        Returns:
            Tuple of (text, confidence)
        """
        try:
            import numpy as np

            # Convert PIL to numpy for PaddleOCR
            loop = asyncio.get_event_loop()

            def run_ocr() -> tuple[str, float]:
                img_array = np.array(image)
                result = ocr.ocr(img_array, cls=True)

                if not result or not result[0]:
                    return "", 0.0

                # Extract text from all detected regions
                texts = []
                confidences = []

                for line in result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, tuple) and len(text_info) >= 2:
                            texts.append(text_info[0])
                            confidences.append(text_info[1])

                if not texts:
                    return "", 0.0

                # Join texts and average confidences
                combined_text = " ".join(texts).strip()
                avg_confidence = sum(confidences) / len(confidences)

                return combined_text, avg_confidence

            return await loop.run_in_executor(None, run_ocr)

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return "", 0.0

    async def _detect_violence(self, image: Image.Image) -> ViolenceDetectionResult:
        """Run violence detection on a full frame image.

        This method loads the violence detection model, runs inference,
        and returns the classification result.

        Args:
            image: PIL Image (full frame) to classify

        Returns:
            ViolenceDetectionResult with classification

        Raises:
            RuntimeError: If violence detection fails
        """
        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("violence-detection") as model_data:
                record_enrichment_model_call("violence")
                result = await classify_violence(model_data, image)
                # Record semantic metric for enrichment model call
                record_enrichment_model_call("violence-detection")
                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("violence-detection", duration)
                if result.is_violent:
                    logger.warning(f"Violence detected with {result.confidence:.0%} confidence")
                return result

        except KeyError as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("violence-detection", duration)
            record_enrichment_model_error("violence-detection")
            logger.warning("violence-detection model not available in MODEL_ZOO")
            raise RuntimeError("violence-detection model not configured") from e
        except Exception:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("violence-detection", duration)
            record_enrichment_model_error("violence-detection")
            logger.error("Violence detection error", exc_info=True)
            raise

    async def _classify_weather(self, image: Image.Image) -> WeatherResult:
        """Run weather classification on a full frame image.

        This method loads the weather classification model, runs inference,
        and returns the classification result. Weather context helps Nemotron
        calibrate risk assessments based on visibility and environmental conditions.

        Args:
            image: PIL Image (full frame) to classify

        Returns:
            WeatherResult with condition and confidence

        Raises:
            RuntimeError: If weather classification fails
        """
        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("weather-classification") as model_data:
                record_enrichment_model_call("weather")
                result = await classify_weather(model_data, image)
                # Record semantic metric for enrichment model call
                record_enrichment_model_call("weather-classification")
                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("weather-classification", duration)
                logger.info(
                    f"Weather classified as {result.simple_condition} "
                    f"({result.confidence:.0%} confidence)"
                )
                return result

        except KeyError as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("weather-classification", duration)
            record_enrichment_model_error("weather-classification")
            logger.warning("weather-classification model not available in MODEL_ZOO")
            raise RuntimeError("weather-classification model not configured") from e
        except Exception:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("weather-classification", duration)
            record_enrichment_model_error("weather-classification")
            logger.error("Weather classification error", exc_info=True)
            raise

    async def _classify_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingClassification]:
        """Classify clothing for each person detection using FashionCLIP.

        Args:
            persons: List of person detections to classify
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingClassification results
        """
        results: dict[str, ClothingClassification] = {}

        if not persons:
            return results

        try:
            async with self.model_manager.load("fashion-clip") as model_data:
                record_enrichment_model_call("clothing")
                for i, person in enumerate(persons):
                    det_id = str(person.id) if person.id else str(i)

                    try:
                        # Crop person from full frame
                        person_crop = await self._crop_to_bbox(image, person.bbox)
                        if person_crop is None:
                            continue

                        # Classify clothing
                        classification = await classify_clothing(model_data, person_crop)
                        results[det_id] = classification

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("fashion-clip")

                        logger.debug(
                            f"Person {det_id} clothing: {classification.raw_description} "
                            f"({classification.confidence:.0%})"
                        )

                    except Exception as e:
                        logger.warning(f"Clothing classification failed for person {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning(
                "fashion-clip model not available in MODEL_ZOO",
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                },
            )
        except (
            EnrichmentUnavailableError,
            AIServiceError,
            FlorenceUnavailableError,
            CLIPUnavailableError,
        ) as e:
            # Service unavailable - transient, log as warning
            logger.warning(
                f"Clothing classification service unavailable: {sanitize_error(e)}",
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.ConnectError as e:
            # Connection error - transient, log as warning
            logger.warning(
                f"Clothing classification connection failed: {sanitize_error(e)}",
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.TimeoutException as e:
            # Timeout - transient, log as warning
            logger.warning(
                f"Clothing classification timed out: {sanitize_error(e)}",
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.TIMEOUT.value,
                    "is_transient": True,
                },
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            # 5xx = transient server error, 4xx = permanent client error
            if 500 <= status_code < 600:
                logger.warning(
                    f"Clothing classification server error (HTTP {status_code})",
                    extra={
                        "detection_type": "person",
                        "operation": "clothing_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.SERVER_ERROR.value,
                        "status_code": status_code,
                        "is_transient": True,
                    },
                )
            else:
                # 4xx errors are permanent - likely a bug
                logger.error(
                    f"Clothing classification client error (HTTP {status_code})",
                    extra={
                        "detection_type": "person",
                        "operation": "clothing_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.CLIENT_ERROR.value,
                        "status_code": status_code,
                        "is_transient": False,
                    },
                )
        except (ValueError, TypeError) as e:
            # Parse/validation errors - permanent, log as error
            logger.error(
                f"Clothing classification parse error: {sanitize_error(e)}",
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                    "is_transient": False,
                },
            )
        except Exception:
            # Unexpected error - log with full traceback for debugging
            logger.error(
                "Clothing classification error",
                exc_info=True,
                extra={
                    "detection_type": "person",
                    "operation": "clothing_classification",
                    "error_category": ErrorCategory.UNEXPECTED.value,
                    "is_transient": True,
                },
            )

        return results

    async def _segment_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingSegmentationResult]:
        """Segment clothing for each person detection using SegFormer.

        Runs SegFormer B2 Clothes model on person crops to extract detailed
        clothing segmentation including hats, sunglasses, upper clothes, pants,
        dress, bags, shoes, and other apparel items.

        Args:
            persons: List of person detections to segment
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingSegmentationResult
        """
        from backend.services.segformer_loader import segment_clothing

        results: dict[str, ClothingSegmentationResult] = {}

        if not persons:
            return results

        try:
            async with self.model_manager.load("segformer-b2-clothes") as model_data:
                model, processor = model_data

                for i, person in enumerate(persons):
                    det_id = str(person.id) if person.id else str(i)

                    try:
                        # Crop person from full frame
                        person_crop = await self._crop_to_bbox(image, person.bbox)
                        if person_crop is None:
                            continue

                        # Segment clothing
                        segmentation = await segment_clothing(model, processor, person_crop)
                        results[det_id] = segmentation

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("segformer-b2-clothes")

                        logger.debug(
                            f"Person {det_id} clothing items: {segmentation.clothing_items}, "
                            f"face_covered={segmentation.has_face_covered}, "
                            f"has_bag={segmentation.has_bag}"
                        )

                    except Exception as e:
                        logger.warning(f"Clothing segmentation failed for person {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("segformer-b2-clothes model not available in MODEL_ZOO")
        except Exception:
            logger.error("Clothing segmentation error", exc_info=True)

        return results

    async def _classify_vehicle_types(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleClassificationResult]:
        """Classify vehicle types for each vehicle detection using ResNet-50.

        Runs the vehicle segment classification model on vehicle crops to identify
        specific vehicle types (car, pickup_truck, work_van, etc.).

        Args:
            vehicles: List of vehicle detections to classify
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleClassificationResult
        """
        results: dict[str, VehicleClassificationResult] = {}

        if not vehicles:
            return results

        try:
            async with self.model_manager.load("vehicle-segment-classification") as model_data:
                record_enrichment_model_call("vehicle")
                for i, vehicle in enumerate(vehicles):
                    det_id = str(vehicle.id) if vehicle.id else str(i)

                    try:
                        # Crop vehicle from full frame
                        vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                        if vehicle_crop is None:
                            continue

                        # Classify vehicle type
                        classification = await classify_vehicle(model_data, vehicle_crop)
                        results[det_id] = classification

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("vehicle-segment-classification")

                        logger.debug(
                            f"Vehicle {det_id} type: {classification.vehicle_type} "
                            f"({classification.confidence:.0%})"
                        )

                    except Exception as e:
                        logger.warning(f"Vehicle classification failed for vehicle {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning(
                "vehicle-segment-classification model not available in MODEL_ZOO",
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                },
            )
        except (
            EnrichmentUnavailableError,
            AIServiceError,
            FlorenceUnavailableError,
            CLIPUnavailableError,
        ) as e:
            # Service unavailable - transient, log as warning
            logger.warning(
                f"Vehicle classification service unavailable: {sanitize_error(e)}",
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.ConnectError as e:
            # Connection error - transient, log as warning
            logger.warning(
                f"Vehicle classification connection failed: {sanitize_error(e)}",
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.TimeoutException as e:
            # Timeout - transient, log as warning
            logger.warning(
                f"Vehicle classification timed out: {sanitize_error(e)}",
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.TIMEOUT.value,
                    "is_transient": True,
                },
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            # 5xx = transient server error, 4xx = permanent client error
            if 500 <= status_code < 600:
                logger.warning(
                    f"Vehicle classification server error (HTTP {status_code})",
                    extra={
                        "detection_type": "vehicle",
                        "operation": "vehicle_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.SERVER_ERROR.value,
                        "status_code": status_code,
                        "is_transient": True,
                    },
                )
            else:
                # 4xx errors are permanent - likely a bug
                logger.error(
                    f"Vehicle classification client error (HTTP {status_code})",
                    extra={
                        "detection_type": "vehicle",
                        "operation": "vehicle_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.CLIENT_ERROR.value,
                        "status_code": status_code,
                        "is_transient": False,
                    },
                )
        except (ValueError, TypeError) as e:
            # Parse/validation errors - permanent, log as error
            logger.error(
                f"Vehicle classification parse error: {sanitize_error(e)}",
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                    "is_transient": False,
                },
            )
        except Exception:
            # Unexpected error - log with full traceback for debugging
            logger.error(
                "Vehicle classification error",
                exc_info=True,
                extra={
                    "detection_type": "vehicle",
                    "operation": "vehicle_classification",
                    "error_category": ErrorCategory.UNEXPECTED.value,
                    "is_transient": True,
                },
            )

        return results

    async def _detect_vehicle_damage(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleDamageResult]:
        """Detect damage on vehicle detections using YOLOv11-seg.

        Runs the vehicle damage detection model on vehicle crops to identify:
        - cracks: Surface cracks in paint/body
        - dents: Impact dents on body panels
        - glass_shatter: Broken/shattered glass (HIGH SECURITY)
        - lamp_broken: Damaged headlights/taillights (HIGH SECURITY)
        - scratches: Surface scratches on paint
        - tire_flat: Flat or damaged tires

        Security Value:
        - glass_shatter + lamp_broken at night = suspicious (break-in/vandalism)
        - Fresh damage on parked vehicles = possible hit-and-run or vandalism

        Args:
            vehicles: List of vehicle detections to analyze
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleDamageResult
        """
        results: dict[str, VehicleDamageResult] = {}

        if not vehicles:
            return results

        try:
            async with self.model_manager.load("vehicle-damage-detection") as model:
                for i, vehicle in enumerate(vehicles):
                    det_id = str(vehicle.id) if vehicle.id else str(i)

                    try:
                        # Crop vehicle from full frame
                        vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                        if vehicle_crop is None:
                            continue

                        # Detect damage
                        damage_result = await detect_vehicle_damage(model, vehicle_crop)
                        results[det_id] = damage_result

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("vehicle-damage-detection")

                        if damage_result.has_damage:
                            logger.info(
                                f"Vehicle {det_id} damage detected: "
                                f"types={damage_result.damage_types}, "
                                f"count={damage_result.total_damage_count}, "
                                f"high_security={damage_result.has_high_security_damage}"
                            )

                    except Exception as e:
                        logger.warning(f"Vehicle damage detection failed for vehicle {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("vehicle-damage-detection model not available in MODEL_ZOO")
        except Exception:
            logger.error("Vehicle damage detection error", exc_info=True)

        return results

    async def _assess_image_quality(
        self,
        image: Image.Image,
        camera_id: str | None = None,
    ) -> ImageQualityResult:
        """Assess image quality using BRISQUE metric.

        BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator) is a
        no-reference image quality metric that detects blur, noise, and
        other quality degradations.

        Security use cases:
        - Sudden quality drop = possible camera obstruction/tampering
        - High blur + person = fast movement (running)
        - Consistent low quality = camera maintenance needed

        Args:
            image: PIL Image to assess
            camera_id: Camera ID for tracking quality over time

        Returns:
            ImageQualityResult with quality assessment

        Raises:
            RuntimeError: If quality assessment fails
        """
        start_time = time.perf_counter()
        try:
            async with self.model_manager.load("brisque-quality") as model_data:
                record_enrichment_model_call("brisque")
                result = await assess_image_quality(model_data, image)

                # Record semantic metric for enrichment model call
                record_enrichment_model_call("brisque-quality")
                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("brisque-quality", duration)

                if result.is_low_quality:
                    camera_str = f" (camera: {camera_id})" if camera_id else ""
                    logger.debug(
                        f"Low quality image detected{camera_str}: "
                        f"score={result.quality_score:.0f}, "
                        f"issues={result.quality_issues}"
                    )

                return result

        except KeyError as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("brisque-quality", duration)
            record_enrichment_model_error("brisque-quality")
            logger.warning("brisque-quality model not available in MODEL_ZOO")
            raise RuntimeError("brisque-quality model not configured") from e
        except RuntimeError as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("brisque-quality", duration)
            # Model disabled is expected behavior, log at debug level
            if "disabled" in str(e).lower():
                logger.debug(f"Image quality assessment skipped: {e}")
            else:
                record_enrichment_model_error("brisque-quality")
                logger.error("Image quality assessment error (runtime)", exc_info=True)
            raise
        except Exception:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("brisque-quality", duration)
            record_enrichment_model_error("brisque-quality")
            logger.error("Image quality assessment error", exc_info=True)
            raise

    async def _classify_pets(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PetClassificationResult]:
        """Classify pets (dog/cat) for false positive reduction.

        Runs the ResNet-18 pet classifier on animal crop detections to
        distinguish between cats and dogs. High-confidence pet detections
        can be used to skip Nemotron risk analysis for false positive reduction.

        Args:
            animals: List of animal detections (cat/dog classes from YOLO26v2)
            image: Full frame image to crop animals from

        Returns:
            Dictionary mapping detection IDs to PetClassificationResult
        """
        results: dict[str, PetClassificationResult] = {}

        if not animals:
            return results

        try:
            async with self.model_manager.load("pet-classifier") as model_data:
                record_enrichment_model_call("pet")
                for i, animal in enumerate(animals):
                    det_id = str(animal.id) if animal.id else str(i)

                    try:
                        # Crop animal from full frame
                        animal_crop = await self._crop_to_bbox(image, animal.bbox)
                        if animal_crop is None:
                            continue

                        # Classify pet
                        pet_result = await classify_pet(model_data, animal_crop)
                        results[det_id] = pet_result

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("pet-classifier")

                        logger.debug(
                            f"Animal {det_id} classified as {pet_result.animal_type} "
                            f"({pet_result.confidence:.0%} confidence), "
                            f"is_household_pet={pet_result.is_household_pet}"
                        )

                    except Exception as e:
                        logger.warning(f"Pet classification failed for animal {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning(
                "pet-classifier model not available in MODEL_ZOO",
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                },
            )
        except (
            EnrichmentUnavailableError,
            AIServiceError,
            FlorenceUnavailableError,
            CLIPUnavailableError,
        ) as e:
            # Service unavailable - transient, log as warning
            logger.warning(
                f"Pet classification service unavailable: {sanitize_error(e)}",
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.ConnectError as e:
            # Connection error - transient, log as warning
            logger.warning(
                f"Pet classification connection failed: {sanitize_error(e)}",
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.SERVICE_UNAVAILABLE.value,
                    "is_transient": True,
                },
            )
        except httpx.TimeoutException as e:
            # Timeout - transient, log as warning
            logger.warning(
                f"Pet classification timed out: {sanitize_error(e)}",
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.TIMEOUT.value,
                    "is_transient": True,
                },
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            # 5xx = transient server error, 4xx = permanent client error
            if 500 <= status_code < 600:
                logger.warning(
                    f"Pet classification server error (HTTP {status_code})",
                    extra={
                        "detection_type": "animal",
                        "operation": "pet_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.SERVER_ERROR.value,
                        "status_code": status_code,
                        "is_transient": True,
                    },
                )
            else:
                # 4xx errors are permanent - likely a bug
                logger.error(
                    f"Pet classification client error (HTTP {status_code})",
                    extra={
                        "detection_type": "animal",
                        "operation": "pet_classification",
                        "error_type": type(e).__name__,
                        "error_category": ErrorCategory.CLIENT_ERROR.value,
                        "status_code": status_code,
                        "is_transient": False,
                    },
                )
        except (ValueError, TypeError) as e:
            # Parse/validation errors - permanent, log as error
            logger.error(
                f"Pet classification parse error: {sanitize_error(e)}",
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_type": type(e).__name__,
                    "error_category": ErrorCategory.PARSE_ERROR.value,
                    "is_transient": False,
                },
            )
        except Exception:
            # Unexpected error - log with full traceback for debugging
            logger.error(
                "Pet classification error",
                exc_info=True,
                extra={
                    "detection_type": "animal",
                    "operation": "pet_classification",
                    "error_category": ErrorCategory.UNEXPECTED.value,
                    "is_transient": True,
                },
            )

        return results

    async def enrich_batch_with_tracking(
        self,
        detections: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
        camera_id: str | None = None,
    ) -> EnrichmentTrackingResult:
        """Enrich a batch with tracking of individual model success/failure.

        This method wraps enrich_batch and tracks which enrichment models
        succeeded or failed, providing visibility into partial failures
        instead of silently degrading.

        Args:
            detections: List of detections to enrich
            images: Dictionary mapping detection IDs to images
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentTrackingResult with status, model results, and data
        """
        from backend.core.metrics import (
            record_enrichment_batch_status,
            record_enrichment_failure,
            record_enrichment_partial_batch,
            set_enrichment_success_rate,
        )

        # Track which models were attempted and their success/failure
        successful_models: list[str] = []
        failed_models: list[str] = []
        errors: dict[str, str] = {}

        # If no detections, return skipped status
        if not detections:
            tracking_result = EnrichmentTrackingResult(
                status=EnrichmentStatus.SKIPPED,
                successful_models=[],
                failed_models=[],
                errors={},
                data=None,
            )
            record_enrichment_batch_status("skipped")
            return tracking_result

        # Run the standard enrichment and capture results
        result = await self.enrich_batch(detections, images, camera_id)

        # Analyze which models succeeded/failed based on result.errors
        # and the presence of enrichment data

        # Map of error message operation names to model names
        # New structured error format: "{operation} failed: ..."
        error_model_mapping = {
            "license_plate_detection": "license_plate",
            "face_detection": "face",
            "vision_extraction": "vision",
            "re_identification": "reid",
            "scene_change_detection": "scene_change",
            "violence_detection": "violence",
            "weather_classification": "weather",
            "clothing_classification": "clothing",
            "clothing_segmentation": "segformer",
            "vehicle_damage_detection": "vehicle_damage",
            "vehicle_classification": "vehicle_class",
            "image_quality_assessment": "image_quality",
            "pet_classification": "pet",
            "depth_estimation": "depth",
        }

        # Track failed models from errors list (new format: "{operation} failed: ...")
        for error_msg in result.errors:
            for operation, model_name in error_model_mapping.items():
                if error_msg.startswith(operation):
                    failed_models.append(model_name)
                    errors[model_name] = error_msg
                    record_enrichment_failure(model_name)
                    break

        # Determine which models were enabled and attempted
        # Get the shared image to check if image-based processing was possible
        shared_image = images.get(None)
        pil_image_available = shared_image is not None

        # Track successful models based on enabled features and results
        high_conf_detections = [d for d in detections if d.confidence >= self.min_confidence]
        has_vehicles = any(d.class_name in VEHICLE_CLASSES for d in high_conf_detections)
        has_persons = any(d.class_name == PERSON_CLASS for d in high_conf_detections)
        has_animals = any(d.class_name in ANIMAL_CLASSES for d in high_conf_detections)
        has_multiple_persons = (
            sum(1 for d in high_conf_detections if d.class_name == PERSON_CLASS) >= 2
        )

        # Check each model that was enabled and applicable
        if self.license_plate_enabled and has_vehicles:
            if "license_plate" not in failed_models:
                successful_models.append("license_plate")
                set_enrichment_success_rate("license_plate", 1.0)
            else:
                set_enrichment_success_rate("license_plate", 0.0)

        if self.face_detection_enabled and has_persons:
            if "face" not in failed_models:
                successful_models.append("face")
                set_enrichment_success_rate("face", 1.0)
            else:
                set_enrichment_success_rate("face", 0.0)

        if self.vision_extraction_enabled and pil_image_available:
            if "vision" not in failed_models and result.vision_extraction is not None:
                successful_models.append("vision")
                set_enrichment_success_rate("vision", 1.0)
            elif "vision" in failed_models:
                set_enrichment_success_rate("vision", 0.0)

        if self.reid_enabled and self.redis_client and pil_image_available:
            if "reid" not in failed_models:
                successful_models.append("reid")
                set_enrichment_success_rate("reid", 1.0)
            else:
                set_enrichment_success_rate("reid", 0.0)

        if self.scene_change_enabled and camera_id and pil_image_available:
            if "scene_change" not in failed_models:
                successful_models.append("scene_change")
                set_enrichment_success_rate("scene_change", 1.0)
            else:
                set_enrichment_success_rate("scene_change", 0.0)

        if self.violence_detection_enabled and pil_image_available and has_multiple_persons:
            if "violence" not in failed_models:
                successful_models.append("violence")
                set_enrichment_success_rate("violence", 1.0)
            else:
                set_enrichment_success_rate("violence", 0.0)

        if self.weather_classification_enabled and pil_image_available:
            if "weather" not in failed_models and result.weather_classification is not None:
                successful_models.append("weather")
                set_enrichment_success_rate("weather", 1.0)
            elif "weather" in failed_models:
                set_enrichment_success_rate("weather", 0.0)

        if self.clothing_classification_enabled and pil_image_available and has_persons:
            if "clothing" not in failed_models:
                successful_models.append("clothing")
                set_enrichment_success_rate("clothing", 1.0)
            else:
                set_enrichment_success_rate("clothing", 0.0)

        if self.clothing_segmentation_enabled and pil_image_available and has_persons:
            if "segformer" not in failed_models:
                successful_models.append("segformer")
                set_enrichment_success_rate("segformer", 1.0)
            else:
                set_enrichment_success_rate("segformer", 0.0)

        if self.vehicle_damage_detection_enabled and pil_image_available and has_vehicles:
            if "vehicle_damage" not in failed_models:
                successful_models.append("vehicle_damage")
                set_enrichment_success_rate("vehicle_damage", 1.0)
            else:
                set_enrichment_success_rate("vehicle_damage", 0.0)

        if self.vehicle_classification_enabled and pil_image_available and has_vehicles:
            if "vehicle_class" not in failed_models:
                successful_models.append("vehicle_class")
                set_enrichment_success_rate("vehicle_class", 1.0)
            else:
                set_enrichment_success_rate("vehicle_class", 0.0)

        if self.image_quality_enabled and pil_image_available:
            if "image_quality" not in failed_models and result.image_quality is not None:
                successful_models.append("image_quality")
                set_enrichment_success_rate("image_quality", 1.0)
            elif "image_quality" in failed_models:
                set_enrichment_success_rate("image_quality", 0.0)

        if self.pet_classification_enabled and pil_image_available and has_animals:
            if "pet" not in failed_models:
                successful_models.append("pet")
                set_enrichment_success_rate("pet", 1.0)
            else:
                set_enrichment_success_rate("pet", 0.0)

        if self.depth_estimation_enabled and pil_image_available and high_conf_detections:
            if "depth" not in failed_models and result.depth_analysis is not None:
                successful_models.append("depth")
                set_enrichment_success_rate("depth", 1.0)
            elif "depth" in failed_models:
                set_enrichment_success_rate("depth", 0.0)

        # Compute final status
        status = EnrichmentTrackingResult.compute_status(successful_models, failed_models)

        # Record metrics
        record_enrichment_batch_status(status.value)
        if status == EnrichmentStatus.PARTIAL:
            record_enrichment_partial_batch()

        # Create tracking result
        tracking_result = EnrichmentTrackingResult(
            status=status,
            successful_models=successful_models,
            failed_models=failed_models,
            errors=errors,
            data=result,
        )

        logger.info(
            f"Enrichment tracking for camera {camera_id}: "
            f"status={status.value}, "
            f"success={len(successful_models)}, "
            f"failed={len(failed_models)}, "
            f"success_rate={tracking_result.success_rate:.0%}"
        )

        return tracking_result


# Global EnrichmentPipeline instance
_enrichment_pipeline: EnrichmentPipeline | None = None


def get_enrichment_pipeline() -> EnrichmentPipeline:
    """Get or create the global EnrichmentPipeline instance.

    The pipeline is initialized with the global Redis client (if available)
    to enable Re-ID functionality for entity tracking.

    Note: This function returns a pipeline WITHOUT PostgreSQL entity persistence.
    For entity persistence, use get_enrichment_pipeline_with_session() which
    configures HybridEntityStorage for PostgreSQL writes (NEM-2453).

    Returns:
        Global EnrichmentPipeline instance (Redis-only storage)
    """
    global _enrichment_pipeline  # noqa: PLW0603
    if _enrichment_pipeline is None:
        from backend.core.config import get_settings
        from backend.core.redis import get_redis_client_sync

        settings = get_settings()
        redis_client = get_redis_client_sync()
        _enrichment_pipeline = EnrichmentPipeline(
            redis_client=redis_client,
            use_enrichment_service=settings.use_enrichment_service,
        )
    return _enrichment_pipeline


async def get_enrichment_pipeline_with_session(
    session: Any,
    redis_client: Any | None = None,
) -> EnrichmentPipeline:
    """Create an EnrichmentPipeline with PostgreSQL entity persistence.

    This factory function creates a pipeline configured with HybridEntityStorage,
    enabling entities to be written to PostgreSQL when detections are processed.
    Use this for production pipelines that need persistent entity tracking.

    Related to NEM-2453: Verify and Update Enrichment Pipeline to Write Entities to PostgreSQL.

    Args:
        session: SQLAlchemy async session for database operations
        redis_client: Optional Redis client (uses global if not provided)

    Returns:
        EnrichmentPipeline with HybridEntityStorage configured

    Example:
        async with get_session() as session:
            pipeline = await get_enrichment_pipeline_with_session(session, redis_client)
            result = await pipeline.enrich_batch(detections, images, camera_id="front_door")
            # Entities are now persisted to PostgreSQL
    """
    from backend.core.redis import get_redis_client_sync
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.services.hybrid_entity_storage import HybridEntityStorage
    from backend.services.reid_service import ReIdentificationService

    # Get Redis client
    if redis_client is None:
        redis_client = get_redis_client_sync()

    # Create repository and clustering service
    entity_repo = EntityRepository(session)
    clustering_service = EntityClusteringService(entity_repository=entity_repo)

    # Create Reid service without hybrid storage first (to avoid circular dependency)
    reid_service = ReIdentificationService()

    # Create hybrid storage bridge
    # Note: redis_client may be RedisClient wrapper or raw Redis - HybridEntityStorage handles both
    hybrid_storage = HybridEntityStorage(
        redis_client=redis_client,  # type: ignore[arg-type]
        entity_repository=entity_repo,
        clustering_service=clustering_service,
        reid_service=reid_service,
    )

    # Create Reid service with hybrid storage enabled
    reid_service_with_storage = ReIdentificationService(
        hybrid_storage=hybrid_storage,
    )

    # Create pipeline with the configured services
    pipeline = EnrichmentPipeline(
        redis_client=redis_client,
        reid_service=reid_service_with_storage,
    )

    logger.info(
        "Created EnrichmentPipeline with PostgreSQL entity persistence (HybridEntityStorage)"
    )

    return pipeline


def reset_enrichment_pipeline() -> None:
    """Reset the global EnrichmentPipeline instance (for testing)."""
    global _enrichment_pipeline  # noqa: PLW0603
    _enrichment_pipeline = None
