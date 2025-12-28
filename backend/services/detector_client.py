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
    - Connection errors: Log and return empty list
    - Timeouts: Log and return empty list
    - HTTP errors: Log and return empty list
    - Invalid JSON: Log and return empty list
    - Missing files: Log and return empty list
"""

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    record_detection_processed,
    record_pipeline_error,
)
from backend.models.detection import Detection

logger = get_logger(__name__)


class DetectorClient:
    """Client for interacting with RT-DETRv2 object detection service.

    This client handles communication with the external detector service,
    including health checks, image submission, and response parsing.
    """

    def __init__(self) -> None:
        """Initialize detector client with configuration."""
        settings = get_settings()
        self._detector_url = settings.rtdetr_url
        self._confidence_threshold = settings.detection_confidence_threshold
        self._timeout = 30.0  # 30 second timeout

    async def health_check(self) -> bool:
        """Check if detector service is healthy and reachable.

        Returns:
            True if detector is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._detector_url}/health")
                response.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Detector health check failed: {e}")
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"Detector health check returned error status: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during detector health check: {sanitize_error(e)}")
            return False

    async def detect_objects(  # noqa: PLR0911, PLR0912
        self,
        image_path: str,
        camera_id: str,
        session: AsyncSession,
    ) -> list[Detection]:
        """Send image to detector service and store detections.

        Reads the image file, sends it to the RT-DETRv2 service, parses
        the response, filters by confidence threshold, and stores detections
        in the database.

        Args:
            image_path: Path to the image file
            camera_id: Camera identifier for the image
            session: Database session for storing detections

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

            # Send to detector
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                files = {"file": (image_file.name, image_data, "image/jpeg")}
                response = await client.post(
                    f"{self._detector_url}/detect",
                    files=files,
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
            file_type = image_file.suffix
            detected_at = datetime.now(UTC)

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

                    # Create Detection model
                    detection = Detection(
                        camera_id=camera_id,
                        file_path=image_path,
                        file_type=file_type,
                        detected_at=detected_at,
                        object_type=detection_data.get("class"),
                        confidence=confidence,
                        bbox_x=bbox_x,
                        bbox_y=bbox_y,
                        bbox_width=bbox_width,
                        bbox_height=bbox_height,
                    )

                    session.add(detection)
                    detections.append(detection)

                    logger.debug(
                        f"Created detection: {detection.object_type} "
                        f"(confidence: {confidence:.2f}, bbox: {bbox})"
                    )

                except Exception as e:
                    logger.error(f"Error processing detection data: {sanitize_error(e)}")
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
            )
            return []

        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_timeout")
            logger.error(
                f"Detector request timed out: {e}",
                extra={"camera_id": camera_id, "file_path": image_path, "duration_ms": duration_ms},
            )
            return []

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_http_error")
            logger.error(
                f"Detector returned HTTP error: {e.response.status_code} - {e}",
                extra={"camera_id": camera_id, "file_path": image_path, "duration_ms": duration_ms},
            )
            return []

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("rtdetr_unexpected_error")
            logger.error(
                f"Unexpected error during object detection: {sanitize_error(e)}",
                extra={"camera_id": camera_id, "duration_ms": duration_ms},
            )
            return []
