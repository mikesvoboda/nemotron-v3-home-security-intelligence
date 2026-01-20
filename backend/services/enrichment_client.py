"""Combined Enrichment HTTP client service for classification endpoints.

This service provides an HTTP client interface to the ai-enrichment service,
which hosts vehicle classification, pet classification, clothing classification,
depth estimation, and pose analysis models in a single container.

The ai-enrichment service runs at http://ai-enrichment:8094 and provides:
- /vehicle-classify: Vehicle type and color classification
- /pet-classify: Cat/dog classification
- /clothing-classify: FashionCLIP clothing attribute extraction
- /depth-estimate: Depth Anything V2 monocular depth estimation
- /object-distance: Object distance estimation from depth map
- /pose-analyze: ViTPose+ human pose keypoint detection
- /action-classify: X-CLIP temporal action recognition

Error Handling:
    - Connection errors: Raise EnrichmentUnavailableError (allows retry)
    - Timeouts: Raise EnrichmentUnavailableError (allows retry)
    - HTTP 5xx errors: Raise EnrichmentUnavailableError (allows retry)
    - HTTP 4xx errors: Log and return None (client error, no retry)
    - Invalid JSON: Log and return None (malformed response)
"""

from __future__ import annotations

import asyncio
import base64
import io
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx

from backend.core.config import get_settings
from backend.core.exceptions import EnrichmentUnavailableError
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    increment_enrichment_retry,
    observe_ai_request_duration,
    record_pipeline_error,
)
from backend.services.bbox_validation import is_valid_bbox, validate_and_clamp_bbox
from backend.services.circuit_breaker import CircuitBreaker, CircuitState

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Timeout configuration for Enrichment service
# Note: These defaults are used as fallbacks. Production code uses Settings values:
# - settings.ai_connect_timeout: Maximum time to establish connection (default: 10s)
# - settings.enrichment_read_timeout: Maximum time to wait for response (default: 60s)
# - settings.ai_health_timeout: Health check timeout (default: 5s)
ENRICHMENT_CONNECT_TIMEOUT = 10.0  # Fallback, use settings.ai_connect_timeout
ENRICHMENT_READ_TIMEOUT = 60.0  # Fallback, use settings.enrichment_read_timeout (was 30s, now 60s)
ENRICHMENT_HEALTH_TIMEOUT = 5.0  # Fallback, use settings.ai_health_timeout

# Default Enrichment service URL
DEFAULT_ENRICHMENT_URL = "http://ai-enrichment:8094"


@dataclass(slots=True)
class VehicleClassificationResult:
    """Result from vehicle segment classification.

    Attributes:
        vehicle_type: Classified vehicle type (e.g., "pickup_truck")
        display_name: Human-readable vehicle type description
        confidence: Classification confidence (0-1)
        is_commercial: Whether the vehicle is a commercial/delivery type
        all_scores: Dictionary of all class scores (top 3)
        inference_time_ms: Inference time in milliseconds
    """

    vehicle_type: str
    display_name: str
    confidence: float
    is_commercial: bool
    all_scores: dict[str, float]
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vehicle_type": self.vehicle_type,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "is_commercial": self.is_commercial,
            "all_scores": self.all_scores,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable vehicle type description for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        base = f"Vehicle type: {self.display_name} ({conf_str} confidence)"
        if self.is_commercial:
            base += " [Commercial/delivery vehicle]"
        return base


@dataclass(slots=True)
class PetClassificationResult:
    """Result from pet classification.

    Attributes:
        pet_type: Classified pet type ("cat" or "dog")
        breed: Pet breed (if available)
        confidence: Classification confidence (0-1)
        is_household_pet: Always True for this classifier
        inference_time_ms: Inference time in milliseconds
    """

    pet_type: str
    breed: str
    confidence: float
    is_household_pet: bool
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pet_type": self.pet_type,
            "breed": self.breed,
            "confidence": self.confidence,
            "is_household_pet": self.is_household_pet,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable pet classification for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        return f"Household pet detected: {self.pet_type} ({conf_str} confidence)"


@dataclass(slots=True)
class ClothingClassificationResult:
    """Result from clothing classification.

    Attributes:
        clothing_type: Primary clothing type (hoodie, vest, uniform, etc.)
        color: Primary color
        style: Overall style classification
        confidence: Confidence score (0-1)
        top_category: Top matched category from prompts
        description: Human-readable description
        is_suspicious: Whether clothing is potentially suspicious
        is_service_uniform: Whether clothing is a service uniform
        inference_time_ms: Inference time in milliseconds
    """

    clothing_type: str
    color: str
    style: str
    confidence: float
    top_category: str
    description: str
    is_suspicious: bool
    is_service_uniform: bool
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "clothing_type": self.clothing_type,
            "color": self.color,
            "style": self.style,
            "confidence": self.confidence,
            "top_category": self.top_category,
            "description": self.description,
            "is_suspicious": self.is_suspicious,
            "is_service_uniform": self.is_service_uniform,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable clothing description for Nemotron context
        """
        lines = [f"Clothing: {self.description}"]

        if self.is_suspicious:
            lines.append("  [ALERT: Potentially suspicious attire detected]")
        elif self.is_service_uniform:
            lines.append("  [Service/delivery worker uniform detected]")

        lines.append(f"  Confidence: {self.confidence:.1%}")
        return "\n".join(lines)


@dataclass(slots=True)
class DepthEstimationResult:
    """Result from depth estimation.

    Attributes:
        depth_map_base64: Base64 encoded PNG depth map visualization
        min_depth: Minimum depth value (normalized 0-1)
        max_depth: Maximum depth value (normalized 0-1)
        mean_depth: Mean depth value across the image
        inference_time_ms: Inference time in milliseconds
    """

    depth_map_base64: str
    min_depth: float
    max_depth: float
    mean_depth: float
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "depth_map_base64": self.depth_map_base64,
            "min_depth": self.min_depth,
            "max_depth": self.max_depth,
            "mean_depth": self.mean_depth,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable depth statistics for Nemotron context
        """
        return f"Scene depth: avg={self.mean_depth:.2f} (min={self.min_depth:.2f}, max={self.max_depth:.2f})"


