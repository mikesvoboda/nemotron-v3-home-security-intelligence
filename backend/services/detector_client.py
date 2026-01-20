"""Detector client service for RT-DETRv2 object detection.

This service provides an HTTP client interface to the RT-DETRv2 detection server,
sending images for object detection and storing results in the database.

Detection Flow:
    1. Read image file from filesystem
    2. Validate image integrity (catch truncated/corrupt images)
    3. Acquire shared AI inference semaphore (NEM-1463)
    4. POST to detector server with image data (with retry on transient failures)
    5. Release semaphore
    6. Parse JSON response with detections
    7. Filter by confidence threshold
    8. Store detections in database
    9. Return Detection model instances

Concurrency Control (NEM-1463):
    Uses a shared asyncio.Semaphore to limit concurrent AI inference operations.
    This prevents GPU/AI service overload under high traffic. The limit is
    configurable via AI_MAX_CONCURRENT_INFERENCES setting (default: 4).

Error Handling:
    - Connection errors: Retry with exponential backoff, then raise DetectorUnavailableError
    - Timeouts: Retry with exponential backoff, then raise DetectorUnavailableError
    - HTTP 5xx errors: Retry with exponential backoff, then raise DetectorUnavailableError
    - HTTP 4xx errors: Log and return empty list (client error, no retry)
    - Invalid JSON: Log and return empty list (malformed response)
    - Missing files: Log and return empty list (local file issue)
    - Truncated/corrupt images: Log and return empty list (skip bad images)

Retry Logic (NEM-1343):
    - Configurable max retries via DETECTOR_MAX_RETRIES setting (default: 3)
    - Exponential backoff: 2^attempt seconds between retries (capped at 30s)
    - Only retries transient failures (connection, timeout, HTTP 5xx)
"""

__all__ = [
    # Constants
    "DETECTOR_CONNECT_TIMEOUT",
    "DETECTOR_HEALTH_TIMEOUT",
    "DETECTOR_READ_TIMEOUT",
    "MIN_DETECTION_IMAGE_SIZE",
    # Classes
    "DetectorClient",
    "DetectorUnavailableError",
]

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware.correlation import get_correlation_headers
from backend.core.config import get_settings
from backend.core.exceptions import DetectorUnavailableError
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    observe_detection_confidence,
    record_detection_by_class,
    record_detection_filtered,
    record_detection_processed,
    record_pipeline_error,
)
from backend.core.mime_types import get_mime_type_with_default
from backend.core.telemetry import get_trace_id, trace_span
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.baseline import get_baseline_service
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
)
from backend.services.inference_semaphore import get_inference_semaphore

logger = get_logger(__name__)

# Minimum image file size for detection (10KB)
# Images smaller than this are likely truncated from incomplete FTP uploads
MIN_DETECTION_IMAGE_SIZE = 10 * 1024  # 10KB

# Timeout configuration for AI service clients
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for response (60s for AI inference)
DETECTOR_CONNECT_TIMEOUT = 10.0
DETECTOR_READ_TIMEOUT = 60.0
DETECTOR_HEALTH_TIMEOUT = 5.0


