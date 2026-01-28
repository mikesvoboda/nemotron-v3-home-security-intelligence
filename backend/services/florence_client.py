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
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from backend.api.middleware.correlation import get_correlation_headers
from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    record_florence_task,
    record_pipeline_error,
)
from backend.services.circuit_breaker import CircuitBreaker, CircuitState

if TYPE_CHECKING:
    from PIL import Image


@dataclass(slots=True)
class OCRRegion:
    """A text region with bounding box coordinates."""

    text: str
    bbox: list[float]  # [x1, y1, x2, y2, x3, y3, x4, y4] quadrilateral


@dataclass(slots=True)
class Detection:
    """A detected object with bounding box and confidence score."""

    label: str
    bbox: list[float]  # [x1, y1, x2, y2]
    score: float = 1.0


@dataclass(slots=True)
class CaptionedRegion:
    """A region with its caption and bounding box."""

    caption: str
    bbox: list[float]  # [x1, y1, x2, y2]


@dataclass(slots=True)
class BoundingBox:
    """A bounding box with x1, y1, x2, y2 coordinates (NEM-3911)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def as_list(self) -> list[float]:
        """Return as [x1, y1, x2, y2] list."""
        return [self.x1, self.y1, self.x2, self.y2]

    @classmethod
    def from_list(cls, bbox: list[float]) -> BoundingBox:
        """Create from [x1, y1, x2, y2] list."""
        return cls(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3])

    def as_dict(self) -> dict[str, float]:
        """Return as dict for JSON serialization."""
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


@dataclass(slots=True)
class GroundedPhrase:
    """A phrase with its grounded bounding boxes (NEM-3911)."""

    phrase: str
    bboxes: list[list[float]]  # List of [x1, y1, x2, y2] boxes
    confidence_scores: list[float]


logger = get_logger(__name__)

# Timeout configuration for Florence-2 service
# Note: These defaults are used as fallbacks. Production code uses Settings values:
# - settings.ai_connect_timeout: Maximum time to establish connection (default: 10s)
# - settings.florence_read_timeout: Maximum time to wait for response (default: 30s)
# - settings.ai_health_timeout: Health check timeout (default: 5s)
FLORENCE_CONNECT_TIMEOUT = 10.0  # Fallback, use settings.ai_connect_timeout
FLORENCE_READ_TIMEOUT = 30.0  # Fallback, use settings.florence_read_timeout
FLORENCE_HEALTH_TIMEOUT = 5.0  # Fallback, use settings.ai_health_timeout

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
                     Defaults to settings.florence_url (http://localhost:8092 by default).
        """
        settings = get_settings()

        # Use provided URL or get from settings (which has default configured)
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        else:
            # Use florence_url from settings (configured in config.py with proper default)
            self._base_url = settings.florence_url.rstrip("/")

        # Use httpx.Timeout for proper timeout configuration from Settings (NEM-2524)
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.florence_read_timeout,
            write=settings.florence_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        # Initialize circuit breaker for Florence service
        self._circuit_breaker = CircuitBreaker(
            name="florence",
            failure_threshold=getattr(settings, "florence_cb_failure_threshold", 5),
            recovery_timeout=getattr(settings, "florence_cb_recovery_timeout", 60.0),
            half_open_max_calls=getattr(settings, "florence_cb_half_open_max_calls", 3),
        )

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

        logger.info(f"FlorenceClient initialized with base_url={self._base_url}")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for outgoing HTTP requests.

        Includes W3C Trace Context headers (traceparent, tracestate) for
        distributed tracing and correlation IDs for request tracking.

        Returns:
            Dictionary of headers to include in requests
        """
        return get_correlation_headers()

    async def close(self) -> None:
        """Close the HTTP client connections.

        Should be called when the client is no longer needed to release resources.
        """
        await self._http_client.aclose()
        await self._health_http_client.aclose()
        logger.debug("FlorenceClient HTTP connections closed")

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

    def get_circuit_breaker_state(self) -> CircuitState:
        """Get current circuit breaker state.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        return self._circuit_breaker.get_state()

    def _check_circuit_breaker(self) -> None:
        """Check if the circuit breaker allows the request to proceed.

        Raises:
            FlorenceUnavailableError: If circuit breaker is open
        """
        if not self._circuit_breaker.allow_request():
            record_pipeline_error("florence_circuit_open")
            raise FlorenceUnavailableError(
                "Florence service circuit breaker is open - service temporarily unavailable"
            )

    async def check_health(self) -> bool:
        """Check if Florence service is healthy and reachable.

        Returns:
            True if Florence service is healthy and circuit breaker is not open,
            False otherwise
        """
        # If circuit breaker is open, consider service unhealthy
        if self._circuit_breaker.get_state() == CircuitState.OPEN:
            logger.warning("Florence health check: circuit breaker is open")
            return False

        try:
            # Use persistent HTTP client (NEM-1721)
            # NEM-3147: Include W3C Trace Context headers for distributed tracing
            response = await self._health_http_client.get(
                f"{self._base_url}/health",
                headers=self._get_headers(),
            )
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
                                     or if the circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

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

            # Send to Florence service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/extract",
                json=payload,
                headers=self._get_headers(),
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
                # Don't count malformed response as failure for circuit breaker
                # (server responded, just with unexpected format)
                self._circuit_breaker.record_success()
                return ""

            extracted_text: str = result["result"]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence task executed
            # Extract task type from prompt (e.g., "<CAPTION>" -> "caption")
            task_type = (
                prompt.strip("<>").split(">")[0].lower() if prompt.startswith("<") else "extract"
            )
            record_florence_task(task_type)

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

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
            # Record failure with circuit breaker
            self._circuit_breaker.record_failure()
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
            # Record failure with circuit breaker
            self._circuit_breaker.record_failure()
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
                # Record failure with circuit breaker for server errors
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.) - don't retry
            # and don't count against circuit breaker (our fault, not server's)
            record_pipeline_error("florence_client_error")
            logger.error(
                f"Florence returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            return ""

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("florence_unexpected_error")
            logger.error(
                f"Unexpected error during Florence extraction: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            # Record failure with circuit breaker
            self._circuit_breaker.record_failure()
            # For unexpected errors, also raise to allow retry
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence extraction: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def ocr(self, image: Image.Image) -> str:
        """Extract text from an image using OCR.

        Args:
            image: PIL Image to analyze

        Returns:
            Extracted text from the image, or empty string on error

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug("Sending OCR request...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {"image": image_b64}

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/ocr",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_ocr", ai_duration)

            result = response.json()

            if "text" not in result:
                logger.warning(f"Malformed OCR response (missing 'text'): {result}")
                record_pipeline_error("florence_ocr_malformed_response")
                self._circuit_breaker.record_success()
                return ""

            extracted_text: str = result["text"]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence OCR task
            record_florence_task("ocr")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(f"Florence OCR completed: {len(extracted_text)} chars in {duration_ms}ms")
            return extracted_text

        except httpx.ConnectError as e:
            record_pipeline_error("florence_ocr_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for OCR: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_ocr_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence OCR request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_ocr_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence OCR returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_ocr_client_error")
            logger.error(f"Florence OCR returned client error: {status_code} - {e}")
            return ""

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_ocr_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence OCR: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def ocr_with_regions(self, image: Image.Image) -> list[OCRRegion]:
        """Extract text with bounding box regions from an image.

        Args:
            image: PIL Image to analyze

        Returns:
            List of OCRRegion objects with text and bounding boxes

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug("Sending OCR with regions request...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {"image": image_b64}

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/ocr-with-regions",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_ocr_regions", ai_duration)

            result = response.json()

            if "regions" not in result:
                logger.warning(f"Malformed OCR regions response (missing 'regions'): {result}")
                record_pipeline_error("florence_ocr_regions_malformed_response")
                self._circuit_breaker.record_success()
                return []

            regions = [
                OCRRegion(text=r.get("text", ""), bbox=r.get("bbox", [])) for r in result["regions"]
            ]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence OCR with regions task
            record_florence_task("ocr_with_regions")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(
                f"Florence OCR regions completed: {len(regions)} regions in {duration_ms}ms"
            )
            return regions

        except httpx.ConnectError as e:
            record_pipeline_error("florence_ocr_regions_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for OCR regions: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_ocr_regions_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence OCR regions request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_ocr_regions_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence OCR regions returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_ocr_regions_client_error")
            logger.error(f"Florence OCR regions returned client error: {status_code} - {e}")
            return []

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_ocr_regions_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence OCR regions: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def detect(self, image: Image.Image) -> list[Detection]:
        """Detect objects with bounding boxes in an image.

        Args:
            image: PIL Image to analyze

        Returns:
            List of Detection objects with labels and bounding boxes

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug("Sending object detection request...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {"image": image_b64}

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/detect",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_detect", ai_duration)

            result = response.json()

            if "detections" not in result:
                logger.warning(f"Malformed detect response (missing 'detections'): {result}")
                record_pipeline_error("florence_detect_malformed_response")
                self._circuit_breaker.record_success()
                return []

            detections = [
                Detection(
                    label=d.get("label", ""),
                    bbox=d.get("bbox", []),
                    score=d.get("score", 1.0),
                )
                for d in result["detections"]
            ]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence detect task
            record_florence_task("detect")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(f"Florence detect completed: {len(detections)} objects in {duration_ms}ms")
            return detections

        except httpx.ConnectError as e:
            record_pipeline_error("florence_detect_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for detection: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_detect_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence detect request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_detect_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence detect returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_detect_client_error")
            logger.error(f"Florence detect returned client error: {status_code} - {e}")
            return []

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_detect_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence detection: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def dense_caption(self, image: Image.Image) -> list[CaptionedRegion]:
        """Generate captions for all regions in an image.

        Args:
            image: PIL Image to analyze

        Returns:
            List of CaptionedRegion objects with captions and bounding boxes

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug("Sending dense captioning request...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {"image": image_b64}

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/dense-caption",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_dense_caption", ai_duration)

            result = response.json()

            if "regions" not in result:
                logger.warning(f"Malformed dense caption response (missing 'regions'): {result}")
                record_pipeline_error("florence_dense_caption_malformed_response")
                self._circuit_breaker.record_success()
                return []

            regions = [
                CaptionedRegion(caption=r.get("caption", ""), bbox=r.get("bbox", []))
                for r in result["regions"]
            ]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence dense caption task
            record_florence_task("dense_caption")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(
                f"Florence dense caption completed: {len(regions)} regions in {duration_ms}ms"
            )
            return regions

        except httpx.ConnectError as e:
            record_pipeline_error("florence_dense_caption_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for dense captioning: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_dense_caption_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence dense caption request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_dense_caption_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence dense caption returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_dense_caption_client_error")
            logger.error(f"Florence dense caption returned client error: {status_code} - {e}")
            return []

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_dense_caption_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence dense captioning: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def describe_regions(
        self, image: Image.Image, regions: list[BoundingBox]
    ) -> list[CaptionedRegion]:
        """Describe what's in specific bounding box regions (NEM-3911).

        Args:
            image: PIL Image to analyze
            regions: List of BoundingBox regions to describe

        Returns:
            List of CaptionedRegion objects with descriptions and bounding boxes

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug(f"Sending region description request for {len(regions)} regions...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {
                "image": image_b64,
                "regions": [r.as_dict() for r in regions],
            }

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/describe-region",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_describe_region", ai_duration)

            result = response.json()

            if "descriptions" not in result:
                logger.warning(
                    f"Malformed describe region response (missing 'descriptions'): {result}"
                )
                record_pipeline_error("florence_describe_region_malformed_response")
                self._circuit_breaker.record_success()
                return []

            descriptions = [
                CaptionedRegion(caption=d.get("caption", ""), bbox=d.get("bbox", []))
                for d in result["descriptions"]
            ]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence describe region task
            record_florence_task("describe_region")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(
                f"Florence describe region completed: {len(descriptions)} regions in {duration_ms}ms"
            )
            return descriptions

        except httpx.ConnectError as e:
            record_pipeline_error("florence_describe_region_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for region description: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_describe_region_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence describe region request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_describe_region_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence describe region returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_describe_region_client_error")
            logger.error(f"Florence describe region returned client error: {status_code} - {e}")
            return []

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_describe_region_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence region description: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def phrase_grounding(
        self, image: Image.Image, phrases: list[str]
    ) -> list[GroundedPhrase]:
        """Find objects matching text descriptions (phrase grounding) (NEM-3911).

        Args:
            image: PIL Image to analyze
            phrases: List of text phrases to find in the image

        Returns:
            List of GroundedPhrase objects with bounding boxes for each phrase

        Raises:
            FlorenceUnavailableError: If the service is unavailable or circuit breaker is open
        """
        # Check circuit breaker before proceeding
        self._check_circuit_breaker()

        start_time = time.time()

        logger.debug(f"Sending phrase grounding request for {len(phrases)} phrases...")

        try:
            image_b64 = self._encode_image_to_base64(image)
            payload = {
                "image": image_b64,
                "phrases": phrases,
            }

            ai_start_time = time.time()

            # Use persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/phrase-grounding",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("florence_phrase_grounding", ai_duration)

            result = response.json()

            if "grounded_phrases" not in result:
                logger.warning(
                    f"Malformed phrase grounding response (missing 'grounded_phrases'): {result}"
                )
                record_pipeline_error("florence_phrase_grounding_malformed_response")
                self._circuit_breaker.record_success()
                return []

            grounded = [
                GroundedPhrase(
                    phrase=g.get("phrase", ""),
                    bboxes=g.get("bboxes", []),
                    confidence_scores=g.get("confidence_scores", []),
                )
                for g in result["grounded_phrases"]
            ]
            duration_ms = int((time.time() - start_time) * 1000)

            # Record semantic metric for Florence phrase grounding task
            record_florence_task("phrase_grounding")

            # Record success with circuit breaker
            self._circuit_breaker.record_success()

            logger.debug(
                f"Florence phrase grounding completed: {len(grounded)} phrases in {duration_ms}ms"
            )
            return grounded

        except httpx.ConnectError as e:
            record_pipeline_error("florence_phrase_grounding_connection_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Failed to connect to Florence service for phrase grounding: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            record_pipeline_error("florence_phrase_grounding_timeout")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Florence phrase grounding request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code >= 500:
                record_pipeline_error("florence_phrase_grounding_server_error")
                self._circuit_breaker.record_failure()
                raise FlorenceUnavailableError(
                    f"Florence phrase grounding returned server error: {status_code}",
                    original_error=e,
                ) from e
            record_pipeline_error("florence_phrase_grounding_client_error")
            logger.error(f"Florence phrase grounding returned client error: {status_code} - {e}")
            return []

        except FlorenceUnavailableError:
            # Re-raise circuit breaker errors without modification
            raise

        except Exception as e:
            record_pipeline_error("florence_phrase_grounding_unexpected_error")
            self._circuit_breaker.record_failure()
            raise FlorenceUnavailableError(
                f"Unexpected error during Florence phrase grounding: {sanitize_error(e)}",
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


async def reset_florence_client() -> None:
    """Reset the global FlorenceClient instance (for testing).

    This async function properly closes HTTP connections before resetting.
    """
    global _florence_client  # noqa: PLW0603
    if _florence_client is not None:
        await _florence_client.close()
    _florence_client = None