@dataclass(slots=True)
class ObjectDistanceResult:
    """Result from object distance estimation.

    Attributes:
        estimated_distance_m: Estimated distance in meters (approximate)
        relative_depth: Normalized depth value (0=close, 1=far)
        proximity_label: Human-readable proximity description
        inference_time_ms: Inference time in milliseconds
    """

    estimated_distance_m: float
    relative_depth: float
    proximity_label: str
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "estimated_distance_m": self.estimated_distance_m,
            "relative_depth": self.relative_depth,
            "proximity_label": self.proximity_label,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable distance for Nemotron context
        """
        return f"Object distance: ~{self.estimated_distance_m:.1f}m ({self.proximity_label})"

    def is_close(self) -> bool:
        """Check if the object is considered close.

        Returns:
            True if object is very close or close
        """
        return self.proximity_label in ("very close", "close")


@dataclass(slots=True)
class ActionClassificationResult:
    """Result from X-CLIP action classification.

    Attributes:
        action: Detected action (e.g., "a person loitering")
        confidence: Classification confidence (0-1)
        is_suspicious: Whether action is considered suspicious
        risk_weight: Risk weight (0-1) for security assessment
        all_scores: Dictionary of top action scores
        inference_time_ms: Inference time in milliseconds
    """

    action: str
    confidence: float
    is_suspicious: bool
    risk_weight: float
    all_scores: dict[str, float]
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "confidence": self.confidence,
            "is_suspicious": self.is_suspicious,
            "risk_weight": self.risk_weight,
            "all_scores": self.all_scores,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable action description for Nemotron context
        """
        lines = [f"Detected action: {self.action}"]

        if self.is_suspicious:
            lines.append(
                f"  [ALERT: Suspicious behavior detected - risk weight {self.risk_weight:.0%}]"
            )
        else:
            lines.append(f"  Risk weight: {self.risk_weight:.0%}")

        lines.append(f"  Confidence: {self.confidence:.1%}")
        return "\n".join(lines)

    def has_security_alerts(self) -> bool:
        """Check if the action classification indicates a security concern.

        Returns:
            True if the action is suspicious or has high risk weight
        """
        return self.is_suspicious or self.risk_weight >= 0.7


@dataclass(slots=True)
class KeypointData:
    """A single pose keypoint with normalized coordinates.

    Attributes:
        name: Keypoint name (e.g., 'nose', 'left_shoulder')
        x: Normalized X coordinate (0-1)
        y: Normalized Y coordinate (0-1)
        confidence: Detection confidence (0-1)
    """

    name: str
    x: float
    y: float
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
        }


# =============================================================================
# New Unified Enrichment Result Types (for /enrich endpoint)
# =============================================================================


@dataclass(slots=True)
class UnifiedPoseResult:
    """Pose estimation result from the unified /enrich endpoint.

    Attributes:
        keypoints: List of keypoint dictionaries with x, y, confidence
        pose_class: Classified pose (standing, crouching, bending_over, arms_raised, etc.)
        confidence: Overall pose detection confidence (0-1)
        is_suspicious: Whether the pose is considered suspicious for security
    """

    keypoints: list[dict[str, Any]]
    pose_class: str
    confidence: float
    is_suspicious: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "keypoints": self.keypoints,
            "pose_class": self.pose_class,
            "confidence": self.confidence,
            "is_suspicious": self.is_suspicious,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        lines = [f"Pose: {self.pose_class} (confidence: {self.confidence:.0%})"]
        if self.is_suspicious:
            lines.append("  [ALERT: Suspicious posture detected]")
        return "\n".join(lines)


@dataclass(slots=True)
class UnifiedClothingResult:
    """Clothing analysis result from the unified /enrich endpoint.

    Attributes:
        categories: List of clothing category matches with confidence scores
        is_suspicious: Whether clothing indicates suspicious attire
    """

    categories: list[dict[str, Any]]
    is_suspicious: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "categories": self.categories,
            "is_suspicious": self.is_suspicious,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        if not self.categories:
            return "Clothing: No classification available"
        top = self.categories[0] if self.categories else {}
        lines = [
            f"Clothing: {top.get('category', 'unknown')} (confidence: {top.get('confidence', 0):.0%})"
        ]
        if self.is_suspicious:
            lines.append("  [ALERT: Potentially suspicious attire]")
        return "\n".join(lines)


