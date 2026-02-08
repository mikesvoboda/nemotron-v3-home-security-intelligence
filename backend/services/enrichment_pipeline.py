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
clothing classification, pose estimation, action recognition, threat detection,
demographics analysis, and person re-identification instead of loading models
locally. Threat detection and re-ID route to ai-enrichment-light:8096, demographics
and action route to ai-enrichment:8094 by default (configurable via
ENRICHMENT_*_SERVICE env vars).
"""

from __future__ import annotations

__all__ = [
    "CLIP_SCENE_LABELS",
    "CLIP_THREAT_DESCRIPTIONS",
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
import io
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

# Frame buffer is lazily imported to avoid circular imports
# Import type for annotation only
from typing import TYPE_CHECKING, Any

import httpx
from PIL import Image
from pydantic import ValidationError

from backend.core.async_utils import bounded_gather
from backend.core.exceptions import (
    AIServiceError,
    CLIPUnavailableError,
    EnrichmentUnavailableError,
    FlorenceUnavailableError,
)
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_enrichment_model_duration,
    observe_enrichment_pipeline_stage,
    record_cascade_model_deferred,
    record_cascade_processed,
    record_cascade_skipped,
    record_enrichment_model_call,
    record_enrichment_model_error,
    record_enrichment_pipeline_timeout,
    record_pipeline_error,
    set_enrichment_quality_level,
)
from backend.core.mime_types import VIDEO_MIME_TYPES
from backend.core.telemetry import add_span_event
from backend.services.age_classifier_loader import (
    AgeClassificationResult,
    classify_ages_batch,
)
from backend.services.depth_anything_loader import (
    DepthAnalysisResult,
    analyze_depth,
)

# Import enrichment client for remote HTTP service
from backend.services.enrichment_client import (
    ActionClassificationResult as RemoteActionResult,
)
from backend.services.enrichment_client import (
    EnrichmentClient,
    UnifiedEnrichmentResult,
    get_enrichment_client,
)
from backend.services.enrichment_client import (
    PoseAnalysisResult as RemotePoseResult,
)
from backend.services.fashion_clip_loader import (
    ClothingClassification,
    classify_clothing,
    format_clothing_context,
)
from backend.services.gender_classifier_loader import (
    GenderClassificationResult,
    classify_genders_batch,
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
from backend.services.osnet_loader import extract_person_embedding
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
from backend.services.scene_ocr_service import (
    SceneOCRResult,
    get_scene_ocr_service,
)
from backend.services.segformer_loader import (
    ClothingSegmentationResult,
)
from backend.services.skeleton_action_service import SkeletonActionService
from backend.services.smoke_fire_loader import (
    SmokeFireDetectionResult,
    detect_smoke_fire,
)
from backend.services.stgcn_loader import (
    SkeletonActionResult,
)
from backend.services.threat_detection_loader import (
    ThreatDetection,
    ThreatDetectionResult,
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
    Keypoint,
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
from backend.services.yolo_world_loader import (
    detect_with_prompts,
    get_object_priority,
)
from backend.services.zero_dce_loader import (
    enhance_image as zero_dce_enhance,
)
from backend.services.zero_dce_loader import (
    should_enhance as zero_dce_should_enhance,
)

if TYPE_CHECKING:
    from backend.services.frame_buffer import FrameBuffer

logger = get_logger(__name__)

# =============================================================================
# CLIP Zero-Shot Scene Classification Labels (NEM-5525)
# =============================================================================
# These labels are used by CLIP's /classify endpoint for surveillance-relevant
# scene-level zero-shot classification. The results provide additional context
# to Nemotron for more accurate threat analysis (+5-10% accuracy).

CLIP_SCENE_LABELS: list[str] = [
    "normal activity",
    "person loitering",
    "property intrusion",
    "delivery in progress",
    "service worker visiting",
    "suspicious approach",
    "person with tool or weapon",
    "vehicle break-in attempt",
    "package theft",
    "trespassing",
]

# =============================================================================
# CLIP Threat Pattern Descriptions (NEM-5525)
# =============================================================================
# These text descriptions are compared against the scene via CLIP's
# /batch-similarity endpoint. High-scoring matches indicate threat patterns
# that Nemotron should factor into risk assessment (+3-7% precision).

CLIP_THREAT_DESCRIPTIONS: list[str] = [
    "a person checking door handles",
    "a person looking through windows",
    "a person hiding their face from camera",
    "a person carrying tools near a building",
    "a delivery person leaving a package",
    "a person walking a dog",
    "a vehicle circling a neighborhood",
    "a person crouching behind a car",
    "a person attempting to break into a vehicle",
    "a person stealing a package from a porch",
]


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary containing all BoundingBox fields for storage.
        """
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "confidence": self.confidence,
        }

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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary containing all LicensePlateResult fields for storage.
        """
        return {
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "confidence": self.confidence,
            "ocr_confidence": self.ocr_confidence,
            "source_detection_id": self.source_detection_id,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary containing all FaceResult fields for storage.
        """
        return {
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
            "source_detection_id": self.source_detection_id,
        }


