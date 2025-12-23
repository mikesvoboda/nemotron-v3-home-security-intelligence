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

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.models.detection import Detection

logger = logging.getLogger(__name__)


class DetectorClient:
    """Client for interacting with RT-DETRv2 object detection service.

    This client handles communication with the external detector service,
    including health checks, image submission, and response parsing.
    """

    def __init__(self):
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
            logger.error(f"Unexpected error during detector health check: {e}", exc_info=True)
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
        # Validate image file exists
        image_file = Path(image_path)
        if not image_file.exists():
            logger.error(f"Image file not found: {image_path}")
            return []

        try:
            # Read image file
            image_data = image_file.read_bytes()

            # Send to detector
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                files = {"file": (image_file.name, image_data, "image/jpeg")}
                response = await client.post(
                    f"{self._detector_url}/detect",
                    files=files,
                )
                response.raise_for_status()

            # Parse response
            result = response.json()

            if "detections" not in result:
                logger.warning(f"Malformed response from detector (missing 'detections'): {result}")
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
                    bbox = detection_data.get("bbox", [])
                    if len(bbox) != 4:
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
                        bbox_x=int(bbox[0]),
                        bbox_y=int(bbox[1]),
                        bbox_width=int(bbox[2]),
                        bbox_height=int(bbox[3]),
                    )

                    session.add(detection)
                    detections.append(detection)

                    logger.debug(
                        f"Created detection: {detection.object_type} "
                        f"(confidence: {confidence:.2f}, bbox: {bbox})"
                    )

                except Exception as e:
                    logger.error(f"Error processing detection data: {e}", exc_info=True)
                    continue

            # Commit to database
            if detections:
                await session.commit()
                logger.info(
                    f"Stored {len(detections)} detections for {camera_id} from {image_path}"
                )
            else:
                logger.debug(f"No detections above threshold for {image_path}")

            return detections

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to detector service: {e}")
            return []

        except httpx.TimeoutException as e:
            logger.error(f"Detector request timed out: {e}")
            return []

        except httpx.HTTPStatusError as e:
            logger.error(f"Detector returned HTTP error: {e.response.status_code} - {e}")
            return []

        except Exception as e:
            logger.error(f"Unexpected error during object detection: {e}", exc_info=True)
            return []