@dataclass(slots=True)
class UnifiedDemographicsResult:
    """Demographics result from the unified /enrich endpoint.

    Attributes:
        age_range: Estimated age range (e.g., "25-35", "child", "senior")
        age_confidence: Confidence in age estimation (0-1)
        gender: Estimated gender ("male", "female", "unknown")
        gender_confidence: Confidence in gender estimation (0-1)
    """

    age_range: str
    age_confidence: float
    gender: str
    gender_confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "age_range": self.age_range,
            "age_confidence": self.age_confidence,
            "gender": self.gender,
            "gender_confidence": self.gender_confidence,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        return (
            f"Demographics: {self.gender} ({self.gender_confidence:.0%}), "
            f"age {self.age_range} ({self.age_confidence:.0%})"
        )


@dataclass(slots=True)
class UnifiedVehicleResult:
    """Vehicle analysis result from the unified /enrich endpoint.

    Attributes:
        make: Vehicle make (e.g., "Toyota", "Ford") or None if unknown
        model: Vehicle model (e.g., "Camry", "F-150") or None if unknown
        color: Vehicle color (e.g., "red", "black")
        type: Vehicle type (e.g., "sedan", "pickup_truck", "suv")
        confidence: Classification confidence (0-1)
    """

    make: str | None
    model: str | None
    color: str | None
    type: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "make": self.make,
            "model": self.model,
            "color": self.color,
            "type": self.type,
            "confidence": self.confidence,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        parts = []
        if self.color:
            parts.append(self.color)
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        parts.append(self.type)
        return f"Vehicle: {' '.join(parts)} (confidence: {self.confidence:.0%})"


@dataclass(slots=True)
class UnifiedThreatResult:
    """Threat detection result from the unified /enrich endpoint.

    Attributes:
        threats: List of detected threats with type, confidence, and bbox
        has_threat: Whether any threat was detected
        max_severity: Maximum severity level ("none", "low", "medium", "high", "critical")
    """

    threats: list[dict[str, Any]]
    has_threat: bool
    max_severity: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "threats": self.threats,
            "has_threat": self.has_threat,
            "max_severity": self.max_severity,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        if not self.has_threat:
            return "Threat detection: No threats detected"
        threat_types = [t.get("type", "unknown") for t in self.threats]
        return f"THREAT DETECTED: {', '.join(threat_types)} (severity: {self.max_severity})"


@dataclass(slots=True)
class UnifiedEnrichmentResult:
    """Unified result from the /enrich endpoint containing all enrichment types.

    This result contains optional fields for each enrichment type. Only fields
    that are relevant to the detection type will be populated.

    Attributes:
        pose: Pose estimation result (for person detections)
        clothing: Clothing analysis result (for person detections)
        demographics: Demographics result (when face is visible)
        vehicle: Vehicle analysis result (for vehicle detections)
        pet: Pet classification result (for animal detections)
        threat: Threat detection result (for person detections)
        reid_embedding: Re-identification embedding vector (for person detections)
        action: Action recognition result (when frames buffer provided)
        depth: Depth estimation result (for proximity analysis)
        models_loaded: List of models that were loaded for this request
        inference_time_ms: Total inference time in milliseconds
    """

    pose: UnifiedPoseResult | None = None
    clothing: UnifiedClothingResult | None = None
    demographics: UnifiedDemographicsResult | None = None
    vehicle: UnifiedVehicleResult | None = None
    pet: dict[str, Any] | None = None
    threat: UnifiedThreatResult | None = None
    reid_embedding: list[float] | None = None
    action: dict[str, Any] | None = None
    depth: dict[str, Any] | None = None
    models_loaded: list[str] | None = None
    inference_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {}
        if self.pose:
            result["pose"] = self.pose.to_dict()
        if self.clothing:
            result["clothing"] = self.clothing.to_dict()
        if self.demographics:
            result["demographics"] = self.demographics.to_dict()
        if self.vehicle:
            result["vehicle"] = self.vehicle.to_dict()
        if self.pet:
            result["pet"] = self.pet
        if self.threat:
            result["threat"] = self.threat.to_dict()
        if self.reid_embedding:
            result["reid_embedding"] = self.reid_embedding
        if self.action:
            result["action"] = self.action
        if self.depth:
            result["depth"] = self.depth
        if self.models_loaded:
            result["models_loaded"] = self.models_loaded
        result["inference_time_ms"] = self.inference_time_ms
        return result

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt."""
        lines = []
        if self.threat and self.threat.has_threat:
            lines.append(self.threat.to_context_string())
        if self.pose:
            lines.append(self.pose.to_context_string())
        if self.demographics:
            lines.append(self.demographics.to_context_string())
        if self.clothing:
            lines.append(self.clothing.to_context_string())
        if self.vehicle:
            lines.append(self.vehicle.to_context_string())
        if self.action:
            action_str = self.action.get("top_action", "unknown")
            conf = self.action.get("confidence", 0)
            lines.append(f"Action: {action_str} (confidence: {conf:.0%})")
        return "\n".join(lines) if lines else "No enrichment data available"

    def has_security_alerts(self) -> bool:
        """Check if any security alerts are present.

        Returns:
            True if threats detected, suspicious pose, or suspicious clothing
        """
        if self.threat and self.threat.has_threat:
            return True
        if self.pose and self.pose.is_suspicious:
            return True
        return bool(self.clothing and self.clothing.is_suspicious)


@dataclass(slots=True)
class PoseAnalysisResult:
    """Result from ViTPose pose analysis.

    Attributes:
        keypoints: List of detected COCO 17 keypoints
        posture: Classified posture (standing, walking, sitting, crouching, lying_down, running, unknown)
        alerts: Security-relevant alerts (crouching, lying_down, hands_raised, fighting_stance)
        inference_time_ms: Inference time in milliseconds
    """

    keypoints: list[KeypointData]
    posture: str
    alerts: list[str]
    inference_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "keypoints": [kp.to_dict() for kp in self.keypoints],
            "posture": self.posture,
            "alerts": self.alerts,
            "inference_time_ms": self.inference_time_ms,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable pose description for Nemotron context
        """
        lines = [f"Person posture: {self.posture}"]

        if self.alerts:
            for alert in self.alerts:
                if alert == "crouching":
                    lines.append("  [ALERT: Person crouching - potential hiding/break-in]")
                elif alert == "lying_down":
                    lines.append("  [ALERT: Person lying down - possible medical emergency]")
                elif alert == "hands_raised":
                    lines.append("  [ALERT: Hands raised - possible surrender/robbery]")
                elif alert == "fighting_stance":
                    lines.append("  [ALERT: Fighting stance detected - potential aggression]")
                else:
                    lines.append(f"  [ALERT: {alert}]")

        lines.append(f"  Keypoints detected: {len(self.keypoints)}/17")
        return "\n".join(lines)

    def has_security_alerts(self) -> bool:
        """Check if the pose analysis has any security alerts.

        Returns:
            True if there are any security-relevant alerts
        """
        return len(self.alerts) > 0


