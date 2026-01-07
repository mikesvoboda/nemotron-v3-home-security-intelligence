"""OCR service for reading text from license plates using PaddleOCR.

This service provides text recognition functionality specifically optimized
for reading license plate text from cropped plate images.

The module is designed for async operation with OCR inference running
in a thread pool to avoid blocking the event loop.

Error Handling:
    This module uses a best-effort approach, returning empty lists on failure.
    All errors are logged but do not raise exceptions, allowing the pipeline
    to continue processing other plates.

Example:
    plate_texts = await read_plates(ocr_model, plate_detections, images)
    for text in plate_texts:
        print(f"Plate text: {text.text} (confidence: {text.confidence})")
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from backend.core.logging import get_logger
from backend.services.plate_detector import PlateDetection

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = get_logger(__name__)


@dataclass
class PlateText:
    """Recognized license plate text.

    Attributes:
        text: Cleaned/normalized plate text
        raw_text: Original OCR output before cleaning
        confidence: OCR confidence score (0.0 to 1.0)
        plate_detection_id: Reference to the source plate detection
        bbox: Bounding box of the plate in original image coordinates
    """

    text: str
    confidence: float
    plate_detection_id: int | None = None
    raw_text: str | None = None
    bbox: tuple[float, float, float, float] | None = None


# Regex for cleaning plate text - keep only alphanumeric characters
_PLATE_TEXT_PATTERN = re.compile(r"[^A-Z0-9]")


def clean_plate_text(text: str) -> str | None:
    """Clean and normalize license plate text.

    Removes spaces, dashes, and non-alphanumeric characters,
    converts to uppercase for consistent matching.

    Args:
        text: Raw OCR text output

    Returns:
        Cleaned plate text, or None if result is too short (<2 chars)
    """
    if not text:
        return None

    # Convert to uppercase and remove non-alphanumeric characters
    cleaned = text.upper().strip()
    cleaned = _PLATE_TEXT_PATTERN.sub("", cleaned)

    # License plates typically have at least 2-3 characters
    if len(cleaned) < 2:
        return None

    return cleaned


def _crop_plate_region(
    image: PILImage,
    bbox: tuple[float, float, float, float],
    padding: float = 0.05,
) -> PILImage:
    """Crop image to plate bounding box with minimal padding.

    Args:
        image: PIL Image containing the plate
        bbox: Plate bounding box (x1, y1, x2, y2)
        padding: Small padding ratio to ensure full plate capture

    Returns:
        Cropped PIL Image of plate region
    """
    img_w, img_h = image.size
    x1, y1, x2, y2 = bbox

    # Calculate padding
    w = x2 - x1
    h = y2 - y1
    pad_w = int(w * padding)
    pad_h = int(h * padding)

    # Apply padding with bounds checking
    x1 = max(0, int(x1) - pad_w)
    y1 = max(0, int(y1) - pad_h)
    x2 = min(img_w, int(x2) + pad_w)
    y2 = min(img_h, int(y2) + pad_h)

    return image.crop((x1, y1, x2, y2))


def _run_ocr_sync(
    ocr_model: Any,
    plate_crop: PILImage,
) -> tuple[str | None, float]:
    """Run OCR synchronously (for thread pool execution).

    Args:
        ocr_model: Loaded PaddleOCR model
        plate_crop: Cropped PIL Image of plate region

    Returns:
        Tuple of (extracted_text, average_confidence)
    """
    try:
        # Convert PIL Image to numpy array for PaddleOCR
        plate_array = np.array(plate_crop)

        # Run OCR - cls=True enables text direction classification
        result = ocr_model.ocr(plate_array, cls=True)

        if not result or not result[0]:
            return None, 0.0

        # Extract text and confidence from results
        # PaddleOCR returns: [[[box], (text, confidence)], ...]
        texts = []
        confidences = []

        for line in result[0]:
            if len(line) >= 2 and isinstance(line[1], (list, tuple)):
                text = line[1][0] if len(line[1]) > 0 else ""
                conf = line[1][1] if len(line[1]) > 1 else 0.0
                if text:
                    texts.append(text)
                    confidences.append(conf)

        if not texts:
            return None, 0.0

        # Combine all detected text
        combined_text = " ".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return combined_text, avg_confidence

    except Exception as e:
        logger.warning(f"OCR inference failed: {e}")
        return None, 0.0


def _find_image_for_plate(
    image_paths: list[str] | None,
    loaded_images: dict[str, PILImage],
) -> PILImage | None:
    """Find an image for plate OCR from available sources.

    Args:
        image_paths: List of potential image paths to search
        loaded_images: Dict of already loaded images

    Returns:
        PIL Image if found, None otherwise
    """
    # Try image_paths first
    if image_paths:
        for path in image_paths:
            if path in loaded_images:
                return loaded_images[path]
            path_obj = Path(path)
            if path_obj.exists():
                loaded_images[path] = Image.open(path_obj).convert("RGB")
                return loaded_images[path]

    # Fall back to any pre-loaded image
    if loaded_images:
        return next(iter(loaded_images.values()))

    return None


async def read_plates(
    ocr_model: Any,
    plate_detections: list[PlateDetection],
    images: dict[str, PILImage] | None = None,
    image_paths: list[str] | None = None,
    min_confidence: float = 0.5,
) -> list[PlateText]:
    """Read text from detected license plates using OCR.

    Crops each plate region and runs PaddleOCR to extract the plate text.
    Text is cleaned and normalized for consistent matching.

    Args:
        ocr_model: Loaded PaddleOCR model instance
        plate_detections: List of plate detections with bounding boxes
        images: Optional dict mapping file_path -> PIL Image for caching.
                Used if plate detections reference file paths.
        image_paths: Optional list of image paths corresponding to detections.
                    Used to find the correct image for each plate.
        min_confidence: Minimum OCR confidence to include result

    Returns:
        List of PlateText objects with recognized text.
        Returns empty list on any error.
    """
    if not plate_detections:
        return []

    if ocr_model is None:
        logger.warning("No OCR model provided, skipping plate text recognition")
        return []

    results: list[PlateText] = []
    loaded_images: dict[str, PILImage] = images.copy() if images else {}

    for plate in plate_detections:
        try:
            # Find the image for this plate
            image = _find_image_for_plate(image_paths, loaded_images)
            if image is None:
                logger.warning(
                    f"No image available for plate detection {plate.vehicle_detection_id}"
                )
                continue

            # Crop plate region
            plate_crop = _crop_plate_region(image, plate.bbox)

            # Run OCR in thread pool
            raw_text, confidence = await asyncio.to_thread(
                _run_ocr_sync,
                ocr_model,
                plate_crop,
            )

            if raw_text is None or confidence < min_confidence:
                logger.debug(
                    f"OCR result below threshold for plate "
                    f"{plate.vehicle_detection_id}: "
                    f"text='{raw_text}', conf={confidence:.2f}"
                )
                continue

            # Clean the plate text
            cleaned_text = clean_plate_text(raw_text)
            if cleaned_text is None:
                logger.debug(
                    f"Cleaned plate text too short for plate "
                    f"{plate.vehicle_detection_id}: raw='{raw_text}'"
                )
                continue

            results.append(
                PlateText(
                    text=cleaned_text,
                    raw_text=raw_text,
                    confidence=confidence,
                    plate_detection_id=plate.vehicle_detection_id,
                    bbox=plate.bbox,
                )
            )

            logger.debug(
                f"OCR read plate text '{cleaned_text}' (raw: '{raw_text}', conf: {confidence:.2f})"
            )

        except Exception as e:
            logger.warning(
                f"Failed to OCR plate {plate.vehicle_detection_id}: {e}",
                exc_info=True,
            )
            continue

    logger.info(f"OCR complete: read {len(results)} plates from {len(plate_detections)} detections")
    return results


async def read_single_plate(
    ocr_model: Any,
    plate_image: PILImage,
    min_confidence: float = 0.5,
) -> PlateText | None:
    """Read text from a single plate image.

    Convenience function for OCR on a pre-cropped plate image.

    Args:
        ocr_model: Loaded PaddleOCR model instance
        plate_image: Pre-cropped PIL Image of the license plate
        min_confidence: Minimum OCR confidence to return result

    Returns:
        PlateText object if text was recognized, None otherwise
    """
    if ocr_model is None:
        logger.warning("No OCR model provided")
        return None

    try:
        raw_text, confidence = await asyncio.to_thread(
            _run_ocr_sync,
            ocr_model,
            plate_image,
        )

        if raw_text is None or confidence < min_confidence:
            return None

        cleaned_text = clean_plate_text(raw_text)
        if cleaned_text is None:
            return None

        return PlateText(
            text=cleaned_text,
            raw_text=raw_text,
            confidence=confidence,
        )

    except Exception as e:
        logger.warning(f"Single plate OCR failed: {e}", exc_info=True)
        return None
