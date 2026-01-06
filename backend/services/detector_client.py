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

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
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
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.baseline import get_baseline_service
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


class DetectorUnavailableError(Exception):
    """Raised when the RT-DETR detector service is unavailable.

    This exception is raised when the detector cannot be reached due to:
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
    # Default: 4 concurrent requests (configurable via ai_max_concurrent_requests)
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
        limit = settings.ai_max_concurrent_requests

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
        self._max_concurrent = settings.ai_max_concurrent_requests
        logger.debug(
            f"DetectorClient initialized with max_retries={self._max_retries}, "
            f"timeout={settings.rtdetr_read_timeout}s, max_concurrent={self._max_concurrent}"
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Security: Returns X-API-Key header if API key is configured.

        Returns:
            Dictionary of headers to include in requests
        """
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    async def health_check(self) -> bool:
        """Check if detector service is healthy and reachable.

        Returns:
            True if detector is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                # Include auth headers in health check
                response = await client.get(
                    f"{self._detector_url}/health",
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Detector health check failed: {e}", exc_info=True)
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"Detector health check returned error status: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error during detector health check: {sanitize_error(e)}", exc_info=True
            )
            return False

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

        for attempt in range(self._max_retries):
            try:
                # Use semaphore to limit concurrent GPU requests (NEM-1500)
                async with semaphore, httpx.AsyncClient(timeout=self._timeout) as client:
                    files = {"file": (image_name, image_data, "image/jpeg")}
                    response = await client.post(
                        f"{self._detector_url}/detect",
                        files=files,
                        headers=self._get_auth_headers(),
                    )
                    response.raise_for_status()
                    result: dict[str, Any] = response.json()
                    return result

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = min(2**attempt, 30)  # Cap at 30 seconds
                    logger.warning(
                        f"Detector connection error (attempt {attempt + 1}/{self._max_retries}), "
                        f"retrying in {delay}s: {e}",
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
                    record_pipeline_error("rtdetr_connection_error")
                    logger.error(
                        f"Detector connection error after {self._max_retries} attempts: {e}",
                        extra={
                            "camera_id": camera_id,
                            "file_path": image_path,
                            "attempts": self._max_retries,
                        },
                        exc_info=True,
                    )

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = min(2**attempt, 30)  # Cap at 30 seconds
                    logger.warning(
                        f"Detector timeout (attempt {attempt + 1}/{self._max_retries}), "
                        f"retrying in {delay}s: {e}",
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
                    record_pipeline_error("rtdetr_timeout")
                    logger.error(
                        f"Detector timeout after {self._max_retries} attempts: {e}",
                        extra={
                            "camera_id": camera_id,
                            "file_path": image_path,
                            "attempts": self._max_retries,
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
                            f"Detector server error {status_code} "
                            f"(attempt {attempt + 1}/{self._max_retries}), "
                            f"retrying in {delay}s",
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
                            f"Detector server error {status_code} after {self._max_retries} attempts",
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
                        except Exception:
                            error_detail = e.response.text[:500] if e.response.text else str(e)

                    record_pipeline_error("rtdetr_client_error")
                    logger.error(
                        f"Detector client error {status_code}: {error_detail or e}",
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

            except Exception as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = min(2**attempt, 30)  # Cap at 30 seconds
                    logger.warning(
                        f"Unexpected detector error (attempt {attempt + 1}/{self._max_retries}), "
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
                    record_pipeline_error("rtdetr_unexpected_error")
                    logger.error(
                        f"Unexpected detector error after {self._max_retries} attempts: "
                        f"{sanitize_error(e)}",
                        extra={
                            "camera_id": camera_id,
                            "file_path": image_path,
                            "attempts": self._max_retries,
                        },
                        exc_info=True,
                    )

        # All retries exhausted
        error_msg = f"Detection failed after {self._max_retries} attempts"
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
                    f"Image too small for detection ({file_size} bytes, "
                    f"minimum {MIN_DETECTION_IMAGE_SIZE}): {image_path}",
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
                f"Image validation failed (corrupt/truncated) {image_path}: {e}",
                extra={"camera_id": camera_id, "file_path": image_path, "error": str(e)},
            )
            return False
        except Exception as e:
            logger.warning(
                f"Image validation failed {image_path}: {sanitize_error(e)}",
                extra={"camera_id": camera_id, "file_path": image_path, "error": str(e)},
            )
            return False

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
        start_time = time.time()

        # Validate image file exists
        image_file = Path(image_path)
        if not image_file.exists():
            logger.error(
                f"Image file not found: {image_path}",
                extra={"camera_id": camera_id, "file_path": image_path},
            )
            record_pipeline_error("file_not_found")
            return []

        # Validate image integrity before sending to detector
        # This catches truncated/corrupt images from incomplete FTP uploads
        if not self._validate_image_for_detection(image_path, camera_id):
            record_pipeline_error("invalid_image")
            return []

        logger.debug(
            f"Sending detection request for {image_path}",
            extra={"camera_id": camera_id, "file_path": image_path},
        )

        try:
            # Read image file
            image_data = image_file.read_bytes()

            # Track AI request time separately
            ai_start_time = time.time()

            # Acquire shared AI inference semaphore (NEM-1463)
            # This limits concurrent AI operations to prevent GPU/service overload
            inference_semaphore = get_inference_semaphore()
            async with inference_semaphore:
                # Send to detector with retry logic (NEM-1343)
                result = await self._send_detection_request(
                    image_data=image_data,
                    image_name=image_file.name,
                    camera_id=camera_id,
                    image_path=image_path,
                )

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("rtdetr", ai_duration)

            if "detections" not in result:
                logger.warning(f"Malformed response from detector (missing 'detections'): {result}")
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

                except Exception as e:
                    logger.error(
                        f"Error processing detection data: {sanitize_error(e)}", exc_info=True
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
                logger.info(
                    f"Stored {len(detections)} detections for {camera_id} from {image_path}",
                    extra={
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "detection_count": len(detections),
                        "duration_ms": duration_ms,
                    },
                )
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
        except DetectorUnavailableError:
            # Transient errors after retry exhaustion - propagate for caller to handle
            raise
        except Exception as e:
            # Catch any other unexpected errors (e.g., file read errors)
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_unexpected_error")
            logger.error(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                extra={"camera_id": camera_id, "duration_ms": duration_ms},
                exc_info=True,
            )
            raise DetectorUnavailableError(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                original_error=e,
            ) from e