class EnrichmentClient:
    """Client for interacting with combined enrichment classification service.

    This client handles communication with the external ai-enrichment service,
    including health checks, image submission, and response parsing.

    The enrichment service provides:
    - Vehicle type classification (ResNet-50)
    - Pet classification (ResNet-18 cat/dog)
    - Clothing classification (FashionCLIP)
    - Pose analysis (ViTPose+ Small)
    - Action classification (X-CLIP temporal video understanding)

    Usage:
        client = EnrichmentClient()

        # Check if service is healthy
        if await client.check_health():
            # Classify vehicle
            result = await client.classify_vehicle(image)

            # Classify pet
            pet = await client.classify_pet(animal_image)

            # Classify clothing
            clothing = await client.classify_clothing(person_image)

            # Analyze pose
            pose = await client.analyze_pose(person_image)

            # Classify action from video frames
            action = await client.classify_action(video_frames)
    """

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize Enrichment client with configuration.

        Args:
            base_url: Optional base URL for the Enrichment service.
                     Defaults to ENRICHMENT_URL setting or http://ai-enrichment:8094
        """
        settings = get_settings()

        # Use provided URL, or settings, or default
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        else:
            self._base_url = getattr(settings, "enrichment_url", DEFAULT_ENRICHMENT_URL).rstrip("/")

        # Use httpx.Timeout for proper timeout configuration from Settings (NEM-2524)
        # Read timeout from settings (configurable via ENRICHMENT_READ_TIMEOUT env var)
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.enrichment_read_timeout,
            write=settings.enrichment_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        # Initialize circuit breaker with configuration
        self._circuit_breaker = CircuitBreaker(
            name="enrichment",
            failure_threshold=settings.enrichment_cb_failure_threshold,
            recovery_timeout=settings.enrichment_cb_recovery_timeout,
            half_open_max_calls=settings.enrichment_cb_half_open_max_calls,
        )

        # Retry configuration for transient failures (NEM-1732)
        self._max_retries = settings.enrichment_max_retries

        # Create persistent HTTP connection pool (NEM-1721)
        # Reusing connections avoids TCP overhead and resource exhaustion
        self._http_client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._health_http_client = httpx.AsyncClient(
            timeout=self._health_timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        logger.info(f"EnrichmentClient initialized with base_url={self._base_url}")

    async def close(self) -> None:
        """Close the HTTP client connections.

        Should be called when the client is no longer needed to release resources.
        """
        await self._http_client.aclose()
        await self._health_http_client.aclose()
        logger.debug("EnrichmentClient HTTP connections closed")

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """Encode a PIL Image to base64 string.

        Args:
            image: PIL Image to encode

        Returns:
            Base64-encoded string of the image in PNG format
        """
        buffer = io.BytesIO()
        # Use PNG for lossless encoding
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def get_circuit_breaker_state(self) -> CircuitState:
        """Get current circuit breaker state.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        return self._circuit_breaker.get_state()

    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open.

        Returns:
            True if circuit is open (requests are being rejected), False otherwise
        """
        return self._circuit_breaker.get_state() == CircuitState.OPEN

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker to CLOSED state.

        This clears all failure counts and returns the circuit to normal operation.
        Use this after fixing underlying issues or for maintenance.
        """
        self._circuit_breaker.reset()

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Uses 2^attempt seconds as base delay with +/-10% jitter, capped at 30 seconds.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        # Exponential backoff: 2^attempt (1s, 2s, 4s, 8s, ...)
        base_delay: float = float(2**attempt)
        # Add jitter of +/-10% (not for crypto, just for backoff distribution)
        jitter: float = random.uniform(-0.1, 0.1)  # noqa: S311
        delay: float = base_delay * (1 + jitter)
        # Cap at 30 seconds
        return min(delay, 30.0)

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable.

        Transient errors that should trigger retry:
        - ConnectError: Network connectivity issues
        - TimeoutException: Request/response timeouts
        - HTTPStatusError with 5xx: Server-side errors

        Non-retryable errors (no retry):
        - HTTPStatusError with 4xx: Client errors (bad request)
        - Other exceptions: Unexpected/programming errors

        Args:
            error: The exception to check

        Returns:
            True if the error is retryable, False otherwise
        """
        if isinstance(error, httpx.ConnectError):
            return True
        if isinstance(error, httpx.TimeoutException):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return bool(error.response.status_code >= 500)
        return False

    async def check_health(self) -> dict[str, Any]:
        """Check if Enrichment service is healthy and get model status.

        Returns:
            Dictionary with health status, model information, and circuit breaker state
        """
        # Always include circuit breaker state in health response
        circuit_state = self._circuit_breaker.get_state().value

        try:
            # Use persistent HTTP client (NEM-1721)
            response = await self._health_http_client.get(f"{self._base_url}/health")
            response.raise_for_status()
            result = cast("dict[str, Any]", response.json())
            result["circuit_breaker_state"] = circuit_state
            return result
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Enrichment health check failed: {e}", exc_info=True)
            return {
                "status": "unavailable",
                "error": str(e),
                "circuit_breaker_state": circuit_state,
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"Enrichment health check returned error status: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "circuit_breaker_state": circuit_state}
        except Exception as e:
            logger.error(
                f"Unexpected error during Enrichment health check: {sanitize_error(e)}",
                exc_info=True,
            )
            return {"status": "error", "error": str(e), "circuit_breaker_state": circuit_state}

    async def is_healthy(self) -> bool:
        """Check if Enrichment service is healthy.

        Returns True only if the service is healthy/degraded AND circuit breaker is not open.

        Returns:
            True if service is healthy and circuit is not open, False otherwise
        """
        # If circuit is open, service is not healthy from client perspective
        if self.is_circuit_open():
            return False

        health = await self.check_health()
        return health.get("status") in ("healthy", "degraded")

    async def classify_vehicle(  # noqa: PLR0912
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> VehicleClassificationResult | None:
        """Classify vehicle type from an image.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image containing vehicle
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            VehicleClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "vehicle-classify"
        endpoint_name = "vehicle"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        logger.debug("Sending vehicle classification request")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = list(bbox)

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_vehicle", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return VehicleClassificationResult(
                    vehicle_type=result["vehicle_type"],
                    display_name=result["display_name"],
                    confidence=result["confidence"],
                    is_commercial=result["is_commercial"],
                    all_scores=result["all_scores"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_vehicle_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_vehicle_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_vehicle_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_vehicle_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_vehicle_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during vehicle classification: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during vehicle classification: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment vehicle classification failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def classify_pet(  # noqa: PLR0912
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> PetClassificationResult | None:
        """Classify pet type (cat/dog) from an image.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image containing pet
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            PetClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "pet-classify"
        endpoint_name = "pet"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        logger.debug("Sending pet classification request")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = list(bbox)

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_pet", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return PetClassificationResult(
                    pet_type=result["pet_type"],
                    breed=result["breed"],
                    confidence=result["confidence"],
                    is_household_pet=result["is_household_pet"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pet_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pet_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_pet_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pet_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_pet_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during pet classification: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during pet classification: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment pet classification failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def classify_clothing(  # noqa: PLR0912
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> ClothingClassificationResult | None:
        """Classify clothing attributes from a person image using FashionCLIP.

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image containing person
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            ClothingClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable or circuit is open
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "clothing-classify"
        endpoint_name = "clothing"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        logger.debug("Sending clothing classification request")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload
        payload: dict[str, Any] = {"image": image_b64}
        if bbox:
            payload["bbox"] = list(bbox)

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_clothing", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return ClothingClassificationResult(
                    clothing_type=result["clothing_type"],
                    color=result["color"],
                    style=result["style"],
                    confidence=result["confidence"],
                    top_category=result["top_category"],
                    description=result["description"],
                    is_suspicious=result["is_suspicious"],
                    is_service_uniform=result["is_service_uniform"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_clothing_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_clothing_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_clothing_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_clothing_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_clothing_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during clothing classification: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during clothing classification: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment clothing classification failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def estimate_depth(  # noqa: PLR0912
        self,
        image: Image.Image,
    ) -> DepthEstimationResult | None:
        """Estimate depth map for an image using Depth Anything V2.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image to estimate depth for

        Returns:
            DepthEstimationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "depth-estimate"
        endpoint_name = "depth"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        logger.debug("Sending depth estimation request")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload
        payload: dict[str, Any] = {"image": image_b64}

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_depth", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return DepthEstimationResult(
                    depth_map_base64=result["depth_map_base64"],
                    min_depth=result["min_depth"],
                    max_depth=result["max_depth"],
                    mean_depth=result["mean_depth"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_depth_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_depth_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_depth_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_depth_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_depth_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during depth estimation: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during depth estimation: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment depth estimation failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def estimate_object_distance(  # noqa: PLR0912
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float],
        method: str = "center",
    ) -> ObjectDistanceResult | None:
        """Estimate distance to an object within a bounding box.

        This method validates and clamps the bounding box to image boundaries
        before processing. Invalid bounding boxes (zero width/height, NaN values,
        inverted coordinates) will return None.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image
            bbox: Bounding box (x1, y1, x2, y2) of object to measure
            method: Depth sampling method ('center', 'mean', 'median', 'min')

        Returns:
            ObjectDistanceResult or None if bbox is invalid or on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "object-distance"
        endpoint_name = "distance"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        # Validate and clamp bounding box (NEM-1102, NEM-1122)
        image_width, image_height = image.size
        if not is_valid_bbox(bbox, allow_negative=True):
            logger.warning(
                f"Invalid bounding box for object distance estimation: {bbox}. "
                "Bounding box has invalid dimensions (zero width/height, NaN, or inverted)."
            )
            record_pipeline_error("enrichment_distance_invalid_bbox")
            return None

        validation_result = validate_and_clamp_bbox(bbox, image_width, image_height)
        if not validation_result.is_valid:
            logger.warning(
                f"Bounding box {bbox} is invalid after validation: {validation_result.warnings}. "
                f"Image size: {image_width}x{image_height}"
            )
            record_pipeline_error("enrichment_distance_bbox_outside_image")
            return None

        # Use clamped bbox for the request
        validated_bbox = validation_result.clamped_bbox
        if validation_result.was_clamped:
            logger.debug(
                f"Bounding box clamped from {bbox} to {validated_bbox} "
                f"for image size {image_width}x{image_height}"
            )

        logger.debug(f"Sending object distance request with method={method}")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload with validated bbox
        payload: dict[str, Any] = {
            "image": image_b64,
            "bbox": list(validated_bbox),  # type: ignore[arg-type]
            "method": method,
        }

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_distance", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return ObjectDistanceResult(
                    estimated_distance_m=result["estimated_distance_m"],
                    relative_depth=result["relative_depth"],
                    proximity_label=result["proximity_label"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_distance_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_distance_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_distance_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_distance_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_distance_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during distance estimation: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during distance estimation: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment distance estimation failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def analyze_pose(  # noqa: PLR0912
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
        min_confidence: float = 0.3,
    ) -> PoseAnalysisResult | None:
        """Analyze human pose keypoints from an image using ViTPose.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            image: PIL Image containing person
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before analysis
            min_confidence: Minimum confidence threshold for keypoints (0-1)

        Returns:
            PoseAnalysisResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "pose-analyze"
        endpoint_name = "pose"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        settings = get_settings()
        explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

        logger.debug("Sending pose analysis request")

        # Encode image to base64 (done once before retry loop)
        image_b64 = self._encode_image_to_base64(image)

        # Build request payload
        payload: dict[str, Any] = {
            "image": image_b64,
            "min_confidence": min_confidence,
        }
        if bbox:
            payload["bbox"] = list(bbox)

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_pose", ai_duration)

                # Parse response
                result = response.json()

                # Parse keypoints
                keypoints = [
                    KeypointData(
                        name=kp["name"],
                        x=kp["x"],
                        y=kp["y"],
                        confidence=kp["confidence"],
                    )
                    for kp in result["keypoints"]
                ]

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return PoseAnalysisResult(
                    keypoints=keypoints,
                    posture=result["posture"],
                    alerts=result["alerts"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pose_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pose_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_pose_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_pose_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_pose_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during pose analysis: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during pose analysis: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment pose analysis failed after {self._max_retries} retries",
            original_error=last_error,
        )

    async def classify_action(  # noqa: PLR0912
        self,
        frames: list[Image.Image],
        labels: list[str] | None = None,
    ) -> ActionClassificationResult | None:
        """Classify action from a sequence of video frames using X-CLIP.

        X-CLIP analyzes temporal patterns across frames to detect security-relevant
        actions like loitering, running away, or suspicious behavior.

        Includes retry logic with exponential backoff for transient failures
        (ConnectError, TimeoutException, HTTP 5xx).

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        Args:
            frames: List of PIL Images representing video frames (8 is optimal)
            labels: Optional custom action labels (defaults to security-focused prompts)

        Returns:
            ActionClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable after retries
        """
        # Check circuit breaker before making request
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("enrichment_circuit_open")
            raise EnrichmentUnavailableError(
                "Enrichment service circuit open - requests temporarily blocked"
            )

        start_time = time.time()
        endpoint = "action-classify"
        endpoint_name = "action"
        last_error: Exception | None = None
        # Explicit timeout as defense-in-depth (NEM-1465)
        # Use longer timeout for multi-frame video processing (60s read + connect timeout)
        settings = get_settings()
        action_read_timeout = 60.0  # Longer timeout for video processing
        explicit_timeout = action_read_timeout + settings.ai_connect_timeout

        logger.debug(f"Sending action classification request with {len(frames)} frames")

        # Encode all frames to base64 (done once before retry loop)
        frames_b64 = [self._encode_image_to_base64(frame) for frame in frames]

        # Build request payload
        payload: dict[str, Any] = {"frames": frames_b64}
        if labels:
            payload["labels"] = labels

        # Use longer timeout for multi-frame video processing (override default)
        action_timeout = httpx.Timeout(
            connect=self._timeout.connect,
            read=action_read_timeout,  # Longer timeout for video processing
            write=self._timeout.write,
            pool=self._timeout.pool,
        )

        # Retry loop with exponential backoff
        for attempt in range(self._max_retries):
            try:
                # Track AI request time
                ai_start_time = time.time()

                # Send to Enrichment service using persistent HTTP client (NEM-1721)
                # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                async with asyncio.timeout(explicit_timeout):
                    response = await self._http_client.post(
                        f"{self._base_url}/{endpoint}",
                        json=payload,
                        timeout=action_timeout,  # Override default timeout for this request
                    )
                    response.raise_for_status()

                # Record AI request duration
                ai_duration = time.time() - ai_start_time
                observe_ai_request_duration("enrichment_action", ai_duration)

                # Parse response
                result = response.json()

                # Record success with circuit breaker
                self._circuit_breaker.record_success()

                return ActionClassificationResult(
                    action=result["action"],
                    confidence=result["confidence"],
                    is_suspicious=result["is_suspicious"],
                    risk_weight=result["risk_weight"],
                    all_scores=result["all_scores"],
                    inference_time_ms=result["inference_time_ms"],
                )

            except httpx.HTTPStatusError as e:
                # Check if it's a client error (4xx) - don't retry
                if e.response.status_code < 500:
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_action_client_error")
                    logger.error(
                        f"Enrichment returned client error: {e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )
                    return None

                # Server error (5xx) - retry
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after server error {e.response.status_code}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_action_server_error")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment returned server error after {self._max_retries} retries: "
                        f"{e.response.status_code} - {e}",
                        extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
                        exc_info=True,
                    )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                error_type = "connection_error" if isinstance(e, httpx.ConnectError) else "timeout"

                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} retry {attempt + 1}/{self._max_retries}, "
                        f"waiting {delay:.1f}s after {error_type}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_metric = f"enrichment_action_{error_type}"
                    record_pipeline_error(error_metric)
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} failed after {self._max_retries} retries: {e}",
                        extra={"duration_ms": duration_ms},
                        exc_info=True,
                    )

            except TimeoutError as e:
                # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    increment_enrichment_retry(endpoint_name)
                    logger.warning(
                        f"Enrichment {endpoint_name} asyncio timeout "
                        f"(attempt {attempt + 1}/{self._max_retries}), "
                        f"waiting {delay:.1f}s: request timed out after {explicit_timeout}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    duration_ms = int((time.time() - start_time) * 1000)
                    record_pipeline_error("enrichment_action_asyncio_timeout")
                    self._circuit_breaker.record_failure()
                    logger.error(
                        f"Enrichment {endpoint_name} asyncio timeout after {self._max_retries} retries: "
                        f"request timed out after {explicit_timeout}s",
                        extra={"duration_ms": duration_ms, "explicit_timeout": explicit_timeout},
                        exc_info=True,
                    )

            except Exception as e:
                # Unexpected errors - don't retry
                duration_ms = int((time.time() - start_time) * 1000)
                record_pipeline_error("enrichment_action_unexpected_error")
                self._circuit_breaker.record_failure()
                logger.error(
                    f"Unexpected error during action classification: {sanitize_error(e)}",
                    extra={"duration_ms": duration_ms},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Unexpected error during action classification: {sanitize_error(e)}",
                    original_error=e,
                ) from e

        # All retries exhausted
        raise EnrichmentUnavailableError(
            f"Enrichment action classification failed after {self._max_retries} retries",
            original_error=last_error,
        )

    # =========================================================================
    # Unified Enrichment Endpoint Methods (NEM-3040)
    # =========================================================================

    def _parse_unified_response(self, data: dict[str, Any]) -> UnifiedEnrichmentResult:
        """Parse response from unified /enrich endpoint into typed result.

        Args:
            data: Raw JSON response from the enrichment service

        Returns:
            UnifiedEnrichmentResult with parsed typed fields
        """
        result = UnifiedEnrichmentResult(
            models_loaded=data.get("models_loaded"),
            inference_time_ms=data.get("inference_time_ms", 0.0),
        )

        # Parse pose result
        if data.get("pose"):
            pose_data = data["pose"]
            result.pose = UnifiedPoseResult(
                keypoints=pose_data.get("keypoints", []),
                pose_class=pose_data.get("pose_class", "unknown"),
                confidence=pose_data.get("confidence", 0.0),
                is_suspicious=pose_data.get("is_suspicious", False),
            )

        # Parse clothing result
        if data.get("clothing"):
            clothing_data = data["clothing"]
            result.clothing = UnifiedClothingResult(
                categories=clothing_data.get("categories", []),
                is_suspicious=clothing_data.get("is_suspicious", False),
            )

        # Parse demographics result
        if data.get("demographics"):
            demo_data = data["demographics"]
            result.demographics = UnifiedDemographicsResult(
                age_range=demo_data.get("age_range", "unknown"),
                age_confidence=demo_data.get("age_confidence", 0.0),
                gender=demo_data.get("gender", "unknown"),
                gender_confidence=demo_data.get("gender_confidence", 0.0),
            )

        # Parse vehicle result
        if data.get("vehicle"):
            vehicle_data = data["vehicle"]
            result.vehicle = UnifiedVehicleResult(
                make=vehicle_data.get("make"),
                model=vehicle_data.get("model"),
                color=vehicle_data.get("color"),
                type=vehicle_data.get("type", "unknown"),
                confidence=vehicle_data.get("confidence", 0.0),
            )

        # Parse threat result
        if data.get("threat"):
            threat_data = data["threat"]
            result.threat = UnifiedThreatResult(
                threats=threat_data.get("threats", []),
                has_threat=threat_data.get("has_threat", False),
                max_severity=threat_data.get("max_severity", "none"),
            )

        # Copy simple fields directly
        if data.get("reid_embedding"):
            result.reid_embedding = data["reid_embedding"]
        if data.get("pet"):
            result.pet = data["pet"]
        if data.get("action"):
            result.action = data["action"]
        if data.get("depth"):
            result.depth = data["depth"]

        return result

    async def enrich_detection(
        self,
        image: bytes,
        detection_type: str,
        bbox: tuple[float, float, float, float],
        frames: list[bytes] | None = None,
        options: dict[str, Any] | None = None,
    ) -> UnifiedEnrichmentResult:
        """Call unified /enrich endpoint for comprehensive detection enrichment.

        This method calls the new unified enrichment endpoint that automatically
        loads appropriate models based on detection type and returns all relevant
        enrichment data in a single request.

        Args:
            image: Raw image bytes (PNG or JPEG)
            detection_type: Type of detection ("person", "vehicle", "animal", "object")
            bbox: Bounding box as (x1, y1, x2, y2)
            frames: Optional list of frame bytes for action recognition
            options: Optional dictionary with additional options:
                - face_visible: bool - Whether a face is visible (enables demographics)
                - suspicious_score: float - Suspicion score 0-100 (enables action recognition)

        Returns:
            UnifiedEnrichmentResult with all applicable enrichment data

        Note:
            On timeout or error, returns an empty UnifiedEnrichmentResult rather than
            raising an exception, allowing the pipeline to continue with available data.
        """
        start_time = time.time()
        endpoint = "enrich"
        endpoint_name = "unified_enrich"

        logger.debug(f"Sending unified enrichment request for {detection_type}")

        try:
            # Build request payload
            payload: dict[str, Any] = {
                "image": base64.b64encode(image).decode("utf-8"),
                "detection_type": detection_type,
                "bbox": {
                    "x1": bbox[0],
                    "y1": bbox[1],
                    "x2": bbox[2],
                    "y2": bbox[3],
                },
                "frames": [base64.b64encode(f).decode("utf-8") for f in (frames or [])],
                "options": options or {},
            }

            # Get explicit timeout for defense-in-depth
            settings = get_settings()
            explicit_timeout = settings.enrichment_read_timeout + settings.ai_connect_timeout

            # Track AI request time
            ai_start_time = time.time()

            # Send request with explicit timeout
            async with asyncio.timeout(explicit_timeout):
                response = await self._http_client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_unified", ai_duration)

            # Parse response
            data = response.json()

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            return self._parse_unified_response(data)

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"Enrichment {endpoint_name} request timed out",
                extra={"duration_ms": duration_ms, "detection_type": detection_type},
            )
            return UnifiedEnrichmentResult()

        except TimeoutError:
            # asyncio.timeout() raises TimeoutError
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"Enrichment {endpoint_name} asyncio timeout",
                extra={"duration_ms": duration_ms, "detection_type": detection_type},
            )
            return UnifiedEnrichmentResult()

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Enrichment {endpoint_name} HTTP error: {e.response.status_code}",
                extra={"duration_ms": duration_ms, "status_code": e.response.status_code},
            )
            return UnifiedEnrichmentResult()

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"Enrichment {endpoint_name} connection error: {e}",
                extra={"duration_ms": duration_ms},
            )
            return UnifiedEnrichmentResult()

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Enrichment {endpoint_name} unexpected error: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            return UnifiedEnrichmentResult()

    async def get_model_status(self) -> dict[str, Any]:
        """Get current model loading status from the enrichment service.

        Returns:
            Dictionary with model status information:
            - loaded_models: List of currently loaded model names
            - vram_usage_mb: Current VRAM usage in MB
            - vram_budget_mb: Total VRAM budget in MB
            - model_specs: Dictionary of registered model specifications
        """
        try:
            response = await self._http_client.get(f"{self._base_url}/models/status")
            response.raise_for_status()
            return cast("dict[str, Any]", response.json())
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to get model status: HTTP {e.response.status_code}")
            return {"error": f"HTTP {e.response.status_code}", "loaded_models": []}
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Failed to get model status: {e}")
            return {"error": str(e), "loaded_models": []}
        except Exception as e:
            logger.error(f"Unexpected error getting model status: {sanitize_error(e)}")
            return {"error": str(e), "loaded_models": []}

    async def preload_model(self, model_name: str) -> bool:
        """Preload a specific model into GPU memory.

        This can be used to warm up models before they are needed,
        reducing latency for the first detection of a given type.

        Args:
            model_name: Name of the model to preload (e.g., "pose", "threat", "clothing")

        Returns:
            True if the model was successfully loaded, False otherwise
        """
        try:
            response = await self._http_client.post(
                f"{self._base_url}/models/preload",
                params={"model_name": model_name},
            )
            if response.status_code == 200:
                logger.info(f"Successfully preloaded model: {model_name}")
                return True
            else:
                logger.warning(f"Failed to preload model {model_name}: HTTP {response.status_code}")
                return False
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Failed to preload model {model_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error preloading model {model_name}: {sanitize_error(e)}")
            return False


# Global client instance
_enrichment_client: EnrichmentClient | None = None


def get_enrichment_client() -> EnrichmentClient:
    """Get or create the global EnrichmentClient instance.

    Returns:
        Global EnrichmentClient instance
    """
    global _enrichment_client  # noqa: PLW0603
    if _enrichment_client is None:
        _enrichment_client = EnrichmentClient()
    return _enrichment_client


async def reset_enrichment_client() -> None:
    """Reset the global EnrichmentClient instance (for testing).

    This async function properly closes HTTP connections before resetting.
    """
    global _enrichment_client  # noqa: PLW0603
    if _enrichment_client is not None:
        await _enrichment_client.close()
    _enrichment_client = None
