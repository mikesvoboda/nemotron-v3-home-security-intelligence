"""Face detection service using YOLO11.

This service detects faces within person bounding box regions,
cropping the upper portion of person detections and running YOLO11
face detection to find faces.

The module is designed for async operation with model inference running
in a thread pool to avoid blocking the event loop.

Error Handling:
    This module uses a best-effort approach, returning empty lists on failure.
    All errors are logged but do not raise exceptions, allowing the pipeline
    to continue processing other detections.

Metrics (NEM-4143):
    - hsi_face_detections_total: Counter of face detections by camera_id and match_status
    - hsi_face_embedding_duration_seconds: Histogram of embedding generation time
    - hsi_face_recognition_confidence: Histogram of recognition confidence scores

Example:
    faces = await detect_faces(model, person_detections, images)
    if faces:
        for face in faces:
            print(f"Face at {face.bbox} with confidence {face.confidence}")
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_face_embedding_duration,
    observe_face_recognition_confidence,
    record_face_detection,
)

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = get_logger(__name__)


@dataclass(slots=True)
class FaceDetection:
    """Detected face information.

    Attributes:
        bbox: Bounding box in original image coordinates (x1, y1, x2, y2)
        confidence: Detection confidence score (0.0 to 1.0)
        person_detection_id: ID of the parent person detection
    """

    bbox: tuple[float, float, float, float]
    confidence: float
    person_detection_id: int | None = None


@dataclass(slots=True)
class PersonDetection:
    """Person detection information for face detection.

    Attributes:
        id: Detection ID in database (optional)
        bbox_x: Top-left x coordinate
        bbox_y: Top-left y coordinate
        bbox_width: Bounding box width
        bbox_height: Bounding box height
        file_path: Path to the source image
    """

    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    file_path: str
    id: int | None = None


# Fraction of person bbox height to use for head region (top portion)
HEAD_REGION_RATIO = 0.4


def _get_head_region(
    person_bbox: tuple[int, int, int, int],
    head_ratio: float = HEAD_REGION_RATIO,
) -> tuple[int, int, int, int]:
    """Extract the upper portion of a person bounding box for head detection.

    The head/face is typically in the top 40% of a standing person's bbox.

    Args:
        person_bbox: Person bounding box as (x, y, width, height)
        head_ratio: Fraction of height to use (default 0.4 = 40%)

    Returns:
        Head region as (x, y, width, height)
    """
    x, y, w, h = person_bbox

    # Calculate head region height
    head_h = int(h * head_ratio)

    return (x, y, w, head_h)


def _crop_bbox_with_padding(
    image: PILImage,
    bbox: tuple[int, int, int, int],
    padding: float = 0.2,
) -> PILImage:
    """Crop image to bounding box with optional padding.

    Args:
        image: PIL Image to crop
        bbox: Bounding box as (x, y, width, height)
        padding: Padding ratio to add around bbox (0.2 = 20%)

    Returns:
        Cropped PIL Image
    """
    img_w, img_h = image.size
    x, y, w, h = bbox

    # Calculate padded coordinates
    pad_w = int(w * padding)
    pad_h = int(h * padding)

    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(img_w, x + w + pad_w)
    y2 = min(img_h, y + h + pad_h)

    return image.crop((x1, y1, x2, y2))


def _convert_crop_bbox_to_original(
    crop_bbox_normalized: list[float],
    original_bbox: tuple[int, int, int, int],
    crop_size: tuple[int, int],
    image_size: tuple[int, int],
    padding: float = 0.2,
) -> tuple[float, float, float, float]:
    """Convert bounding box from crop coordinates to original image coordinates.

    Args:
        crop_bbox_normalized: Normalized bbox from model (x1, y1, x2, y2) in [0,1]
        original_bbox: Original head bbox (x, y, width, height)
        crop_size: Size of the cropped image (width, height)
        image_size: Size of original image (width, height)
        padding: Padding ratio used when cropping

    Returns:
        Bounding box in original image coordinates (x1, y1, x2, y2)
    """
    orig_x, orig_y, orig_w, orig_h = original_bbox
    crop_w, crop_h = crop_size
    img_w, img_h = image_size

    # Calculate the actual crop region (with padding applied)
    pad_w = int(orig_w * padding)
    pad_h = int(orig_h * padding)

    crop_x1 = max(0, orig_x - pad_w)
    crop_y1 = max(0, orig_y - pad_h)

    # Convert normalized coordinates to absolute in crop space
    x1_crop = crop_bbox_normalized[0] * crop_w
    y1_crop = crop_bbox_normalized[1] * crop_h
    x2_crop = crop_bbox_normalized[2] * crop_w
    y2_crop = crop_bbox_normalized[3] * crop_h

    # Convert to original image coordinates
    x1_orig = crop_x1 + x1_crop
    y1_orig = crop_y1 + y1_crop
    x2_orig = crop_x1 + x2_crop
    y2_orig = crop_y1 + y2_crop

    # Clamp to image bounds
    x1_orig = max(0, min(img_w, x1_orig))
    y1_orig = max(0, min(img_h, y1_orig))
    x2_orig = max(0, min(img_w, x2_orig))
    y2_orig = max(0, min(img_h, y2_orig))

    return (x1_orig, y1_orig, x2_orig, y2_orig)


def _load_image_sync(path: Path) -> PILImage:
    """Load an image file synchronously.

    This is a helper function that should be called via asyncio.to_thread()
    to avoid blocking the event loop.

    Args:
        path: Path object to the image file

    Returns:
        PIL Image in RGB format
    """
    return Image.open(path).convert("RGB")


def _run_face_detection_sync(
    model: Any,
    image_crop: PILImage,
    confidence_threshold: float = 0.3,
) -> list[tuple[list[float], float]]:
    """Run face detection synchronously (for thread pool execution).

    Args:
        model: Loaded YOLO face detection model
        image_crop: Cropped PIL Image of head region
        confidence_threshold: Minimum confidence for detections

    Returns:
        List of (normalized_bbox, confidence) tuples
    """
    try:
        # Run inference
        predictions = model.predict(image_crop, verbose=False, conf=confidence_threshold)

        results = []
        if predictions and len(predictions) > 0:
            for pred in predictions[0].boxes:
                # Get normalized bounding box (xyxyn format)
                bbox_norm = pred.xyxyn[0].tolist()
                conf = float(pred.conf[0])
                results.append((bbox_norm, conf))

        return results
    except Exception as e:
        logger.warning(f"Face detection inference failed: {e}")
        return []


async def detect_faces(
    model: Any,
    person_detections: list[PersonDetection],
    images: dict[str, PILImage] | None = None,
    confidence_threshold: float = 0.3,
    head_ratio: float = HEAD_REGION_RATIO,
    padding: float = 0.2,
    camera_id: str | None = None,
) -> list[FaceDetection]:
    """Detect faces in person regions.

    Crops the upper portion (head region) of each person bounding box,
    runs YOLO11 face detection, and returns face detections with
    coordinates converted back to the original image space.

    Args:
        model: Loaded YOLO11 face detection model
        person_detections: List of person detections to process
        images: Optional dict mapping file_path -> PIL Image for caching.
                If not provided, images are loaded from disk.
        confidence_threshold: Minimum confidence for face detections
        head_ratio: Fraction of person bbox height for head region (default 0.4)
        padding: Padding ratio to add around head bbox (0.2 = 20%)
        camera_id: Optional camera ID for metrics labeling

    Returns:
        List of FaceDetection objects for detected faces.
        Returns empty list on any error.
    """
    if not person_detections:
        return []

    if model is None:
        logger.warning("No face detection model provided, skipping")
        return []

    results: list[FaceDetection] = []
    loaded_images: dict[str, PILImage] = images.copy() if images else {}
    effective_camera_id = camera_id or "unknown"

    for detection in person_detections:
        try:
            # Get or load the image
            file_path = detection.file_path
            if file_path not in loaded_images:
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"Image not found for face detection: {file_path}")
                    continue
                # Load image synchronously - this is a fast operation for cached filesystems
                # and image loading is already performed before entering the detection loop
                # when the caller provides pre-loaded images. For uncached file loading,
                # the subsequent inference call via asyncio.to_thread will release the GIL.
                loaded_images[file_path] = _load_image_sync(path)

            image = loaded_images[file_path]
            img_w, img_h = image.size

            # Get head region (upper portion of person bbox)
            person_bbox = (
                detection.bbox_x,
                detection.bbox_y,
                detection.bbox_width,
                detection.bbox_height,
            )
            head_bbox = _get_head_region(person_bbox, head_ratio)

            # Crop head region with padding
            crop = _crop_bbox_with_padding(image, head_bbox, padding)
            crop_size = crop.size

            # Run inference in thread pool with timing for metrics (NEM-4143)
            start_time = time.perf_counter()
            face_results = await asyncio.to_thread(
                _run_face_detection_sync,
                model,
                crop,
                confidence_threshold,
            )
            inference_duration = time.perf_counter() - start_time

            # Record embedding/inference duration metric
            observe_face_embedding_duration(effective_camera_id, inference_duration)

            # Convert results to FaceDetection objects and record metrics
            for bbox_norm, conf in face_results:
                original_bbox = _convert_crop_bbox_to_original(
                    bbox_norm,
                    head_bbox,
                    crop_size,
                    (img_w, img_h),
                    padding,
                )
                results.append(
                    FaceDetection(
                        bbox=original_bbox,
                        confidence=conf,
                        person_detection_id=detection.id,
                    )
                )

                # Record face detection metric (match_status is "unknown" at detection time,
                # will be updated to "known" by face recognition service if matched)
                record_face_detection(effective_camera_id, "unknown")

                # Record confidence score metric
                observe_face_recognition_confidence(effective_camera_id, conf)

            logger.debug(
                f"Detected {len(face_results)} faces in person detection "
                f"{detection.id} from {file_path} (took {inference_duration * 1000:.1f}ms)"
            )

        except Exception as e:
            logger.warning(
                f"Failed to detect faces in person detection {detection.id}: {e}",
                exc_info=True,
            )
            continue

    logger.info(
        f"Face detection complete: {len(results)} faces found in {len(person_detections)} persons"
    )
    return results


def is_person_class(object_type: str) -> bool:
    """Check if an object type is a person.

    Args:
        object_type: The detected object class name

    Returns:
        True if the object type is a person
    """
    return object_type.lower() == "person"
