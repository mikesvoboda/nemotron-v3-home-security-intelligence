"""CLIP HTTP client service for embedding generation.

This service provides an HTTP client interface to the ai-clip service,
sending images for embedding generation using the CLIP ViT-L model.

The ai-clip service runs CLIP as a dedicated HTTP service at http://ai-clip:8093
to avoid loading the model on-demand in the backend, which improves VRAM management.

Embedding Flow:
    1. Encode image to base64
    2. POST to ai-clip service with image
    3. Parse JSON response with embedding
    4. Return 768-dimensional embedding vector

Error Handling:
    - Connection errors: Raise CLIPUnavailableError (allows retry)
    - Timeouts: Raise CLIPUnavailableError (allows retry)
    - HTTP 5xx errors: Raise CLIPUnavailableError (allows retry)
    - HTTP 4xx errors: Log and raise CLIPUnavailableError (client error)
    - Invalid JSON: Log and raise CLIPUnavailableError (malformed response)
"""

from __future__ import annotations

import base64
import io
import time
from typing import TYPE_CHECKING

import httpx

from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import observe_ai_request_duration, record_pipeline_error

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Timeout configuration for CLIP service
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for response (15s for embedding generation)
CLIP_CONNECT_TIMEOUT = 10.0
CLIP_READ_TIMEOUT = 15.0
CLIP_HEALTH_TIMEOUT = 5.0

# Default CLIP service URL
DEFAULT_CLIP_URL = "http://ai-clip:8093"

# CLIP ViT-L embedding dimension
EMBEDDING_DIMENSION = 768


class CLIPUnavailableError(Exception):
    """Raised when the CLIP service is unavailable.

    This exception is raised when the CLIP service cannot be reached due to:
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


class CLIPClient:
    """Client for interacting with CLIP embedding service.

    This client handles communication with the external ai-clip service,
    including health checks, image submission, and response parsing.

    The CLIP model generates 768-dimensional embeddings suitable for
    cosine similarity comparisons in re-identification tasks.

    Usage:
        client = CLIPClient()

        # Check if service is healthy
        if await client.check_health():
            # Generate embedding from image
            embedding = await client.embed(image)
            # embedding is a list of 768 floats
    """

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize CLIP client with configuration.

        Args:
            base_url: Optional base URL for the CLIP service.
                     Defaults to CLIP_URL setting or http://ai-clip:8093
        """
        settings = get_settings()

        # Use provided URL, or settings, or default
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        else:
            self._base_url = settings.clip_url.rstrip("/")

        # Use httpx.Timeout for proper timeout configuration
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=CLIP_READ_TIMEOUT,
            write=CLIP_READ_TIMEOUT,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        logger.info(f"CLIPClient initialized with base_url={self._base_url}")

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

    async def check_health(self) -> bool:
        """Check if CLIP service is healthy and reachable.

        Returns:
            True if CLIP service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                response = await client.get(f"{self._base_url}/health")
                response.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"CLIP health check failed: {e}", exc_info=True)
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"CLIP health check returned error status: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error during CLIP health check: {sanitize_error(e)}", exc_info=True
            )
            return False

    async def embed(self, image: Image.Image) -> list[float]:
        """Generate CLIP embedding from an image.

        Sends an image to the CLIP service and returns the 768-dimensional
        embedding vector suitable for cosine similarity comparisons.

        Args:
            image: PIL Image to generate embedding from

        Returns:
            768-dimensional embedding vector as list of floats

        Raises:
            CLIPUnavailableError: If the service is unavailable (connection, timeout, 5xx)
        """
        start_time = time.time()

        logger.debug("Sending embedding request to CLIP service...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/embed",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip", ai_duration)

            # Parse response
            result = response.json()

            if "embedding" not in result:
                logger.warning(f"Malformed response from CLIP (missing 'embedding'): {result}")
                record_pipeline_error("clip_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'embedding'"
                )

            embedding: list[float] = result["embedding"]

            # Validate embedding dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                logger.warning(
                    f"CLIP returned embedding with unexpected dimension: {len(embedding)} != {EMBEDDING_DIMENSION}"
                )
                record_pipeline_error("clip_invalid_dimension")
                raise CLIPUnavailableError(
                    f"CLIP returned embedding with invalid dimension: {len(embedding)}"
                )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.debug(f"CLIP embedding completed: {len(embedding)} dims in {duration_ms}ms")
            return embedding

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_connection_error")
            logger.error(
                f"Failed to connect to CLIP service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_timeout")
            logger.error(
                f"CLIP request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            # 5xx errors are server-side failures that should be retried
            if status_code >= 500:
                record_pipeline_error("clip_server_error")
                logger.error(
                    f"CLIP returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.)
            record_pipeline_error("clip_client_error")
            logger.error(
                f"CLIP returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP embedding: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP embedding: {sanitize_error(e)}",
                original_error=e,
            ) from e


# Global client instance
_clip_client: CLIPClient | None = None


def get_clip_client() -> CLIPClient:
    """Get or create the global CLIPClient instance.

    Returns:
        Global CLIPClient instance
    """
    global _clip_client  # noqa: PLW0603
    if _clip_client is None:
        _clip_client = CLIPClient()
    return _clip_client


def reset_clip_client() -> None:
    """Reset the global CLIPClient instance (for testing)."""
    global _clip_client  # noqa: PLW0603
    _clip_client = None
