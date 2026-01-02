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

import base64
import io
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx

from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import observe_ai_request_duration, record_pipeline_error

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Timeout configuration for Enrichment service
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for response (30s for model inference)
ENRICHMENT_CONNECT_TIMEOUT = 10.0
ENRICHMENT_READ_TIMEOUT = 30.0
ENRICHMENT_HEALTH_TIMEOUT = 5.0

# Default Enrichment service URL
DEFAULT_ENRICHMENT_URL = "http://ai-enrichment:8094"


class EnrichmentUnavailableError(Exception):
    """Raised when the Enrichment service is unavailable.

    This exception is raised when the Enrichment service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.
    """

    def __init__(self, message: str, original_error: Exception | None = None):
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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


@dataclass
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

        # Use httpx.Timeout for proper timeout configuration
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=ENRICHMENT_READ_TIMEOUT,
            write=ENRICHMENT_READ_TIMEOUT,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        logger.info(f"EnrichmentClient initialized with base_url={self._base_url}")

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

    async def check_health(self) -> dict[str, Any]:
        """Check if Enrichment service is healthy and get model status.

        Returns:
            Dictionary with health status and model information
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                response = await client.get(f"{self._base_url}/health")
                response.raise_for_status()
                return cast("dict[str, Any]", response.json())
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Enrichment health check failed: {e}", exc_info=True)
            return {"status": "unavailable", "error": str(e)}
        except httpx.HTTPStatusError as e:
            logger.warning(f"Enrichment health check returned error status: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(
                f"Unexpected error during Enrichment health check: {sanitize_error(e)}",
                exc_info=True,
            )
            return {"status": "error", "error": str(e)}

    async def is_healthy(self) -> bool:
        """Check if Enrichment service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        health = await self.check_health()
        return health.get("status") in ("healthy", "degraded")

    async def classify_vehicle(
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> VehicleClassificationResult | None:
        """Classify vehicle type from an image.

        Args:
            image: PIL Image containing vehicle
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            VehicleClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "vehicle-classify"

        logger.debug("Sending vehicle classification request")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {"image": image_b64}
            if bbox:
                payload["bbox"] = list(bbox)

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_vehicle", ai_duration)

            # Parse response
            result = response.json()

            return VehicleClassificationResult(
                vehicle_type=result["vehicle_type"],
                display_name=result["display_name"],
                confidence=result["confidence"],
                is_commercial=result["is_commercial"],
                all_scores=result["all_scores"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_vehicle_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_vehicle_timeout")
            logger.error(
                f"Enrichment vehicle request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment vehicle request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_vehicle_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_vehicle_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_vehicle_unexpected_error")
            logger.error(
                f"Unexpected error during vehicle classification: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during vehicle classification: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def classify_pet(
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> PetClassificationResult | None:
        """Classify pet type (cat/dog) from an image.

        Args:
            image: PIL Image containing pet
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            PetClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "pet-classify"

        logger.debug("Sending pet classification request")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {"image": image_b64}
            if bbox:
                payload["bbox"] = list(bbox)

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_pet", ai_duration)

            # Parse response
            result = response.json()

            return PetClassificationResult(
                pet_type=result["pet_type"],
                breed=result["breed"],
                confidence=result["confidence"],
                is_household_pet=result["is_household_pet"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pet_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pet_timeout")
            logger.error(
                f"Enrichment pet request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment pet request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_pet_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_pet_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pet_unexpected_error")
            logger.error(
                f"Unexpected error during pet classification: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during pet classification: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def classify_clothing(
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> ClothingClassificationResult | None:
        """Classify clothing attributes from a person image using FashionCLIP.

        Args:
            image: PIL Image containing person
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before classification

        Returns:
            ClothingClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "clothing-classify"

        logger.debug("Sending clothing classification request")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {"image": image_b64}
            if bbox:
                payload["bbox"] = list(bbox)

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_clothing", ai_duration)

            # Parse response
            result = response.json()

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

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_clothing_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_clothing_timeout")
            logger.error(
                f"Enrichment clothing request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment clothing request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_clothing_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_clothing_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_clothing_unexpected_error")
            logger.error(
                f"Unexpected error during clothing classification: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during clothing classification: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def estimate_depth(
        self,
        image: Image.Image,
    ) -> DepthEstimationResult | None:
        """Estimate depth map for an image using Depth Anything V2.

        Args:
            image: PIL Image to estimate depth for

        Returns:
            DepthEstimationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "depth-estimate"

        logger.debug("Sending depth estimation request")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {"image": image_b64}

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_depth", ai_duration)

            # Parse response
            result = response.json()

            return DepthEstimationResult(
                depth_map_base64=result["depth_map_base64"],
                min_depth=result["min_depth"],
                max_depth=result["max_depth"],
                mean_depth=result["mean_depth"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_depth_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_depth_timeout")
            logger.error(
                f"Enrichment depth request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment depth request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_depth_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_depth_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_depth_unexpected_error")
            logger.error(
                f"Unexpected error during depth estimation: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during depth estimation: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def estimate_object_distance(
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float],
        method: str = "center",
    ) -> ObjectDistanceResult | None:
        """Estimate distance to an object within a bounding box.

        Args:
            image: PIL Image
            bbox: Bounding box (x1, y1, x2, y2) of object to measure
            method: Depth sampling method ('center', 'mean', 'median', 'min')

        Returns:
            ObjectDistanceResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "object-distance"

        logger.debug(f"Sending object distance request with method={method}")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {
                "image": image_b64,
                "bbox": list(bbox),
                "method": method,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_distance", ai_duration)

            # Parse response
            result = response.json()

            return ObjectDistanceResult(
                estimated_distance_m=result["estimated_distance_m"],
                relative_depth=result["relative_depth"],
                proximity_label=result["proximity_label"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_distance_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_distance_timeout")
            logger.error(
                f"Enrichment distance request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment distance request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_distance_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_distance_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_distance_unexpected_error")
            logger.error(
                f"Unexpected error during distance estimation: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during distance estimation: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def analyze_pose(
        self,
        image: Image.Image,
        bbox: tuple[float, float, float, float] | None = None,
        min_confidence: float = 0.3,
    ) -> PoseAnalysisResult | None:
        """Analyze human pose keypoints from an image using ViTPose.

        Args:
            image: PIL Image containing person
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before analysis
            min_confidence: Minimum confidence threshold for keypoints (0-1)

        Returns:
            PoseAnalysisResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "pose-analyze"

        logger.debug("Sending pose analysis request")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload: dict[str, Any] = {
                "image": image_b64,
                "min_confidence": min_confidence,
            }
            if bbox:
                payload["bbox"] = list(bbox)

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
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

            return PoseAnalysisResult(
                keypoints=keypoints,
                posture=result["posture"],
                alerts=result["alerts"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pose_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pose_timeout")
            logger.error(
                f"Enrichment pose request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment pose request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_pose_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_pose_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_pose_unexpected_error")
            logger.error(
                f"Unexpected error during pose analysis: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during pose analysis: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def classify_action(
        self,
        frames: list[Image.Image],
        labels: list[str] | None = None,
    ) -> ActionClassificationResult | None:
        """Classify action from a sequence of video frames using X-CLIP.

        X-CLIP analyzes temporal patterns across frames to detect security-relevant
        actions like loitering, running away, or suspicious behavior.

        Args:
            frames: List of PIL Images representing video frames (8 is optimal)
            labels: Optional custom action labels (defaults to security-focused prompts)

        Returns:
            ActionClassificationResult or None on error

        Raises:
            EnrichmentUnavailableError: If the service is unavailable
        """
        start_time = time.time()
        endpoint = "action-classify"

        logger.debug(f"Sending action classification request with {len(frames)} frames")

        try:
            # Encode all frames to base64
            frames_b64 = [self._encode_image_to_base64(frame) for frame in frames]

            # Build request payload
            payload: dict[str, Any] = {"frames": frames_b64}
            if labels:
                payload["labels"] = labels

            # Track AI request time
            ai_start_time = time.time()

            # Send to Enrichment service (longer timeout for multi-frame processing)
            action_timeout = httpx.Timeout(
                connect=self._timeout.connect,
                read=60.0,  # Longer timeout for video processing
                write=self._timeout.write,
                pool=self._timeout.pool,
            )
            async with httpx.AsyncClient(timeout=action_timeout) as client:
                response = await client.post(
                    f"{self._base_url}/{endpoint}",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("enrichment_action", ai_duration)

            # Parse response
            result = response.json()

            return ActionClassificationResult(
                action=result["action"],
                confidence=result["confidence"],
                is_suspicious=result["is_suspicious"],
                risk_weight=result["risk_weight"],
                all_scores=result["all_scores"],
                inference_time_ms=result["inference_time_ms"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_action_connection_error")
            logger.error(
                f"Failed to connect to Enrichment service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Failed to connect to Enrichment service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_action_timeout")
            logger.error(
                f"Enrichment action request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Enrichment action request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                record_pipeline_error("enrichment_action_server_error")
                logger.error(
                    f"Enrichment returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise EnrichmentUnavailableError(
                    f"Enrichment returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors - don't retry
            record_pipeline_error("enrichment_action_client_error")
            logger.error(
                f"Enrichment returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return None

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("enrichment_action_unexpected_error")
            logger.error(
                f"Unexpected error during action classification: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise EnrichmentUnavailableError(
                f"Unexpected error during action classification: {sanitize_error(e)}",
                original_error=e,
            ) from e


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


def reset_enrichment_client() -> None:
    """Reset the global EnrichmentClient instance (for testing)."""
    global _enrichment_client  # noqa: PLW0603
    _enrichment_client = None
