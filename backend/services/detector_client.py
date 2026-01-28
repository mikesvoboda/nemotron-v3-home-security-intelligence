"""Detector client service for object detection (YOLO26).

This service provides an HTTP client interface to the YOLO26 TensorRT object
detection server. The client sends images for object detection and stores
results in the database.

Configuration:
    - YOLO26_URL: URL of the YOLO26 detection server
    - YOLO26_API_KEY: Optional API key for authentication
    - YOLO26_READ_TIMEOUT: Request timeout for detection requests

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
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from backend.services.frame_buffer import FrameBuffer

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
from backend.core.telemetry import add_span_event, get_trace_id, trace_span
from backend.core.telemetry_ai_conventions import (
    AIModelAttributes,
    set_detection_attributes,
    set_inference_result_attributes,
)
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


# =============================================================================
# Free-Threading Support (Python 3.13t/3.14t)
# =============================================================================


def _is_free_threaded() -> bool:
    """Check if Python is running in free-threaded mode (GIL disabled).

    Free-threaded Python (3.13t, 3.14t) disables the Global Interpreter Lock,
    enabling true thread parallelism for CPU-bound operations like image
    preprocessing.

    Returns:
        True if running free-threaded Python with GIL disabled, False otherwise.
    """
    # Python 3.13+ exposes sys._is_gil_enabled() to check GIL status
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()
    return False


def _get_default_inference_limit() -> int:
    """Get default inference limit based on Python capabilities.

    Returns a higher concurrency limit when running on free-threaded Python
    to leverage true thread parallelism for AI inference operations.

    Returns:
        Default limit: 20 for free-threaded Python, 4 for standard Python.
    """
    if _is_free_threaded():
        return 20  # Higher limit with true parallelism
    return 4  # Conservative limit with GIL


def _get_preprocess_worker_count() -> int:
    """Get the number of preprocessing workers based on Python capabilities.

    Returns more workers for free-threaded Python since we can achieve
    true parallelism for image preprocessing (PIL operations, file I/O).

    Returns:
        Worker count: 8 for free-threaded Python, 2 for standard Python.
    """
    if _is_free_threaded():
        return 8  # More workers with true parallelism
    return 2  # Fewer workers with GIL (limited parallelism benefit)


class DetectorClient:
    """Client for interacting with the YOLO26 object detection service.

    This client handles communication with the YOLO26 TensorRT detection server.
    It handles health checks, image submission, and response parsing.

    Configuration:
        - YOLO26_URL: URL of the detection server
        - YOLO26_API_KEY: Optional API key for authentication
        - YOLO26_READ_TIMEOUT: Request timeout for detection requests

    Features:
        - Retry logic with exponential backoff for transient failures (NEM-1343)
        - Configurable timeouts and retry attempts via settings
        - API key authentication via X-API-Key header when configured
        - Concurrency limiting via semaphore to prevent GPU overload (NEM-1500)
        - Parallel preprocessing with ThreadPoolExecutor (free-threading optimized)
        - Circuit breaker to prevent retry storms

    Free-Threading Support (Python 3.13t/3.14t):
        When running on free-threaded Python (GIL disabled), this client
        automatically increases concurrency limits and preprocessing workers
        to leverage true thread parallelism for AI inference operations.

    Security: Supports API key authentication via X-API-Key header when
    configured in settings (YOLO26_API_KEY environment variable).
    """

    # Class-level semaphore for limiting concurrent AI requests (NEM-1500)
    # This prevents overwhelming the GPU service with too many parallel requests
    # Default depends on Python runtime: 20 for free-threaded, 4 for standard
    _request_semaphore: asyncio.Semaphore | None = None
    _semaphore_limit: int = 0

    # Class-level thread pool for parallel image preprocessing
    # Workers count adapts to free-threading availability
    _preprocess_executor: ThreadPoolExecutor | None = None
    _preprocess_workers: int = 0

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

    @classmethod
    def _get_preprocess_executor(cls) -> ThreadPoolExecutor:
        """Get or create the thread pool for parallel image preprocessing.

        Uses a class-level ThreadPoolExecutor to parallelize CPU-bound image
        preprocessing operations (PIL image loading, validation, etc.).

        The worker count adapts to Python's threading capabilities:
        - Free-threaded Python (GIL disabled): 8 workers for true parallelism
        - Standard Python with GIL: 2 workers (limited parallelism benefit)

        Returns:
            ThreadPoolExecutor for preprocessing tasks
        """
        workers = _get_preprocess_worker_count()

        # Create or recreate executor if worker count changed
        if cls._preprocess_executor is None or cls._preprocess_workers != workers:
            # Shutdown existing executor if any
            if cls._preprocess_executor is not None:
                cls._preprocess_executor.shutdown(wait=False)

            cls._preprocess_executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="yolo26-preprocess",
            )
            cls._preprocess_workers = workers
            logger.debug(
                "Created DetectorClient preprocess executor",
                extra={
                    "workers": workers,
                    "free_threading": _is_free_threaded(),
                },
            )

        return cls._preprocess_executor

    def __init__(
        self,
        max_retries: int | None = None,
        frame_buffer: FrameBuffer | None = None,
    ) -> None:
        """Initialize detector client with configuration.

        Args:
            max_retries: Maximum retry attempts for transient failures.
                If not provided, uses DETECTOR_MAX_RETRIES from settings (default: 3).
            frame_buffer: Optional FrameBuffer instance for buffering frames during
                detection. If provided, frames are buffered with their camera_id and
                timestamp for later use by X-CLIP temporal action recognition.
        """
        self._frame_buffer = frame_buffer
        settings = get_settings()

        # YOLO26 is the only supported detector
        self._detector_type = "yolo26"
        self._model_version = "yolo26m"  # YOLO26 medium model
        self._detector_url = settings.yolo26_url
        self._api_key = settings.yolo26_api_key
        read_timeout = settings.yolo26_read_timeout

        self._confidence_threshold = settings.detection_confidence_threshold
        # Use httpx.Timeout for proper timeout configuration from Settings
        # connect: time to establish connection, read: time to wait for response
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )
        # Store read timeout for use in explicit timeout calculation
        self._read_timeout = read_timeout
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

        # Circuit breaker for detector service protection (NEM-1724)
        # Named per detector type to maintain separate circuit breaker state
        # Prevents retry storms when the detector service is unavailable.
        # - failure_threshold=5: Opens circuit after 5 consecutive failures
        # - recovery_timeout=60: Waits 60 seconds before attempting recovery
        # - excluded_exceptions: ValueError (client errors) don't count as failures
        self._circuit_breaker = CircuitBreaker(
            name=f"detector_{self._detector_type}",
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

        # Get preprocess worker count for logging
        preprocess_workers = _get_preprocess_worker_count()
        free_threading = _is_free_threaded()

        logger.info(
            "DetectorClient initialized",
            extra={
                "detector_type": self._detector_type,
                "detector_url": self._detector_url,
                "free_threading": free_threading,
                "max_concurrent_inferences": self._max_concurrent,
                "preprocess_workers": preprocess_workers,
                "max_retries": self._max_retries,
                "timeout_seconds": read_timeout,
                "circuit_breaker_failure_threshold": 5,
                "circuit_breaker_recovery_timeout": 60.0,
            },
        )

    @property
    def detector_type(self) -> str:
        """Return the configured detector type.

        Returns:
            The detector type string: "yolo26"
        """
        return self._detector_type

    async def close(self) -> None:
        """Close the HTTP client connections.

        Should be called when the client is no longer needed to release resources.
        """
        await self._http_client.aclose()
        await self._health_http_client.aclose()
        logger.debug(
            "DetectorClient HTTP connections closed",
            extra={"detector_type": self._detector_type},
        )

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
        # Add API key if configured (support SecretStr and str)
        if self._api_key:
            api_key_value: str = (
                self._api_key.get_secret_value()
                if hasattr(self._api_key, "get_secret_value")
                else str(self._api_key)
            )
            headers["X-API-Key"] = api_key_value
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
            logger.warning(f"YOLO26 readiness probe failed (unavailable): {e}")
            return False
        except Exception as e:
            logger.warning(f"YOLO26 readiness probe failed: {e}")
            return False

    async def warmup(self) -> bool:
        """Perform model warmup by running a test inference.

        Called on service startup to preload model weights into GPU memory.
        This reduces first-request latency for production traffic.

        Records metrics:
        - hsi_model_warmup_duration_seconds{model="yolo26"}
        - hsi_model_cold_start_total{model="yolo26"} (if model was cold)

        Returns:
            True if warmup succeeded, False otherwise
        """
        from backend.core.metrics import (
            observe_model_warmup_duration,
            record_model_cold_start,
            set_model_warmth_state,
        )

        if not self._warmup_enabled:
            logger.debug("YOLO26 warmup disabled by configuration")
            return True

        was_cold = self.is_cold()
        self._is_warming = True
        set_model_warmth_state("yolo26", "warming")

        try:
            logger.info("Starting YOLO26 model warmup...")
            start_time = time.monotonic()

            result = await self.model_readiness_probe()

            duration = time.monotonic() - start_time
            observe_model_warmup_duration("yolo26", duration)

            if result:
                self._track_inference()
                if was_cold:
                    record_model_cold_start("yolo26")
                set_model_warmth_state("yolo26", "warm")
                logger.info(
                    f"YOLO26 warmup completed in {duration:.2f}s",
                    extra={"duration": duration, "was_cold": was_cold},
                )
                return True
            else:
                set_model_warmth_state("yolo26", "cold")
                logger.warning("YOLO26 warmup failed - model not ready")
                return False
        finally:
            self._is_warming = False

    async def _send_detection_request(
        self,
        image_data: bytes,
        image_name: str,
        camera_id: str,
        image_path: str,
    ) -> dict[str, Any]:
        """Send detection request to YOLO26 service with retry logic and concurrency limiting.

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
        # Use detector-specific read timeout from settings
        explicit_timeout = self._read_timeout + settings.ai_connect_timeout

        # Create span for AI service call with attributes for observability
        # NEM-3794: Use semantic AI conventions for standardized telemetry
        with trace_span(
            f"{self._detector_type}_detection_request",
            camera_id=camera_id,
            image_path=image_path,
            image_size_bytes=len(image_data),
        ) as span:
            # Set AI model semantic attributes (NEM-3794)
            AIModelAttributes.set_on_span(
                span,
                model_name=self._detector_type,
                model_version=self._model_version,
                model_provider="huggingface" if self._detector_type == "yolo26" else "ultralytics",
                device="cuda:0",  # Default GPU device
                batch_size=1,  # Single image per request
            )

            for attempt in range(self._max_retries):
                span.set_attribute("retry_attempt", attempt)
                try:
                    # Use semaphore to limit concurrent GPU requests (NEM-1500)
                    # Use persistent HTTP client (NEM-1721)
                    # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                    async with semaphore:
                        start_time = time.monotonic()
                        async with asyncio.timeout(explicit_timeout):
                            files = {"file": (image_name, image_data, "image/jpeg")}
                            response = await self._http_client.post(
                                f"{self._detector_url}/detect",
                                files=files,
                                headers=self._get_auth_headers(),
                            )
                            response.raise_for_status()
                            result: dict[str, Any] = response.json()
                            inference_time_ms = (time.monotonic() - start_time) * 1000

                            # NEM-3794: Set detection result semantic attributes
                            detections = result.get("detections", [])
                            set_detection_attributes(
                                span,
                                detections=detections,
                                inference_time_ms=inference_time_ms,
                            )
                            set_inference_result_attributes(
                                span, duration_ms=inference_time_ms, status="success"
                            )
                            return result

                except httpx.ConnectError as e:
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)  # Cap at 30 seconds
                        logger.warning(
                            "Detector connection error, retrying",
                            extra={
                                "detector_type": self._detector_type,
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
                        record_pipeline_error(f"{self._detector_type}_connection_error")
                        logger.error(
                            "Detector connection error after all attempts",
                            extra={
                                "detector_type": self._detector_type,
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
                                "detector_type": self._detector_type,
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
                        record_pipeline_error(f"{self._detector_type}_timeout")
                        logger.error(
                            "Detector timeout after all attempts",
                            extra={
                                "detector_type": self._detector_type,
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
                                "detector_type": self._detector_type,
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
                        record_pipeline_error(f"{self._detector_type}_asyncio_timeout")
                        logger.error(
                            f"Detector asyncio timeout after {self._max_retries} attempts: "
                            f"request timed out after {explicit_timeout}s",
                            extra={
                                "detector_type": self._detector_type,
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
                                    "detector_type": self._detector_type,
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
                            record_pipeline_error(f"{self._detector_type}_server_error")
                            logger.error(
                                "Detector server error after all attempts",
                                extra={
                                    "detector_type": self._detector_type,
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

                        record_pipeline_error(f"{self._detector_type}_client_error")
                        logger.error(
                            "Detector client error",
                            extra={
                                "detector_type": self._detector_type,
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
                                "detector_type": self._detector_type,
                                "camera_id": camera_id,
                                "file_path": image_path,
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_delay": delay,
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error(f"{self._detector_type}_json_error")
                        logger.error(
                            f"Detector JSON/value error after {self._max_retries} attempts: "
                            f"{sanitize_error(e)}",
                            extra={
                                "detector_type": self._detector_type,
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
                                "detector_type": self._detector_type,
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
                        record_pipeline_error(f"{self._detector_type}_unexpected_error")
                        logger.error(
                            "Unexpected detector error after all attempts",
                            extra={
                                "detector_type": self._detector_type,
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

    async def segment_image(
        self,
        image_data: bytes,
        image_name: str = "image.jpg",
    ) -> dict[str, Any]:
        """Send segmentation request to YOLO26 service (NEM-3912).

        Performs instance segmentation on an image, returning both bounding boxes
        and segmentation masks for detected objects.

        Args:
            image_data: Raw image bytes to send
            image_name: Filename for the multipart upload

        Returns:
            Parsed JSON response with segmentation results:
            {
                "detections": [
                    {
                        "class": "person",
                        "confidence": 0.95,
                        "bbox": {"x": 100, "y": 150, "width": 200, "height": 400},
                        "mask_rle": {"counts": [...], "size": [height, width]},
                        "mask_polygon": [[x1, y1, x2, y2, ...], ...]
                    }
                ],
                "inference_time_ms": 45.2,
                "image_width": 640,
                "image_height": 480
            }

        Raises:
            DetectorUnavailableError: If segmentation request fails
        """
        last_exception: Exception | None = None
        semaphore = self._get_semaphore()
        settings = get_settings()
        explicit_timeout = self._read_timeout + settings.ai_connect_timeout

        with trace_span(
            f"{self._detector_type}_segmentation_request",
            image_size_bytes=len(image_data),
        ) as span:
            AIModelAttributes.set_on_span(
                span,
                model_name=self._detector_type,
                model_version=self._model_version,
                model_provider="huggingface",
                device="cuda:0",
                batch_size=1,
            )

            for attempt in range(self._max_retries):
                span.set_attribute("retry_attempt", attempt)
                try:
                    async with semaphore:
                        start_time = time.monotonic()
                        async with asyncio.timeout(explicit_timeout):
                            files = {"file": (image_name, image_data, "image/jpeg")}
                            response = await self._http_client.post(
                                f"{self._detector_url}/segment",
                                files=files,
                                headers=self._get_auth_headers(),
                            )
                            response.raise_for_status()
                            result: dict[str, Any] = response.json()
                            inference_time_ms = (time.monotonic() - start_time) * 1000

                            detections = result.get("detections", [])
                            set_detection_attributes(
                                span,
                                detections=detections,
                                inference_time_ms=inference_time_ms,
                            )
                            set_inference_result_attributes(
                                span, duration_ms=inference_time_ms, status="success"
                            )
                            return result

                except (
                    httpx.ConnectError,
                    httpx.ReadTimeout,
                    httpx.WriteTimeout,
                    TimeoutError,
                ) as e:
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = min(2**attempt, 30)
                        logger.warning(
                            f"Segmentation request failed (attempt {attempt + 1}/{self._max_retries}), "
                            f"retrying in {delay}s: {sanitize_error(e)}",
                        )
                        await asyncio.sleep(delay)
                    else:
                        record_pipeline_error(f"{self._detector_type}_segmentation_error")
                        logger.error(
                            f"Segmentation failed after {self._max_retries} attempts",
                            exc_info=True,
                        )

                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    if status_code >= 500:
                        last_exception = e
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error(
                                f"{self._detector_type}_segmentation_server_error"
                            )
                    else:
                        raise ValueError(f"Segmentation client error: HTTP {status_code}") from e

            error_msg = f"Segmentation failed after {self._max_retries} attempts"
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

    async def detect_objects(
        self,
        image_path: str,
        camera_id: str,
        session: AsyncSession,
        video_path: str | None = None,
        video_metadata: dict[str, Any] | None = None,
    ) -> list[Detection]:
        """Send image to detector service and store detections.

        Reads the image file, sends it to the configured detector service
        (YOLO26v2 or YOLO26 based on DETECTOR_TYPE setting) with retry logic,
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

        # NEM-3797: Add span event for frame capture start
        add_span_event(
            "frame_capture.start",
            {
                "camera.id": camera_id,
                "file.path": image_path,
                "detector.type": self._detector_type,
            },
        )

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
                    f"Circuit breaker open for {self._detector_type}, rejecting detection request",
                    extra={
                        "detector_type": self._detector_type,
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "circuit_state": self._circuit_breaker.state.value,
                    },
                )
                record_pipeline_error("circuit_breaker_open")
                raise DetectorUnavailableError(
                    f"{self._detector_type} service temporarily unavailable (circuit breaker open)"
                )

            # Read image file asynchronously to avoid blocking the event loop
            image_data = await asyncio.to_thread(image_file.read_bytes)

            # NEM-3797: Add span event for frame capture complete
            add_span_event(
                "frame_capture.complete",
                {
                    "camera.id": camera_id,
                    "frame.size_bytes": len(image_data),
                },
            )

            # Buffer frame for X-CLIP temporal action recognition (NEM-3334)
            # This enables the enrichment pipeline to access recent frames for
            # action classification (e.g., loitering, approaching_door, running_away)
            if self._frame_buffer is not None:
                frame_timestamp = datetime.now(UTC)
                await self._frame_buffer.add_frame(camera_id, image_data, frame_timestamp)
                logger.debug(
                    f"Buffered frame for camera {camera_id}",
                    extra={
                        "camera_id": camera_id,
                        "frame_size_bytes": len(image_data),
                        "buffer_count": self._frame_buffer.frame_count(camera_id),
                    },
                )

            # Track AI request time separately
            ai_start_time = time.time()

            # Acquire shared AI inference semaphore (NEM-1463)
            # This limits concurrent AI operations to prevent GPU/service overload
            inference_semaphore = get_inference_semaphore()
            async with inference_semaphore:
                # NEM-3797: Add span event for detection inference start
                add_span_event(
                    "detection_inference.start",
                    {
                        "camera.id": camera_id,
                        "detector.type": self._detector_type,
                        "detector.url": self._detector_url,
                    },
                )

                # Send to detector with retry logic (NEM-1343) and circuit breaker (NEM-1724)
                # The circuit breaker tracks failures and opens after threshold is reached
                result = await self._circuit_breaker.call(
                    self._send_detection_request,
                    image_data=image_data,
                    image_name=image_file.name,
                    camera_id=camera_id,
                    image_path=image_path,
                )

            # Record AI request duration with detector type label
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration(self._detector_type, ai_duration)

            # NEM-3797: Add span event for detection inference complete
            detection_count = len(result.get("detections", []))
            add_span_event(
                "detection_inference.complete",
                {
                    "camera.id": camera_id,
                    "detector.type": self._detector_type,
                    "detection.count": detection_count,
                    "inference.duration_ms": int(ai_duration * 1000),
                },
            )

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

            # Extract image dimensions from YOLO response for bbox scaling (NEM-3903)
            # YOLO returns bounding boxes in pixel coordinates relative to the original
            # image dimensions. We store these dimensions so the enrichment pipeline
            # can properly scale bboxes if the image is later loaded at a different resolution.
            response_image_width = result.get("image_width")
            response_image_height = result.get("image_height")

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
                    elif isinstance(bbox, list | tuple) and len(bbox) == 4:
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
                    else:
                        # NEM-3903: Store image dimensions for bbox scaling in enrichment
                        # This ensures bounding boxes can be properly scaled when the image
                        # is loaded at a different resolution during enrichment processing.
                        # Uses the same video_width/video_height fields for consistency.
                        if response_image_width is not None:
                            detection.video_width = response_image_width
                        if response_image_height is not None:
                            detection.video_height = response_image_height

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

            # Update camera's last_seen_at timestamp when image is processed (NEM-3268)
            # This reflects when the camera last sent an image, regardless of detections
            camera = await session.get(Camera, camera_id)
            if camera:
                camera.last_seen_at = detected_at
                logger.debug(
                    f"Updated camera {camera_id} last_seen_at to {detected_at}",
                    extra={"camera_id": camera_id, "last_seen_at": detected_at.isoformat()},
                )

            # Commit to database
            if detections:
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

            # Commit camera.last_seen_at update and any detections (NEM-3268)
            await session.commit()
            duration_ms = int((time.time() - start_time) * 1000)

            if detections:
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
                f"Circuit breaker open for {self._detector_type}",
                extra={
                    "detector_type": self._detector_type,
                    "camera_id": camera_id,
                    "file_path": image_path,
                    "duration_ms": duration_ms,
                    "circuit_state": self._circuit_breaker.state.value,
                    "error": str(e),
                },
            )
            raise DetectorUnavailableError(
                f"{self._detector_type} service temporarily unavailable (circuit breaker open)",
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
            record_pipeline_error(f"{self._detector_type}_unexpected_error")
            logger.error(
                "Unexpected error during object detection",
                extra={
                    "detector_type": self._detector_type,
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
