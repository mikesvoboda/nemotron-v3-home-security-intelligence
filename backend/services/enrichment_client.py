"""Combined Enrichment HTTP client service for classification endpoints.

This service provides an HTTP client interface to the ai-enrichment service,
which hosts vehicle classification, pet classification, and clothing classification
models in a single container.

The ai-enrichment service runs at http://ai-enrichment:8094 and provides:
- /vehicle-classify: Vehicle type and color classification
- /pet-classify: Cat/dog classification
- /clothing-classify: FashionCLIP clothing attribute extraction

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


class EnrichmentClient:
    """Client for interacting with combined enrichment classification service.

    This client handles communication with the external ai-enrichment service,
    including health checks, image submission, and response parsing.

    The enrichment service provides:
    - Vehicle type classification (ResNet-50)
    - Pet classification (ResNet-18 cat/dog)
    - Clothing classification (FashionCLIP)

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
