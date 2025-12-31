"""Detector client service for RT-DETRv2 object detection.

This service provides an HTTP client interface to the RT-DETRv2 detection server,
sending images for object detection and storing results in the database.

Detection Flow:
    1. Read image file from filesystem
    2. POST to detector server with image data
    3. Parse JSON response with detections
    4. Filter by confidence threshold
    5. Store detections in database
    6. Return Detection model instances

Error Handling:
    - Connection errors: Raise DetectorUnavailableError (allows retry)
    - Timeouts: Raise DetectorUnavailableError (allows retry)
    - HTTP 5xx errors: Raise DetectorUnavailableError (allows retry)
    - HTTP 4xx errors: Log and return empty list (client error, no retry)
    - Invalid JSON: Log and return empty list (malformed response)
    - Missing files: Log and return empty list (local file issue)
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    record_detection_processed,
    record_pipeline_error,
)
from backend.core.mime_types import get_mime_type_with_default
from backend.models.detection import Detection

logger = get_logger(__name__)

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

    Security: Supports API key authentication via X-API-Key header when
    configured in settings (RTDETR_API_KEY environment variable).
    """

    def __init__(self) -> None:
        """Initialize detector client with configuration."""
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

    async def detect_objects(  # noqa: PLR0912
        self,
        image_path: str,
        camera_id: str,
        session: AsyncSession,
        video_path: str | None = None,
        video_metadata: dict[str, Any] | None = None,
    ) -> list[Detection]:
        """Send image to detector service and store detections.

        Reads the image file, sends it to the RT-DETRv2 service, parses
        the response, filters by confidence threshold, and stores detections
        in the database.

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

        logger.debug(
            f"Sending detection request for {image_path}",
            extra={"camera_id": camera_id, "file_path": image_path},
        )

        try:
            # Read image file
            image_data = image_file.read_bytes()

            # Track AI request time separately
            ai_start_time = time.time()

            # Send to detector with authentication if configured
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                files = {"file": (image_file.name, image_data, "image/jpeg")}
                response = await client.post(
                    f"{self._detector_url}/detect",
                    files=files,
                    headers=self._get_auth_headers(),
                )
                response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("rtdetr", ai_duration)

            # Parse response
            result = response.json()

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

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_connection_error")
            logger.error(
                f"Failed to connect to detector service: {e}",
                extra={"camera_id": camera_id, "file_path": image_path, "duration_ms": duration_ms},
                exc_info=True,
            )
            # Raise exception to signal retry is needed
            raise DetectorUnavailableError(
                f"Failed to connect to detector service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_timeout")
            logger.error(
                f"Detector request timed out: {e}",
                extra={"camera_id": camera_id, "file_path": image_path, "duration_ms": duration_ms},
                exc_info=True,
            )
            # Raise exception to signal retry is needed
            raise DetectorUnavailableError(
                f"Detector request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            # 5xx errors are server-side failures that should be retried
            if status_code >= 500:
                record_pipeline_error("rtdetr_server_error")
                logger.error(
                    f"Detector returned server error: {status_code} - {e}",
                    extra={
                        "camera_id": camera_id,
                        "file_path": image_path,
                        "duration_ms": duration_ms,
                        "status_code": status_code,
                    },
                    exc_info=True,
                )
                raise DetectorUnavailableError(
                    f"Detector returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.) - don't retry
            record_pipeline_error("rtdetr_client_error")
            logger.error(
                f"Detector returned client error: {status_code} - {e}",
                extra={
                    "camera_id": camera_id,
                    "file_path": image_path,
                    "duration_ms": duration_ms,
                    "status_code": status_code,
                },
                exc_info=True,
            )
            return []

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_unexpected_error")
            logger.error(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                extra={"camera_id": camera_id, "duration_ms": duration_ms},
                exc_info=True,
            )
            # For unexpected errors, also raise to allow retry
            # This could be network issues, DNS failures, etc.
            raise DetectorUnavailableError(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                original_error=e,
            ) from e
