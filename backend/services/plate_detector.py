"""License plate detection service using YOLO11.

This service detects license plates in vehicle bounding box regions,
cropping vehicle areas and running YOLO11 detection to find plates.

The module is designed for async operation with model inference running
in a thread pool to avoid blocking the event loop.

Error Handling:
    This module uses a best-effort approach, returning empty lists on failure.
    All errors are logged but do not raise exceptions, allowing the pipeline
    to continue processing other detections.

Example:
    plates = await detect_plates(model, vehicle_detections, images)
    if plates:
        # Process detected plates
        for plate in plates:
            print(f"Plate at {plate.bbox} with confidence {plate.confidence}")
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = get_logger(__name__)


@dataclass(slots=True)
class PlateDetection:
    """Detected license plate information.

    Attributes:
        bbox: Bounding box in original image coordinates (x1, y1, x2, y2)
        confidence: Detection confidence score (0.0 to 1.0)
        vehicle_detection_id: ID of the parent vehicle detection
    """

    bbox: tuple[float, float, float, float]
    confidence: float
    vehicle_detection_id: int | None = None


@dataclass(slots=True)
class VehicleDetection:
    """Vehicle detection information for plate detection.

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


# Vehicle classes from COCO dataset that may contain license plates
VEHICLE_CLASSES = frozenset({"car", "truck", "bus", "motorcycle"})


def _crop_bbox_with_padding(
    image: PILImage,
    bbox: tuple[int, int, int, int],
    padding: float = 0.1,
) -> PILImage:
    """Crop image to bounding box with optional padding.

    Args:
        image: PIL Image to crop
        bbox: Bounding box as (x, y, width, height)
        padding: Padding ratio to add around bbox (0.1 = 10%)

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
    padding: float = 0.1,
) -> tuple[float, float, float, float]:
    """Convert bounding box from crop coordinates to original image coordinates.

    Args:
        crop_bbox_normalized: Normalized bbox from model (x1, y1, x2, y2) in [0,1]
        original_bbox: Original vehicle bbox (x, y, width, height)
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

    This is a helper function used for fallback image loading when
    images are not provided by the caller.

    Args:
        path: Path object to the image file

    Returns:
        PIL Image in RGB format
    """
    return Image.open(path).convert("RGB")


def _run_plate_detection_sync(
    model: Any,
    image_crop: PILImage,
    confidence_threshold: float = 0.25,
) -> list[tuple[list[float], float]]:
    """Run plate detection synchronously (for thread pool execution).

    Args:
        model: Loaded YOLO model
        image_crop: Cropped PIL Image of vehicle region
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
        logger.warning(f"Plate detection inference failed: {e}")
        return []


async def detect_plates(
    model: Any,
    vehicle_detections: list[VehicleDetection],
    images: dict[str, PILImage] | None = None,
    confidence_threshold: float = 0.25,
    padding: float = 0.1,
) -> list[PlateDetection]:
    """Detect license plates in vehicle regions.

    Crops each vehicle bounding box from its source image, runs YOLO11
    plate detection, and returns plate detections with coordinates
    converted back to the original image space.

    Args:
        model: Loaded YOLO11 license plate detection model
        vehicle_detections: List of vehicle detections to process
        images: Optional dict mapping file_path -> PIL Image for caching.
                If not provided, images are loaded from disk.
        confidence_threshold: Minimum confidence for plate detections
        padding: Padding ratio to add around vehicle bbox (0.1 = 10%)

    Returns:
        List of PlateDetection objects for detected plates.
        Returns empty list on any error.
    """
    if not vehicle_detections:
        return []

    if model is None:
        logger.warning("No plate detection model provided, skipping")
        return []

    results: list[PlateDetection] = []
    loaded_images: dict[str, PILImage] = images.copy() if images else {}

    for detection in vehicle_detections:
        try:
            # Get or load the image
            file_path = detection.file_path
            if file_path not in loaded_images:
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"Image not found for plate detection: {file_path}")
                    continue
                # Load image synchronously - this is a fast operation for cached filesystems
                # and image loading is already performed before entering the detection loop
                # when the caller provides pre-loaded images. For uncached file loading,
                # the subsequent inference call via asyncio.to_thread will release the GIL.
                loaded_images[file_path] = _load_image_sync(path)

            image = loaded_images[file_path]
            img_w, img_h = image.size

            # Crop vehicle region with padding
            bbox = (
                detection.bbox_x,
                detection.bbox_y,
                detection.bbox_width,
                detection.bbox_height,
            )
            crop = _crop_bbox_with_padding(image, bbox, padding)
            crop_size = crop.size

            # Run inference in thread pool
            plate_results = await asyncio.to_thread(
                _run_plate_detection_sync,
                model,
                crop,
                confidence_threshold,
            )

            # Convert results to PlateDetection objects
            for bbox_norm, conf in plate_results:
                original_bbox = _convert_crop_bbox_to_original(
                    bbox_norm,
                    bbox,
                    crop_size,
                    (img_w, img_h),
                    padding,
                )
                results.append(
                    PlateDetection(
                        bbox=original_bbox,
                        confidence=conf,
                        vehicle_detection_id=detection.id,
                    )
                )

            logger.debug(
                f"Detected {len(plate_results)} plates in vehicle detection "
                f"{detection.id} from {file_path}"
            )

        except Exception as e:
            logger.warning(
                f"Failed to detect plates in vehicle detection {detection.id}: {e}",
                exc_info=True,
            )
            continue

    logger.info(
        f"Plate detection complete: {len(results)} plates found in "
        f"{len(vehicle_detections)} vehicles"
    )
    return results


def is_vehicle_class(object_type: str) -> bool:
    """Check if an object type is a vehicle that may have a license plate.

    Args:
        object_type: The detected object class name

    Returns:
        True if the object type is a vehicle
    """
    return object_type.lower() in VEHICLE_CLASSES
