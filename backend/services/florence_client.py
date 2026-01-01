"""Florence-2 HTTP client service for vision-language extraction.

This service provides an HTTP client interface to the ai-florence service,
sending images for attribute extraction using the Florence-2 vision-language model.

The ai-florence service runs Florence-2 as a dedicated HTTP service at http://ai-florence:8092
to avoid loading the model on-demand in the backend, which improves VRAM management.

Extraction Flow:
    1. Encode image to base64
    2. POST to ai-florence service with image and prompt
    3. Parse JSON response with extraction result
    4. Return extracted text

Error Handling:
    - Connection errors: Raise FlorenceUnavailableError (allows retry)
    - Timeouts: Raise FlorenceUnavailableError (allows retry)
    - HTTP 5xx errors: Raise FlorenceUnavailableError (allows retry)
    - HTTP 4xx errors: Log and return empty string (client error, no retry)
    - Invalid JSON: Log and return empty string (malformed response)
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

# Timeout configuration for Florence-2 service
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for response (30s for model inference)
FLORENCE_CONNECT_TIMEOUT = 10.0
FLORENCE_READ_TIMEOUT = 30.0
FLORENCE_HEALTH_TIMEOUT = 5.0

# Default Florence service URL
DEFAULT_FLORENCE_URL = "http://ai-florence:8092"


class FlorenceUnavailableError(Exception):
    """Raised when the Florence-2 service is unavailable.

    This exception is raised when the Florence service cannot be reached due to:
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


class FlorenceClient:
    """Client for interacting with Florence-2 vision-language service.

    This client handles communication with the external ai-florence service,
    including health checks, image submission, and response parsing.

    The Florence-2 model supports various vision-language tasks:
    - <CAPTION>: Generate a brief caption
    - <DETAILED_CAPTION>: Generate a detailed caption
    - <MORE_DETAILED_CAPTION>: Generate an even more detailed caption
    - <VQA>: Visual question answering (append question to prompt)

    Usage:
        client = FlorenceClient()

        # Check if service is healthy
        if await client.check_health():
            # Extract caption from image
            caption = await client.extract(image, "<CAPTION>")

            # Visual question answering
            answer = await client.extract(image, "<VQA>What color is the car?")
    """

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize Florence client with configuration.

        Args:
            base_url: Optional base URL for the Florence service.
                     Defaults to FLORENCE_URL setting or http://ai-florence:8092
        """
        settings = get_settings()

        # Use provided URL, or settings, or default
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        else:
            # Check for FLORENCE_URL in settings (we'll add this later if needed)
            # For now, use the default service URL
            self._base_url = getattr(settings, "florence_url", DEFAULT_FLORENCE_URL).rstrip("/")

        # Use httpx.Timeout for proper timeout configuration
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=FLORENCE_READ_TIMEOUT,
            write=FLORENCE_READ_TIMEOUT,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        logger.info(f"FlorenceClient initialized with base_url={self._base_url}")

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """Encode a PIL Image to base64 string.

        Args:
            image: PIL Image to encode

        Returns:
            Base64-encoded string of the image in PNG format
        """
        buffer = io.BytesIO()
        # Use PNG for lossless encoding, or JPEG for smaller size
        # PNG is safer for quality preservation
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    async def check_health(self) -> bool:
        """Check if Florence service is healthy and reachable.

        Returns:
            True if Florence service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                response = await client.get(f"{self._base_url}/health")
                response.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Florence health check failed: {e}", exc_info=True)
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"Florence health check returned error status: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error during Florence health check: {sanitize_error(e)}", exc_info=True
            )
            return False

    async def extract(self, image: Image.Image, prompt: str) -> str:
        """Send image to Florence service for extraction.

        Sends an image and prompt to the Florence-2 service and returns
        the extracted text. Supports various Florence-2 task prompts:
        - <CAPTION>: Brief caption
        - <DETAILED_CAPTION>: Detailed caption
        - <VQA>question: Visual question answering

        Args:
            image: PIL Image to analyze
            prompt: Florence-2 task prompt (e.g., "<CAPTION>", "<VQA>What is this?")

        Returns:
            Extracted text from Florence-2, or empty string on error

        Raises:
            FlorenceUnavailableError: If the service is unavailable (connection, timeout, 5xx)
        """
        start_time = time.time()

        logger.debug(f"Sending extraction request with prompt: {prompt[:50]}...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
                "prompt": prompt,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to Florence service
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/extract",
                    json=payload,
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence", ai_duration)

            # Parse response
            result = response.json()

            if "result" not in result:
                logger.warning(f"Malformed response from Florence (missing 'result'): {result}")
                record_pipeline_error("florence_malformed_response")
                return ""

            extracted_text: str = result["result"]
            duration_ms = int((time.time() - start_time) * 1000)

            logger.debug(
                f"Florence extraction completed: {len(extracted_text)} chars in {duration_ms}ms"
            )
            return extracted_text

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("florence_connection_error")
            logger.error(
                f"Failed to connect to Florence service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("florence_timeout")
            logger.error(
                f"Florence request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise FlorenceUnavailableError(
                f"Florence request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            # 5xx errors are server-side failures that should be retried
            if status_code >= 500:
                record_pipeline_error("florence_server_error")
                logger.error(
                    f"Florence returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise FlorenceUnavailableError(
                    f"Florence returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.) - don't retry
            record_pipeline_error("florence_client_error")
            logger.error(
                f"Florence returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return ""

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("florence_unexpected_error")
            logger.error(
                f"Unexpected error during Florence extraction: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            # For unexpected errors, also raise to allow retry
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence extraction: {sanitize_error(e)}",
                original_error=e,
            ) from e


# Global client instance
_florence_client: FlorenceClient | None = None


def get_florence_client() -> FlorenceClient:
    """Get or create the global FlorenceClient instance.

    Returns:
        Global FlorenceClient instance
    """
    global _florence_client  # noqa: PLW0603
    if _florence_client is None:
        _florence_client = FlorenceClient()
    return _florence_client


def reset_florence_client() -> None:
    """Reset the global FlorenceClient instance (for testing)."""
    global _florence_client  # noqa: PLW0603
    _florence_client = None
