"""Bounding box validation utilities.

This module provides shared bounding box validation, clamping, and error handling
for use across the AI detection and enrichment pipeline.

Bounding Box Format:
    All bounding boxes in this system use the format (x1, y1, x2, y2) where:
    - x1, y1: Top-left corner coordinates
    - x2, y2: Bottom-right corner coordinates

Validation Errors:
    - BoundingBoxValidationError: Base class for bbox validation errors
    - InvalidBoundingBoxError: Raised when bbox has invalid dimensions/coordinates
    - BoundingBoxOutOfBoundsError: Raised when bbox extends beyond image boundaries

Usage:
    from backend.services.bbox_validation import (
        validate_bbox,
        clamp_bbox_to_image,
        is_valid_bbox,
        BoundingBoxValidationError,
    )

    # Validate and raise on error
    validate_bbox(bbox, image_width=640, image_height=480)

    # Get clamped bbox that fits within image
    clamped = clamp_bbox_to_image(bbox, image_width=640, image_height=480)

    # Check validity without raising
    if is_valid_bbox(bbox):
        process(bbox)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import overload

from backend.core.logging import get_logger

logger = get_logger(__name__)


class BoundingBoxValidationError(ValueError):
    """Base exception for bounding box validation errors.

    This exception is raised when a bounding box fails validation checks.
    It provides details about the specific validation failure.
    """

    def __init__(self, message: str, bbox: tuple[float, float, float, float] | None = None):
        """Initialize the error.

        Args:
            message: Human-readable error description
            bbox: The invalid bounding box that caused the error
        """
        super().__init__(message)
        self.bbox = bbox


class InvalidBoundingBoxError(BoundingBoxValidationError):
    """Raised when a bounding box has invalid dimensions or coordinates.

    Examples of invalid bounding boxes:
    - x2 <= x1 (zero or negative width)
    - y2 <= y1 (zero or negative height)
    - Negative coordinates when not allowed
    - NaN or infinite values
    """

    pass


class BoundingBoxOutOfBoundsError(BoundingBoxValidationError):
    """Raised when a bounding box extends beyond image boundaries.

    This error is raised when strict boundary checking is enabled and
    the bounding box coordinates exceed the image dimensions.
    """

    def __init__(
        self,
        message: str,
        bbox: tuple[float, float, float, float] | None = None,
        image_size: tuple[int, int] | None = None,
    ):
        """Initialize the error.

        Args:
            message: Human-readable error description
            bbox: The out-of-bounds bounding box
            image_size: The image dimensions (width, height)
        """
        super().__init__(message, bbox)
        self.image_size = image_size


@dataclass(slots=True)
class BoundingBoxValidationResult:
    """Result of bounding box validation.

    Attributes:
        is_valid: Whether the bounding box is valid
        clamped_bbox: The bounding box clamped to image boundaries (if image_size provided)
        original_bbox: The original input bounding box
        warnings: List of warning messages about the bbox
        was_clamped: Whether the bbox was modified during clamping
        was_empty_after_clamp: Whether the bbox became empty after clamping
    """

    is_valid: bool
    clamped_bbox: tuple[float, float, float, float] | None
    original_bbox: tuple[float, float, float, float]
    warnings: list[str]
    was_clamped: bool = False
    was_empty_after_clamp: bool = False


def is_valid_bbox(
    bbox: tuple[float, float, float, float],
    allow_negative: bool = False,
) -> bool:
    """Check if a bounding box is valid without raising exceptions.

    A bounding box is considered valid if:
    - It has positive width (x2 > x1)
    - It has positive height (y2 > y1)
    - Coordinates are not NaN or infinite
    - Optionally: coordinates are non-negative

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        allow_negative: If False, negative coordinates are invalid

    Returns:
        True if the bounding box is valid, False otherwise
    """
    try:
        x1, y1, x2, y2 = bbox

        # Check for NaN or infinite values
        import math

        if any(math.isnan(v) or math.isinf(v) for v in (x1, y1, x2, y2)):
            return False

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def validate_bbox(
    bbox: tuple[float, float, float, float],
    image_width: int | None = None,
    image_height: int | None = None,
    allow_negative: bool = False,
    strict_bounds: bool = False,
) -> None:
    """Validate a bounding box and raise an exception if invalid.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        image_width: Optional image width for bounds checking
        image_height: Optional image height for bounds checking
        allow_negative: If False, negative coordinates raise InvalidBoundingBoxError
        strict_bounds: If True, bbox extending beyond image raises BoundingBoxOutOfBoundsError

    Raises:
        InvalidBoundingBoxError: If bbox has invalid dimensions or coordinates
        BoundingBoxOutOfBoundsError: If strict_bounds and bbox exceeds image bounds
    """
    import math

    try:
        x1, y1, x2, y2 = bbox
    except (TypeError, ValueError) as e:
        raise InvalidBoundingBoxError(
            f"Invalid bounding box format: {bbox}. Expected (x1, y1, x2, y2)",
            bbox=bbox,
        ) from e

    # Check for NaN or infinite values
    if any(math.isnan(v) or math.isinf(v) for v in (x1, y1, x2, y2)):
        raise InvalidBoundingBoxError(
            f"Bounding box contains NaN or infinite values: {bbox}",
            bbox=bbox,
        )

    # Check for positive dimensions
    if x2 <= x1:
        raise InvalidBoundingBoxError(
            f"Bounding box has zero or negative width: x1={x1}, x2={x2}",
            bbox=bbox,
        )

    if y2 <= y1:
        raise InvalidBoundingBoxError(
            f"Bounding box has zero or negative height: y1={y1}, y2={y2}",
            bbox=bbox,
        )

    # Check for non-negative coordinates if required
    if not allow_negative:
        if x1 < 0 or y1 < 0:
            raise InvalidBoundingBoxError(
                f"Bounding box has negative coordinates: ({x1}, {y1}, {x2}, {y2})",
                bbox=bbox,
            )
        if x2 < 0 or y2 < 0:
            raise InvalidBoundingBoxError(
                f"Bounding box has negative coordinates: ({x1}, {y1}, {x2}, {y2})",
                bbox=bbox,
            )

    # Check bounds if image dimensions provided
    if (
        image_width is not None
        and image_height is not None
        and strict_bounds
        and (x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


@overload
def clamp_bbox_to_image(
    bbox: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    min_size: float = 1.0,
    return_none_if_empty: bool = True,
) -> tuple[int, int, int, int] | None: ...


@overload
def clamp_bbox_to_image(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    min_size: float = 1.0,
    return_none_if_empty: bool = True,
) -> tuple[float, float, float, float] | None: ...


def clamp_bbox_to_image(
    bbox: tuple[float, float, float, float] | tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    min_size: float = 1.0,
    return_none_if_empty: bool = True,
) -> tuple[float, float, float, float] | tuple[int, int, int, int] | None:
    """Clamp a bounding box to fit within image boundaries.

    This function ensures the bounding box coordinates are within valid
    image bounds, adjusting coordinates as needed while preserving as
    much of the original box as possible.

    If coordinates are inverted (x2 < x1 or y2 < y1), they are automatically
    swapped to fix the bounding box before clamping.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        image_width: Image width in pixels
        image_height: Image height in pixels
        min_size: Minimum width/height after clamping (default 1.0)
        return_none_if_empty: If True, return None when clamped box is too small

    Returns:
        Clamped bounding box, or None if the box becomes invalid after clamping
        (when return_none_if_empty is True)

    Examples:
        >>> clamp_bbox_to_image((-10, -10, 50, 50), 100, 100)
        (0, 0, 50, 50)

        >>> clamp_bbox_to_image((90, 90, 150, 150), 100, 100)
        (90, 90, 100, 100)

        >>> clamp_bbox_to_image((200, 200, 300, 300), 100, 100)
        None  # Completely outside image

        >>> clamp_bbox_to_image((50, 50, 10, 10), 100, 100)  # Inverted
        (10, 10, 50, 50)  # Fixed by swapping
    """
    x1, y1, x2, y2 = bbox

    # Fix inverted coordinates before clamping
    if x2 < x1:
        logger.debug(f"Swapping inverted X coordinates: x1={x1}, x2={x2}")
        x1, x2 = x2, x1

    if y2 < y1:
        logger.debug(f"Swapping inverted Y coordinates: y1={y1}, y2={y2}")
        y1, y2 = y2, y1

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = y2_clamped - y1_clamped

    if width < min_size or height < min_size:
        if return_none_if_empty:
            logger.debug(
                f"Bounding box {bbox} became too small after clamping to "
                f"({image_width}x{image_height}): width={width}, height={height}"
            )
            return None
        # Return minimal valid box at the clamped location
        x2_clamped = x1_clamped + min_size
        y2_clamped = y1_clamped + min_size

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def validate_and_clamp_bbox(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    _allow_negative: bool = True,  # Reserved for future use
    min_size: float = 1.0,
) -> BoundingBoxValidationResult:
    """Validate a bounding box and clamp it to image boundaries.

    This is a convenience function that combines validation and clamping,
    providing detailed information about the validation result.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        image_width: Image width in pixels
        image_height: Image height in pixels
        allow_negative: If True, allow negative input coordinates (they will be clamped)
        min_size: Minimum width/height after clamping

    Returns:
        BoundingBoxValidationResult with validation details
    """
    warnings: list[str] = []
    x1, y1, x2, y2 = bbox

    # Check for completely invalid input
    import math

    if any(math.isnan(v) or math.isinf(v) for v in (x1, y1, x2, y2)):
        return BoundingBoxValidationResult(
            is_valid=False,
            clamped_bbox=None,
            original_bbox=bbox,
            warnings=["Bounding box contains NaN or infinite values"],
        )

    # Check for inverted coordinates
    if x2 <= x1 or y2 <= y1:
        return BoundingBoxValidationResult(
            is_valid=False,
            clamped_bbox=None,
            original_bbox=bbox,
            warnings=[f"Bounding box has invalid dimensions: width={x2 - x1}, height={y2 - y1}"],
        )

    # Track if clamping is needed
    was_clamped = False

    # Check for negative coordinates
    if x1 < 0 or y1 < 0:
        warnings.append(f"Bounding box has negative coordinates: ({x1}, {y1})")
        was_clamped = True

    # Check for out-of-bounds coordinates
    if x2 > image_width or y2 > image_height:
        warnings.append(
            f"Bounding box exceeds image bounds: ({x2}, {y2}) > ({image_width}, {image_height})"
        )
        was_clamped = True

    # Check if completely outside image
    if x1 >= image_width or y1 >= image_height or x2 <= 0 or y2 <= 0:
        return BoundingBoxValidationResult(
            is_valid=False,
            clamped_bbox=None,
            original_bbox=bbox,
            warnings=["Bounding box is completely outside image boundaries"],
            was_clamped=True,
            was_empty_after_clamp=True,
        )

    # Clamp to image boundaries
    clamped = clamp_bbox_to_image(
        bbox,
        image_width,
        image_height,
        min_size=min_size,
        return_none_if_empty=True,
    )

    if clamped is None:
        return BoundingBoxValidationResult(
            is_valid=False,
            clamped_bbox=None,
            original_bbox=bbox,
            warnings=[*warnings, "Bounding box became too small after clamping"],
            was_clamped=was_clamped,
            was_empty_after_clamp=True,
        )

    return BoundingBoxValidationResult(
        is_valid=True,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def normalize_bbox_to_pixels(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Convert normalized (0-1) bounding box coordinates to pixel coordinates.

    Args:
        bbox: Bounding box with coordinates in [0, 1] range
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Bounding box with pixel coordinates (x1, y1, x2, y2)
    """
    x1, y1, x2, y2 = bbox
    return (
        int(x1 * image_width),
        int(y1 * image_height),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def normalize_bbox_to_float(
    bbox: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    """Convert pixel bounding box coordinates to normalized (0-1) coordinates.

    Args:
        bbox: Bounding box with pixel coordinates
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Bounding box with coordinates in [0, 1] range
    """
    x1, y1, x2, y2 = bbox
    return (
        x1 / image_width,
        y1 / image_height,
        x2 / image_width,
        y2 / image_height,
    )


def calculate_bbox_area(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def calculate_bbox_iou(
    bbox1: tuple[float, float, float, float],
    bbox2: tuple[float, float, float, float],
) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes.

    Args:
        bbox1: First bounding box as (x1, y1, x2, y2)
        bbox2: Second bounding box as (x1, y1, x2, y2)

    Returns:
        IoU score in [0, 1] range
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    # Calculate intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)

    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def prepare_bbox_for_crop(
    bbox: tuple[float, float, float, float] | tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    padding: int = 0,
    min_size: int = 1,
) -> tuple[int, int, int, int] | None:
    """Prepare a bounding box for safe PIL Image.crop() operation.

    This function handles all edge cases that can cause PIL to raise
    "Coordinate 'right' is less than 'left'" or similar errors:
    - Inverted coordinates (x2 < x1 or y2 < y1) are swapped
    - Out-of-bounds coordinates are clamped to image dimensions
    - Padding is applied after validation
    - Boxes that become too small after clamping return None

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        image_width: Image width in pixels
        image_height: Image height in pixels
        padding: Pixels to add around bbox (applied after clamping)
        min_size: Minimum width/height required (default 1)

    Returns:
        Safe bounding box tuple (x1, y1, x2, y2) ready for PIL crop,
        or None if the box is invalid or too small after processing.

    Examples:
        >>> prepare_bbox_for_crop((50, 50, 10, 10), 100, 100)  # Inverted
        (10, 10, 50, 50)  # Fixed by swapping

        >>> prepare_bbox_for_crop((-10, -10, 50, 50), 100, 100)  # Negative
        (0, 0, 50, 50)  # Clamped

        >>> prepare_bbox_for_crop((10, 10, 150, 150), 100, 100)  # Out of bounds
        (10, 10, 100, 100)  # Clamped
    """
    x1, y1, x2, y2 = bbox

    # Fix inverted coordinates
    if x2 < x1:
        logger.debug(f"Fixing inverted X coordinates for crop: x1={x1}, x2={x2}")
        x1, x2 = x2, x1

    if y2 < y1:
        logger.debug(f"Fixing inverted Y coordinates for crop: y1={y1}, y2={y2}")
        y1, y2 = y2, y1

    # Convert to integers for PIL
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

    # Check for zero-dimension boxes (after int conversion)
    if x2 <= x1 or y2 <= y1:
        logger.debug(f"Bounding box has zero dimensions: ({x1}, {y1}, {x2}, {y2})")
        return None

    # Check if bbox is completely outside image boundaries BEFORE padding
    # This prevents creating tiny boxes at corners for completely outside bboxes
    if x1 >= image_width or y1 >= image_height or x2 <= 0 or y2 <= 0:
        logger.debug(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) is completely outside "
            f"image boundaries ({image_width}x{image_height})"
        )
        return None

    # Apply padding (expand the box)
    if padding > 0:
        x1 = x1 - padding
        y1 = y1 - padding
        x2 = x2 + padding
        y2 = y2 + padding

    # Clamp to image bounds
    x1 = max(0, min(x1, image_width - 1))
    y1 = max(0, min(y1, image_height - 1))
    x2 = max(1, min(x2, image_width))
    y2 = max(1, min(y2, image_height))

    # Ensure x2 > x1 and y2 > y1 after clamping
    if x2 <= x1 or y2 <= y1:
        logger.debug(f"Bounding box became invalid after clamping: ({x1}, {y1}, {x2}, {y2})")
        return None

    # Check minimum size
    if (x2 - x1) < min_size or (y2 - y1) < min_size:
        logger.debug(
            f"Bounding box too small after processing: "
            f"width={x2 - x1}, height={y2 - y1}, min_size={min_size}"
        )
        return None

    return (x1, y1, x2, y2)


def scale_bbox_to_image(
    bbox: tuple[float, float, float, float],
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[float, float, float, float]:
    """Scale bounding box coordinates from source dimensions to target dimensions.

    This function handles the common case where YOLO returns bounding box coordinates
    relative to the original image dimensions, but the image is later loaded at a
    different resolution (e.g., for thumbnail processing or memory optimization).

    NEM-3903: YOLO detection coordinates are always relative to the actual image
    dimensions at inference time. When the enrichment pipeline loads an image at
    a different resolution, bboxes must be scaled proportionally.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2) in source coordinates
        source_width: Width of the image when bbox was generated
        source_height: Height of the image when bbox was generated
        target_width: Width of the image to scale bbox to
        target_height: Height of the image to scale bbox to

    Returns:
        Scaled bounding box as (x1, y1, x2, y2) in target coordinates

    Example:
        >>> # YOLO returned bbox for 640x480 image, but we loaded 320x240
        >>> scale_bbox_to_image((100, 100, 200, 200), 640, 480, 320, 240)
        (50.0, 50.0, 100.0, 100.0)

        >>> # Upscaling: bbox from 320x240 to 640x480
        >>> scale_bbox_to_image((50, 50, 100, 100), 320, 240, 640, 480)
        (100.0, 100.0, 200.0, 200.0)
    """
    if source_width <= 0 or source_height <= 0:
        logger.warning(
            f"Invalid source dimensions: {source_width}x{source_height}. Returning original bbox."
        )
        return bbox

    if target_width <= 0 or target_height <= 0:
        logger.warning(
            f"Invalid target dimensions: {target_width}x{target_height}. Returning original bbox."
        )
        return bbox

    # No scaling needed if dimensions match
    if source_width == target_width and source_height == target_height:
        return bbox

    x1, y1, x2, y2 = bbox
    scale_x = target_width / source_width
    scale_y = target_height / source_height

    return (
        x1 * scale_x,
        y1 * scale_y,
        x2 * scale_x,
        y2 * scale_y,
    )