@dataclass(slots=True)
class EnrichmentResult:
    """Result from the enrichment pipeline.

    Contains all additional context extracted from detections
    for use in the Nemotron LLM prompt.

    Thread Safety (NEM-4471):
    Multiple async tasks populate this object concurrently via asyncio.gather().
    This is safe because:
    1. asyncio uses cooperative multitasking (single-threaded event loop)
    2. list.append() and dict assignment are atomic in CPython due to GIL
    3. Each attribute is written by only one task (no read-modify-write races)

    If migrating to true parallelism (ProcessPoolExecutor), add synchronization.

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
    # Household matching results (NEM-3314, NEM-5512/5513/5514 - detection-attributed)
    # Keys are detection IDs (int) to enable per-detection context isolation
    person_household_matches: dict[int, HouseholdMatch] = field(default_factory=dict)
    vehicle_household_matches: dict[int, HouseholdMatch] = field(default_factory=dict)
    scene_change: SceneChangeResult | None = None
    violence_detection: ViolenceDetectionResult | None = None
    weather_classification: WeatherResult | None = None
    # Scene OCR results (text from uniforms, vehicles, signs)
    scene_ocr: SceneOCRResult | None = None
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
    # Smoke/fire detection results (NEM-5566) - runs on every frame
    smoke_fire_detection: SmokeFireDetectionResult | None = None
    # Consecutive smoke detection counter per camera for confirmation
    _smoke_consecutive_count: int = 0
    # YOLO-World zero-shot detection results (NEM-5566) - suspicious scenarios only
    yolo_world_detections: list[dict[str, Any]] = field(default_factory=list)
    # CLIP embeddings for re-identification (768-dim), keyed by detection ID
    # These are generated during _run_reid and cached for reuse by downstream services
    # (NEM-5517/5518/5519: Embedding Caching)
    clip_embeddings: dict[str, list[float]] = field(default_factory=dict)
    # CLIP zero-shot scene classification results (NEM-5525)
    # Contains {label: score} dict and top_label from CLIP /classify endpoint
    clip_scene_classification: dict[str, float] | None = None
    clip_scene_top_label: str | None = None
    # CLIP batch similarity threat pattern matching results (NEM-5525)
    # Contains {threat_description: similarity_score} from CLIP /batch-similarity endpoint
    clip_threat_matches: dict[str, float] | None = None
    # CLIP visual anomaly detection score (NEM-5525)
    # Anomaly score (0-1) comparing current frame against per-camera baseline embedding
    clip_anomaly_score: float | None = None
    clip_anomaly_similarity: float | None = None
    errors: list[str] = field(default_factory=list)
    structured_errors: list[EnrichmentError] = field(default_factory=list)
    processing_time_ms: float = 0.0
    # Weather risk modifier fields (NEM-5288)
    is_nighttime: bool = False  # Whether event occurred during nighttime hours
    is_indoor_camera: bool = False  # Whether this is an indoor camera (weather N/A)
    event_timestamp: datetime | None = None  # Timestamp of the event for nighttime detection
    time_of_day: str | None = None  # Optional time context (dawn, dusk, etc.)
    # Trajectory analysis results (NEM-5532)
    # Keyed by track_id (int) for per-detection trajectory context
    trajectory_analyses: dict[int, Any] = field(default_factory=dict)  # TrajectoryAnalysis

    @property
    def has_trajectory_analysis(self) -> bool:
        """Check if any trajectory analyses are available (NEM-5532)."""
        return bool(self.trajectory_analyses)

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
    def has_smoke_fire(self) -> bool:
        """Check if smoke or fire was detected (NEM-5566)."""
        return self.smoke_fire_detection is not None and self.smoke_fire_detection.has_detections

    @property
    def has_fire(self) -> bool:
        """Check if fire was detected (NEM-5566, CRITICAL)."""
        return self.smoke_fire_detection is not None and self.smoke_fire_detection.has_fire

    @property
    def has_yolo_world_detections(self) -> bool:
        """Check if YOLO-World zero-shot detections are available (NEM-5566)."""
        return bool(self.yolo_world_detections)

    @property
    def has_person_embeddings(self) -> bool:
        """Check if any person embeddings (OSNet) are available."""
        return bool(self.person_embeddings)

    @property
    def has_clip_embeddings(self) -> bool:
        """Check if any CLIP embeddings are available (NEM-5517/5518/5519)."""
        return bool(self.clip_embeddings)

    @property
    def has_clip_scene_classification(self) -> bool:
        """Check if CLIP scene classification results are available (NEM-5525)."""
        return self.clip_scene_classification is not None

    @property
    def has_clip_threat_matches(self) -> bool:
        """Check if CLIP threat pattern matches are available (NEM-5525)."""
        return self.clip_threat_matches is not None

    @property
    def has_clip_anomaly_score(self) -> bool:
        """Check if CLIP anomaly score is available (NEM-5525)."""
        return self.clip_anomaly_score is not None

    @property
    def has_clip_analysis(self) -> bool:
        """Check if any CLIP analysis results are available (NEM-5525)."""
        return (
            self.has_clip_scene_classification
            or self.has_clip_threat_matches
            or self.has_clip_anomaly_score
        )

    @property
    def has_weather(self) -> bool:
        """Check if weather classification results are available (NEM-5288)."""
        return self.weather_classification is not None

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

        # Smoke/Fire Detection (NEM-5566 - SAFETY CRITICAL)
        if self.smoke_fire_detection and self.smoke_fire_detection.has_detections:
            lines.append("## **SMOKE/FIRE DETECTION**")
            lines.append(self.smoke_fire_detection.to_context_string())

        # YOLO-World Zero-Shot Detections (NEM-5566)
        if self.yolo_world_detections:
            lines.append(
                f"## Zero-Shot Object Detection ({len(self.yolo_world_detections)} objects)"
            )
            for det in sorted(
                self.yolo_world_detections,
                key=lambda d: d.get("confidence", 0),
                reverse=True,
            )[:10]:
                priority = det.get("priority", "low")
                priority_marker = (
                    f" [{priority.upper()}]" if priority in ("critical", "high") else ""
                )
                lines.append(
                    f"  - {det.get('class_name', 'unknown')}: "
                    f"{det.get('confidence', 0):.0%} confidence{priority_marker}"
                )

        # Image Quality Assessment
        if self.image_quality:
            lines.append("## Image Quality Assessment")
            lines.append(f"  {self.image_quality.format_context()}")
            if self.quality_change_detected:
                lines.append(f"  **ALERT**: {self.quality_change_description}")

        # Weather Classification (NEM-5288)
        if self.weather_classification:
            lines.append("## Weather Conditions")
            lines.append(f"  {self.weather_classification.to_context_string()}")
            # Add visibility note for relevant conditions
            condition = self.weather_classification.simple_condition
            if condition in ("foggy", "snowy"):
                lines.append(
                    f"  **NOTE**: {condition.capitalize()} conditions may reduce visibility"
                )
            elif condition == "rainy":
                lines.append("  **NOTE**: Rain may affect detection accuracy")

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
            "smoke_fire_detection": (
                self.smoke_fire_detection.to_dict() if self.smoke_fire_detection else None
            ),
            "yolo_world_detections": self.yolo_world_detections,
            # Household matching results (NEM-3314, NEM-5512/5513/5514 - detection-attributed)
            # Now keyed by detection ID for context isolation
            "person_household_matches": {
                str(det_id): {
                    "detection_id": det_id,
                    "member_id": match.member_id,
                    "member_name": match.member_name,
                    "similarity": match.similarity,
                    "match_type": match.match_type,
                    "member_role": getattr(match, "member_role", None),
                    "schedule_status": getattr(match, "schedule_status", None),
                }
                for det_id, match in self.person_household_matches.items()
            },
            "vehicle_household_matches": {
                str(det_id): {
                    "detection_id": det_id,
                    "vehicle_id": match.vehicle_id,
                    "vehicle_description": match.vehicle_description,
                    "similarity": match.similarity,
                    "match_type": match.match_type,
                }
                for det_id, match in self.vehicle_household_matches.items()
            },
            "vision_extraction": (
                self.vision_extraction.to_dict() if self.vision_extraction else None
            ),
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
        }

    def _determine_nighttime(self) -> bool:
        """Determine if this event occurred during nighttime.

        Uses the is_nighttime flag if set, otherwise falls back to
        timestamp-based detection.

        Returns:
            True if nighttime, False otherwise
        """
        if self.is_nighttime:
            return True
        if self.event_timestamp is not None:
            from backend.services.weather_loader import is_nighttime as check_nighttime

            return check_nighttime(self.event_timestamp)
        return False

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

    def to_prompt_context(self, time_of_day: str | None = None) -> dict[str, str | None]:
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

        # Weather-based modifiers (skip for indoor cameras)
        if not self.is_indoor_camera:
            weather = self.weather_classification
            if weather and weather.confidence >= 0.5:
                condition = weather.simple_condition
                is_night = self._determine_nighttime()

                if condition == "rainy":
                    modifiers["weather_rainy"] = -0.15
                elif condition in ("foggy", "snowy"):
                    modifiers["weather_low_visibility"] = 0.1

                if condition == "clear" and is_night:
                    modifiers["weather_clear_night"] = 0.25

        return modifiers

    def get_weather_risk_modifier(self) -> float:
        """Get aggregate weather risk modifier value.

        Returns the total weather-based risk modifier for easy use in
        risk calculation. This is a convenience method that extracts
        weather-related modifiers from get_risk_modifiers().

        Returns:
            Aggregate weather risk modifier value (can be positive or negative)
        """
        from backend.services.weather_loader import get_weather_risk_modifier

        return get_weather_risk_modifier(self.weather_classification, self._determine_nighttime())

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

        # Weather-related flags (NEM-5288)
        if self.weather_classification and self.weather_classification.confidence >= 0.5:
            condition = self.weather_classification.simple_condition
            confidence = self.weather_classification.confidence

            # Low visibility weather flag
            if condition in ("foggy", "snowy"):
                flags.append(
                    {
                        "type": "weather_low_visibility",
                        "description": f"{condition.capitalize()} conditions ({confidence:.0%} confidence) - reduced visibility",
                        "severity": "info",
                    }
                )

        return flags

    def to_storage_dict(self, detection_id: int) -> dict[str, Any] | None:
        """Create storage-ready dict that matches prompt content for a detection.

        Uses to_dict() methods on result classes for full data fidelity.
        This method preserves all fields (display_name, is_commercial, all_scores, etc.)
        that are used in prompt generation, ensuring storage and prompt paths have
        identical data.

        Args:
            detection_id: The detection ID to get enrichment for

        Returns:
            Dictionary with detection-specific enrichment data, or None if no data
        """
        enrichment: dict[str, Any] = {}
        det_id_str = str(detection_id)

        # Vehicle classification - use to_dict() for full data
        if det_id_str in self.vehicle_classifications:
            vc = self.vehicle_classifications[det_id_str]
            enrichment["vehicle"] = vc.to_dict()

        # Vehicle damage
        if det_id_str in self.vehicle_damage:
            vd = self.vehicle_damage[det_id_str]
            if "vehicle" not in enrichment:
                enrichment["vehicle"] = {}
            enrichment["vehicle"]["damage"] = [
                {"type": d.damage_type, "confidence": d.confidence} for d in vd.detections
            ]

        # Pet classification - use to_dict() for full data
        if det_id_str in self.pet_classifications:
            pc = self.pet_classifications[det_id_str]
            enrichment["pet"] = pc.to_dict()

        # Person: clothing classification - use to_dict()
        if det_id_str in self.clothing_classifications:
            cc = self.clothing_classifications[det_id_str]
            detected_action = (
                self.action_results.get("detected_action") if self.action_results else None
            )
            enrichment["person"] = (
                cc.to_dict()
                if hasattr(cc, "to_dict")
                else {
                    "clothing": cc.top_category,
                    "action": detected_action,
                    "carrying": None,
                    "confidence": cc.confidence,
                }
            )
            if detected_action and "action" not in enrichment["person"]:
                enrichment["person"]["action"] = detected_action

        # Person: pose estimation (ViTPose)
        if det_id_str in self.pose_results:
            pose = self.pose_results[det_id_str]
            detected_action = (
                self.action_results.get("detected_action") if self.action_results else None
            )
            if "person" not in enrichment:
                enrichment["person"] = {
                    "action": detected_action,
                }
            enrichment["person"]["pose"] = pose.pose_class
            enrichment["person"]["pose_confidence"] = pose.pose_confidence
            enrichment["pose"] = self._serialize_pose_result(pose)

        # Person: clothing segmentation
        if det_id_str in self.clothing_segmentation:
            cs = self.clothing_segmentation[det_id_str]
            if "person" not in enrichment:
                enrichment["person"] = {}
            enrichment["person"]["face_covered"] = cs.has_face_covered

        # License plates associated with this detection
        detection_plates = [
            lp for lp in self.license_plates if lp.source_detection_id == detection_id
        ]
        if detection_plates:
            best_plate = max(detection_plates, key=lambda p: p.ocr_confidence or 0.0)
            enrichment["license_plate"] = best_plate.to_dict()

        # Faces associated with this detection
        detection_faces = [f for f in self.faces if f.source_detection_id == detection_id]
        if detection_faces:
            enrichment["face_detected"] = True
            enrichment["face_count"] = len(detection_faces)
            enrichment["faces"] = [f.to_dict() for f in detection_faces]

        # Shared/global enrichment data
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

        # Cached embeddings for reuse (NEM-5517/5518/5519: Embedding Caching)
        # Store embeddings computed during enrichment to prevent redundant computation
        # in downstream services (household_matcher, entity_clustering, reid_service)
        embeddings: dict[str, list[float] | None] = {}

        # CLIP embedding (768-dim) from re-identification
        # This is the primary embedding source for persons and vehicles
        if det_id_str in self.clip_embeddings:
            clip_emb = self.clip_embeddings[det_id_str]
            # Determine the embedding type based on detection context
            # Check if this detection has vehicle re-id matches (indicates vehicle)
            if det_id_str in self.vehicle_reid_matches:
                embeddings["vehicle_visual"] = clip_emb
            # Check if this detection has person re-id matches (indicates person)
            elif det_id_str in self.person_reid_matches:
                # Use face_clip for persons (CLIP is used for face-level matching)
                embeddings["face_clip"] = clip_emb
            # Default: store as person_reid if we have CLIP but no matches yet
            # Could be either person or vehicle, store based on available context
            # If we have person_embeddings (OSNet), this is likely a person
            elif det_id_str in self.person_embeddings:
                embeddings["face_clip"] = clip_emb
            else:
                # Store as vehicle_visual by default for unmatched CLIP embeddings
                # The extraction functions will handle both cases
                embeddings["vehicle_visual"] = clip_emb

        # Person re-ID embedding (512-dim OSNet) - separate from CLIP
        # OSNet embeddings are more specialized for person re-identification
        if det_id_str in self.person_embeddings:
            embedding_result = self.person_embeddings[det_id_str]
            if hasattr(embedding_result, "embedding"):
                emb = embedding_result.embedding
                # Convert numpy array to list for JSON serialization
                if hasattr(emb, "tolist"):
                    embeddings["person_reid"] = emb.tolist()
                elif isinstance(emb, list):
                    embeddings["person_reid"] = emb
            elif isinstance(embedding_result, dict) and "embedding" in embedding_result:
                emb = embedding_result["embedding"]
                if hasattr(emb, "tolist"):
                    embeddings["person_reid"] = emb.tolist()
                elif isinstance(emb, list):
                    embeddings["person_reid"] = emb

        # Only add embeddings key if we have any embeddings to store
        if embeddings:
            enrichment["embeddings"] = embeddings

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
        scene_ocr_enabled: bool = True,
        household_matching_enabled: bool = False,
        age_classification_enabled: bool = True,
        gender_classification_enabled: bool = True,
        smoke_fire_detection_enabled: bool = True,
        yolo_world_enabled: bool = True,
        osnet_reid_enabled: bool = True,
        low_light_enhancement_enabled: bool = True,
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
            scene_ocr_enabled: Enable scene OCR for text extraction (uniforms, vehicles, signs)
            household_matching_enabled: Enable matching persons/vehicles against household database (NEM-3314).
                                       Disabled by default for backward compatibility.
            frame_buffer: FrameBuffer for accumulating frames for X-CLIP temporal action recognition.
                         If provided, frames are buffered per camera and X-CLIP runs on frame sequences
                         (8 frames) for better action recognition. If None, falls back to single-frame.
            redis_client: Redis client for re-id storage (optional)
            use_enrichment_service: Use HTTP service at ai-enrichment:8094 / ai-enrichment-light:8096
                                    instead of local models for vehicle, pet, clothing classification,
                                    pose estimation, and action recognition
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
        self.scene_ocr_enabled = scene_ocr_enabled
        self.household_matching_enabled = household_matching_enabled
        self.age_classification_enabled = age_classification_enabled
        self.gender_classification_enabled = gender_classification_enabled
        self.smoke_fire_detection_enabled = smoke_fire_detection_enabled
        self.yolo_world_enabled = yolo_world_enabled
        self.osnet_reid_enabled = osnet_reid_enabled
        self.low_light_enhancement_enabled = low_light_enhancement_enabled
        # Smoke consecutive detection tracker per camera (for false positive reduction)
        self._smoke_consecutive_counts: dict[str, int] = {}
        self._previous_quality_results: dict[str, ImageQualityResult] = {}
        self.redis_client = redis_client

        # Frame buffer for X-CLIP temporal action recognition (legacy, kept for fallback)
        self._frame_buffer = frame_buffer

        # ST-GCN++ skeleton action service (NEM-5563: replaces X-CLIP)
        # Initialized lazily on first use (needs model loaded)
        self._skeleton_action_service: SkeletonActionService | None = None

        # Enrichment service settings
        self.use_enrichment_service = use_enrichment_service
        self._enrichment_client = enrichment_client

        # Initialize services
        self._vision_extractor = get_vision_extractor()
        # Use provided reid_service (with HybridEntityStorage) or global (Redis-only)
        self._reid_service = reid_service if reid_service is not None else get_reid_service()
        self._scene_detector = get_scene_change_detector()
        self._scene_ocr_service = get_scene_ocr_service() if scene_ocr_enabled else None

        # Per-service concurrency semaphores to prevent GPU saturation
        settings = get_settings()
        self._florence_semaphore = asyncio.Semaphore(settings.enrichment_florence_concurrency)
        self._clip_semaphore = asyncio.Semaphore(settings.enrichment_clip_concurrency)
        self._enrichment_service_semaphore = asyncio.Semaphore(
            settings.enrichment_service_concurrency
        )
        self._pipeline_timeout = settings.enrichment_pipeline_timeout_seconds
        self._quality_level = settings.enrichment_quality_level

        # Record quality level metric
        set_enrichment_quality_level(self._quality_level)

        logger.info(
            f"EnrichmentPipeline initialized: "
            f"license_plate={license_plate_enabled}, "
            f"face_detection={face_detection_enabled}, "
            f"ocr={ocr_enabled}, "
            f"vision_extraction={vision_extraction_enabled}, "
            f"reid={reid_enabled}, "
            f"scene_change={scene_change_enabled}, "
            f"household_matching={household_matching_enabled}, "
            f"use_enrichment_service={use_enrichment_service}, "
            f"quality_level={self._quality_level}, "
            f"pipeline_timeout={self._pipeline_timeout}s"
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

    # ==========================================================================
    # Phase 4: Parallel Enrichment Architecture (NEM-4234, NEM-5525 optimized)
    # ==========================================================================
    #
    # Maximum parallelism with concurrency-limited execution:
    #
    # Super-Phase (ALL run concurrently via asyncio.gather):
    #   Phase 1 (local models + enrichment services) + Florence-2 Vision Extraction
    #
    # Phase 2 (After Phase 1 + Florence complete):
    #   OCR, Re-ID, Scene Change, Scene OCR Crop (parallel)
    #
    # Phase 3 (After Phase 2):
    #   CLIP Anomaly Detection, Household Matching (parallel)
    #
    # Adaptive quality levels: full, standard, minimal
    # ==========================================================================

    def _should_run_for_quality(self, tier: str) -> bool:
        """Check if a model should run based on current quality level.

        Args:
            tier: The minimum quality tier needed ('minimal', 'standard', 'full')

        Returns:
            True if the model should run at the current quality level
        """
        level_order = {"minimal": 0, "standard": 1, "full": 2}
        current = level_order.get(self._quality_level, 2)
        required = level_order.get(tier, 2)
        return current >= required

    async def _run_parallel_enrichment(
        self,
        result: EnrichmentResult,
        pil_image: Image.Image,
        high_conf_detections: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
        camera_id: str | None,
    ) -> None:
        """Run enrichment models with maximum parallelism and concurrency control.

        When use_enrichment_service=True, this method uses the unified /enrich
        endpoint per detection type (person, vehicle, animal), replacing 8+
        individual HTTP calls with one call per detection. Each /enrich call
        returns all applicable enrichment data for that detection type.

        When use_enrichment_service=False, falls back to local model loading
        (existing behavior).

        Args:
            result: EnrichmentResult to populate
            pil_image: Full frame PIL Image for analysis
            high_conf_detections: Filtered high-confidence detections
            images: Dictionary mapping detection IDs to images
            camera_id: Camera ID for context-dependent operations
        """
        persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
        vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
        animals = [d for d in high_conf_detections if d.class_name in ANIMAL_CLASSES]

        # NEM-5570: Cascade Level 2 — log per-model cascade decisions based on detection types
        if not persons:
            for model in (
                "face_detection",
                "pose",
                "clothing",
                "action",
                "reid",
                "threat",
                "violence",
            ):
                record_cascade_model_deferred(model, "no_person_detections")
        if not vehicles:
            for model in ("license_plate", "vehicle_class", "vehicle_damage"):
                record_cascade_model_deferred(model, "no_vehicle_detections")
        if not animals:
            record_cascade_model_deferred("pet_class", "no_animal_detections")

        logger.debug(
            "Cascade: %d detections — %d persons, %d vehicles, %d animals",
            len(high_conf_detections),
            len(persons),
            len(vehicles),
            len(animals),
        )

        super_phase_start = time.monotonic()
        phase1_tasks: dict[str, Any] = {}

        # --- Core detections (always run locally - these don't have unified equivalents) ---
        if self.face_detection_enabled and persons:
            phase1_tasks["face_detection"] = self._safe_detect_faces(persons, images)
        if self.license_plate_enabled and vehicles:
            # NEM-5569: Use FastALPR (end-to-end detection+OCR, 28MB) if available,
            # otherwise fall back to YOLO11 + PaddleOCR (400MB)
            if self._is_fast_alpr_available():
                phase1_tasks["license_plate_detection"] = self._safe_detect_plates_fast_alpr(
                    vehicles, images
                )
            else:
                phase1_tasks["license_plate_detection"] = self._safe_detect_license_plates(
                    vehicles, images
                )
        if self.violence_detection_enabled and len(persons) >= 2:
            phase1_tasks["violence_detection"] = self._safe_detect_violence(pil_image)

        if self.use_enrichment_service:
            # ================================================================
            # UNIFIED ENRICHMENT PATH: One /enrich call per detection
            # Replaces 8+ individual _*_via_service HTTP calls with unified
            # endpoint calls that return all enrichment data per detection.
            # ================================================================

            # Unified person enrichment (replaces pose, clothing, threat,
            # demographics, action, and reid individual calls)
            if persons:
                phase1_tasks["unified_person_enrichment"] = (
                    self._enrich_persons_via_unified_service(persons, pil_image, camera_id, result)
                )

            # Unified vehicle enrichment (replaces vehicle classification)
            if (
                self.vehicle_classification_enabled
                and vehicles
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["unified_vehicle_enrichment"] = (
                    self._enrich_vehicles_via_unified_service(vehicles, pil_image, result)
                )

            # Unified animal enrichment (replaces pet classification)
            if (
                self.pet_classification_enabled
                and animals
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["unified_animal_enrichment"] = (
                    self._enrich_animals_via_unified_service(animals, pil_image, result)
                )

            # ================================================================
            # ENRICHMENT-LIGHT SERVICE CALLS: Individual calls for models
            # hosted on ai-enrichment-light:8096 (pose, threat, reid).
            # The unified /enrich endpoint only reaches the heavy service,
            # so these models must be called individually via the light
            # service. EnrichmentClient._get_service_for_model() routes
            # each call to the correct service based on config.
            # ================================================================
            if self.pose_estimation_enabled and persons:
                phase1_tasks["pose_estimation"] = self._estimate_poses_via_service(
                    persons, pil_image
                )
            if persons:
                phase1_tasks["threat_detection"] = self._detect_threats_via_service(pil_image)
            if self.reid_enabled and persons:
                phase1_tasks["reid_via_service"] = self._compute_reid_via_service(
                    high_conf_detections, pil_image, result
                )
        else:
            # ================================================================
            # LOCAL MODEL PATH: Individual model loading (existing behavior)
            # ================================================================

            # --- Threat/Pose (minimal quality) ---
            if self.pose_estimation_enabled and persons:
                phase1_tasks["pose_estimation"] = self._safe_estimate_poses(persons, pil_image)
            # NOTE: Action recognition moved to post-pose phase (NEM-5563)
            # ST-GCN++ uses pose keypoints, so it runs after pose results are available.
            # See _run_skeleton_action_recognition() called after phase1 results assembly.

            # --- Standard quality models ---
            if (
                self.clothing_classification_enabled
                and persons
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["clothing_classification"] = self._safe_classify_person_clothing(
                    persons, pil_image
                )
            if (
                self.vehicle_classification_enabled
                and vehicles
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["vehicle_classification"] = self._safe_classify_vehicle_types(
                    vehicles, pil_image
                )
            if (
                self.pet_classification_enabled
                and animals
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["pet_classification"] = self._safe_classify_pets(animals, pil_image)

            # --- NEM-5566: Demographics (age + gender) for person detections ---
            if (
                (self.age_classification_enabled or self.gender_classification_enabled)
                and persons
                and self._should_run_for_quality("standard")
            ):
                phase1_tasks["demographics"] = self._safe_classify_demographics(persons, pil_image)

            # --- NEM-5566: OSNet person re-ID embeddings (local path) ---
            if self.osnet_reid_enabled and persons and self._should_run_for_quality("standard"):
                phase1_tasks["osnet_reid"] = self._safe_extract_osnet_embeddings(persons, pil_image)

        # --- Models that always use local loading regardless of enrichment service ---
        # --- NEM-5566: Smoke/fire detection (SAFETY CRITICAL - runs on EVERY frame) ---
        if self.smoke_fire_detection_enabled:
            phase1_tasks["smoke_fire_detection"] = self._safe_detect_smoke_fire(
                pil_image, camera_id
            )

        # --- NEM-5566: YOLO-World zero-shot (suspicious scenarios only) ---
        if (
            self.yolo_world_enabled
            and high_conf_detections
            and self._should_run_for_quality("standard")
        ):
            phase1_tasks["yolo_world_detection"] = self._safe_detect_yolo_world(
                pil_image, high_conf_detections
            )
        if self.image_quality_enabled and self._should_run_for_quality("standard"):
            phase1_tasks["image_quality"] = self._safe_assess_image_quality(pil_image, camera_id)
        if self.weather_classification_enabled and self._should_run_for_quality("standard"):
            phase1_tasks["weather_classification"] = self._safe_classify_weather(pil_image)
        if (
            self.depth_estimation_enabled
            and high_conf_detections
            and self._should_run_for_quality("standard")
            and not self.use_enrichment_service
        ):
            phase1_tasks["depth_estimation"] = self._safe_analyze_depth(
                high_conf_detections, pil_image
            )
        if (
            self.vehicle_damage_detection_enabled
            and vehicles
            and self._should_run_for_quality("standard")
        ):
            phase1_tasks["vehicle_damage"] = self._safe_detect_vehicle_damage(vehicles, pil_image)
        if self.scene_ocr_enabled and self._should_run_for_quality("standard"):
            phase1_tasks["scene_ocr_frame"] = self._safe_run_scene_ocr_frame(pil_image)

        # --- Full quality models ---
        if self.clothing_segmentation_enabled and persons and self._should_run_for_quality("full"):
            phase1_tasks["clothing_segmentation"] = self._safe_segment_person_clothing(
                persons, pil_image
            )
        if self.reid_enabled and self._should_run_for_quality("full"):
            phase1_tasks["clip_scene_classification"] = self._safe_clip_scene_classify(pil_image)
        if self.reid_enabled and self._should_run_for_quality("full"):
            phase1_tasks["clip_threat_matching"] = self._safe_clip_threat_match(pil_image)

        # Florence-2 Vision Extraction (runs IN PARALLEL with Phase 1)
        # NEM-5570: Cascade Level 3 — skip Florence-2 when all detections are
        # high-confidence (>= 0.7). YOLO's class label is sufficient for obvious
        # detections; Florence-2 captioning only adds value for ambiguous ones.
        florence_task = None
        _FLORENCE_CONFIDENCE_THRESHOLD = 0.7
        if (
            self.vision_extraction_enabled
            and pil_image
            and self._should_run_for_quality("standard")
        ):
            # Filter to only ambiguous (low-confidence) detections for Florence-2
            ambiguous_detections = [
                d for d in high_conf_detections if d.confidence < _FLORENCE_CONFIDENCE_THRESHOLD
            ]
            if ambiguous_detections:
                det_dicts = [
                    {
                        "class_name": d.class_name,
                        "confidence": d.confidence,
                        "bbox": d.bbox.to_tuple() if d.bbox else None,
                        "detection_id": str(d.id) if d.id else str(i),
                    }
                    for i, d in enumerate(ambiguous_detections)
                ]
                florence_task = self._vision_extractor.extract_batch_attributes(
                    pil_image, det_dicts
                )
                deferred_count = len(high_conf_detections) - len(ambiguous_detections)
                if deferred_count > 0:
                    record_cascade_model_deferred("florence2", "high_confidence")
                    logger.debug(
                        "Cascade: Florence-2 deferred for %d/%d high-confidence detections "
                        "(threshold=%.2f)",
                        deferred_count,
                        len(high_conf_detections),
                        _FLORENCE_CONFIDENCE_THRESHOLD,
                    )
            else:
                # All detections are high-confidence — skip Florence-2 entirely
                record_cascade_model_deferred("florence2", "all_high_confidence")
                logger.debug(
                    "Cascade: Florence-2 skipped entirely — all %d detections above %.2f confidence",
                    len(high_conf_detections),
                    _FLORENCE_CONFIDENCE_THRESHOLD,
                )

        # Execute Super-Phase: Phase 1 + Florence-2 concurrently
        # NEM-5548: Split tasks by resource type for bounded concurrency.
        # GPU-bound models share VRAM so they need tighter limits (2).
        # CPU-bound models can run more freely (limit=5).
        # Service calls are HTTP-bound and use limit=5.
        _GPU_TASK_NAMES = frozenset(
            {
                "pose_estimation",
                "depth_estimation",
                "clothing_segmentation",
                "clip_scene_classification",
                "clip_threat_matching",
                "face_detection",
                "license_plate_detection",
                "violence_detection",
                "smoke_fire_detection",
                "yolo_world_detection",
                "demographics",
            }
        )

        phase1_start = time.monotonic()
        if phase1_tasks or florence_task:
            phase1_keys = list(phase1_tasks.keys())

            # NEM-5525: Span event for super-phase parallel execution
            add_span_event(
                "enrichment_pipeline.super_phase_start",
                {
                    "phase1_task.count": len(phase1_keys),
                    "phase1_tasks": ", ".join(phase1_keys),
                    "florence_enabled": florence_task is not None,
                    "use_enrichment_service": self.use_enrichment_service,
                },
            )

            # Partition phase1 tasks into GPU-bound and CPU/service-bound
            gpu_keys: list[str] = []
            gpu_coros: list[Any] = []
            cpu_keys: list[str] = []
            cpu_coros: list[Any] = []
            for key in phase1_keys:
                if not self.use_enrichment_service and key in _GPU_TASK_NAMES:
                    gpu_keys.append(key)
                    gpu_coros.append(phase1_tasks[key])
                else:
                    cpu_keys.append(key)
                    cpu_coros.append(phase1_tasks[key])

            # Florence-2 is GPU-bound; run it alongside GPU tasks
            if florence_task:
                gpu_keys.append("_florence")
                gpu_coros.append(florence_task)

            # Run GPU and CPU groups concurrently, each internally bounded
            async def _run_gpu_group() -> list[Any]:
                if not gpu_coros:
                    return []
                return await bounded_gather(gpu_coros, limit=2, return_exceptions=True)

            async def _run_cpu_group() -> list[Any]:
                if not cpu_coros:
                    return []
                return await bounded_gather(cpu_coros, limit=5, return_exceptions=True)

            gpu_results_list, cpu_results_list = await asyncio.gather(
                _run_gpu_group(), _run_cpu_group()
            )

            # Reassemble results in original key order
            phase1_dict: dict[str, Any] = {}
            florence_result = None
            for key, res in zip(gpu_keys, gpu_results_list, strict=True):
                if key == "_florence":
                    florence_result = res
                else:
                    phase1_dict[key] = res
            for key, res in zip(cpu_keys, cpu_results_list, strict=True):
                phase1_dict[key] = res

            if phase1_dict:
                self._process_phase1_results(result, phase1_dict)

            # ST-GCN++ skeleton action recognition (NEM-5563)
            # Runs after pose estimation so we have keypoints to feed the model.
            # Uses buffered keypoints across frames for temporal classification.
            if (
                self.action_recognition_enabled
                and persons
                and result.pose_results
                and not self.use_enrichment_service
            ):
                try:
                    action_result = await self._recognize_actions_from_skeleton(
                        result.pose_results, persons, camera_id
                    )
                    if action_result:
                        result.action_results = action_result
                except Exception as e:
                    self._handle_enrichment_error("action_recognition", e, result)

            if florence_task:
                if isinstance(florence_result, Exception):
                    self._handle_enrichment_error("vision_extraction", florence_result, result)
                elif florence_result is not None:
                    result.vision_extraction = florence_result  # type: ignore[assignment]

        phase1_duration = time.monotonic() - phase1_start
        observe_enrichment_pipeline_stage("phase1_and_florence", phase1_duration)

        # NEM-5525: Span event for super-phase completion
        add_span_event(
            "enrichment_pipeline.super_phase_complete",
            {
                "phase1_task.count": len(phase1_tasks),
                "florence_enabled": florence_task is not None,
                "duration_ms": int(phase1_duration * 1000),
            },
        )
        logger.debug(
            f"Phase 1 + Florence completed in {phase1_duration:.2f}s "
            f"({len(phase1_tasks)} phase1 tasks{' + florence' if florence_task else ''})"
        )

        # Phase 2: Run dependent models in parallel
        phase2_start = time.monotonic()
        phase2_tasks: dict[str, Any] = {}

        # NEM-5569: Skip OCR phase when FastALPR was used (text already populated)
        plates_need_ocr = [p for p in result.license_plates if not p.text]
        if self.ocr_enabled and plates_need_ocr:

            async def _ocr_task() -> None:
                await self._read_plates(plates_need_ocr, images)

            phase2_tasks["ocr"] = _ocr_task()

        # Re-ID: When using unified service, person embeddings are already populated
        # by _enrich_persons_via_unified_service. Only fall back to individual calls
        # or local models when not using unified path.
        if self.reid_enabled and pil_image:
            if self.use_enrichment_service:
                # Unified path already populated person_embeddings in Phase 1.
                # No separate re-ID call needed.
                pass
            elif self.redis_client:

                async def _reid_local_task() -> None:
                    await self._run_reid(high_conf_detections, pil_image, camera_id, result)

                phase2_tasks["re_identification"] = _reid_local_task()

        if self.scene_change_enabled and camera_id and pil_image:

            async def _scene_change_task() -> None:
                import numpy as np

                frame_array = np.array(pil_image)
                result.scene_change = self._scene_detector.detect_changes(camera_id, frame_array)

            phase2_tasks["scene_change_detection"] = _scene_change_task()

        if (
            self.scene_ocr_enabled
            and high_conf_detections
            and self._should_run_for_quality("standard")
        ):

            async def _scene_ocr_crop_task() -> None:
                frame_ocr_result = result.scene_ocr
                result.scene_ocr = await self._safe_run_scene_ocr_crops(
                    pil_image, high_conf_detections, frame_ocr_result
                )

            phase2_tasks["scene_ocr_crop"] = _scene_ocr_crop_task()

        if phase2_tasks:
            phase2_keys = list(phase2_tasks.keys())
            phase2_results = await bounded_gather(
                list(phase2_tasks.values()),
                limit=5,
                return_exceptions=True,
            )
            for key, phase2_result in zip(phase2_keys, phase2_results, strict=True):
                if isinstance(phase2_result, Exception):
                    self._handle_enrichment_error(key, phase2_result, result)

        phase2_duration = time.monotonic() - phase2_start
        observe_enrichment_pipeline_stage("phase2", phase2_duration)

        # Phase 3: Post-Phase 2 dependents
        phase3_start = time.monotonic()
        phase3_tasks: dict[str, Any] = {}

        if (
            self.reid_enabled
            and pil_image
            and camera_id
            and self.redis_client
            and self._should_run_for_quality("full")
        ):

            async def _clip_anomaly_task() -> None:
                await self._run_clip_anomaly_detection(pil_image, camera_id, result)

            phase3_tasks["clip_anomaly_detection"] = _clip_anomaly_task()

        if self.household_matching_enabled and self._should_run_for_quality("standard"):

            async def _household_task() -> None:
                await self._run_household_matching(high_conf_detections, result)

            phase3_tasks["household_matching"] = _household_task()

        if phase3_tasks:
            phase3_keys = list(phase3_tasks.keys())
            phase3_results = await bounded_gather(
                list(phase3_tasks.values()),
                limit=5,
                return_exceptions=True,
            )
            for key, phase3_result in zip(phase3_keys, phase3_results, strict=True):
                if isinstance(phase3_result, Exception):
                    self._handle_enrichment_error(key, phase3_result, result)

        phase3_duration = time.monotonic() - phase3_start
        observe_enrichment_pipeline_stage("phase3", phase3_duration)

        total_duration = time.monotonic() - super_phase_start
        observe_enrichment_pipeline_stage("total", total_duration)
        logger.info(
            f"Enrichment pipeline timing: "
            f"phase1+florence={phase1_duration:.2f}s, "
            f"phase2={phase2_duration:.2f}s, "
            f"phase3={phase3_duration:.2f}s, "
            f"total={total_duration:.2f}s, "
            f"quality={self._quality_level}"
        )

    def _process_phase1_results(
        self,
        result: EnrichmentResult,
        phase1_dict: dict[str, Any],
    ) -> None:
        """Process Phase 1 parallel results and populate EnrichmentResult.

        Args:
            result: EnrichmentResult to populate
            phase1_dict: Dictionary mapping task names to results or exceptions
        """
        # Face Detection
        if "face_detection" in phase1_dict:
            faces_result = phase1_dict["face_detection"]
            if isinstance(faces_result, Exception):
                self._handle_enrichment_error("face_detection", faces_result, result)
            elif faces_result:
                result.faces.extend(faces_result)

        # License Plate Detection
        if "license_plate_detection" in phase1_dict:
            plates_result = phase1_dict["license_plate_detection"]
            if isinstance(plates_result, Exception):
                self._handle_enrichment_error("license_plate_detection", plates_result, result)
            elif plates_result:
                result.license_plates.extend(plates_result)

        # Violence Detection
        if "violence_detection" in phase1_dict:
            violence_result = phase1_dict["violence_detection"]
            if isinstance(violence_result, Exception):
                self._handle_enrichment_error("violence_detection", violence_result, result)
            elif violence_result:
                result.violence_detection = violence_result

        # Image Quality
        if "image_quality" in phase1_dict:
            quality_result = phase1_dict["image_quality"]
            if isinstance(quality_result, Exception):
                # Skip "disabled" errors which are expected
                if "disabled" not in str(quality_result).lower():
                    self._handle_enrichment_error(
                        "image_quality_assessment", quality_result, result
                    )
            elif quality_result:
                result.image_quality = quality_result

        # Weather Classification
        if "weather_classification" in phase1_dict:
            weather_result = phase1_dict["weather_classification"]
            if isinstance(weather_result, Exception):
                self._handle_enrichment_error("weather_classification", weather_result, result)
            elif weather_result:
                result.weather_classification = weather_result

        # Clothing Classification
        if "clothing_classification" in phase1_dict:
            clothing_result = phase1_dict["clothing_classification"]
            if isinstance(clothing_result, Exception):
                self._handle_enrichment_error("clothing_classification", clothing_result, result)
            elif clothing_result:
                result.clothing_classifications = clothing_result

        # Pose Estimation
        if "pose_estimation" in phase1_dict:
            pose_result = phase1_dict["pose_estimation"]
            if isinstance(pose_result, Exception):
                self._handle_enrichment_error("pose_estimation", pose_result, result)
            elif pose_result:
                result.pose_results = pose_result

        # Depth Estimation
        if "depth_estimation" in phase1_dict:
            depth_result = phase1_dict["depth_estimation"]
            if isinstance(depth_result, Exception):
                self._handle_enrichment_error("depth_estimation", depth_result, result)
            elif depth_result:
                result.depth_analysis = depth_result

        # Action Recognition
        if "action_recognition" in phase1_dict:
            action_result = phase1_dict["action_recognition"]
            if isinstance(action_result, Exception):
                self._handle_enrichment_error("action_recognition", action_result, result)
            elif action_result:
                result.action_results = action_result

        # Vehicle Classification
        if "vehicle_classification" in phase1_dict:
            vehicle_result = phase1_dict["vehicle_classification"]
            if isinstance(vehicle_result, Exception):
                self._handle_enrichment_error("vehicle_classification", vehicle_result, result)
            elif vehicle_result:
                result.vehicle_classifications = vehicle_result

        # Vehicle Damage
        if "vehicle_damage" in phase1_dict:
            damage_result = phase1_dict["vehicle_damage"]
            if isinstance(damage_result, Exception):
                self._handle_enrichment_error("vehicle_damage_detection", damage_result, result)
            elif damage_result:
                result.vehicle_damage = damage_result

        # Pet Classification
        if "pet_classification" in phase1_dict:
            pet_result = phase1_dict["pet_classification"]
            if isinstance(pet_result, Exception):
                self._handle_enrichment_error("pet_classification", pet_result, result)
            elif pet_result:
                result.pet_classifications = pet_result
                if result.pet_only_event:
                    logger.info("Pet-only event detected - can skip Nemotron risk analysis")

        # Clothing Segmentation
        if "clothing_segmentation" in phase1_dict:
            seg_result = phase1_dict["clothing_segmentation"]
            if isinstance(seg_result, Exception):
                self._handle_enrichment_error("clothing_segmentation", seg_result, result)
            elif seg_result:
                result.clothing_segmentation = seg_result

        # Scene OCR Frame (Phase 1 partial result - frame-only OCR)
        if "scene_ocr_frame" in phase1_dict:
            ocr_frame_result = phase1_dict["scene_ocr_frame"]
            if isinstance(ocr_frame_result, Exception):
                self._handle_enrichment_error("scene_ocr_frame", ocr_frame_result, result)
            elif ocr_frame_result:
                # Store partial result; Phase 2 will complete with crop OCR
                result.scene_ocr = ocr_frame_result

        # Threat Detection (via enrichment-light service)
        if "threat_detection" in phase1_dict:
            threat_result = phase1_dict["threat_detection"]
            if isinstance(threat_result, Exception):
                self._handle_enrichment_error("threat_detection", threat_result, result)
            elif threat_result:
                result.threat_detection = threat_result

        # Demographics Analysis (via heavy enrichment service)
        if "demographics" in phase1_dict:
            demo_result = phase1_dict["demographics"]
            if isinstance(demo_result, Exception):
                self._handle_enrichment_error("demographics", demo_result, result)
            elif demo_result:
                # Unpack tuple of (age_classifications, gender_classifications)
                age_cls, gender_cls = demo_result
                if age_cls:
                    result.age_classifications = age_cls
                if gender_cls:
                    result.gender_classifications = gender_cls

        # Smoke/Fire Detection (NEM-5566 - SAFETY CRITICAL)
        if "smoke_fire_detection" in phase1_dict:
            sf_result = phase1_dict["smoke_fire_detection"]
            if isinstance(sf_result, Exception):
                self._handle_enrichment_error("smoke_fire_detection", sf_result, result)
            elif sf_result is not None:
                result.smoke_fire_detection = sf_result

        # YOLO-World Zero-Shot Detection (NEM-5566)
        if "yolo_world_detection" in phase1_dict:
            yw_result = phase1_dict["yolo_world_detection"]
            if isinstance(yw_result, Exception):
                self._handle_enrichment_error("yolo_world_detection", yw_result, result)
            elif yw_result:
                result.yolo_world_detections = yw_result

        # OSNet Person Re-ID Embeddings (NEM-5566)
        if "osnet_reid" in phase1_dict:
            osnet_result = phase1_dict["osnet_reid"]
            if isinstance(osnet_result, Exception):
                self._handle_enrichment_error("osnet_reid", osnet_result, result)
            elif osnet_result:
                # Merge into person_embeddings (don't overwrite if service already populated)
                for det_id, emb in osnet_result.items():
                    if det_id not in result.person_embeddings:
                        result.person_embeddings[det_id] = emb

        # CLIP Scene Classification (NEM-5525)
        if "clip_scene_classification" in phase1_dict:
            classify_result = phase1_dict["clip_scene_classification"]
            if isinstance(classify_result, Exception):
                self._handle_enrichment_error("clip_scene_classification", classify_result, result)
            elif classify_result:
                scores, top_label = classify_result
                result.clip_scene_classification = scores
                result.clip_scene_top_label = top_label

        # CLIP Threat Pattern Matching (NEM-5525)
        if "clip_threat_matching" in phase1_dict:
            threat_result = phase1_dict["clip_threat_matching"]
            if isinstance(threat_result, Exception):
                self._handle_enrichment_error("clip_threat_matching", threat_result, result)
            elif threat_result:
                result.clip_threat_matches = threat_result

        # Re-ID via enrichment-light service (populates result directly)
        if "reid_via_service" in phase1_dict:
            reid_result = phase1_dict["reid_via_service"]
            if isinstance(reid_result, Exception):
                self._handle_enrichment_error("reid_via_service", reid_result, result)

        # Unified Enrichment tasks (NEM-5525)
        # These tasks populate `result` directly via _map_unified_to_enrichment_result,
        # so we only need to handle exceptions here.
        for unified_key in (
            "unified_person_enrichment",
            "unified_vehicle_enrichment",
            "unified_animal_enrichment",
        ):
            if unified_key in phase1_dict:
                unified_result = phase1_dict[unified_key]
                if isinstance(unified_result, Exception):
                    self._handle_enrichment_error(unified_key, unified_result, result)

    # ==========================================================================
    # Safe wrapper methods for Phase 1 parallel execution
    # These methods catch exceptions and return them for asyncio.gather
    # ==========================================================================

    async def _safe_detect_faces(
        self,
        persons: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[FaceResult]:
        """Safe wrapper for face detection that returns empty list on error."""
        return await self._detect_faces(persons, images)

    async def _safe_detect_license_plates(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Safe wrapper for license plate detection."""
        return await self._detect_license_plates(vehicles, images)

    async def _safe_detect_plates_fast_alpr(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Safe wrapper for FastALPR end-to-end plate detection + OCR (NEM-5569).

        Uses FastALPR (~28MB) instead of YOLO11 (300MB) + PaddleOCR (100MB).
        Returns LicensePlateResult with text already populated (skips Phase 2 OCR).
        """
        return await self._detect_plates_fast_alpr(vehicles, images)

    async def _safe_detect_violence(
        self,
        image: Image.Image,
    ) -> ViolenceDetectionResult | None:
        """Safe wrapper for violence detection."""
        return await self._detect_violence(image)

    async def _safe_assess_image_quality(
        self,
        image: Image.Image,
        camera_id: str | None,
    ) -> ImageQualityResult | None:
        """Safe wrapper for image quality assessment."""
        return await self._assess_image_quality(image, camera_id)

    async def _safe_classify_weather(
        self,
        image: Image.Image,
    ) -> WeatherResult | None:
        """Safe wrapper for weather classification."""
        return await self._classify_weather(image)

    async def _safe_classify_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingClassification]:
        """Safe wrapper for clothing classification."""
        return await self._classify_person_clothing(persons, image)

    async def _safe_estimate_poses(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PoseResult]:
        """Safe wrapper for pose estimation."""
        return await self._estimate_poses(persons, image)

    async def _safe_analyze_depth(
        self,
        detections: list[DetectionInput],
        image: Image.Image,
    ) -> DepthAnalysisResult | None:
        """Safe wrapper for depth analysis."""
        return await self._analyze_depth(detections, image)

    async def _safe_recognize_actions(
        self,
        image: Image.Image,
        camera_id: str | None,
    ) -> dict[str, Any] | None:
        """Safe wrapper for X-CLIP action recognition (DEPRECATED).

        Deprecated in favor of _recognize_actions_from_skeleton() (NEM-5563).
        Kept as fallback if ST-GCN++ is unavailable.
        """
        frames = await self._get_action_frames(camera_id, image)
        if frames:
            return await self._recognize_actions(frames)
        return None

    async def _safe_classify_vehicle_types(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleClassificationResult]:
        """Safe wrapper for vehicle classification."""
        return await self._classify_vehicle_types(vehicles, image)

    async def _safe_detect_vehicle_damage(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleDamageResult]:
        """Safe wrapper for vehicle damage detection."""
        return await self._detect_vehicle_damage(vehicles, image)

    async def _safe_classify_pets(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PetClassificationResult]:
        """Safe wrapper for pet classification."""
        return await self._classify_pets(animals, image)

    async def _safe_classify_demographics(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> tuple[dict[str, AgeClassificationResult], dict[str, GenderClassificationResult]]:
        """Classify age and gender for person detections (NEM-5566).

        Crops each person detection and runs age + gender classifiers.
        Uses batch inference when multiple persons are detected.

        Args:
            persons: Person detections to classify
            image: Full frame PIL Image

        Returns:
            Tuple of (age_classifications, gender_classifications) dicts keyed by detection ID
        """
        age_results: dict[str, AgeClassificationResult] = {}
        gender_results: dict[str, GenderClassificationResult] = {}

        if not persons:
            return age_results, gender_results

        # Crop person images
        person_crops: list[tuple[str, Image.Image]] = []
        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            crop = await self._crop_to_bbox(image, person.bbox)
            if crop is not None:
                person_crops.append((det_id, crop))

        if not person_crops:
            return age_results, gender_results

        det_ids = [pc[0] for pc in person_crops]
        crops = [pc[1] for pc in person_crops]

        # Run age classification
        if self.age_classification_enabled:
            try:
                start = time.monotonic()
                async with self.model_manager.load("vit-age-classifier") as model_dict:
                    age_batch = await classify_ages_batch(model_dict, crops)
                    for det_id, age_result in zip(det_ids, age_batch, strict=True):
                        age_results[det_id] = age_result
                duration = time.monotonic() - start
                observe_enrichment_model_duration("age_classification", duration)
                record_enrichment_model_call("age_classification")
                logger.debug(
                    "Age classification completed for %d persons in %.2fs",
                    len(age_results),
                    duration,
                )
            except Exception as e:
                record_enrichment_model_error("age_classification")
                logger.debug(f"Age classification skipped: {e}")

        # Run gender classification
        if self.gender_classification_enabled:
            try:
                start = time.monotonic()
                async with self.model_manager.load("vit-gender-classifier") as model_dict:
                    gender_batch = await classify_genders_batch(model_dict, crops)
                    for det_id, gender_result in zip(det_ids, gender_batch, strict=True):
                        gender_results[det_id] = gender_result
                duration = time.monotonic() - start
                observe_enrichment_model_duration("gender_classification", duration)
                record_enrichment_model_call("gender_classification")
                logger.debug(
                    "Gender classification completed for %d persons in %.2fs",
                    len(gender_results),
                    duration,
                )
            except Exception as e:
                record_enrichment_model_error("gender_classification")
                logger.debug(f"Gender classification skipped: {e}")

        return age_results, gender_results

    async def _safe_detect_smoke_fire(
        self,
        image: Image.Image,
        camera_id: str | None = None,
    ) -> SmokeFireDetectionResult | None:
        """Detect smoke/fire on full frame (NEM-5566, SAFETY CRITICAL).

        Runs on every frame regardless of YOLO detections.
        Fire detection is immediate; smoke requires 2 consecutive frames
        to confirm (reduces false positives from steam/fog).

        Args:
            image: Full frame PIL Image
            camera_id: Camera identifier for consecutive frame tracking

        Returns:
            SmokeFireDetectionResult or None if detection fails/skipped
        """
        try:
            start = time.monotonic()
            async with self.model_manager.load("smoke-fire-yolov8n") as model:
                result = await detect_smoke_fire(model, image, confidence_threshold=0.5)
            duration = time.monotonic() - start
            observe_enrichment_model_duration("smoke_fire_detection", duration)
            record_enrichment_model_call("smoke_fire_detection")

            cam_key = camera_id or "_default"

            if result.has_fire:
                # Fire: immediate alert, reset smoke counter
                self._smoke_consecutive_counts[cam_key] = 0
                logger.warning(
                    "FIRE DETECTED (confidence=%.2f)",
                    result.highest_confidence,
                    extra={"camera_id": camera_id},
                )
                return result

            if result.has_smoke:
                # Smoke: require 2 consecutive frames to confirm
                self._smoke_consecutive_counts[cam_key] = (
                    self._smoke_consecutive_counts.get(cam_key, 0) + 1
                )
                count = self._smoke_consecutive_counts[cam_key]
                if count >= 2:
                    logger.warning(
                        "SMOKE CONFIRMED (%d consecutive frames, confidence=%.2f)",
                        count,
                        result.highest_confidence,
                        extra={"camera_id": camera_id},
                    )
                    return result
                else:
                    logger.debug(
                        "Smoke detected (%d/2 consecutive frames needed)",
                        count,
                        extra={"camera_id": camera_id},
                    )
                    return None  # Not yet confirmed
            else:
                # No smoke/fire: reset counter
                self._smoke_consecutive_counts[cam_key] = 0
                return result if result.has_detections else None

        except Exception as e:
            record_enrichment_model_error("smoke_fire_detection")
            logger.debug(f"Smoke/fire detection skipped: {e}")
            return None

    async def _safe_detect_yolo_world(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
    ) -> list[dict[str, Any]]:
        """Run YOLO-World zero-shot detection for suspicious scenarios (NEM-5566).

        Only triggered when YOLO26 detects potentially suspicious items or
        unknown objects. Not run on every frame due to 1.5GB VRAM cost.

        Args:
            image: Full frame PIL Image
            detections: Current YOLO26 detections to check for suspicious triggers

        Returns:
            List of YOLO-World detection dicts with class_name, confidence, bbox, priority
        """
        # Determine if we should run YOLO-World based on detection context
        suspicious_classes = {
            "backpack",
            "suitcase",
            "handbag",
            "umbrella",
            "knife",
            "scissors",
            "baseball bat",
            "unknown",
        }
        has_suspicious = any(d.class_name.lower() in suspicious_classes for d in detections)
        has_person_with_low_conf = any(
            d.class_name == PERSON_CLASS and d.confidence < 0.6 for d in detections
        )

        if not has_suspicious and not has_person_with_low_conf:
            return []

        try:
            start = time.monotonic()
            async with self.model_manager.load("yolo-world-s") as model:
                results = await detect_with_prompts(model, image, confidence_threshold=0.25)
            duration = time.monotonic() - start
            observe_enrichment_model_duration("yolo_world_detection", duration)
            record_enrichment_model_call("yolo_world_detection")

            # Annotate results with priority level
            for det in results:
                det["priority"] = get_object_priority(det.get("class_name", ""))

            logger.debug(
                "YOLO-World detected %d objects in %.2fs",
                len(results),
                duration,
            )
            return results

        except Exception as e:
            record_enrichment_model_error("yolo_world_detection")
            logger.debug(f"YOLO-World detection skipped: {e}")
            return []

    async def _safe_extract_osnet_embeddings(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, Any]:
        """Extract OSNet person re-ID embeddings (NEM-5566).

        Extracts appearance embeddings for each person detection using
        OSNet for cross-camera person matching.

        Args:
            persons: Person detections
            image: Full frame PIL Image

        Returns:
            Dict mapping detection IDs to embedding results
        """
        embeddings: dict[str, Any] = {}
        if not persons:
            return embeddings

        try:
            start = time.monotonic()
            async with self.model_manager.load("osnet-ain-x1-0") as model_data:
                for i, person in enumerate(persons):
                    det_id = str(person.id) if person.id else str(i)
                    crop = await self._crop_to_bbox(image, person.bbox)
                    if crop is None:
                        continue

                    emb_result = await extract_person_embedding(
                        model_data, crop, detection_id=det_id
                    )
                    if emb_result is not None and emb_result.embedding is not None:
                        emb = emb_result.embedding
                        embeddings[det_id] = {
                            "embedding": emb.tolist() if hasattr(emb, "tolist") else emb,
                            "embedding_dim": len(emb) if hasattr(emb, "__len__") else 0,
                            "detection_id": det_id,
                        }

            duration = time.monotonic() - start
            observe_enrichment_model_duration("osnet_reid", duration)
            record_enrichment_model_call("osnet_reid")
            logger.debug(
                "OSNet embeddings extracted for %d/%d persons in %.2fs",
                len(embeddings),
                len(persons),
                duration,
            )
        except Exception as e:
            record_enrichment_model_error("osnet_reid")
            logger.debug(f"OSNet embedding extraction skipped: {e}")

        return embeddings

    async def _safe_segment_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingSegmentationResult]:
        """Safe wrapper for clothing segmentation."""
        return await self._segment_person_clothing(persons, image)

    async def _safe_run_scene_ocr_frame(
        self,
        image: Image.Image,
    ) -> SceneOCRResult | None:
        """Safe wrapper for full-frame scene OCR.

        Runs in Phase 1 parallel with other enrichment models.
        Extracts text from the full frame (signs, house numbers, etc.)

        Args:
            image: Full frame PIL Image

        Returns:
            SceneOCRResult with frame-level OCR results, or None on error
        """
        if self._scene_ocr_service is None:
            return None

        try:
            # Run full-frame OCR only (no crops yet - detections not processed)
            # This extracts scene text like signs, house numbers, etc.
            result = await self._scene_ocr_service._run_full_frame_ocr(image)
            # Return a partial SceneOCRResult with just frame results
            # Crop results will be added in Phase 2
            from backend.services.scene_ocr_service import SceneOCRResult as OCRResult
            from backend.services.scene_ocr_service import SceneTextResult, _classify_text_type

            scene_texts = []
            for ocr in result:
                # Determine if uncertain (confidence 0.50-0.79)
                is_uncertain = 0.50 <= ocr.confidence < 0.80
                scene_texts.append(
                    SceneTextResult(
                        value=ocr.text,
                        confidence=ocr.confidence,
                        bbox=ocr.bbox,
                        text_type=_classify_text_type(ocr.text),
                        is_uncertain=is_uncertain,
                    )
                )
            return OCRResult(scene_texts=scene_texts)
        except Exception as e:
            logger.warning(f"Full-frame scene OCR failed: {e}")
            return None

    async def _safe_run_scene_ocr_crops(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
        frame_ocr_result: SceneOCRResult | None,
    ) -> SceneOCRResult | None:
        """Run crop OCR and merge with frame results.

        Runs in Phase 2 after detections are processed.
        Extracts text from person, vehicle, and package crops.

        Args:
            image: Full frame PIL Image
            detections: List of high-confidence detections
            frame_ocr_result: Previous frame OCR result from Phase 1

        Returns:
            Complete SceneOCRResult with merged frame and crop OCR, or None on error
        """
        if self._scene_ocr_service is None:
            return frame_ocr_result

        try:
            # Run the complete process_frame which does crop OCR and deduplication
            result = await self._scene_ocr_service.process_frame(image, detections)

            # If we had frame results from Phase 1, the process_frame will have
            # re-run frame OCR. This is acceptable for now as it ensures consistency.
            # Future optimization: pass frame results to avoid re-running
            return result
        except Exception as e:
            logger.warning(f"Scene OCR crop processing failed: {e}")
            # Return the frame-only results if we have them
            return frame_ocr_result

    # ==========================================================================
    # CLIP Analysis Methods (NEM-5525)
    # ==========================================================================

    async def _safe_clip_scene_classify(
        self,
        image: Image.Image,
    ) -> tuple[dict[str, float], str] | None:
        """Classify the scene using CLIP zero-shot classification with surveillance labels.

        Runs CLIP /classify with surveillance-relevant labels to provide scene-level
        context for Nemotron threat analysis. Expected to improve accuracy by 5-10%.

        Args:
            image: Full frame PIL Image

        Returns:
            Tuple of (scores dict, top_label), or None on error
        """
        record_enrichment_model_call("clip-scene-classify")
        start_time = time.perf_counter()
        try:
            from backend.services.clip_client import get_clip_client

            clip_client = get_clip_client()
            scores, top_label = await clip_client.classify(image, CLIP_SCENE_LABELS)
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("clip-scene-classify", duration)
            logger.debug(
                f"CLIP scene classification: top='{top_label}' ({scores.get(top_label, 0):.2f})",
                extra={
                    "service": "clip-scene-classify",
                    "duration_ms": int(duration * 1000),
                    "top_label": top_label,
                },
            )
            return scores, top_label
        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("clip-scene-classify", duration)
            record_enrichment_model_error("clip-scene-classify")
            logger.warning(
                f"CLIP scene classification failed: {e}",
                extra={
                    "service": "clip-scene-classify",
                    "error_type": type(e).__name__,
                    "duration_ms": int(duration * 1000),
                },
            )
            return None

    async def _safe_clip_threat_match(
        self,
        image: Image.Image,
    ) -> dict[str, float] | None:
        """Match the scene against threat description patterns using CLIP batch similarity.

        Runs CLIP /batch-similarity with a library of threat description texts.
        High-scoring matches indicate visual similarity to known threat patterns.
        Expected to improve precision by 3-7%.

        Args:
            image: Full frame PIL Image

        Returns:
            Dictionary mapping threat descriptions to similarity scores, or None on error
        """
        record_enrichment_model_call("clip-threat-match")
        start_time = time.perf_counter()
        try:
            from backend.services.clip_client import get_clip_client

            clip_client = get_clip_client()
            similarities = await clip_client.batch_similarity(image, CLIP_THREAT_DESCRIPTIONS)
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("clip-threat-match", duration)
            # Log top matches for debugging
            if similarities:
                top_matches = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:3]
                top_str = ", ".join(f"'{desc}' ({score:.2f})" for desc, score in top_matches)
                logger.debug(
                    f"CLIP threat matches (top 3): {top_str}",
                    extra={
                        "service": "clip-threat-match",
                        "duration_ms": int(duration * 1000),
                        "match_count": len(similarities),
                    },
                )
            return similarities
        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("clip-threat-match", duration)
            record_enrichment_model_error("clip-threat-match")
            logger.warning(
                f"CLIP threat matching failed: {e}",
                extra={
                    "service": "clip-threat-match",
                    "error_type": type(e).__name__,
                    "duration_ms": int(duration * 1000),
                },
            )
            return None

    async def _run_clip_anomaly_detection(
        self,
        image: Image.Image,
        camera_id: str,
        result: EnrichmentResult,
    ) -> None:
        """Run CLIP visual anomaly detection by comparing against per-camera baseline.

        Uses the SceneBaselineService to compare the current frame against
        a stored baseline embedding for the camera. Also updates the baseline
        when the scene is normal (low anomaly score).

        Expected to improve recall by 2-5%.

        Args:
            image: Full frame PIL Image
            camera_id: Camera identifier for baseline lookup
            result: EnrichmentResult to populate with anomaly score
        """
        record_enrichment_model_call("clip-anomaly-detect")
        start_time = time.perf_counter()
        try:
            from backend.services.clip_client import get_clip_client
            from backend.services.scene_baseline import (
                BaselineNotFoundError,
                get_scene_baseline_service,
            )

            clip_client = get_clip_client()
            baseline_service = get_scene_baseline_service(self.redis_client, clip_client)  # type: ignore[arg-type]

            # Check if baseline exists for this camera
            has_baseline = await baseline_service.has_baseline(camera_id)

            if has_baseline:
                # Compute anomaly score against baseline
                anomaly_score, similarity = await baseline_service.get_anomaly_score(
                    camera_id, image
                )
                result.clip_anomaly_score = anomaly_score
                result.clip_anomaly_similarity = similarity

                observe_enrichment_model_duration(
                    "clip-anomaly-detect", time.perf_counter() - start_time
                )
                logger.debug(
                    f"CLIP anomaly detection for camera={camera_id}: "
                    f"score={anomaly_score:.3f}, similarity={similarity:.3f}",
                    extra={
                        "service": "clip-anomaly-detect",
                        "camera_id": camera_id,
                        "anomaly_score": anomaly_score,
                    },
                )

                # Update baseline with current frame if scene is normal
                # (anomaly score < 0.3 indicates a normal scene)
                if anomaly_score < 0.3:
                    await baseline_service.update_baseline_from_image(camera_id, image)
            else:
                observe_enrichment_model_duration(
                    "clip-anomaly-detect", time.perf_counter() - start_time
                )
                # No baseline yet - initialize with current frame
                logger.info(
                    f"No CLIP baseline for camera={camera_id}, initializing with current frame",
                    extra={"service": "clip-anomaly-detect", "camera_id": camera_id},
                )
                await baseline_service.update_baseline_from_image(camera_id, image)
                # Skip anomaly scoring on first frame (no reference point)

        except BaselineNotFoundError:
            observe_enrichment_model_duration(
                "clip-anomaly-detect", time.perf_counter() - start_time
            )
            logger.debug(
                f"No CLIP baseline for camera={camera_id}, skipping anomaly detection",
                extra={"service": "clip-anomaly-detect", "camera_id": camera_id},
            )
        except Exception as e:
            observe_enrichment_model_duration(
                "clip-anomaly-detect", time.perf_counter() - start_time
            )
            record_enrichment_model_error("clip-anomaly-detect")
            logger.warning(
                f"CLIP anomaly detection failed for camera={camera_id}: {e}",
                extra={
                    "service": "clip-anomaly-detect",
                    "camera_id": camera_id,
                    "error_type": type(e).__name__,
                },
            )

    # ==========================================================================
    # Unified Enrichment Service Methods
    # These methods replace the individual _*_via_service methods by calling
    # the single /enrich endpoint per detection (NEM-5525).
    # ==========================================================================

    def _pil_to_bytes(self, image: Image.Image, fmt: str = "PNG") -> bytes:
        """Convert a PIL Image to raw bytes.

        Args:
            image: PIL Image to convert
            fmt: Image format (PNG or JPEG)

        Returns:
            Raw image bytes
        """
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()

    async def _enrich_single_detection_unified(
        self,
        detection: DetectionInput,
        image: Image.Image,
        detection_type: str,
        camera_id: str | None = None,
    ) -> tuple[str, UnifiedEnrichmentResult]:
        """Enrich a single detection via the unified /enrich endpoint.

        Crops the detection from the full frame, then calls the unified
        enrichment endpoint which runs all applicable models in one request.

        Args:
            detection: Detection to enrich
            image: Full frame PIL Image
            detection_type: One of "person", "vehicle", "animal"
            camera_id: Camera ID for action recognition frame buffer

        Returns:
            Tuple of (detection_id, UnifiedEnrichmentResult)
        """
        det_id = str(detection.id) if detection.id else "0"

        # Crop detection from full frame
        cropped = await self._crop_to_bbox(image, detection.bbox)
        if cropped is None:
            return det_id, UnifiedEnrichmentResult()

        # Convert to bytes for the client
        image_bytes = self._pil_to_bytes(cropped)

        # Get bounding box tuple
        bbox_tuple = detection.bbox.to_tuple() if detection.bbox else (0.0, 0.0, 0.0, 0.0)

        # Build options
        options: dict[str, Any] = {}
        if detection_type == "person":
            # Check if face is visible based on detection context
            options["face_visible"] = True  # Default to True; the service decides

        # Get frame bytes for action recognition (person detections only)
        frame_bytes_list: list[bytes] | None = None
        if detection_type == "person" and self.action_recognition_enabled:
            frames = await self._get_action_frames(camera_id, image)
            if frames and len(frames) > 1:
                frame_bytes_list = [self._pil_to_bytes(f) for f in frames]

        # Call unified enrichment endpoint
        client = self._get_enrichment_client()
        async with self._enrichment_service_semaphore:
            unified_result = await client.enrich_detection(
                image=image_bytes,
                detection_type=detection_type,
                bbox=bbox_tuple,
                frames=frame_bytes_list,
                options=options,
            )

        return det_id, unified_result

    def _map_unified_to_enrichment_result(
        self,
        result: EnrichmentResult,
        det_id: str,
        unified: UnifiedEnrichmentResult,
        detection_type: str,
    ) -> None:
        """Map fields from UnifiedEnrichmentResult into EnrichmentResult.

        Converts the unified result's typed fields back to the pipeline's
        expected result types so downstream code (context generation,
        Nemotron prompts) continues to work unchanged.

        Args:
            result: EnrichmentResult to populate
            det_id: Detection ID string
            unified: UnifiedEnrichmentResult from the /enrich endpoint
            detection_type: One of "person", "vehicle", "animal"
        """
        # --- Pose (person only) ---
        if unified.pose is not None and detection_type == "person":
            # Convert UnifiedPoseResult to local PoseResult
            keypoints_dict: dict[str, Keypoint] = {}
            for kp_data in unified.pose.keypoints:
                name = kp_data.get("name", "unknown")
                keypoints_dict[name] = Keypoint(
                    x=kp_data.get("x", 0.0),
                    y=kp_data.get("y", 0.0),
                    confidence=kp_data.get("confidence", 0.0),
                    name=name,
                )

            avg_confidence = (
                sum(kp_data.get("confidence", 0.0) for kp_data in unified.pose.keypoints)
                / len(unified.pose.keypoints)
                if unified.pose.keypoints
                else 0.0
            )

            result.pose_results[det_id] = PoseResult(
                keypoints=keypoints_dict,
                pose_class=unified.pose.pose_class,
                pose_confidence=avg_confidence,
                bbox=None,
            )

        # --- Clothing (person only) ---
        if unified.clothing is not None and detection_type == "person":
            top_cat = ""
            confidence = 0.0
            description = ""
            if unified.clothing.categories:
                top = unified.clothing.categories[0]
                top_cat = top.get("category", "")
                confidence = top.get("confidence", 0.0)
                description = top.get("description", top_cat)

            result.clothing_classifications[det_id] = ClothingClassification(
                top_category=top_cat,
                confidence=confidence,
                all_scores={},
                is_suspicious=unified.clothing.is_suspicious,
                is_service_uniform=False,
                raw_description=description,
            )

        # --- Demographics (person only) ---
        if unified.demographics is not None and detection_type == "person":
            from types import SimpleNamespace

            is_minor = unified.demographics.age_range in (
                "0-10",
                "11-20",
                "child",
                "teenager",
            )
            result.age_classifications[det_id] = SimpleNamespace(
                age_group=unified.demographics.age_range,
                display_name=unified.demographics.age_range,
                confidence=unified.demographics.age_confidence,
                is_minor=is_minor,
            )
            result.gender_classifications[det_id] = SimpleNamespace(
                gender=unified.demographics.gender,
                confidence=unified.demographics.gender_confidence,
            )

        # --- Threat (person only) ---
        if unified.threat is not None and unified.threat.has_threat and detection_type == "person":
            # Convert UnifiedThreatResult to local ThreatDetectionResult
            threats = []
            for t in unified.threat.threats:
                threat_class = t.get("type", t.get("class_name", "unknown"))
                threats.append(
                    ThreatDetection(
                        class_name=threat_class,
                        confidence=t.get("confidence", 0.0),
                        bbox=tuple(t["bbox"]) if "bbox" in t else (0.0, 0.0, 0.0, 0.0),
                        is_high_priority=threat_class.lower()
                        in {
                            "gun",
                            "pistol",
                            "rifle",
                            "firearm",
                            "handgun",
                            "knife",
                            "machete",
                            "sword",
                        },
                    )
                )
            # Only set if we don't already have threat detection results
            if result.threat_detection is None:
                result.threat_detection = ThreatDetectionResult(threats=threats)

        # --- Re-ID embedding (person only) ---
        if unified.reid_embedding is not None and detection_type == "person":
            result.person_embeddings[det_id] = {
                "embedding": unified.reid_embedding,
                "embedding_dim": len(unified.reid_embedding),
                "detection_id": det_id,
            }

        # --- Action (person only) ---
        if unified.action is not None and detection_type == "person":
            # Convert to local action dict format
            action_data = unified.action
            if result.action_results is None:
                result.action_results = {}
            result.action_results[det_id] = {
                "detected_action": action_data.get(
                    "top_action", action_data.get("action", "unknown")
                ),
                "confidence": action_data.get("confidence", 0.0),
                "top_actions": sorted(
                    action_data.get("all_scores", {}).items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
                if action_data.get("all_scores")
                else [],
                "all_scores": action_data.get("all_scores", {}),
            }

        # --- Vehicle (vehicle only) ---
        if unified.vehicle is not None and detection_type == "vehicle":
            v = unified.vehicle
            display_parts = []
            if v.color:
                display_parts.append(v.color)
            if v.make:
                display_parts.append(v.make)
            if v.model:
                display_parts.append(v.model)
            display_parts.append(v.type)
            display_name = " ".join(display_parts)

            result.vehicle_classifications[det_id] = VehicleClassificationResult(
                vehicle_type=v.type,
                confidence=v.confidence,
                display_name=display_name,
                is_commercial=v.type
                in {
                    "delivery_van",
                    "box_truck",
                    "semi_truck",
                    "cargo_van",
                    "pickup_truck",
                },
                all_scores={},
            )

        # --- Pet (animal only) ---
        if unified.pet is not None and detection_type == "animal":
            pet_data = unified.pet
            result.pet_classifications[det_id] = PetClassificationResult(
                animal_type=pet_data.get("pet_type", pet_data.get("type", "unknown")),
                confidence=pet_data.get("confidence", 0.0),
                cat_score=0.0,
                dog_score=0.0,
                is_household_pet=pet_data.get("is_household_pet", True),
            )

        # --- Depth (any type) ---
        if unified.depth is not None:
            # Depth from unified endpoint provides per-detection depth info.
            # We merge this into the existing depth_analysis if present, or note it.
            # The unified depth is typically per-detection, not full-frame, so
            # we store it as a supplemental annotation.
            if result.depth_analysis is None:
                # Create a minimal DepthAnalysisResult from the unified data
                # The unified depth format is a dict with depth values
                depth_data = unified.depth
                if isinstance(depth_data, dict):
                    # Store in a way that's compatible with DepthAnalysisResult
                    logger.debug(
                        f"Depth data from unified endpoint for {det_id}: "
                        f"mean={depth_data.get('mean_depth', 'N/A')}"
                    )

    async def _enrich_persons_via_unified_service(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
        camera_id: str | None,
        result: EnrichmentResult,
    ) -> None:
        """Enrich all person detections via the unified /enrich endpoint.

        Makes one /enrich call per person detection (in parallel), replacing
        separate calls to pose, clothing, threat, demographics, and action
        endpoints.

        Args:
            persons: List of person detections
            image: Full frame PIL Image
            camera_id: Camera ID for action recognition frame buffer
            result: EnrichmentResult to populate
        """
        if not persons:
            return

        record_enrichment_model_call("unified-enrich-person")
        start_time = time.perf_counter()

        tasks = []
        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            tasks.append(self._enrich_single_detection_unified(person, image, "person", camera_id))

        # Run all person enrichments in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - start_time
        observe_enrichment_model_duration("unified-enrich-person", duration)

        for i, task_result in enumerate(results_list):
            if isinstance(task_result, BaseException):
                det_id = str(persons[i].id) if persons[i].id else str(i)
                logger.warning(
                    f"Unified enrichment failed for person {det_id}: {sanitize_error(task_result)}",  # type: ignore[arg-type]
                    extra={"service": "unified-enrich", "detection_id": det_id},
                )
                record_enrichment_model_error("unified-enrich-person")
                continue

            det_id, unified = task_result
            self._map_unified_to_enrichment_result(result, det_id, unified, "person")

        logger.debug(
            f"Unified person enrichment complete: {len(persons)} persons in {duration:.2f}s"
        )

    async def _enrich_vehicles_via_unified_service(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
        result: EnrichmentResult,
    ) -> None:
        """Enrich all vehicle detections via the unified /enrich endpoint.

        Makes one /enrich call per vehicle detection (in parallel), replacing
        the separate _classify_vehicle_via_service call.

        Args:
            vehicles: List of vehicle detections
            image: Full frame PIL Image
            result: EnrichmentResult to populate
        """
        if not vehicles:
            return

        record_enrichment_model_call("unified-enrich-vehicle")
        start_time = time.perf_counter()

        tasks = []
        for vehicle in vehicles:
            tasks.append(self._enrich_single_detection_unified(vehicle, image, "vehicle"))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - start_time
        observe_enrichment_model_duration("unified-enrich-vehicle", duration)

        for i, task_result in enumerate(results_list):
            if isinstance(task_result, BaseException):
                det_id = str(vehicles[i].id) if vehicles[i].id else str(i)
                logger.warning(
                    f"Unified enrichment failed for vehicle {det_id}: {sanitize_error(task_result)}",  # type: ignore[arg-type]
                    extra={"service": "unified-enrich", "detection_id": det_id},
                )
                record_enrichment_model_error("unified-enrich-vehicle")
                continue

            det_id, unified = task_result
            self._map_unified_to_enrichment_result(result, det_id, unified, "vehicle")

        logger.debug(
            f"Unified vehicle enrichment complete: {len(vehicles)} vehicles in {duration:.2f}s"
        )

    async def _enrich_animals_via_unified_service(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
        result: EnrichmentResult,
    ) -> None:
        """Enrich all animal detections via the unified /enrich endpoint.

        Makes one /enrich call per animal detection (in parallel), replacing
        the separate _classify_pets_via_service call.

        Args:
            animals: List of animal detections
            image: Full frame PIL Image
            result: EnrichmentResult to populate
        """
        if not animals:
            return

        record_enrichment_model_call("unified-enrich-animal")
        start_time = time.perf_counter()

        tasks = []
        for animal in animals:
            tasks.append(self._enrich_single_detection_unified(animal, image, "animal"))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - start_time
        observe_enrichment_model_duration("unified-enrich-animal", duration)

        for i, task_result in enumerate(results_list):
            if isinstance(task_result, BaseException):
                det_id = str(animals[i].id) if animals[i].id else str(i)
                logger.warning(
                    f"Unified enrichment failed for animal {det_id}: {sanitize_error(task_result)}",  # type: ignore[arg-type]
                    extra={"service": "unified-enrich", "detection_id": det_id},
                )
                record_enrichment_model_error("unified-enrich-animal")
                continue

            det_id, unified = task_result
            self._map_unified_to_enrichment_result(result, det_id, unified, "animal")

        # Check for pet-only event
        if result.pet_classifications and result.pet_only_event:
            logger.info(
                "Pet-only event detected via unified enrichment - can skip Nemotron risk analysis"
            )

        logger.debug(
            f"Unified animal enrichment complete: {len(animals)} animals in {duration:.2f}s"
        )

    # ==========================================================================
    # DEPRECATED: Individual _via_service methods
    # These are kept for backward compatibility but are no longer called when
    # use_enrichment_service=True. The unified enrichment methods above
    # replace all of these with single /enrich calls per detection.
    # ==========================================================================

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
        record_enrichment_model_call("vehicle-via-service")

        for i, vehicle in enumerate(vehicles):
            det_id = str(vehicle.id) if vehicle.id else str(i)
            start_time = time.perf_counter()

            try:
                # Crop vehicle from full frame
                vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                if vehicle_crop is None:
                    continue

                # Call remote service
                bbox_tuple = vehicle.bbox.to_tuple() if vehicle.bbox else None
                remote_result = await client.classify_vehicle(vehicle_crop, bbox_tuple)

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("vehicle-via-service", duration)

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
                        f"({remote_result.confidence:.0%})",
                        extra={
                            "service": "vehicle-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (
                httpx.ConnectError,
                httpx.TimeoutException,
                EnrichmentUnavailableError,
            ) as e:
                observe_enrichment_model_duration(
                    "vehicle-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("vehicle-via-service")
                logger.warning(
                    f"Enrichment service unavailable for vehicle {det_id}",
                    extra={
                        "service": "vehicle-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "vehicle-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("vehicle-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Vehicle classification client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "vehicle-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Vehicle classification server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "vehicle-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "vehicle-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("vehicle-via-service")
                logger.error(
                    f"Vehicle classification parse error for {det_id}",
                    extra={
                        "service": "vehicle-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "vehicle-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("vehicle-via-service")
                logger.error(
                    f"Vehicle classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "vehicle-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
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
        record_enrichment_model_call("pet-via-service")

        for i, animal in enumerate(animals):
            det_id = str(animal.id) if animal.id else str(i)
            start_time = time.perf_counter()

            try:
                animal_crop = await self._crop_to_bbox(image, animal.bbox)
                if animal_crop is None:
                    continue

                bbox_tuple = animal.bbox.to_tuple() if animal.bbox else None
                remote_result = await client.classify_pet(animal_crop, bbox_tuple)

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("pet-via-service", duration)

                if remote_result:
                    results[det_id] = PetClassificationResult(
                        animal_type=remote_result.pet_type,
                        confidence=remote_result.confidence,
                        cat_score=0.0,
                        dog_score=0.0,
                        is_household_pet=remote_result.is_household_pet,
                    )
                    logger.debug(
                        f"Animal {det_id} classified (via service) as {remote_result.pet_type} "
                        f"({remote_result.confidence:.0%} confidence)",
                        extra={
                            "service": "pet-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
                observe_enrichment_model_duration(
                    "pet-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pet-via-service")
                logger.warning(
                    f"Enrichment service unavailable for animal {det_id}",
                    extra={
                        "service": "pet-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "pet-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pet-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Pet classification client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "pet-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Pet classification server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "pet-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "pet-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pet-via-service")
                logger.error(
                    f"Pet classification parse error for {det_id}",
                    extra={
                        "service": "pet-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "pet-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pet-via-service")
                logger.error(
                    f"Pet classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "pet-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
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
            async with self.model_manager.load("depth-anything-v2-tiny") as depth_pipeline:
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
        num_frames: int = 16,
    ) -> list[Image.Image]:
        """Get frames for X-CLIP action recognition.

        Retrieves a sequence of frames for temporal action recognition. If a
        FrameBuffer is configured and has enough frames for the camera, returns
        evenly sampled frames from the buffer converted to PIL Images.
        Otherwise, falls back to using just the current frame.

        X-CLIP xclip-base-patch16-16-frames model works best with 16 frames
        spanning the action sequence (NEM-3908 upgrade for +4% accuracy).

        Args:
            camera_id: Camera identifier for looking up buffered frames
            current_frame: The current PIL Image (fallback if no buffer)
            num_frames: Number of frames to retrieve (default 16 for patch16 model)

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

    async def _recognize_actions_from_skeleton(
        self,
        pose_results: dict[str, PoseResult],
        persons: list[DetectionInput],  # noqa: ARG002
        camera_id: str | None,
    ) -> dict[str, Any] | None:
        """Recognize actions using ST-GCN++ skeleton-based approach (NEM-5563).

        Uses pose keypoints already extracted by ViTPose/YOLOv8n-Pose to classify
        actions. Buffers keypoints per tracked person across frames and runs
        ST-GCN++ when enough temporal context is available.

        This replaces X-CLIP video-based action recognition, saving ~1,986MB VRAM.

        Args:
            pose_results: Dictionary mapping detection IDs to PoseResult
            persons: List of person detections
            camera_id: Camera identifier for per-camera buffering

        Returns:
            Dictionary with detected_action, confidence, top_actions, all_scores
            compatible with the X-CLIP output format, or None if not enough frames
        """
        if not pose_results:
            return None

        start_time = time.perf_counter()

        try:
            # Lazily initialize skeleton action service
            # Use preload (not context manager) so model stays loaded —
            # ST-GCN++ is only ~14MB so it's fine to keep resident
            if self._skeleton_action_service is None:
                await self.model_manager.preload("stgcn-plus-plus")
                model_dict = self.model_manager._loaded_models["stgcn-plus-plus"]
                self._skeleton_action_service = SkeletonActionService(
                    model_dict=model_dict,
                    buffer_size=60,
                    min_frames=30,
                    inference_interval=15,
                )

            # Feed keypoints for each detected person to the buffer
            best_result: SkeletonActionResult | None = None
            for det_id, pose in pose_results.items():
                # Build person tracking key from detection ID + camera
                person_key = f"{camera_id or 'unknown'}_{det_id}"

                # Feed keypoints to the skeleton service
                result = await self._skeleton_action_service.add_keypoints(
                    person_id=person_key,
                    keypoints=pose.keypoints,
                )

                # Keep the most security-relevant or highest-confidence result
                if result is not None:
                    if (
                        best_result is None
                        or (result.is_security_relevant and not best_result.is_security_relevant)
                        or result.confidence > best_result.confidence
                    ):
                        best_result = result

            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("stgcn", duration)

            if best_result is None:
                # Not enough frames buffered yet — this is expected for the first
                # 30 frames of a new person. Return None (no action result yet).
                return None

            record_enrichment_model_call("action")

            # Convert SkeletonActionResult to X-CLIP-compatible dict format
            # so the rest of the pipeline (prompts, LLM context) works unchanged
            action_dict: dict[str, Any] = {
                "detected_action": best_result.action_label,
                "confidence": best_result.confidence,
                "top_actions": best_result.top_actions,
                "all_scores": dict(best_result.top_actions),
                "security_risk": best_result.security_risk,
                "is_security_relevant": best_result.is_security_relevant,
                "source": "stgcn++",  # Flag for downstream consumers
            }

            logger.debug(
                f"Skeleton action recognition: {best_result.action_label} "
                f"({best_result.confidence:.0%}, risk={best_result.security_risk})"
            )
            return action_dict

        except Exception as e:
            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("stgcn", duration)
            record_enrichment_model_error("stgcn")
            logger.error(
                f"Skeleton action recognition failed: {sanitize_error(e)}",
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
        record_enrichment_model_call("clothing-via-service")

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            start_time = time.perf_counter()

            try:
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result = await client.classify_clothing(person_crop, bbox_tuple)

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("clothing-via-service", duration)

                if remote_result:
                    results[det_id] = ClothingClassification(
                        top_category=remote_result.top_category,
                        confidence=remote_result.confidence,
                        all_scores={},
                        is_suspicious=remote_result.is_suspicious,
                        is_service_uniform=remote_result.is_service_uniform,
                        raw_description=remote_result.description,
                    )
                    logger.debug(
                        f"Person {det_id} clothing (via service): {remote_result.description} "
                        f"({remote_result.confidence:.0%})",
                        extra={
                            "service": "clothing-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
                observe_enrichment_model_duration(
                    "clothing-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("clothing-via-service")
                logger.warning(
                    f"Enrichment service unavailable for person {det_id}",
                    extra={
                        "service": "clothing-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "clothing-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("clothing-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Clothing classification client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "clothing-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Clothing classification server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "clothing-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "clothing-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("clothing-via-service")
                logger.error(
                    f"Clothing classification parse error for {det_id}",
                    extra={
                        "service": "clothing-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "clothing-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("clothing-via-service")
                logger.error(
                    f"Clothing classification unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "clothing-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )

        return results

    async def _estimate_poses_via_service(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PoseResult]:
        """Estimate poses using the remote enrichment HTTP service.

        Routes to the appropriate service (heavy or light) based on
        ENRICHMENT_POSE_SERVICE configuration.

        Args:
            persons: List of person detections with bounding boxes
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to PoseResult
        """
        results: dict[str, PoseResult] = {}

        if not persons:
            return results

        client = self._get_enrichment_client()
        record_enrichment_model_call("pose-via-service")

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            start_time = time.perf_counter()

            try:
                # Crop person from full frame
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                # Call remote service
                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result: RemotePoseResult | None = await client.analyze_pose(
                    person_crop, bbox_tuple
                )

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("pose-via-service", duration)

                if remote_result:
                    # Convert remote PoseAnalysisResult to local PoseResult
                    # Remote keypoints are a list of KeypointData; local expects dict[str, Keypoint]
                    keypoints_dict: dict[str, Keypoint] = {}
                    for kp in remote_result.keypoints:
                        keypoints_dict[kp.name] = Keypoint(
                            x=kp.x,
                            y=kp.y,
                            confidence=kp.confidence,
                            name=kp.name,
                        )

                    # Map posture to pose_class and compute confidence from keypoints
                    avg_confidence = (
                        sum(kp.confidence for kp in remote_result.keypoints)
                        / len(remote_result.keypoints)
                        if remote_result.keypoints
                        else 0.0
                    )

                    results[det_id] = PoseResult(
                        keypoints=keypoints_dict,
                        pose_class=remote_result.posture,
                        pose_confidence=avg_confidence,
                        bbox=list(bbox_tuple) if bbox_tuple else None,
                    )

                    logger.debug(
                        f"Person {det_id} pose (via service): {remote_result.posture} "
                        f"({avg_confidence:.0%} confidence, {len(remote_result.keypoints)} keypoints)",
                        extra={
                            "service": "pose-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
                observe_enrichment_model_duration(
                    "pose-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pose-via-service")
                logger.warning(
                    f"Enrichment service unavailable for pose estimation {det_id}",
                    extra={
                        "service": "pose-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "pose-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pose-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Pose estimation client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "pose-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Pose estimation server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "pose-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "pose-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pose-via-service")
                logger.error(
                    f"Pose estimation parse error for {det_id}",
                    extra={
                        "service": "pose-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "pose-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("pose-via-service")
                logger.error(
                    f"Pose estimation unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "pose-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )

        return results

    async def _recognize_actions_via_service(  # noqa: PLR0911
        self,
        image: Image.Image,
        camera_id: str | None,
    ) -> dict[str, Any] | None:
        """Recognize actions using the remote enrichment HTTP service.

        Routes to the appropriate service (heavy or light) based on
        ENRICHMENT_ACTION_SERVICE configuration. Collects frames from
        the frame buffer (if available) for temporal action recognition.

        Args:
            image: Full frame image (current frame)
            camera_id: Camera ID for looking up buffered frames

        Returns:
            Dictionary with detected_action, confidence, top_actions, all_scores
            or None if recognition fails
        """
        # Collect frames for temporal analysis (same as local path)
        frames = await self._get_action_frames(camera_id, image)
        if not frames:
            return None

        client = self._get_enrichment_client()
        record_enrichment_model_call("action-via-service")
        start_time = time.perf_counter()

        try:
            # Call remote service with frame sequence
            remote_result: RemoteActionResult | None = await client.classify_action(frames)

            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("action-via-service", duration)

            if remote_result:
                # Convert remote ActionClassificationResult to local dict format
                # that matches the output of xclip_loader.classify_actions()
                result: dict[str, Any] = {
                    "detected_action": remote_result.action,
                    "confidence": remote_result.confidence,
                    "top_actions": sorted(
                        remote_result.all_scores.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5],
                    "all_scores": remote_result.all_scores,
                }

                logger.debug(
                    f"Action recognition (via service): {remote_result.action} "
                    f"({remote_result.confidence:.0%} confidence, "
                    f"suspicious={remote_result.is_suspicious})",
                    extra={
                        "service": "action-via-service",
                        "camera_id": camera_id,
                        "duration_ms": int(duration * 1000),
                    },
                )
                return result

            return None

        except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
            observe_enrichment_model_duration(
                "action-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("action-via-service")
            logger.warning(
                "Enrichment service unavailable for action recognition",
                extra={
                    "service": "action-via-service",
                    "error_type": type(e).__name__,
                    "camera_id": camera_id,
                },
            )
            return None
        except httpx.HTTPStatusError as e:
            observe_enrichment_model_duration(
                "action-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("action-via-service")
            status_code = e.response.status_code
            if 400 <= status_code < 500:
                logger.error(
                    f"Action recognition client error (HTTP {status_code})",
                    extra={
                        "service": "action-via-service",
                        "camera_id": camera_id,
                        "status_code": status_code,
                    },
                    exc_info=True,
                )
            else:
                logger.warning(
                    f"Action recognition server error (HTTP {status_code})",
                    extra={
                        "service": "action-via-service",
                        "camera_id": camera_id,
                        "status_code": status_code,
                    },
                )
            return None
        except (ValueError, KeyError, TypeError) as e:
            observe_enrichment_model_duration(
                "action-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("action-via-service")
            logger.error(
                "Action recognition parse error",
                extra={
                    "service": "action-via-service",
                    "error_type": type(e).__name__,
                    "camera_id": camera_id,
                },
                exc_info=True,
            )
            return None
        except Exception as e:
            observe_enrichment_model_duration(
                "action-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("action-via-service")
            logger.error(
                f"Action recognition unexpected error: {sanitize_error(e)}",
                extra={
                    "service": "action-via-service",
                    "error_type": type(e).__name__,
                    "camera_id": camera_id,
                },
                exc_info=True,
            )
            return None

    async def _detect_threats_via_service(
        self,
        image: Image.Image,
    ) -> ThreatDetectionResult | None:
        """Detect threats/weapons using the remote enrichment HTTP service.

        Routes to enrichment-light service (/threat-detect endpoint).
        Scans the full frame for weapons and threatening objects.

        Args:
            image: Full frame PIL Image to scan for threats

        Returns:
            ThreatDetectionResult or None if detection fails
        """
        client = self._get_enrichment_client()
        record_enrichment_model_call("threat-via-service")
        start_time = time.perf_counter()

        try:
            remote_result: Any | None = await client.detect_threats(image)

            duration = time.perf_counter() - start_time
            observe_enrichment_model_duration("threat-via-service", duration)

            if remote_result:
                # Convert remote ThreatDetectionClientResult to local ThreatDetectionResult
                threats = []
                for t in remote_result.threats_detected:
                    threat_class = t.get("class_name", t.get("type", "unknown"))
                    threats.append(
                        ThreatDetection(
                            class_name=threat_class,
                            confidence=t.get("confidence", 0.0),
                            bbox=tuple(t["bbox"]) if "bbox" in t else (0.0, 0.0, 0.0, 0.0),
                            is_high_priority=threat_class.lower()
                            in {
                                "gun",
                                "pistol",
                                "rifle",
                                "firearm",
                                "handgun",
                                "knife",
                                "machete",
                                "sword",
                            },
                        )
                    )

                result = ThreatDetectionResult(threats=threats)

                logger.info(
                    f"Threat detection (via service): "
                    f"has_threats={result.has_threats}, "
                    f"has_high_priority={result.has_high_priority}, "
                    f"count={len(threats)}",
                    extra={
                        "service": "threat-via-service",
                        "duration_ms": int(duration * 1000),
                        "threat_count": len(threats),
                    },
                )
                return result

            return None

        except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
            observe_enrichment_model_duration(
                "threat-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("threat-via-service")
            logger.warning(
                "Enrichment service unavailable for threat detection",
                extra={"service": "threat-via-service", "error_type": type(e).__name__},
            )
            return None
        except httpx.HTTPStatusError as e:
            observe_enrichment_model_duration(
                "threat-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("threat-via-service")
            status_code = e.response.status_code
            if 400 <= status_code < 500:
                logger.error(
                    f"Threat detection client error (HTTP {status_code})",
                    extra={"service": "threat-via-service", "status_code": status_code},
                    exc_info=True,
                )
            else:
                logger.warning(
                    f"Threat detection server error (HTTP {status_code})",
                    extra={"service": "threat-via-service", "status_code": status_code},
                )
            return None
        except (ValueError, KeyError, TypeError) as e:
            observe_enrichment_model_duration(
                "threat-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("threat-via-service")
            logger.error(
                "Threat detection parse error",
                extra={"service": "threat-via-service", "error_type": type(e).__name__},
                exc_info=True,
            )
            return None
        except Exception as e:
            observe_enrichment_model_duration(
                "threat-via-service", time.perf_counter() - start_time
            )
            record_enrichment_model_error("threat-via-service")
            logger.error(
                f"Threat detection unexpected error: {sanitize_error(e)}",
                extra={"service": "threat-via-service", "error_type": type(e).__name__},
                exc_info=True,
            )
            return None

    async def _analyze_demographics_via_service(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Analyze demographics using the remote enrichment HTTP service.

        Routes to the heavy enrichment service (/demographics endpoint).
        Extracts age and gender estimates for each person detection.

        Args:
            persons: List of person detections with bounding boxes
            image: Full frame image to crop persons from

        Returns:
            Tuple of (age_classifications, gender_classifications) dictionaries
            keyed by detection ID
        """
        age_results: dict[str, Any] = {}
        gender_results: dict[str, Any] = {}

        if not persons:
            return age_results, gender_results

        client = self._get_enrichment_client()
        record_enrichment_model_call("demographics-via-service")

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            start_time = time.perf_counter()

            try:
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result: Any | None = await client.analyze_demographics(
                    person_crop, bbox_tuple
                )

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("demographics-via-service", duration)

                if remote_result:
                    # Use SimpleNamespace so getattr/hasattr works in to_context_string()
                    from types import SimpleNamespace

                    is_minor = remote_result.age_range in (
                        "0-10",
                        "11-20",
                        "child",
                        "teenager",
                    )
                    age_results[det_id] = SimpleNamespace(
                        age_group=remote_result.age_range,
                        display_name=remote_result.age_range,
                        confidence=remote_result.age_confidence,
                        is_minor=is_minor,
                    )

                    gender_results[det_id] = SimpleNamespace(
                        gender=remote_result.gender,
                        confidence=remote_result.gender_confidence,
                    )

                    logger.debug(
                        f"Person {det_id} demographics (via service): "
                        f"age={remote_result.age_range} ({remote_result.age_confidence:.0%}), "
                        f"gender={remote_result.gender} ({remote_result.gender_confidence:.0%})",
                        extra={
                            "service": "demographics-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
                observe_enrichment_model_duration(
                    "demographics-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("demographics-via-service")
                logger.warning(
                    f"Enrichment service unavailable for demographics {det_id}",
                    extra={
                        "service": "demographics-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "demographics-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("demographics-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Demographics client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "demographics-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Demographics server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "demographics-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "demographics-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("demographics-via-service")
                logger.error(
                    f"Demographics parse error for {det_id}",
                    extra={
                        "service": "demographics-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "demographics-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("demographics-via-service")
                logger.error(
                    f"Demographics unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "demographics-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )

        return age_results, gender_results

    async def _compute_reid_via_service(
        self,
        detections: list[DetectionInput],
        image: Image.Image,
        result: EnrichmentResult,
    ) -> None:
        """Compute person re-ID embeddings using the remote enrichment HTTP service.

        Routes to enrichment-light service (/person-reid endpoint).
        Extracts OSNet embeddings for each person detection and stores
        them in the EnrichmentResult for downstream matching.

        Args:
            detections: List of detections to extract embeddings for
            image: Full frame image to crop persons from
            result: EnrichmentResult to populate with embeddings
        """
        client = self._get_enrichment_client()
        record_enrichment_model_call("reid-via-service")

        persons = [d for d in detections if d.class_name == PERSON_CLASS]

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)
            start_time = time.perf_counter()

            try:
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                # Call remote service
                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result: Any | None = await client.compute_reid_embedding(
                    person_crop, bbox_tuple
                )

                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("reid-via-service", duration)

                if remote_result and remote_result.embedding:
                    # Store the embedding in person_embeddings for context generation
                    result.person_embeddings[det_id] = {
                        "embedding": remote_result.embedding,
                        "embedding_dim": remote_result.embedding_dim,
                        "detection_id": det_id,
                    }

                    logger.debug(
                        f"Person {det_id} re-ID embedding (via service): "
                        f"dim={remote_result.embedding_dim}",
                        extra={
                            "service": "reid-via-service",
                            "detection_id": det_id,
                            "duration_ms": int(duration * 1000),
                        },
                    )

            except (httpx.ConnectError, httpx.TimeoutException, EnrichmentUnavailableError) as e:
                observe_enrichment_model_duration(
                    "reid-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("reid-via-service")
                logger.warning(
                    f"Enrichment service unavailable for re-ID {det_id}",
                    extra={
                        "service": "reid-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                )
            except httpx.HTTPStatusError as e:
                observe_enrichment_model_duration(
                    "reid-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("reid-via-service")
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    logger.error(
                        f"Re-ID client error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "reid-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                        exc_info=True,
                    )
                else:
                    logger.warning(
                        f"Re-ID server error for {det_id} (HTTP {status_code})",
                        extra={
                            "service": "reid-via-service",
                            "detection_id": det_id,
                            "status_code": status_code,
                        },
                    )
            except (ValueError, KeyError, TypeError) as e:
                observe_enrichment_model_duration(
                    "reid-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("reid-via-service")
                logger.error(
                    f"Re-ID parse error for {det_id}",
                    extra={
                        "service": "reid-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )
            except Exception as e:
                observe_enrichment_model_duration(
                    "reid-via-service", time.perf_counter() - start_time
                )
                record_enrichment_model_error("reid-via-service")
                logger.error(
                    f"Re-ID unexpected error for {det_id}: {sanitize_error(e)}",
                    extra={
                        "service": "reid-via-service",
                        "error_type": type(e).__name__,
                        "detection_id": det_id,
                    },
                    exc_info=True,
                )

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
            # NEM-5570: Cascade Level 1 — no detections, skip all enrichment
            record_cascade_skipped()
            logger.debug("Cascade: no detections, skipping all enrichment")
            return result

        # Get the shared image for full-frame analysis
        shared_image = images.get(None)
        if shared_image:
            pil_image = await self._load_image(shared_image)
        else:
            pil_image = None

        # NEM-5567: Zero-DCE++ low-light enhancement preprocessing
        # Conditionally enhance dark frames before all downstream enrichment models.
        # Only applied when the image brightness is below threshold (low-light).
        if pil_image and self.low_light_enhancement_enabled:
            pil_image = await self._maybe_enhance_low_light(pil_image)

        # Filter detections by confidence
        high_conf_detections = [d for d in detections if d.confidence >= self.min_confidence]

        if not high_conf_detections:
            # NEM-5570: Cascade — all detections below confidence threshold
            record_cascade_skipped()
            logger.debug(
                "Cascade: %d detections all below min_confidence=%.2f, skipping enrichment",
                len(detections),
                self.min_confidence,
            )
            return result

        # NEM-5570: Cascade — frame has qualifying detections, proceed with enrichment
        record_cascade_processed()

        # Run parallel enrichment pipeline (NEM-4234: Phase 4, NEM-5525 optimized)
        # This runs Phase 1 + Florence-2 concurrently, then Phase 2/3 dependents
        # Hard timeout ensures we don't blow the 90s batch window
        if pil_image:
            try:
                async with asyncio.timeout(self._pipeline_timeout):
                    await self._run_parallel_enrichment(
                        result=result,
                        pil_image=pil_image,
                        high_conf_detections=high_conf_detections,
                        images=images,
                        camera_id=camera_id,
                    )
            except TimeoutError:
                elapsed = (time.monotonic() - start_time) * 1000
                record_enrichment_pipeline_timeout()
                logger.warning(
                    f"Enrichment pipeline hard timeout after {self._pipeline_timeout}s "
                    f"({elapsed:.0f}ms elapsed), returning partial results",
                    extra={
                        "camera_id": camera_id or "unknown",
                        "timeout_seconds": self._pipeline_timeout,
                        "elapsed_ms": elapsed,
                        "error_count": len(result.errors),
                    },
                )
                result.errors.append(
                    f"pipeline_timeout: exceeded {self._pipeline_timeout}s hard limit"
                )

        # Handle quality change tracking (needs to happen after image_quality is set)
        if self.image_quality_enabled and result.image_quality and camera_id:
            previous = self._previous_quality_results.get(camera_id)
            change_detected, description = detect_quality_change(result.image_quality, previous)
            result.quality_change_detected = change_detected
            result.quality_change_description = description
            if change_detected:
                logger.warning(f"Camera {camera_id}: {description}")

            # Update tracking
            self._previous_quality_results[camera_id] = result.image_quality

            # Log if blur detected with person (possible running)
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if result.image_quality.is_blurry and persons:
                blur_context = interpret_blur_with_motion(result.image_quality, has_person=True)
                logger.info(f"Motion context: {blur_context}")

        result.processing_time_ms = (time.monotonic() - start_time) * 1000

        # NEM-3797: Add span event for enrichment pipeline complete
        add_span_event(
            "enrichment_pipeline.complete",
            {
                "parallel_execution": True,  # NEM-4234: Phase 4 marker
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
                "clip_scene_classification.available": result.has_clip_scene_classification,
                "clip_threat_matches.available": result.has_clip_threat_matches,
                "clip_anomaly_score.available": result.has_clip_anomaly_score,
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
            f"household_vehicles={len(result.vehicle_household_matches)}, "
            f"clip_scene={'yes' if result.has_clip_scene_classification else 'no'}, "
            f"clip_threats={'yes' if result.has_clip_threat_matches else 'no'}, "
            f"clip_anomaly={'yes' if result.has_clip_anomaly_score else 'no'} "
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
        async with self.model_manager.load("siglip2-base-patch16-224"):
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

                    # Cache the CLIP embedding for reuse by downstream services
                    # (NEM-5517/5518/5519: Embedding Caching)
                    result.clip_embeddings[det_id] = embedding

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
                            # Store with detection ID for context isolation (NEM-5512/5513/5514)
                            # Convert det_id to int for consistent keying
                            int_det_id = int(det_id) if det_id else i
                            result.person_household_matches[int_det_id] = match
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
                                # Store with detection ID for context isolation (NEM-5512/5513/5514)
                                vehicle_det_id = plate_result.source_detection_id
                                if vehicle_det_id is not None:
                                    result.vehicle_household_matches[vehicle_det_id] = match
                                logger.debug(
                                    "Vehicle matched by license plate",
                                    extra={
                                        "detection_id": vehicle_det_id,
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

    def _is_fast_alpr_available(self) -> bool:
        """Check if FastALPR is available in model zoo (NEM-5569).

        Returns True if the fast-alpr model is registered and enabled.
        Falls back to YOLO11 + PaddleOCR if not available.
        """
        try:
            from backend.services.model_zoo import get_model_config

            config = get_model_config("fast-alpr")
            return config is not None and config.enabled
        except Exception:
            return False

    async def _detect_plates_fast_alpr(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Detect license plates using FastALPR end-to-end (NEM-5569).

        FastALPR combines plate detection + OCR in a single pass (~28MB total),
        replacing the two-step YOLO11 (300MB) + PaddleOCR (100MB) pipeline.
        Results include text already populated, skipping the Phase 2 OCR step.

        Args:
            vehicles: List of vehicle detections
            images: Dictionary mapping detection IDs to images

        Returns:
            List of LicensePlateResult with text already populated
        """
        from backend.services.fast_alpr_loader import run_fast_alpr

        results: list[LicensePlateResult] = []

        try:
            async with self.model_manager.load("fast-alpr") as alpr:
                for vehicle in vehicles:
                    image = self._get_image_for_detection(vehicle, images)
                    if image is None:
                        continue

                    # Crop to vehicle bounding box
                    cropped = await self._crop_to_bbox(image, vehicle.bbox)
                    if cropped is None:
                        continue

                    # Run end-to-end detection + OCR
                    alpr_results = await run_fast_alpr(alpr, cropped)

                    for plate in alpr_results:
                        results.append(
                            LicensePlateResult(
                                bbox=BoundingBox(
                                    x1=plate.bbox[0],
                                    y1=plate.bbox[1],
                                    x2=plate.bbox[2],
                                    y2=plate.bbox[3],
                                ),
                                confidence=plate.detection_confidence,
                                text=plate.text,
                                ocr_confidence=plate.confidence,
                                source_detection_id=vehicle.id,
                            )
                        )

        except KeyError:
            logger.warning("fast-alpr model not available, falling back to YOLO11 + PaddleOCR")
            return await self._detect_license_plates(vehicles, images)
        except RuntimeError:
            logger.warning("FastALPR error, falling back to YOLO11 + PaddleOCR", exc_info=True)
            return await self._detect_license_plates(vehicles, images)

        if results:
            logger.info(
                f"FastALPR: detected {len(results)} plates with text in {len(vehicles)} vehicles"
            )
        return results

    async def _detect_license_plates(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Detect license plates in vehicle detections (legacy YOLO11 path).

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

            loop = asyncio.get_running_loop()
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
                loop = asyncio.get_running_loop()
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

            loop = asyncio.get_running_loop()
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
            loop = asyncio.get_running_loop()
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
            loop = asyncio.get_running_loop()
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
            loop = asyncio.get_running_loop()

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

    async def _maybe_enhance_low_light(self, image: Image.Image) -> Image.Image:
        """Conditionally enhance a low-light image using Zero-DCE++.

        Only applies enhancement when the image brightness is below the
        low-light threshold. Bright images are returned unchanged to avoid
        degradation and wasted compute.

        Args:
            image: PIL Image to potentially enhance

        Returns:
            Enhanced image if low-light, original image otherwise
        """
        try:
            if not zero_dce_should_enhance(image):
                return image

            async with self.model_manager.load("zero-dce-plus-plus") as model_data:
                record_enrichment_model_call("zero-dce-plus-plus")
                start_time = time.perf_counter()
                enhanced = await zero_dce_enhance(model_data, image)
                duration = time.perf_counter() - start_time
                observe_enrichment_model_duration("zero-dce-plus-plus", duration)
                logger.debug("Low-light enhancement applied (%.1fms)", duration * 1000)
                return enhanced
        except Exception:
            logger.debug("Zero-DCE++ enhancement skipped (model unavailable or error)")
            return image

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