class DetectorClient:
    """Client for interacting with RT-DETRv2 object detection service.

    This client handles communication with the external detector service,
    including health checks, image submission, and response parsing.

    Features:
        - Retry logic with exponential backoff for transient failures (NEM-1343)
        - Configurable timeouts and retry attempts via settings
        - API key authentication via X-API-Key header when configured
        - Concurrency limiting via semaphore to prevent GPU overload (NEM-1500)

    Security: Supports API key authentication via X-API-Key header when
    configured in settings (RTDETR_API_KEY environment variable).
    """

    # Class-level semaphore for limiting concurrent AI requests (NEM-1500)
    # This prevents overwhelming the GPU service with too many parallel requests
    # Default: 4 concurrent requests (configurable via ai_max_concurrent_inferences)
    _request_semaphore: asyncio.Semaphore | None = None
    _semaphore_limit: int = 0

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """Get or create the shared semaphore for concurrency limiting.

        Uses a class-level semaphore to limit concurrent requests across
        all DetectorClient instances. The limit is configurable via
        AI_MAX_CONCURRENT_REQUESTS setting.

        Returns:
            asyncio.Semaphore for rate limiting concurrent requests
        """
        settings = get_settings()
        limit = settings.ai_max_concurrent_inferences

        # Create or recreate semaphore if limit changed
        if cls._request_semaphore is None or cls._semaphore_limit != limit:
            cls._request_semaphore = asyncio.Semaphore(limit)
            cls._semaphore_limit = limit
            logger.debug(f"Created DetectorClient semaphore with limit={limit}")

        return cls._request_semaphore

    def __init__(self, max_retries: int | None = None) -> None:
        """Initialize detector client with configuration.

        Args:
            max_retries: Maximum retry attempts for transient failures.
                If not provided, uses DETECTOR_MAX_RETRIES from settings (default: 3).
        """
        settings = get_settings()
        self._detector_url = settings.rtdetr_url
        self._confidence_threshold = settings.detection_confidence_threshold
        # Security: Store API key for authentication (None if not configured)
        self._api_key = settings.rtdetr_api_key
        # Use httpx.Timeout for proper timeout configuration from Settings
        # connect: time to establish connection, read: time to wait for response
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.rtdetr_read_timeout,
            write=settings.rtdetr_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )
        # Retry configuration (NEM-1343)
        self._max_retries = (
            max_retries if max_retries is not None else settings.detector_max_retries
        )
        # Concurrency limit (NEM-1500)
        self._max_concurrent = settings.ai_max_concurrent_inferences

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

        # Circuit breaker for RT-DETRv2 service protection (NEM-1724)
        # Prevents retry storms when the detector service is unavailable.
        # - failure_threshold=5: Opens circuit after 5 consecutive failures
        # - recovery_timeout=60: Waits 60 seconds before attempting recovery
        # - excluded_exceptions: ValueError (client errors) don't count as failures
        self._circuit_breaker = CircuitBreaker(
            name="rtdetr",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_max_calls=3,
                success_threshold=2,
                excluded_exceptions=(ValueError,),  # HTTP 4xx errors should not trip circuit
            ),
        )

        # Cold start and warmup tracking (NEM-1670)
        self._last_inference_time: float | None = None
        self._is_warming: bool = False
        self._warmup_enabled = settings.ai_warmup_enabled
        self._cold_start_threshold = settings.ai_cold_start_threshold_seconds

        logger.debug(
            f"DetectorClient initialized with max_retries={self._max_retries}, "
            f"timeout={settings.rtdetr_read_timeout}s, max_concurrent={self._max_concurrent}, "
            f"circuit_breaker=rtdetr(failure_threshold=5, recovery_timeout=60s)"
        )

    async def close(self) -> None:
        """Close the HTTP client connections.

        Should be called when the client is no longer needed to release resources.
        """
        await self._http_client.aclose()
        await self._health_http_client.aclose()
        logger.debug("DetectorClient HTTP connections closed")

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication and correlation headers for API requests.

        NEM-1729: Includes correlation headers for distributed tracing.
        Security: Returns X-API-Key header if API key is configured.

        Returns:
            Dictionary of headers to include in requests (auth + correlation)
        """
        headers: dict[str, str] = {}
        # Add correlation headers for distributed tracing (NEM-1729)
        headers.update(get_correlation_headers())
        # Add API key if configured
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def health_check(self) -> bool:
        """Check if detector service is healthy and reachable.

        Returns:
            True if detector is healthy, False otherwise
        """
        try:
            # Use persistent HTTP client (NEM-1721)
            response = await self._health_http_client.get(
                f"{self._detector_url}/health",
                headers=self._get_auth_headers(),
            )
            response.raise_for_status()
            return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(
                "Detector health check failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Detector health check returned error status",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False
        except (OSError, RuntimeError, ValueError) as e:
            # OSError: network-level failures, RuntimeError: HTTP client issues
            # ValueError: unexpected response parsing errors
            logger.error(
                "Unexpected error during detector health check",
                extra={"error": sanitize_error(e)},
                exc_info=True,
            )
            return False

    # =========================================================================
    # Cold Start Detection and Warmup (NEM-1670)
    # =========================================================================

    def _track_inference(self) -> None:
        """Record the timestamp of an inference operation.

        Called after each successful detection inference to track model warmth.
        """
        self._last_inference_time = time.monotonic()

    def is_cold(self) -> bool:
        """Check if the model is considered cold (not recently used).

        A model is cold if:
        - It has never been used (_last_inference_time is None)
        - The time since last inference exceeds cold_start_threshold

        Returns:
            True if model is cold, False if warm
        """
        if self._last_inference_time is None:
            return True
        seconds_since_last = time.monotonic() - self._last_inference_time
        return seconds_since_last > self._cold_start_threshold

    def get_warmth_state(self) -> dict[str, Any]:
        """Get the current warmth state of the model.

        Returns:
            Dictionary containing:
            - state: 'cold', 'warming', or 'warm'
            - last_inference_seconds_ago: Seconds since last inference, or None
        """
        if self._is_warming:
            return {
                "state": "warming",
                "last_inference_seconds_ago": None,
            }

        if self._last_inference_time is None:
            return {
                "state": "cold",
                "last_inference_seconds_ago": None,
            }

        seconds_ago = time.monotonic() - self._last_inference_time
        is_cold = seconds_ago > self._cold_start_threshold
        return {
            "state": "cold" if is_cold else "warm",
            "last_inference_seconds_ago": seconds_ago,
        }

    async def model_readiness_probe(self) -> bool:
        """Perform model readiness probe with actual inference.

        Unlike health_check which only checks HTTP availability,
        this method sends a test image to verify the model can
        actually perform inference. This is used for warmup and
        to detect if the model is loaded and ready.

        Returns:
            True if model completed inference successfully, False otherwise
        """
        try:
            # Create a simple 32x32 black test image
            # This is small enough to be fast but exercises the full inference path
            test_image = Image.new("RGB", (32, 32), color=(0, 0, 0))
            import io

            buffer = io.BytesIO()
            test_image.save(buffer, format="JPEG")
            image_data = buffer.getvalue()

            # Send detection request - result is not needed, just verify no exception
            await self._send_detection_request(
                image_data=image_data,
                image_name="warmup_test.jpg",
                camera_id="warmup",
                image_path="/dev/null",  # placeholder path for warmup probe
            )
            # Any valid response (even empty detections) means the model is ready
            return True
        except DetectorUnavailableError as e:
            logger.warning(f"RT-DETR readiness probe failed (unavailable): {e}")
            return False
        except Exception as e:
            logger.warning(f"RT-DETR readiness probe failed: {e}")
            return False

    async def warmup(self) -> bool:
        """Perform model warmup by running a test inference.

        Called on service startup to preload model weights into GPU memory.
        This reduces first-request latency for production traffic.

        Records metrics:
        - hsi_model_warmup_duration_seconds{model="rtdetr"}
        - hsi_model_cold_start_total{model="rtdetr"} (if model was cold)

        Returns:
            True if warmup succeeded, False otherwise
        """
        from backend.core.metrics import (
            observe_model_warmup_duration,
            record_model_cold_start,
            set_model_warmth_state,
        )

        if not self._warmup_enabled:
            logger.debug("RT-DETR warmup disabled by configuration")
            return True

        was_cold = self.is_cold()
        self._is_warming = True
        set_model_warmth_state("rtdetr", "warming")

        try:
            logger.info("Starting RT-DETR model warmup...")
            start_time = time.monotonic()

            result = await self.model_readiness_probe()

            duration = time.monotonic() - start_time
            observe_model_warmup_duration("rtdetr", duration)

            if result:
                self._track_inference()
                if was_cold:
                    record_model_cold_start("rtdetr")
                set_model_warmth_state("rtdetr", "warm")
                logger.info(
                    f"RT-DETR warmup completed in {duration:.2f}s",
                    extra={"duration": duration, "was_cold": was_cold},
                )
                return True
            else:
                set_model_warmth_state("rtdetr", "cold")
                logger.warning("RT-DETR warmup failed - model not ready")
                return False
        finally:
            self._is_warming = False

    async def _send_detection_request(  # noqa: PLR0912
        self,
        image_data: bytes,
        image_name: str,
        camera_id: str,
        image_path: str,
    ) -> dict[str, Any]:
        """Send detection request to RT-DETR service with retry logic and concurrency limiting.

        Implements exponential backoff for transient failures (NEM-1343):
        - Connection errors
        - Timeout errors
        - HTTP 5xx server errors

        Also implements concurrency limiting via semaphore (NEM-1500) to prevent
        overwhelming the GPU service with too many parallel requests.

        Defense-in-depth (NEM-1465): Uses explicit asyncio.timeout() wrapper around
        HTTP calls to ensure requests don't hang indefinitely even if httpx timeout fails.

        W3C Trace Context: Headers are automatically propagated via get_correlation_headers()
        which includes traceparent and tracestate for distributed tracing.

        Args:
            image_data: Raw image bytes to send
            image_name: Filename for the multipart upload
            camera_id: Camera identifier (for logging)
            image_path: Full path to image file (for logging)

        Returns:
            Parsed JSON response from the detector service

        Raises:
            DetectorUnavailableError: If all retries are exhausted for transient failures
            ValueError: For HTTP 4xx client errors (not retried)
        """
        last_exception: Exception | None = None
        semaphore = self._get_semaphore()
        settings = get_settings()
        # Explicit timeout as defense-in-depth (NEM-1465)
        # Use rtdetr_read_timeout from settings (default 60s)
        explicit_timeout = settings.rtdetr_read_timeout + settings.ai_connect_timeout

        # Create span for AI service call with attributes for observability
        with trace_span(
            "rtdetr_detection_request",
            ai_service="rtdetr",
            camera_id=camera_id,
            image_path=image_path,
            image_size_bytes=len(image_data),
        ) as span:
            for attempt in range(self._max_retries):
                span.set_attribute("retry_attempt", attempt)
                try:
                    # Use semaphore to limit concurrent GPU requests (NEM-1500)
                    # Use persistent HTTP client (NEM-1721)
                    # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                    async with semaphore:
                        async with asyncio.timeout(explicit_timeout):
                            files = {"file": (image_name, image_data, "image/jpeg")}
                            response = await self._http_client.post(
                                f"{self._detector_url}/detect",
                                files=files,
                                headers=self._get_auth_headers(),
                            )
                            response.raise_for_status()
                            result: dict[str, Any] = response.json()
                            # Add detection count to span for observability
                            detection_count = len(result.get("detections", []))
                            span.set_attribute("ai.detection_count", detection_count)
                            return result

                except httpx.ConnectError as e:
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            "Detector connection error, retrying",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                                "error": str(e),
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error("rtdetr_connection_error")
                        logger.error(
                            "Detector connection error after all attempts",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempts": self._max_retries,
                                "error": str(e),
                            },
                            exc_info=True,
                        )

                except httpx.TimeoutException as e:
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            "Detector timeout, retrying",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                                "error": str(e),
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error("rtdetr_timeout")
                        logger.error(
                            "Detector timeout after all attempts",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempts": self._max_retries,
                                "error": str(e),
                            },
                            exc_info=True,
                        )

                except TimeoutError as e:
                    # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            f"Detector asyncio timeout (attempt {attempt + 1}/{self._max_retries}), "
                            f"retrying in {delay}s: request timed out after {explicit_timeout}s",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                                "explicit_timeout": explicit_timeout,
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error("rtdetr_asyncio_timeout")
                        logger.error(
                            f"Detector asyncio timeout after {self._max_retries} attempts: "
                            f"request timed out after {explicit_timeout}s",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempts": self._max_retries,
                                "explicit_timeout": explicit_timeout,
                            },
                            exc_info=True,
                        )

                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code

                    # 5xx errors are server-side failures that should be retried
                    if status_code >= 500:
                        last_exception = e
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)  # Cap at 30 seconds
                            logger.warning(
                                "Detector server error, retrying",
                                extra={
                                    "camera_id": camera_id,
                                    "file_path": image_path,
                                    "status_code": status_code,
                                    "attempt": attempt + 1,
                                    "max_retries": self._max_retries,
                                    "retry_delay": delay,
                                },
                            )
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error("rtdetr_server_error")
                            logger.error(
                                "Detector server error after all attempts",
                                extra={
                                    "camera_id": camera_id,
                                    "file_path": image_path,
                                    "status_code": status_code,
                                    "attempts": self._max_retries,
                                },
                                exc_info=True,
                            )
                    else:
                        # 4xx errors are client errors - don't retry, raise immediately
                        error_detail = None
                        if status_code == 400:
                            try:
                                error_response = e.response.json()
                                error_detail = error_response.get("detail", str(e))
                            except (json.JSONDecodeError, ValueError, AttributeError):
                                # JSON parsing failures - fall back to raw text
                                error_detail = e.response.text[:500] if e.response.text else str(e)

                        record_pipeline_error("rtdetr_client_error")
                        logger.error(
                            "Detector client error",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "status_code": status_code,
                                "error_detail": error_detail,
                            },
                        )
                        # Raise ValueError for client errors (not retried)
                        raise ValueError(
                            f"Detector client error {status_code}: {error_detail or e}"
                        ) from e

                except (json.JSONDecodeError, ValueError) as e:
                    # json.JSONDecodeError: malformed JSON response from detector
                    # ValueError: invalid response data or JSON decode errors (JSONDecodeError is a ValueError)
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            f"Detector JSON/value error (attempt {attempt + 1}/{self._max_retries}), "
                            f"retrying in {delay}s: {sanitize_error(e)}",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error("rtdetr_json_error")
                        logger.error(
                            f"Detector JSON/value error after {self._max_retries} attempts: "
                            f"{sanitize_error(e)}",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempts": self._max_retries,
                            },
                            exc_info=True,
                        )

                except (OSError, RuntimeError) as e:
                    # OSError: network-level failures, file I/O issues
                    # RuntimeError: HTTP client/asyncio issues
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            "Unexpected detector error, retrying",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                                "error": sanitize_error(e),
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error("rtdetr_unexpected_error")
                        logger.error(
                            "Unexpected detector error after all attempts",
                            extra={
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempts": self._max_retries,
                                "error": sanitize_error(e),
                            },
                            exc_info=True,
                        )

            # All retries exhausted
            error_msg = f"Detection failed after {self._max_retries} attempts"
            span.set_attribute("error", True)
            span.set_attribute("error.message", error_msg)
            if last_exception:
                raise DetectorUnavailableError(
                    error_msg, original_error=last_exception
                ) from last_exception
            raise DetectorUnavailableError(error_msg)

    def _validate_image_for_detection(self, image_path: str, camera_id: str) -> bool:
        """Validate that an image file is suitable for object detection.

        This method performs comprehensive validation to catch truncated or
        corrupt images before sending them to the AI detector service.

        Validation checks:
        1. File size is above minimum threshold (catches truncation)
        2. PIL can load the image data (catches corruption)

        Args:
            image_path: Path to the image file
            camera_id: Camera ID for logging context

        Returns:
            True if image is valid and suitable for detection
        """
        try:
            image_file = Path(image_path)

            # Check file size - very small images are likely truncated
            file_size = image_file.stat().st_size
            if file_size < MIN_DETECTION_IMAGE_SIZE:
                logger.warning(
                    "Image too small for detection",
                    extra={
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "file_size": file_size,
                        "min_size": MIN_DETECTION_IMAGE_SIZE,
                    },
                )
                return False

            # Try to load the image to catch truncation/corruption
            # This reads and decompresses the full image data
            with Image.open(image_path) as img:
                # load() forces full decompression - will fail on truncated images
                img.load()

            return True

        except OSError as e:
            # OSError covers most PIL image errors (truncated, corrupt, etc.)
            logger.warning(
                "Image validation failed (corrupt/truncated)",
                extra={"camera_id": camera_id, "file_path": image_path, "error": str(e)},
            )
            return False
        except (ValueError, RuntimeError) as e:
            # ValueError: invalid image format, RuntimeError: PIL/decoder issues
            logger.warning(
                "Image validation failed",
                extra={"camera_id": camera_id, "file_path": image_path, "error": sanitize_error(e)},
            )
            return False

    async def _validate_image_for_detection_async(self, image_path: str, camera_id: str) -> bool:
        """Validate image file asynchronously without blocking the event loop.

        This is the non-blocking version that runs the validation in a thread pool
        executor. Use this in async code instead of _validate_image_for_detection.

        Args:
            image_path: Path to the image file
            camera_id: Camera ID for logging context

        Returns:
            True if image is valid and suitable for detection
        """
        return await asyncio.to_thread(self._validate_image_for_detection, image_path, camera_id)

    async def detect_objects(  # noqa: PLR0912
        self,
        image_path: str,
        camera_id: str,
        session: AsyncSession,
        video_path: str | None = None,
        video_metadata: dict[str, Any] | None = None,
    ) -> list[Detection]:
        """Send image to detector service and store detections.

        Reads the image file, sends it to the RT-DETRv2 service with retry logic,
        parses the response, filters by confidence threshold, and stores detections
        in the database.

        Retry behavior (NEM-1343):
        - Connection errors, timeouts, and HTTP 5xx errors trigger exponential backoff retry
        - Up to max_retries attempts (configurable via DETECTOR_MAX_RETRIES setting)
        - Backoff delay: 2^attempt seconds, capped at 30 seconds

        For video frame detection, the video_path and video_metadata parameters
        allow associating the detection with the source video file instead of
        the extracted frame.

        Args:
            image_path: Path to the image file (or extracted video frame)
            camera_id: Camera identifier for the image
            session: Database session for storing detections
            video_path: Optional path to the source video (if detecting from video frame)
            video_metadata: Optional video metadata dict with duration, codec, etc.

        Returns:
            List of Detection model instances that were stored

        Raises:
            DetectorUnavailableError: If all retries exhausted for transient failures
        """
        # NEM-1503: Include trace_id in logs for distributed tracing correlation
        trace_id = get_trace_id()
        start_time = time.time()

        # Validate image file exists
        image_file = Path(image_path)
        if not image_file.exists():
            logger.error(
                "Image file not found",
                extra={"camera_id": camera_id, "file_path": image_path},
            )
            record_pipeline_error("file_not_found")
            return []

        # Validate image integrity before sending to detector (async to avoid blocking)
        # This catches truncated/corrupt images from incomplete FTP uploads
        if not await self._validate_image_for_detection_async(image_path, camera_id):
            record_pipeline_error("invalid_image")
            return []

        logger.debug(
            f"Sending detection request for {image_path}",
            extra={"camera_id": camera_id, "file_path": image_path},
        )

        try:
            # Check if circuit breaker is open before proceeding (NEM-1724)
            # This prevents retry storms when the detector is known to be unavailable
            if not await self._circuit_breaker.allow_call():
                logger.warning(
                    "Circuit breaker open for RT-DETR, rejecting detection request",
                    extra={
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "circuit_state": self._circuit_breaker.state.value,
                    },
                )
                record_pipeline_error("circuit_breaker_open")
                raise DetectorUnavailableError(
                    "RT-DETR service temporarily unavailable (circuit breaker open)"
                )

            # Read image file asynchronously to avoid blocking the event loop
            image_data = await asyncio.to_thread(image_file.read_bytes)

            # Track AI request time separately
            ai_start_time = time.time()

            # Acquire shared AI inference semaphore (NEM-1463)
            # This limits concurrent AI operations to prevent GPU/service overload
            inference_semaphore = get_inference_semaphore()
            async with inference_semaphore:
                # Send to detector with retry logic (NEM-1343) and circuit breaker (NEM-1724)
                # The circuit breaker tracks failures and opens after threshold is reached
                result = await self._circuit_breaker.call(
                    self._send_detection_request,
                    image_data=image_data,
                    image_name=image_file.name,
                    camera_id=camera_id,
                    image_path=image_path,
                )

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("rtdetr", ai_duration)

            if "detections" not in result:
                logger.warning(
                    "Malformed response from detector (missing 'detections')",
                    extra={"response": str(result)[:500]},
                )
                record_pipeline_error("malformed_response")
                return []

            # Process detections
            detections = []
            detected_at = datetime.now(UTC)

            # Use video path and file type if this is a video frame detection
            if video_path is not None and video_metadata is not None:
                detection_file_path = video_path
                file_type = video_metadata.get("file_type", "video/mp4")
                media_type = "video"
                is_video = True
            else:
                detection_file_path = image_path
                file_type = get_mime_type_with_default(image_file)
                media_type = "image"
                is_video = False

            for detection_data in result["detections"]:
                try:
                    confidence = detection_data.get("confidence", 0.0)

                    # Filter by confidence threshold
                    if confidence < self._confidence_threshold:
                        logger.debug(
                            f"Filtering out detection with low confidence: "
                            f"{detection_data.get('class')} ({confidence:.2f})"
                        )
                        # Record filtered detection metric (NEM-768)
                        record_detection_filtered()
                        continue

                    # Extract bbox coordinates [x, y, width, height]
                    bbox = detection_data.get("bbox", {})
                    # Handle both dict format {"x", "y", "width", "height"} and array [x, y, w, h]
                    if isinstance(bbox, dict):
                        if not all(k in bbox for k in ("x", "y", "width", "height")):
                            logger.warning(f"Invalid bbox dict format: {bbox}")
                            continue
                        bbox_x = int(bbox["x"])
                        bbox_y = int(bbox["y"])
                        bbox_width = int(bbox["width"])
                        bbox_height = int(bbox["height"])
                    elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        bbox_x = int(bbox[0])
                        bbox_y = int(bbox[1])
                        bbox_width = int(bbox[2])
                        bbox_height = int(bbox[3])
                    else:
                        logger.warning(f"Invalid bbox format: {bbox}")
                        continue

                    # Create Detection model with video metadata if applicable
                    detection = Detection(
                        camera_id=camera_id,
                        file_path=detection_file_path,
                        file_type=file_type,
                        detected_at=detected_at,
                        object_type=detection_data.get("class"),
                        confidence=confidence,
                        bbox_x=bbox_x,
                        bbox_y=bbox_y,
                        bbox_width=bbox_width,
                        bbox_height=bbox_height,
                        media_type=media_type,
                    )

                    # Add video-specific metadata if this is a video detection
                    if is_video and video_metadata:
                        detection.duration = video_metadata.get("duration")
                        detection.video_codec = video_metadata.get("video_codec")
                        detection.video_width = video_metadata.get("video_width")
                        detection.video_height = video_metadata.get("video_height")

                    session.add(detection)
                    detections.append(detection)

                    # Record detection class and confidence metrics (NEM-768)
                    object_class = detection_data.get("class", "unknown")
                    record_detection_by_class(object_class)
                    observe_detection_confidence(confidence)

                    logger.debug(
                        f"Created detection: {detection.object_type} "
                        f"(confidence: {confidence:.2f}, bbox: {bbox})"
                    )

                except (ValueError, TypeError, KeyError) as e:
                    # ValueError: invalid data values (confidence, coordinates)
                    # TypeError: unexpected data types in detection response
                    # KeyError: missing required fields in detection data
                    logger.error(
                        "Error processing detection data",
                        extra={"error": sanitize_error(e)},
                        exc_info=True,
                    )
                    record_pipeline_error("detection_processing_error")
                    continue

            # Commit to database
            if detections:
                # Update camera's last_seen_at timestamp when detections are stored
                # This ensures the camera shows activity only when actual detections occur
                camera = await session.get(Camera, camera_id)
                if camera:
                    camera.last_seen_at = detected_at
                    logger.debug(
                        f"Updated camera {camera_id} last_seen_at to {detected_at}",
                        extra={"camera_id": camera_id, "last_seen_at": detected_at.isoformat()},
                    )

                # Update baseline for analytics (NEM-1259)
                # This populates ActivityBaseline and ClassBaseline tables for the Analytics page
                # Only update once per unique object_type to avoid duplicate updates in same transaction
                baseline_service = get_baseline_service()
                unique_classes = {
                    detection.object_type
                    for detection in detections
                    if detection.object_type is not None
                }
                # Use the first detection's timestamp for consistency
                baseline_timestamp = detections[0].detected_at
                for object_type in unique_classes:
                    await baseline_service.update_baseline(
                        camera_id=camera_id,
                        detection_class=object_type,
                        timestamp=baseline_timestamp,
                        session=session,
                    )
                    # Flush after each baseline update to ensure the SELECT in the next
                    # update_baseline call sees the previous INSERT
                    await session.flush()

                await session.commit()
                duration_ms = int((time.time() - start_time) * 1000)
                # Record detection metrics
                record_detection_processed(count=len(detections))
                # NEM-1503: Include trace_id for distributed tracing correlation
                log_extra: dict[str, Any] = {
                    "camera_id": camera_id,
                    "file_path": image_path,
                    "detection_count": len(detections),
                    "duration_ms": duration_ms,
                }
                if trace_id:
                    log_extra["trace_id"] = trace_id
                logger.info("Stored detections", extra=log_extra)
            else:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.debug(
                    f"No detections above threshold for {image_path}",
                    extra={
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "duration_ms": duration_ms,
                    },
                )

            return detections

        except ValueError:
            # Client errors (4xx) from _send_detection_request - already logged
            return []
        except CircuitBreakerError as e:
            # Circuit breaker tripped (NEM-1724) - service temporarily unavailable
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("circuit_breaker_open")
            logger.warning(
                "Circuit breaker open for RT-DETR",
                extra={
                    "camera_id": camera_id,
                    "file_path": image_path,
                    "duration_ms": duration_ms,
                    "circuit_state": self._circuit_breaker.state.value,
                    "error": str(e),
                },
            )
            raise DetectorUnavailableError(
                "RT-DETR service temporarily unavailable (circuit breaker open)",
                original_error=e,
            ) from e
        except DetectorUnavailableError:
            # Transient errors after retry exhaustion - propagate for caller to handle
            raise
        except (OSError, RuntimeError) as e:
            # OSError/IOError: file system errors, file read failures
            # RuntimeError: asyncio/event loop issues
            # Catch any other unexpected errors (e.g., file read errors)
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_unexpected_error")
            logger.error(
                "Unexpected error during object detection",
                extra={
                    "camera_id": camera_id,
                    "duration_ms": duration_ms,
                    "error": sanitize_error(e),
                },
                exc_info=True,
            )
            raise DetectorUnavailableError(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                original_error=e,
            ) from e
