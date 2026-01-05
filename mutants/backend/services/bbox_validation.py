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
from collections.abc import Callable
from inspect import signature as _mutmut_signature
from typing import Annotated, ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg=None):
    """Forward call to original or mutated function, depending on the environment"""
    import os

    mutant_under_test = os.environ["MUTANT_UNDER_TEST"]
    if mutant_under_test == "fail":
        from mutmut.__main__ import MutmutProgrammaticFailException

        raise MutmutProgrammaticFailException("Failed programmatically")
    elif mutant_under_test == "stats":
        from mutmut.__main__ import record_trampoline_hit

        record_trampoline_hit(orig.__module__ + "." + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + "." + orig.__name__ + "__mutmut_"
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition(".")[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


class BoundingBoxValidationError(ValueError):
    """Base exception for bounding box validation errors.

    This exception is raised when a bounding box fails validation checks.
    It provides details about the specific validation failure.
    """

    def xǁBoundingBoxValidationErrorǁ__init____mutmut_orig(
        self, message: str, bbox: tuple[float, float, float, float] | None = None
    ):
        """Initialize the error.

        Args:
            message: Human-readable error description
            bbox: The invalid bounding box that caused the error
        """
        super().__init__(message)
        self.bbox = bbox

    def xǁBoundingBoxValidationErrorǁ__init____mutmut_1(
        self, message: str, bbox: tuple[float, float, float, float] | None = None
    ):
        """Initialize the error.

        Args:
            message: Human-readable error description
            bbox: The invalid bounding box that caused the error
        """
        super().__init__(None)
        self.bbox = bbox

    def xǁBoundingBoxValidationErrorǁ__init____mutmut_2(
        self, message: str, bbox: tuple[float, float, float, float] | None = None
    ):
        """Initialize the error.

        Args:
            message: Human-readable error description
            bbox: The invalid bounding box that caused the error
        """
        super().__init__(message)
        self.bbox = None

    xǁBoundingBoxValidationErrorǁ__init____mutmut_mutants: ClassVar[MutantDict] = {
        "xǁBoundingBoxValidationErrorǁ__init____mutmut_1": xǁBoundingBoxValidationErrorǁ__init____mutmut_1,
        "xǁBoundingBoxValidationErrorǁ__init____mutmut_2": xǁBoundingBoxValidationErrorǁ__init____mutmut_2,
    }

    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁBoundingBoxValidationErrorǁ__init____mutmut_orig"),
            object.__getattribute__(self, "xǁBoundingBoxValidationErrorǁ__init____mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    __init__.__signature__ = _mutmut_signature(xǁBoundingBoxValidationErrorǁ__init____mutmut_orig)
    xǁBoundingBoxValidationErrorǁ__init____mutmut_orig.__name__ = (
        "xǁBoundingBoxValidationErrorǁ__init__"
    )


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

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_orig(
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

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_1(
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
        super().__init__(None, bbox)
        self.image_size = image_size

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_2(
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
        super().__init__(message, None)
        self.image_size = image_size

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_3(
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
        super().__init__(bbox)
        self.image_size = image_size

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_4(
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
        super().__init__(
            message,
        )
        self.image_size = image_size

    def xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_5(
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
        self.image_size = None

    xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_mutants: ClassVar[MutantDict] = {
        "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_1": xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_1,
        "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_2": xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_2,
        "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_3": xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_3,
        "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_4": xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_4,
        "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_5": xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_5,
    }

    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(
            object.__getattribute__(self, "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_orig"),
            object.__getattribute__(self, "xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_mutants"),
            args,
            kwargs,
            self,
        )
        return result

    __init__.__signature__ = _mutmut_signature(xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_orig)
    xǁBoundingBoxOutOfBoundsErrorǁ__init____mutmut_orig.__name__ = (
        "xǁBoundingBoxOutOfBoundsErrorǁ__init__"
    )


@dataclass
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


def x_is_valid_bbox__mutmut_orig(
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


def x_is_valid_bbox__mutmut_1(
    bbox: tuple[float, float, float, float],
    allow_negative: bool = True,
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


def x_is_valid_bbox__mutmut_2(
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
        x1, y1, x2, y2 = None

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


def x_is_valid_bbox__mutmut_3(
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

        if any(None):
            return False

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_4(
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

        if any(math.isnan(v) and math.isinf(v) for v in (x1, y1, x2, y2)):
            return False

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_5(
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

        if any(math.isnan(None) or math.isinf(v) for v in (x1, y1, x2, y2)):
            return False

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_6(
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

        if any(math.isnan(v) or math.isinf(None) for v in (x1, y1, x2, y2)):
            return False

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_7(
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
            return True

        # Check for positive dimensions
        if x2 <= x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_8(
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
        if x2 <= x1 and y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_9(
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
        if x2 < x1 or y2 <= y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_10(
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
        if x2 <= x1 or y2 < y1:
            return False

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_11(
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
            return True

        # Check for non-negative coordinates if required
        # Return True if allow_negative or all coords non-negative
        return allow_negative or not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_12(
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
        return allow_negative and not any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_13(
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
        return allow_negative or any(v < 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_14(
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
        return allow_negative or not any(None)
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_15(
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
        return allow_negative or not any(v <= 0 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_16(
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
        return allow_negative or not any(v < 1 for v in (x1, y1, x2, y2))
    except (TypeError, ValueError):
        return False


def x_is_valid_bbox__mutmut_17(
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
        return True


x_is_valid_bbox__mutmut_mutants: ClassVar[MutantDict] = {
    "x_is_valid_bbox__mutmut_1": x_is_valid_bbox__mutmut_1,
    "x_is_valid_bbox__mutmut_2": x_is_valid_bbox__mutmut_2,
    "x_is_valid_bbox__mutmut_3": x_is_valid_bbox__mutmut_3,
    "x_is_valid_bbox__mutmut_4": x_is_valid_bbox__mutmut_4,
    "x_is_valid_bbox__mutmut_5": x_is_valid_bbox__mutmut_5,
    "x_is_valid_bbox__mutmut_6": x_is_valid_bbox__mutmut_6,
    "x_is_valid_bbox__mutmut_7": x_is_valid_bbox__mutmut_7,
    "x_is_valid_bbox__mutmut_8": x_is_valid_bbox__mutmut_8,
    "x_is_valid_bbox__mutmut_9": x_is_valid_bbox__mutmut_9,
    "x_is_valid_bbox__mutmut_10": x_is_valid_bbox__mutmut_10,
    "x_is_valid_bbox__mutmut_11": x_is_valid_bbox__mutmut_11,
    "x_is_valid_bbox__mutmut_12": x_is_valid_bbox__mutmut_12,
    "x_is_valid_bbox__mutmut_13": x_is_valid_bbox__mutmut_13,
    "x_is_valid_bbox__mutmut_14": x_is_valid_bbox__mutmut_14,
    "x_is_valid_bbox__mutmut_15": x_is_valid_bbox__mutmut_15,
    "x_is_valid_bbox__mutmut_16": x_is_valid_bbox__mutmut_16,
    "x_is_valid_bbox__mutmut_17": x_is_valid_bbox__mutmut_17,
}


def is_valid_bbox(*args, **kwargs):
    result = _mutmut_trampoline(
        x_is_valid_bbox__mutmut_orig, x_is_valid_bbox__mutmut_mutants, args, kwargs
    )
    return result


is_valid_bbox.__signature__ = _mutmut_signature(x_is_valid_bbox__mutmut_orig)
x_is_valid_bbox__mutmut_orig.__name__ = "x_is_valid_bbox"


def x_validate_bbox__mutmut_orig(
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


def x_validate_bbox__mutmut_1(
    bbox: tuple[float, float, float, float],
    image_width: int | None = None,
    image_height: int | None = None,
    allow_negative: bool = True,
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


def x_validate_bbox__mutmut_2(
    bbox: tuple[float, float, float, float],
    image_width: int | None = None,
    image_height: int | None = None,
    allow_negative: bool = False,
    strict_bounds: bool = True,
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


def x_validate_bbox__mutmut_3(
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
        x1, y1, x2, y2 = None
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


def x_validate_bbox__mutmut_4(
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
            None,
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


def x_validate_bbox__mutmut_5(
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
            bbox=None,
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


def x_validate_bbox__mutmut_6(
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


def x_validate_bbox__mutmut_7(
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


def x_validate_bbox__mutmut_8(
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

    try:
        x1, y1, x2, y2 = bbox
    except (TypeError, ValueError) as e:
        raise InvalidBoundingBoxError(
            f"Invalid bounding box format: {bbox}. Expected (x1, y1, x2, y2)",
            bbox=bbox,
        ) from e

    # Check for NaN or infinite values
    if any(None):
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


def x_validate_bbox__mutmut_9(
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
    if any(math.isnan(v) and math.isinf(v) for v in (x1, y1, x2, y2)):
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


def x_validate_bbox__mutmut_10(
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
    if any(math.isnan(None) or math.isinf(v) for v in (x1, y1, x2, y2)):
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


def x_validate_bbox__mutmut_11(
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
    if any(math.isnan(v) or math.isinf(None) for v in (x1, y1, x2, y2)):
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


def x_validate_bbox__mutmut_12(
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
            None,
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


def x_validate_bbox__mutmut_13(
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
            bbox=None,
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


def x_validate_bbox__mutmut_14(
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


def x_validate_bbox__mutmut_15(
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


def x_validate_bbox__mutmut_16(
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
    if x2 < x1:
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


def x_validate_bbox__mutmut_17(
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
            None,
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


def x_validate_bbox__mutmut_18(
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
            bbox=None,
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


def x_validate_bbox__mutmut_19(
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


def x_validate_bbox__mutmut_20(
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


def x_validate_bbox__mutmut_21(
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

    if y2 < y1:
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


def x_validate_bbox__mutmut_22(
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
            None,
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


def x_validate_bbox__mutmut_23(
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
            bbox=None,
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


def x_validate_bbox__mutmut_24(
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


def x_validate_bbox__mutmut_25(
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


def x_validate_bbox__mutmut_26(
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
    if allow_negative:
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


def x_validate_bbox__mutmut_27(
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
        if x1 < 0 and y1 < 0:
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


def x_validate_bbox__mutmut_28(
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
        if x1 <= 0 or y1 < 0:
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


def x_validate_bbox__mutmut_29(
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
        if x1 < 1 or y1 < 0:
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


def x_validate_bbox__mutmut_30(
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
        if x1 < 0 or y1 <= 0:
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


def x_validate_bbox__mutmut_31(
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
        if x1 < 0 or y1 < 1:
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


def x_validate_bbox__mutmut_32(
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
                None,
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


def x_validate_bbox__mutmut_33(
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
                bbox=None,
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


def x_validate_bbox__mutmut_34(
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


def x_validate_bbox__mutmut_35(
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


def x_validate_bbox__mutmut_36(
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
        if x2 < 0 and y2 < 0:
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


def x_validate_bbox__mutmut_37(
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
        if x2 <= 0 or y2 < 0:
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


def x_validate_bbox__mutmut_38(
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
        if x2 < 1 or y2 < 0:
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


def x_validate_bbox__mutmut_39(
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
        if x2 < 0 or y2 <= 0:
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


def x_validate_bbox__mutmut_40(
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
        if x2 < 0 or y2 < 1:
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


def x_validate_bbox__mutmut_41(
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
                None,
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


def x_validate_bbox__mutmut_42(
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
                bbox=None,
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


def x_validate_bbox__mutmut_43(
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


def x_validate_bbox__mutmut_44(
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


def x_validate_bbox__mutmut_45(
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
    if (image_width is not None and image_height is not None and strict_bounds) or (
        x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_46(
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
    if (image_width is not None and image_height is not None) or (
        strict_bounds and (x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_47(
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
    if image_width is not None or (
        image_height is not None
        and strict_bounds
        and (x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_48(
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
        image_width is None
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


def x_validate_bbox__mutmut_49(
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
        and image_height is None
        and strict_bounds
        and (x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_50(
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
        and (x1 < 0 or y1 < 0 or (x2 > image_width and y2 > image_height))
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_51(
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
        and (x1 < 0 or (y1 < 0 and x2 > image_width) or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_52(
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
        and ((x1 < 0 and y1 < 0) or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_53(
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
        and (x1 <= 0 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_54(
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
        and (x1 < 1 or y1 < 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_55(
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
        and (x1 < 0 or y1 <= 0 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_56(
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
        and (x1 < 0 or y1 < 1 or x2 > image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_57(
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
        and (x1 < 0 or y1 < 0 or x2 >= image_width or y2 > image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_58(
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
        and (x1 < 0 or y1 < 0 or x2 > image_width or y2 >= image_height)
    ):
        raise BoundingBoxOutOfBoundsError(
            f"Bounding box ({x1}, {y1}, {x2}, {y2}) exceeds image bounds "
            f"({image_width}x{image_height})",
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_59(
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
            None,
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_60(
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
            bbox=None,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_61(
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
            image_size=None,
        )


def x_validate_bbox__mutmut_62(
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
            bbox=bbox,
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_63(
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
            image_size=(image_width, image_height),
        )


def x_validate_bbox__mutmut_64(
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
        )


x_validate_bbox__mutmut_mutants: ClassVar[MutantDict] = {
    "x_validate_bbox__mutmut_1": x_validate_bbox__mutmut_1,
    "x_validate_bbox__mutmut_2": x_validate_bbox__mutmut_2,
    "x_validate_bbox__mutmut_3": x_validate_bbox__mutmut_3,
    "x_validate_bbox__mutmut_4": x_validate_bbox__mutmut_4,
    "x_validate_bbox__mutmut_5": x_validate_bbox__mutmut_5,
    "x_validate_bbox__mutmut_6": x_validate_bbox__mutmut_6,
    "x_validate_bbox__mutmut_7": x_validate_bbox__mutmut_7,
    "x_validate_bbox__mutmut_8": x_validate_bbox__mutmut_8,
    "x_validate_bbox__mutmut_9": x_validate_bbox__mutmut_9,
    "x_validate_bbox__mutmut_10": x_validate_bbox__mutmut_10,
    "x_validate_bbox__mutmut_11": x_validate_bbox__mutmut_11,
    "x_validate_bbox__mutmut_12": x_validate_bbox__mutmut_12,
    "x_validate_bbox__mutmut_13": x_validate_bbox__mutmut_13,
    "x_validate_bbox__mutmut_14": x_validate_bbox__mutmut_14,
    "x_validate_bbox__mutmut_15": x_validate_bbox__mutmut_15,
    "x_validate_bbox__mutmut_16": x_validate_bbox__mutmut_16,
    "x_validate_bbox__mutmut_17": x_validate_bbox__mutmut_17,
    "x_validate_bbox__mutmut_18": x_validate_bbox__mutmut_18,
    "x_validate_bbox__mutmut_19": x_validate_bbox__mutmut_19,
    "x_validate_bbox__mutmut_20": x_validate_bbox__mutmut_20,
    "x_validate_bbox__mutmut_21": x_validate_bbox__mutmut_21,
    "x_validate_bbox__mutmut_22": x_validate_bbox__mutmut_22,
    "x_validate_bbox__mutmut_23": x_validate_bbox__mutmut_23,
    "x_validate_bbox__mutmut_24": x_validate_bbox__mutmut_24,
    "x_validate_bbox__mutmut_25": x_validate_bbox__mutmut_25,
    "x_validate_bbox__mutmut_26": x_validate_bbox__mutmut_26,
    "x_validate_bbox__mutmut_27": x_validate_bbox__mutmut_27,
    "x_validate_bbox__mutmut_28": x_validate_bbox__mutmut_28,
    "x_validate_bbox__mutmut_29": x_validate_bbox__mutmut_29,
    "x_validate_bbox__mutmut_30": x_validate_bbox__mutmut_30,
    "x_validate_bbox__mutmut_31": x_validate_bbox__mutmut_31,
    "x_validate_bbox__mutmut_32": x_validate_bbox__mutmut_32,
    "x_validate_bbox__mutmut_33": x_validate_bbox__mutmut_33,
    "x_validate_bbox__mutmut_34": x_validate_bbox__mutmut_34,
    "x_validate_bbox__mutmut_35": x_validate_bbox__mutmut_35,
    "x_validate_bbox__mutmut_36": x_validate_bbox__mutmut_36,
    "x_validate_bbox__mutmut_37": x_validate_bbox__mutmut_37,
    "x_validate_bbox__mutmut_38": x_validate_bbox__mutmut_38,
    "x_validate_bbox__mutmut_39": x_validate_bbox__mutmut_39,
    "x_validate_bbox__mutmut_40": x_validate_bbox__mutmut_40,
    "x_validate_bbox__mutmut_41": x_validate_bbox__mutmut_41,
    "x_validate_bbox__mutmut_42": x_validate_bbox__mutmut_42,
    "x_validate_bbox__mutmut_43": x_validate_bbox__mutmut_43,
    "x_validate_bbox__mutmut_44": x_validate_bbox__mutmut_44,
    "x_validate_bbox__mutmut_45": x_validate_bbox__mutmut_45,
    "x_validate_bbox__mutmut_46": x_validate_bbox__mutmut_46,
    "x_validate_bbox__mutmut_47": x_validate_bbox__mutmut_47,
    "x_validate_bbox__mutmut_48": x_validate_bbox__mutmut_48,
    "x_validate_bbox__mutmut_49": x_validate_bbox__mutmut_49,
    "x_validate_bbox__mutmut_50": x_validate_bbox__mutmut_50,
    "x_validate_bbox__mutmut_51": x_validate_bbox__mutmut_51,
    "x_validate_bbox__mutmut_52": x_validate_bbox__mutmut_52,
    "x_validate_bbox__mutmut_53": x_validate_bbox__mutmut_53,
    "x_validate_bbox__mutmut_54": x_validate_bbox__mutmut_54,
    "x_validate_bbox__mutmut_55": x_validate_bbox__mutmut_55,
    "x_validate_bbox__mutmut_56": x_validate_bbox__mutmut_56,
    "x_validate_bbox__mutmut_57": x_validate_bbox__mutmut_57,
    "x_validate_bbox__mutmut_58": x_validate_bbox__mutmut_58,
    "x_validate_bbox__mutmut_59": x_validate_bbox__mutmut_59,
    "x_validate_bbox__mutmut_60": x_validate_bbox__mutmut_60,
    "x_validate_bbox__mutmut_61": x_validate_bbox__mutmut_61,
    "x_validate_bbox__mutmut_62": x_validate_bbox__mutmut_62,
    "x_validate_bbox__mutmut_63": x_validate_bbox__mutmut_63,
    "x_validate_bbox__mutmut_64": x_validate_bbox__mutmut_64,
}


def validate_bbox(*args, **kwargs):
    result = _mutmut_trampoline(
        x_validate_bbox__mutmut_orig, x_validate_bbox__mutmut_mutants, args, kwargs
    )
    return result


validate_bbox.__signature__ = _mutmut_signature(x_validate_bbox__mutmut_orig)
x_validate_bbox__mutmut_orig.__name__ = "x_validate_bbox"


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


def x_clamp_bbox_to_image__mutmut_orig(
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
    """
    x1, y1, x2, y2 = bbox

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


def x_clamp_bbox_to_image__mutmut_1(
    bbox: tuple[float, float, float, float] | tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    min_size: float = 2.0,
    return_none_if_empty: bool = True,
) -> tuple[float, float, float, float] | tuple[int, int, int, int] | None:
    """Clamp a bounding box to fit within image boundaries.

    This function ensures the bounding box coordinates are within valid
    image bounds, adjusting coordinates as needed while preserving as
    much of the original box as possible.

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
    """
    x1, y1, x2, y2 = bbox

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


def x_clamp_bbox_to_image__mutmut_2(
    bbox: tuple[float, float, float, float] | tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    min_size: float = 1.0,
    return_none_if_empty: bool = False,
) -> tuple[float, float, float, float] | tuple[int, int, int, int] | None:
    """Clamp a bounding box to fit within image boundaries.

    This function ensures the bounding box coordinates are within valid
    image bounds, adjusting coordinates as needed while preserving as
    much of the original box as possible.

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
    """
    x1, y1, x2, y2 = bbox

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


def x_clamp_bbox_to_image__mutmut_3(
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
    """
    x1, y1, x2, y2 = None

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


def x_clamp_bbox_to_image__mutmut_4(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = None
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


def x_clamp_bbox_to_image__mutmut_5(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(None, min(x1, image_width))
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


def x_clamp_bbox_to_image__mutmut_6(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, None)
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


def x_clamp_bbox_to_image__mutmut_7(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(min(x1, image_width))
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


def x_clamp_bbox_to_image__mutmut_8(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(
        0,
    )
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


def x_clamp_bbox_to_image__mutmut_9(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(1, min(x1, image_width))
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


def x_clamp_bbox_to_image__mutmut_10(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(None, image_width))
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


def x_clamp_bbox_to_image__mutmut_11(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, None))
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


def x_clamp_bbox_to_image__mutmut_12(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(image_width))
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


def x_clamp_bbox_to_image__mutmut_13(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(
        0,
        min(
            x1,
        ),
    )
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


def x_clamp_bbox_to_image__mutmut_14(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = None
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


def x_clamp_bbox_to_image__mutmut_15(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(None, min(y1, image_height))
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


def x_clamp_bbox_to_image__mutmut_16(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, None)
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


def x_clamp_bbox_to_image__mutmut_17(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(min(y1, image_height))
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


def x_clamp_bbox_to_image__mutmut_18(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(
        0,
    )
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


def x_clamp_bbox_to_image__mutmut_19(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(1, min(y1, image_height))
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


def x_clamp_bbox_to_image__mutmut_20(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(None, image_height))
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


def x_clamp_bbox_to_image__mutmut_21(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, None))
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


def x_clamp_bbox_to_image__mutmut_22(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(image_height))
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


def x_clamp_bbox_to_image__mutmut_23(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(
        0,
        min(
            y1,
        ),
    )
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


def x_clamp_bbox_to_image__mutmut_24(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = None
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


def x_clamp_bbox_to_image__mutmut_25(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(None, min(x2, image_width))
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


def x_clamp_bbox_to_image__mutmut_26(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, None)
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


def x_clamp_bbox_to_image__mutmut_27(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(min(x2, image_width))
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


def x_clamp_bbox_to_image__mutmut_28(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(
        0,
    )
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


def x_clamp_bbox_to_image__mutmut_29(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(1, min(x2, image_width))
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


def x_clamp_bbox_to_image__mutmut_30(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(None, image_width))
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


def x_clamp_bbox_to_image__mutmut_31(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, None))
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


def x_clamp_bbox_to_image__mutmut_32(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(image_width))
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


def x_clamp_bbox_to_image__mutmut_33(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(
        0,
        min(
            x2,
        ),
    )
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


def x_clamp_bbox_to_image__mutmut_34(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = None

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


def x_clamp_bbox_to_image__mutmut_35(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(None, min(y2, image_height))

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


def x_clamp_bbox_to_image__mutmut_36(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, None)

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


def x_clamp_bbox_to_image__mutmut_37(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(min(y2, image_height))

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


def x_clamp_bbox_to_image__mutmut_38(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(
        0,
    )

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


def x_clamp_bbox_to_image__mutmut_39(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(1, min(y2, image_height))

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


def x_clamp_bbox_to_image__mutmut_40(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(None, image_height))

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


def x_clamp_bbox_to_image__mutmut_41(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, None))

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


def x_clamp_bbox_to_image__mutmut_42(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(image_height))

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


def x_clamp_bbox_to_image__mutmut_43(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(
        0,
        min(
            y2,
        ),
    )

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


def x_clamp_bbox_to_image__mutmut_44(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = None
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


def x_clamp_bbox_to_image__mutmut_45(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped + x1_clamped
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


def x_clamp_bbox_to_image__mutmut_46(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = None

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


def x_clamp_bbox_to_image__mutmut_47(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = y2_clamped + y1_clamped

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


def x_clamp_bbox_to_image__mutmut_48(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = y2_clamped - y1_clamped

    if width < min_size and height < min_size:
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


def x_clamp_bbox_to_image__mutmut_49(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = y2_clamped - y1_clamped

    if width <= min_size or height < min_size:
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


def x_clamp_bbox_to_image__mutmut_50(
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
    """
    x1, y1, x2, y2 = bbox

    # Clamp coordinates to image boundaries
    x1_clamped = max(0, min(x1, image_width))
    y1_clamped = max(0, min(y1, image_height))
    x2_clamped = max(0, min(x2, image_width))
    y2_clamped = max(0, min(y2, image_height))

    # Check if resulting box is valid
    width = x2_clamped - x1_clamped
    height = y2_clamped - y1_clamped

    if width < min_size or height <= min_size:
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


def x_clamp_bbox_to_image__mutmut_51(
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
    """
    x1, y1, x2, y2 = bbox

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
            logger.debug(None)
            return None
        # Return minimal valid box at the clamped location
        x2_clamped = x1_clamped + min_size
        y2_clamped = y1_clamped + min_size

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_52(
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
    """
    x1, y1, x2, y2 = bbox

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
        x2_clamped = None
        y2_clamped = y1_clamped + min_size

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_53(
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
    """
    x1, y1, x2, y2 = bbox

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
        x2_clamped = x1_clamped - min_size
        y2_clamped = y1_clamped + min_size

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_54(
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
    """
    x1, y1, x2, y2 = bbox

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
        y2_clamped = None

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_55(
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
    """
    x1, y1, x2, y2 = bbox

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
        y2_clamped = y1_clamped - min_size

    # Preserve integer type if input was integers
    if isinstance(bbox[0], int):
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_56(
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
    """
    x1, y1, x2, y2 = bbox

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
        return (int(None), int(y1_clamped), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_57(
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
    """
    x1, y1, x2, y2 = bbox

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
        return (int(x1_clamped), int(None), int(x2_clamped), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_58(
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
    """
    x1, y1, x2, y2 = bbox

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
        return (int(x1_clamped), int(y1_clamped), int(None), int(y2_clamped))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


def x_clamp_bbox_to_image__mutmut_59(
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
    """
    x1, y1, x2, y2 = bbox

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
        return (int(x1_clamped), int(y1_clamped), int(x2_clamped), int(None))

    return (x1_clamped, y1_clamped, x2_clamped, y2_clamped)


x_clamp_bbox_to_image__mutmut_mutants: ClassVar[MutantDict] = {
    "x_clamp_bbox_to_image__mutmut_1": x_clamp_bbox_to_image__mutmut_1,
    "x_clamp_bbox_to_image__mutmut_2": x_clamp_bbox_to_image__mutmut_2,
    "x_clamp_bbox_to_image__mutmut_3": x_clamp_bbox_to_image__mutmut_3,
    "x_clamp_bbox_to_image__mutmut_4": x_clamp_bbox_to_image__mutmut_4,
    "x_clamp_bbox_to_image__mutmut_5": x_clamp_bbox_to_image__mutmut_5,
    "x_clamp_bbox_to_image__mutmut_6": x_clamp_bbox_to_image__mutmut_6,
    "x_clamp_bbox_to_image__mutmut_7": x_clamp_bbox_to_image__mutmut_7,
    "x_clamp_bbox_to_image__mutmut_8": x_clamp_bbox_to_image__mutmut_8,
    "x_clamp_bbox_to_image__mutmut_9": x_clamp_bbox_to_image__mutmut_9,
    "x_clamp_bbox_to_image__mutmut_10": x_clamp_bbox_to_image__mutmut_10,
    "x_clamp_bbox_to_image__mutmut_11": x_clamp_bbox_to_image__mutmut_11,
    "x_clamp_bbox_to_image__mutmut_12": x_clamp_bbox_to_image__mutmut_12,
    "x_clamp_bbox_to_image__mutmut_13": x_clamp_bbox_to_image__mutmut_13,
    "x_clamp_bbox_to_image__mutmut_14": x_clamp_bbox_to_image__mutmut_14,
    "x_clamp_bbox_to_image__mutmut_15": x_clamp_bbox_to_image__mutmut_15,
    "x_clamp_bbox_to_image__mutmut_16": x_clamp_bbox_to_image__mutmut_16,
    "x_clamp_bbox_to_image__mutmut_17": x_clamp_bbox_to_image__mutmut_17,
    "x_clamp_bbox_to_image__mutmut_18": x_clamp_bbox_to_image__mutmut_18,
    "x_clamp_bbox_to_image__mutmut_19": x_clamp_bbox_to_image__mutmut_19,
    "x_clamp_bbox_to_image__mutmut_20": x_clamp_bbox_to_image__mutmut_20,
    "x_clamp_bbox_to_image__mutmut_21": x_clamp_bbox_to_image__mutmut_21,
    "x_clamp_bbox_to_image__mutmut_22": x_clamp_bbox_to_image__mutmut_22,
    "x_clamp_bbox_to_image__mutmut_23": x_clamp_bbox_to_image__mutmut_23,
    "x_clamp_bbox_to_image__mutmut_24": x_clamp_bbox_to_image__mutmut_24,
    "x_clamp_bbox_to_image__mutmut_25": x_clamp_bbox_to_image__mutmut_25,
    "x_clamp_bbox_to_image__mutmut_26": x_clamp_bbox_to_image__mutmut_26,
    "x_clamp_bbox_to_image__mutmut_27": x_clamp_bbox_to_image__mutmut_27,
    "x_clamp_bbox_to_image__mutmut_28": x_clamp_bbox_to_image__mutmut_28,
    "x_clamp_bbox_to_image__mutmut_29": x_clamp_bbox_to_image__mutmut_29,
    "x_clamp_bbox_to_image__mutmut_30": x_clamp_bbox_to_image__mutmut_30,
    "x_clamp_bbox_to_image__mutmut_31": x_clamp_bbox_to_image__mutmut_31,
    "x_clamp_bbox_to_image__mutmut_32": x_clamp_bbox_to_image__mutmut_32,
    "x_clamp_bbox_to_image__mutmut_33": x_clamp_bbox_to_image__mutmut_33,
    "x_clamp_bbox_to_image__mutmut_34": x_clamp_bbox_to_image__mutmut_34,
    "x_clamp_bbox_to_image__mutmut_35": x_clamp_bbox_to_image__mutmut_35,
    "x_clamp_bbox_to_image__mutmut_36": x_clamp_bbox_to_image__mutmut_36,
    "x_clamp_bbox_to_image__mutmut_37": x_clamp_bbox_to_image__mutmut_37,
    "x_clamp_bbox_to_image__mutmut_38": x_clamp_bbox_to_image__mutmut_38,
    "x_clamp_bbox_to_image__mutmut_39": x_clamp_bbox_to_image__mutmut_39,
    "x_clamp_bbox_to_image__mutmut_40": x_clamp_bbox_to_image__mutmut_40,
    "x_clamp_bbox_to_image__mutmut_41": x_clamp_bbox_to_image__mutmut_41,
    "x_clamp_bbox_to_image__mutmut_42": x_clamp_bbox_to_image__mutmut_42,
    "x_clamp_bbox_to_image__mutmut_43": x_clamp_bbox_to_image__mutmut_43,
    "x_clamp_bbox_to_image__mutmut_44": x_clamp_bbox_to_image__mutmut_44,
    "x_clamp_bbox_to_image__mutmut_45": x_clamp_bbox_to_image__mutmut_45,
    "x_clamp_bbox_to_image__mutmut_46": x_clamp_bbox_to_image__mutmut_46,
    "x_clamp_bbox_to_image__mutmut_47": x_clamp_bbox_to_image__mutmut_47,
    "x_clamp_bbox_to_image__mutmut_48": x_clamp_bbox_to_image__mutmut_48,
    "x_clamp_bbox_to_image__mutmut_49": x_clamp_bbox_to_image__mutmut_49,
    "x_clamp_bbox_to_image__mutmut_50": x_clamp_bbox_to_image__mutmut_50,
    "x_clamp_bbox_to_image__mutmut_51": x_clamp_bbox_to_image__mutmut_51,
    "x_clamp_bbox_to_image__mutmut_52": x_clamp_bbox_to_image__mutmut_52,
    "x_clamp_bbox_to_image__mutmut_53": x_clamp_bbox_to_image__mutmut_53,
    "x_clamp_bbox_to_image__mutmut_54": x_clamp_bbox_to_image__mutmut_54,
    "x_clamp_bbox_to_image__mutmut_55": x_clamp_bbox_to_image__mutmut_55,
    "x_clamp_bbox_to_image__mutmut_56": x_clamp_bbox_to_image__mutmut_56,
    "x_clamp_bbox_to_image__mutmut_57": x_clamp_bbox_to_image__mutmut_57,
    "x_clamp_bbox_to_image__mutmut_58": x_clamp_bbox_to_image__mutmut_58,
    "x_clamp_bbox_to_image__mutmut_59": x_clamp_bbox_to_image__mutmut_59,
}


def clamp_bbox_to_image(*args, **kwargs):
    result = _mutmut_trampoline(
        x_clamp_bbox_to_image__mutmut_orig, x_clamp_bbox_to_image__mutmut_mutants, args, kwargs
    )
    return result


clamp_bbox_to_image.__signature__ = _mutmut_signature(x_clamp_bbox_to_image__mutmut_orig)
x_clamp_bbox_to_image__mutmut_orig.__name__ = "x_clamp_bbox_to_image"


def x_validate_and_clamp_bbox__mutmut_orig(
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


def x_validate_and_clamp_bbox__mutmut_1(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    _allow_negative: bool = False,  # Reserved for future use
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


def x_validate_and_clamp_bbox__mutmut_2(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    _allow_negative: bool = True,  # Reserved for future use
    min_size: float = 2.0,
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


def x_validate_and_clamp_bbox__mutmut_3(
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
    warnings: list[str] = None
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


def x_validate_and_clamp_bbox__mutmut_4(
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
    x1, y1, x2, y2 = None

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


def x_validate_and_clamp_bbox__mutmut_5(
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

    if any(None):
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


def x_validate_and_clamp_bbox__mutmut_6(
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

    if any(math.isnan(v) and math.isinf(v) for v in (x1, y1, x2, y2)):
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


def x_validate_and_clamp_bbox__mutmut_7(
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

    if any(math.isnan(None) or math.isinf(v) for v in (x1, y1, x2, y2)):
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


def x_validate_and_clamp_bbox__mutmut_8(
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

    if any(math.isnan(v) or math.isinf(None) for v in (x1, y1, x2, y2)):
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


def x_validate_and_clamp_bbox__mutmut_9(
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
            is_valid=None,
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


def x_validate_and_clamp_bbox__mutmut_10(
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
            original_bbox=None,
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


def x_validate_and_clamp_bbox__mutmut_11(
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
            warnings=None,
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


def x_validate_and_clamp_bbox__mutmut_12(
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


def x_validate_and_clamp_bbox__mutmut_13(
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


def x_validate_and_clamp_bbox__mutmut_14(
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


def x_validate_and_clamp_bbox__mutmut_15(
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


def x_validate_and_clamp_bbox__mutmut_16(
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
            is_valid=True,
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


def x_validate_and_clamp_bbox__mutmut_17(
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
            warnings=["XXBounding box contains NaN or infinite valuesXX"],
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


def x_validate_and_clamp_bbox__mutmut_18(
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
            warnings=["bounding box contains nan or infinite values"],
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


def x_validate_and_clamp_bbox__mutmut_19(
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
            warnings=["BOUNDING BOX CONTAINS NAN OR INFINITE VALUES"],
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


def x_validate_and_clamp_bbox__mutmut_20(
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
    if x2 <= x1 and y2 <= y1:
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


def x_validate_and_clamp_bbox__mutmut_21(
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
    if x2 < x1 or y2 <= y1:
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


def x_validate_and_clamp_bbox__mutmut_22(
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
    if x2 <= x1 or y2 < y1:
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


def x_validate_and_clamp_bbox__mutmut_23(
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
            is_valid=None,
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


def x_validate_and_clamp_bbox__mutmut_24(
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
            original_bbox=None,
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


def x_validate_and_clamp_bbox__mutmut_25(
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
            warnings=None,
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


def x_validate_and_clamp_bbox__mutmut_26(
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


def x_validate_and_clamp_bbox__mutmut_27(
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


def x_validate_and_clamp_bbox__mutmut_28(
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


def x_validate_and_clamp_bbox__mutmut_29(
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


def x_validate_and_clamp_bbox__mutmut_30(
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
            is_valid=True,
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


def x_validate_and_clamp_bbox__mutmut_31(
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
            warnings=[f"Bounding box has invalid dimensions: width={x2 + x1}, height={y2 - y1}"],
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


def x_validate_and_clamp_bbox__mutmut_32(
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
            warnings=[f"Bounding box has invalid dimensions: width={x2 - x1}, height={y2 + y1}"],
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


def x_validate_and_clamp_bbox__mutmut_33(
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
    was_clamped = None

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


def x_validate_and_clamp_bbox__mutmut_34(
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
    was_clamped = True

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


def x_validate_and_clamp_bbox__mutmut_35(
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
    if x1 < 0 and y1 < 0:
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


def x_validate_and_clamp_bbox__mutmut_36(
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
    if x1 <= 0 or y1 < 0:
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


def x_validate_and_clamp_bbox__mutmut_37(
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
    if x1 < 1 or y1 < 0:
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


def x_validate_and_clamp_bbox__mutmut_38(
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
    if x1 < 0 or y1 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_39(
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
    if x1 < 0 or y1 < 1:
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


def x_validate_and_clamp_bbox__mutmut_40(
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
        warnings.append(None)
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


def x_validate_and_clamp_bbox__mutmut_41(
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
        was_clamped = None

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


def x_validate_and_clamp_bbox__mutmut_42(
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
        was_clamped = False

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


def x_validate_and_clamp_bbox__mutmut_43(
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
    if x2 > image_width and y2 > image_height:
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


def x_validate_and_clamp_bbox__mutmut_44(
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
    if x2 >= image_width or y2 > image_height:
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


def x_validate_and_clamp_bbox__mutmut_45(
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
    if x2 > image_width or y2 >= image_height:
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


def x_validate_and_clamp_bbox__mutmut_46(
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
        warnings.append(None)
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


def x_validate_and_clamp_bbox__mutmut_47(
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
        was_clamped = None

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


def x_validate_and_clamp_bbox__mutmut_48(
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
        was_clamped = False

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


def x_validate_and_clamp_bbox__mutmut_49(
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
    if x1 >= image_width or y1 >= image_height or (x2 <= 0 and y2 <= 0):
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


def x_validate_and_clamp_bbox__mutmut_50(
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
    if x1 >= image_width or (y1 >= image_height and x2 <= 0) or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_51(
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
    if (x1 >= image_width and y1 >= image_height) or x2 <= 0 or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_52(
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
    if x1 > image_width or y1 >= image_height or x2 <= 0 or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_53(
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
    if x1 >= image_width or y1 > image_height or x2 <= 0 or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_54(
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
    if x1 >= image_width or y1 >= image_height or x2 < 0 or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_55(
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
    if x1 >= image_width or y1 >= image_height or x2 <= 1 or y2 <= 0:
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


def x_validate_and_clamp_bbox__mutmut_56(
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
    if x1 >= image_width or y1 >= image_height or x2 <= 0 or y2 < 0:
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


def x_validate_and_clamp_bbox__mutmut_57(
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
    if x1 >= image_width or y1 >= image_height or x2 <= 0 or y2 <= 1:
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


def x_validate_and_clamp_bbox__mutmut_58(
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
            is_valid=None,
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


def x_validate_and_clamp_bbox__mutmut_59(
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
            original_bbox=None,
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


def x_validate_and_clamp_bbox__mutmut_60(
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
            warnings=None,
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


def x_validate_and_clamp_bbox__mutmut_61(
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
            was_clamped=None,
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


def x_validate_and_clamp_bbox__mutmut_62(
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
            was_empty_after_clamp=None,
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


def x_validate_and_clamp_bbox__mutmut_63(
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


def x_validate_and_clamp_bbox__mutmut_64(
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


def x_validate_and_clamp_bbox__mutmut_65(
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


def x_validate_and_clamp_bbox__mutmut_66(
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


def x_validate_and_clamp_bbox__mutmut_67(
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


def x_validate_and_clamp_bbox__mutmut_68(
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


def x_validate_and_clamp_bbox__mutmut_69(
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
            is_valid=True,
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


def x_validate_and_clamp_bbox__mutmut_70(
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
            warnings=["XXBounding box is completely outside image boundariesXX"],
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


def x_validate_and_clamp_bbox__mutmut_71(
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
            warnings=["bounding box is completely outside image boundaries"],
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


def x_validate_and_clamp_bbox__mutmut_72(
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
            warnings=["BOUNDING BOX IS COMPLETELY OUTSIDE IMAGE BOUNDARIES"],
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


def x_validate_and_clamp_bbox__mutmut_73(
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
            was_clamped=False,
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


def x_validate_and_clamp_bbox__mutmut_74(
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
            was_empty_after_clamp=False,
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


def x_validate_and_clamp_bbox__mutmut_75(
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
    clamped = None

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


def x_validate_and_clamp_bbox__mutmut_76(
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
        None,
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


def x_validate_and_clamp_bbox__mutmut_77(
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
        None,
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


def x_validate_and_clamp_bbox__mutmut_78(
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
        None,
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


def x_validate_and_clamp_bbox__mutmut_79(
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
        min_size=None,
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


def x_validate_and_clamp_bbox__mutmut_80(
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
        return_none_if_empty=None,
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


def x_validate_and_clamp_bbox__mutmut_81(
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


def x_validate_and_clamp_bbox__mutmut_82(
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


def x_validate_and_clamp_bbox__mutmut_83(
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


def x_validate_and_clamp_bbox__mutmut_84(
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


def x_validate_and_clamp_bbox__mutmut_85(
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


def x_validate_and_clamp_bbox__mutmut_86(
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
        return_none_if_empty=False,
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


def x_validate_and_clamp_bbox__mutmut_87(
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

    if clamped is not None:
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


def x_validate_and_clamp_bbox__mutmut_88(
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
            is_valid=None,
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


def x_validate_and_clamp_bbox__mutmut_89(
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
            original_bbox=None,
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


def x_validate_and_clamp_bbox__mutmut_90(
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
            warnings=None,
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


def x_validate_and_clamp_bbox__mutmut_91(
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
            was_clamped=None,
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


def x_validate_and_clamp_bbox__mutmut_92(
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
            was_empty_after_clamp=None,
        )

    return BoundingBoxValidationResult(
        is_valid=True,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_93(
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


def x_validate_and_clamp_bbox__mutmut_94(
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


def x_validate_and_clamp_bbox__mutmut_95(
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


def x_validate_and_clamp_bbox__mutmut_96(
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


def x_validate_and_clamp_bbox__mutmut_97(
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


def x_validate_and_clamp_bbox__mutmut_98(
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
        )

    return BoundingBoxValidationResult(
        is_valid=True,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_99(
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
            is_valid=True,
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


def x_validate_and_clamp_bbox__mutmut_100(
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
            warnings=[*warnings, "XXBounding box became too small after clampingXX"],
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


def x_validate_and_clamp_bbox__mutmut_101(
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
            warnings=[*warnings, "bounding box became too small after clamping"],
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


def x_validate_and_clamp_bbox__mutmut_102(
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
            warnings=[*warnings, "BOUNDING BOX BECAME TOO SMALL AFTER CLAMPING"],
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


def x_validate_and_clamp_bbox__mutmut_103(
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
            was_empty_after_clamp=False,
        )

    return BoundingBoxValidationResult(
        is_valid=True,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_104(
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
        is_valid=None,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_105(
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
        clamped_bbox=None,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_106(
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
        original_bbox=None,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_107(
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
        warnings=None,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_108(
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
        was_clamped=None,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_109(
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
        was_empty_after_clamp=None,
    )


def x_validate_and_clamp_bbox__mutmut_110(
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
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_111(
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
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_112(
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
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_113(
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
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_114(
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
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_115(
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
    )


def x_validate_and_clamp_bbox__mutmut_116(
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
        is_valid=False,
        clamped_bbox=clamped,
        original_bbox=bbox,
        warnings=warnings,
        was_clamped=was_clamped,
        was_empty_after_clamp=False,
    )


def x_validate_and_clamp_bbox__mutmut_117(
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
        was_empty_after_clamp=True,
    )


x_validate_and_clamp_bbox__mutmut_mutants: ClassVar[MutantDict] = {
    "x_validate_and_clamp_bbox__mutmut_1": x_validate_and_clamp_bbox__mutmut_1,
    "x_validate_and_clamp_bbox__mutmut_2": x_validate_and_clamp_bbox__mutmut_2,
    "x_validate_and_clamp_bbox__mutmut_3": x_validate_and_clamp_bbox__mutmut_3,
    "x_validate_and_clamp_bbox__mutmut_4": x_validate_and_clamp_bbox__mutmut_4,
    "x_validate_and_clamp_bbox__mutmut_5": x_validate_and_clamp_bbox__mutmut_5,
    "x_validate_and_clamp_bbox__mutmut_6": x_validate_and_clamp_bbox__mutmut_6,
    "x_validate_and_clamp_bbox__mutmut_7": x_validate_and_clamp_bbox__mutmut_7,
    "x_validate_and_clamp_bbox__mutmut_8": x_validate_and_clamp_bbox__mutmut_8,
    "x_validate_and_clamp_bbox__mutmut_9": x_validate_and_clamp_bbox__mutmut_9,
    "x_validate_and_clamp_bbox__mutmut_10": x_validate_and_clamp_bbox__mutmut_10,
    "x_validate_and_clamp_bbox__mutmut_11": x_validate_and_clamp_bbox__mutmut_11,
    "x_validate_and_clamp_bbox__mutmut_12": x_validate_and_clamp_bbox__mutmut_12,
    "x_validate_and_clamp_bbox__mutmut_13": x_validate_and_clamp_bbox__mutmut_13,
    "x_validate_and_clamp_bbox__mutmut_14": x_validate_and_clamp_bbox__mutmut_14,
    "x_validate_and_clamp_bbox__mutmut_15": x_validate_and_clamp_bbox__mutmut_15,
    "x_validate_and_clamp_bbox__mutmut_16": x_validate_and_clamp_bbox__mutmut_16,
    "x_validate_and_clamp_bbox__mutmut_17": x_validate_and_clamp_bbox__mutmut_17,
    "x_validate_and_clamp_bbox__mutmut_18": x_validate_and_clamp_bbox__mutmut_18,
    "x_validate_and_clamp_bbox__mutmut_19": x_validate_and_clamp_bbox__mutmut_19,
    "x_validate_and_clamp_bbox__mutmut_20": x_validate_and_clamp_bbox__mutmut_20,
    "x_validate_and_clamp_bbox__mutmut_21": x_validate_and_clamp_bbox__mutmut_21,
    "x_validate_and_clamp_bbox__mutmut_22": x_validate_and_clamp_bbox__mutmut_22,
    "x_validate_and_clamp_bbox__mutmut_23": x_validate_and_clamp_bbox__mutmut_23,
    "x_validate_and_clamp_bbox__mutmut_24": x_validate_and_clamp_bbox__mutmut_24,
    "x_validate_and_clamp_bbox__mutmut_25": x_validate_and_clamp_bbox__mutmut_25,
    "x_validate_and_clamp_bbox__mutmut_26": x_validate_and_clamp_bbox__mutmut_26,
    "x_validate_and_clamp_bbox__mutmut_27": x_validate_and_clamp_bbox__mutmut_27,
    "x_validate_and_clamp_bbox__mutmut_28": x_validate_and_clamp_bbox__mutmut_28,
    "x_validate_and_clamp_bbox__mutmut_29": x_validate_and_clamp_bbox__mutmut_29,
    "x_validate_and_clamp_bbox__mutmut_30": x_validate_and_clamp_bbox__mutmut_30,
    "x_validate_and_clamp_bbox__mutmut_31": x_validate_and_clamp_bbox__mutmut_31,
    "x_validate_and_clamp_bbox__mutmut_32": x_validate_and_clamp_bbox__mutmut_32,
    "x_validate_and_clamp_bbox__mutmut_33": x_validate_and_clamp_bbox__mutmut_33,
    "x_validate_and_clamp_bbox__mutmut_34": x_validate_and_clamp_bbox__mutmut_34,
    "x_validate_and_clamp_bbox__mutmut_35": x_validate_and_clamp_bbox__mutmut_35,
    "x_validate_and_clamp_bbox__mutmut_36": x_validate_and_clamp_bbox__mutmut_36,
    "x_validate_and_clamp_bbox__mutmut_37": x_validate_and_clamp_bbox__mutmut_37,
    "x_validate_and_clamp_bbox__mutmut_38": x_validate_and_clamp_bbox__mutmut_38,
    "x_validate_and_clamp_bbox__mutmut_39": x_validate_and_clamp_bbox__mutmut_39,
    "x_validate_and_clamp_bbox__mutmut_40": x_validate_and_clamp_bbox__mutmut_40,
    "x_validate_and_clamp_bbox__mutmut_41": x_validate_and_clamp_bbox__mutmut_41,
    "x_validate_and_clamp_bbox__mutmut_42": x_validate_and_clamp_bbox__mutmut_42,
    "x_validate_and_clamp_bbox__mutmut_43": x_validate_and_clamp_bbox__mutmut_43,
    "x_validate_and_clamp_bbox__mutmut_44": x_validate_and_clamp_bbox__mutmut_44,
    "x_validate_and_clamp_bbox__mutmut_45": x_validate_and_clamp_bbox__mutmut_45,
    "x_validate_and_clamp_bbox__mutmut_46": x_validate_and_clamp_bbox__mutmut_46,
    "x_validate_and_clamp_bbox__mutmut_47": x_validate_and_clamp_bbox__mutmut_47,
    "x_validate_and_clamp_bbox__mutmut_48": x_validate_and_clamp_bbox__mutmut_48,
    "x_validate_and_clamp_bbox__mutmut_49": x_validate_and_clamp_bbox__mutmut_49,
    "x_validate_and_clamp_bbox__mutmut_50": x_validate_and_clamp_bbox__mutmut_50,
    "x_validate_and_clamp_bbox__mutmut_51": x_validate_and_clamp_bbox__mutmut_51,
    "x_validate_and_clamp_bbox__mutmut_52": x_validate_and_clamp_bbox__mutmut_52,
    "x_validate_and_clamp_bbox__mutmut_53": x_validate_and_clamp_bbox__mutmut_53,
    "x_validate_and_clamp_bbox__mutmut_54": x_validate_and_clamp_bbox__mutmut_54,
    "x_validate_and_clamp_bbox__mutmut_55": x_validate_and_clamp_bbox__mutmut_55,
    "x_validate_and_clamp_bbox__mutmut_56": x_validate_and_clamp_bbox__mutmut_56,
    "x_validate_and_clamp_bbox__mutmut_57": x_validate_and_clamp_bbox__mutmut_57,
    "x_validate_and_clamp_bbox__mutmut_58": x_validate_and_clamp_bbox__mutmut_58,
    "x_validate_and_clamp_bbox__mutmut_59": x_validate_and_clamp_bbox__mutmut_59,
    "x_validate_and_clamp_bbox__mutmut_60": x_validate_and_clamp_bbox__mutmut_60,
    "x_validate_and_clamp_bbox__mutmut_61": x_validate_and_clamp_bbox__mutmut_61,
    "x_validate_and_clamp_bbox__mutmut_62": x_validate_and_clamp_bbox__mutmut_62,
    "x_validate_and_clamp_bbox__mutmut_63": x_validate_and_clamp_bbox__mutmut_63,
    "x_validate_and_clamp_bbox__mutmut_64": x_validate_and_clamp_bbox__mutmut_64,
    "x_validate_and_clamp_bbox__mutmut_65": x_validate_and_clamp_bbox__mutmut_65,
    "x_validate_and_clamp_bbox__mutmut_66": x_validate_and_clamp_bbox__mutmut_66,
    "x_validate_and_clamp_bbox__mutmut_67": x_validate_and_clamp_bbox__mutmut_67,
    "x_validate_and_clamp_bbox__mutmut_68": x_validate_and_clamp_bbox__mutmut_68,
    "x_validate_and_clamp_bbox__mutmut_69": x_validate_and_clamp_bbox__mutmut_69,
    "x_validate_and_clamp_bbox__mutmut_70": x_validate_and_clamp_bbox__mutmut_70,
    "x_validate_and_clamp_bbox__mutmut_71": x_validate_and_clamp_bbox__mutmut_71,
    "x_validate_and_clamp_bbox__mutmut_72": x_validate_and_clamp_bbox__mutmut_72,
    "x_validate_and_clamp_bbox__mutmut_73": x_validate_and_clamp_bbox__mutmut_73,
    "x_validate_and_clamp_bbox__mutmut_74": x_validate_and_clamp_bbox__mutmut_74,
    "x_validate_and_clamp_bbox__mutmut_75": x_validate_and_clamp_bbox__mutmut_75,
    "x_validate_and_clamp_bbox__mutmut_76": x_validate_and_clamp_bbox__mutmut_76,
    "x_validate_and_clamp_bbox__mutmut_77": x_validate_and_clamp_bbox__mutmut_77,
    "x_validate_and_clamp_bbox__mutmut_78": x_validate_and_clamp_bbox__mutmut_78,
    "x_validate_and_clamp_bbox__mutmut_79": x_validate_and_clamp_bbox__mutmut_79,
    "x_validate_and_clamp_bbox__mutmut_80": x_validate_and_clamp_bbox__mutmut_80,
    "x_validate_and_clamp_bbox__mutmut_81": x_validate_and_clamp_bbox__mutmut_81,
    "x_validate_and_clamp_bbox__mutmut_82": x_validate_and_clamp_bbox__mutmut_82,
    "x_validate_and_clamp_bbox__mutmut_83": x_validate_and_clamp_bbox__mutmut_83,
    "x_validate_and_clamp_bbox__mutmut_84": x_validate_and_clamp_bbox__mutmut_84,
    "x_validate_and_clamp_bbox__mutmut_85": x_validate_and_clamp_bbox__mutmut_85,
    "x_validate_and_clamp_bbox__mutmut_86": x_validate_and_clamp_bbox__mutmut_86,
    "x_validate_and_clamp_bbox__mutmut_87": x_validate_and_clamp_bbox__mutmut_87,
    "x_validate_and_clamp_bbox__mutmut_88": x_validate_and_clamp_bbox__mutmut_88,
    "x_validate_and_clamp_bbox__mutmut_89": x_validate_and_clamp_bbox__mutmut_89,
    "x_validate_and_clamp_bbox__mutmut_90": x_validate_and_clamp_bbox__mutmut_90,
    "x_validate_and_clamp_bbox__mutmut_91": x_validate_and_clamp_bbox__mutmut_91,
    "x_validate_and_clamp_bbox__mutmut_92": x_validate_and_clamp_bbox__mutmut_92,
    "x_validate_and_clamp_bbox__mutmut_93": x_validate_and_clamp_bbox__mutmut_93,
    "x_validate_and_clamp_bbox__mutmut_94": x_validate_and_clamp_bbox__mutmut_94,
    "x_validate_and_clamp_bbox__mutmut_95": x_validate_and_clamp_bbox__mutmut_95,
    "x_validate_and_clamp_bbox__mutmut_96": x_validate_and_clamp_bbox__mutmut_96,
    "x_validate_and_clamp_bbox__mutmut_97": x_validate_and_clamp_bbox__mutmut_97,
    "x_validate_and_clamp_bbox__mutmut_98": x_validate_and_clamp_bbox__mutmut_98,
    "x_validate_and_clamp_bbox__mutmut_99": x_validate_and_clamp_bbox__mutmut_99,
    "x_validate_and_clamp_bbox__mutmut_100": x_validate_and_clamp_bbox__mutmut_100,
    "x_validate_and_clamp_bbox__mutmut_101": x_validate_and_clamp_bbox__mutmut_101,
    "x_validate_and_clamp_bbox__mutmut_102": x_validate_and_clamp_bbox__mutmut_102,
    "x_validate_and_clamp_bbox__mutmut_103": x_validate_and_clamp_bbox__mutmut_103,
    "x_validate_and_clamp_bbox__mutmut_104": x_validate_and_clamp_bbox__mutmut_104,
    "x_validate_and_clamp_bbox__mutmut_105": x_validate_and_clamp_bbox__mutmut_105,
    "x_validate_and_clamp_bbox__mutmut_106": x_validate_and_clamp_bbox__mutmut_106,
    "x_validate_and_clamp_bbox__mutmut_107": x_validate_and_clamp_bbox__mutmut_107,
    "x_validate_and_clamp_bbox__mutmut_108": x_validate_and_clamp_bbox__mutmut_108,
    "x_validate_and_clamp_bbox__mutmut_109": x_validate_and_clamp_bbox__mutmut_109,
    "x_validate_and_clamp_bbox__mutmut_110": x_validate_and_clamp_bbox__mutmut_110,
    "x_validate_and_clamp_bbox__mutmut_111": x_validate_and_clamp_bbox__mutmut_111,
    "x_validate_and_clamp_bbox__mutmut_112": x_validate_and_clamp_bbox__mutmut_112,
    "x_validate_and_clamp_bbox__mutmut_113": x_validate_and_clamp_bbox__mutmut_113,
    "x_validate_and_clamp_bbox__mutmut_114": x_validate_and_clamp_bbox__mutmut_114,
    "x_validate_and_clamp_bbox__mutmut_115": x_validate_and_clamp_bbox__mutmut_115,
    "x_validate_and_clamp_bbox__mutmut_116": x_validate_and_clamp_bbox__mutmut_116,
    "x_validate_and_clamp_bbox__mutmut_117": x_validate_and_clamp_bbox__mutmut_117,
}


def validate_and_clamp_bbox(*args, **kwargs):
    result = _mutmut_trampoline(
        x_validate_and_clamp_bbox__mutmut_orig,
        x_validate_and_clamp_bbox__mutmut_mutants,
        args,
        kwargs,
    )
    return result


validate_and_clamp_bbox.__signature__ = _mutmut_signature(x_validate_and_clamp_bbox__mutmut_orig)
x_validate_and_clamp_bbox__mutmut_orig.__name__ = "x_validate_and_clamp_bbox"


def x_normalize_bbox_to_pixels__mutmut_orig(
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


def x_normalize_bbox_to_pixels__mutmut_1(
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
    x1, y1, x2, y2 = None
    return (
        int(x1 * image_width),
        int(y1 * image_height),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_2(
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
        int(None),
        int(y1 * image_height),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_3(
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
        int(x1 / image_width),
        int(y1 * image_height),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_4(
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
        int(None),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_5(
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
        int(y1 / image_height),
        int(x2 * image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_6(
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
        int(None),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_7(
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
        int(x2 / image_width),
        int(y2 * image_height),
    )


def x_normalize_bbox_to_pixels__mutmut_8(
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
        int(None),
    )


def x_normalize_bbox_to_pixels__mutmut_9(
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
        int(y2 / image_height),
    )


x_normalize_bbox_to_pixels__mutmut_mutants: ClassVar[MutantDict] = {
    "x_normalize_bbox_to_pixels__mutmut_1": x_normalize_bbox_to_pixels__mutmut_1,
    "x_normalize_bbox_to_pixels__mutmut_2": x_normalize_bbox_to_pixels__mutmut_2,
    "x_normalize_bbox_to_pixels__mutmut_3": x_normalize_bbox_to_pixels__mutmut_3,
    "x_normalize_bbox_to_pixels__mutmut_4": x_normalize_bbox_to_pixels__mutmut_4,
    "x_normalize_bbox_to_pixels__mutmut_5": x_normalize_bbox_to_pixels__mutmut_5,
    "x_normalize_bbox_to_pixels__mutmut_6": x_normalize_bbox_to_pixels__mutmut_6,
    "x_normalize_bbox_to_pixels__mutmut_7": x_normalize_bbox_to_pixels__mutmut_7,
    "x_normalize_bbox_to_pixels__mutmut_8": x_normalize_bbox_to_pixels__mutmut_8,
    "x_normalize_bbox_to_pixels__mutmut_9": x_normalize_bbox_to_pixels__mutmut_9,
}


def normalize_bbox_to_pixels(*args, **kwargs):
    result = _mutmut_trampoline(
        x_normalize_bbox_to_pixels__mutmut_orig,
        x_normalize_bbox_to_pixels__mutmut_mutants,
        args,
        kwargs,
    )
    return result


normalize_bbox_to_pixels.__signature__ = _mutmut_signature(x_normalize_bbox_to_pixels__mutmut_orig)
x_normalize_bbox_to_pixels__mutmut_orig.__name__ = "x_normalize_bbox_to_pixels"


def x_normalize_bbox_to_float__mutmut_orig(
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


def x_normalize_bbox_to_float__mutmut_1(
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
    x1, y1, x2, y2 = None
    return (
        x1 / image_width,
        y1 / image_height,
        x2 / image_width,
        y2 / image_height,
    )


def x_normalize_bbox_to_float__mutmut_2(
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
        x1 * image_width,
        y1 / image_height,
        x2 / image_width,
        y2 / image_height,
    )


def x_normalize_bbox_to_float__mutmut_3(
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
        y1 * image_height,
        x2 / image_width,
        y2 / image_height,
    )


def x_normalize_bbox_to_float__mutmut_4(
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
        x2 * image_width,
        y2 / image_height,
    )


def x_normalize_bbox_to_float__mutmut_5(
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
        y2 * image_height,
    )


x_normalize_bbox_to_float__mutmut_mutants: ClassVar[MutantDict] = {
    "x_normalize_bbox_to_float__mutmut_1": x_normalize_bbox_to_float__mutmut_1,
    "x_normalize_bbox_to_float__mutmut_2": x_normalize_bbox_to_float__mutmut_2,
    "x_normalize_bbox_to_float__mutmut_3": x_normalize_bbox_to_float__mutmut_3,
    "x_normalize_bbox_to_float__mutmut_4": x_normalize_bbox_to_float__mutmut_4,
    "x_normalize_bbox_to_float__mutmut_5": x_normalize_bbox_to_float__mutmut_5,
}


def normalize_bbox_to_float(*args, **kwargs):
    result = _mutmut_trampoline(
        x_normalize_bbox_to_float__mutmut_orig,
        x_normalize_bbox_to_float__mutmut_mutants,
        args,
        kwargs,
    )
    return result


normalize_bbox_to_float.__signature__ = _mutmut_signature(x_normalize_bbox_to_float__mutmut_orig)
x_normalize_bbox_to_float__mutmut_orig.__name__ = "x_normalize_bbox_to_float"


def x_calculate_bbox_area__mutmut_orig(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_1(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = None
    return max(0, x2 - x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_2(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) / max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_3(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(None, x2 - x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_4(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, None) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_5(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(x2 - x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_6(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(
        0,
    ) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_7(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(1, x2 - x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_8(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 + x1) * max(0, y2 - y1)


def x_calculate_bbox_area__mutmut_9(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(None, y2 - y1)


def x_calculate_bbox_area__mutmut_10(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, None)


def x_calculate_bbox_area__mutmut_11(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(y2 - y1)


def x_calculate_bbox_area__mutmut_12(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(
        0,
    )


def x_calculate_bbox_area__mutmut_13(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(1, y2 - y1)


def x_calculate_bbox_area__mutmut_14(bbox: tuple[float, float, float, float]) -> float:
    """Calculate the area of a bounding box.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)

    Returns:
        Area of the bounding box (width * height)
    """
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 + y1)


x_calculate_bbox_area__mutmut_mutants: ClassVar[MutantDict] = {
    "x_calculate_bbox_area__mutmut_1": x_calculate_bbox_area__mutmut_1,
    "x_calculate_bbox_area__mutmut_2": x_calculate_bbox_area__mutmut_2,
    "x_calculate_bbox_area__mutmut_3": x_calculate_bbox_area__mutmut_3,
    "x_calculate_bbox_area__mutmut_4": x_calculate_bbox_area__mutmut_4,
    "x_calculate_bbox_area__mutmut_5": x_calculate_bbox_area__mutmut_5,
    "x_calculate_bbox_area__mutmut_6": x_calculate_bbox_area__mutmut_6,
    "x_calculate_bbox_area__mutmut_7": x_calculate_bbox_area__mutmut_7,
    "x_calculate_bbox_area__mutmut_8": x_calculate_bbox_area__mutmut_8,
    "x_calculate_bbox_area__mutmut_9": x_calculate_bbox_area__mutmut_9,
    "x_calculate_bbox_area__mutmut_10": x_calculate_bbox_area__mutmut_10,
    "x_calculate_bbox_area__mutmut_11": x_calculate_bbox_area__mutmut_11,
    "x_calculate_bbox_area__mutmut_12": x_calculate_bbox_area__mutmut_12,
    "x_calculate_bbox_area__mutmut_13": x_calculate_bbox_area__mutmut_13,
    "x_calculate_bbox_area__mutmut_14": x_calculate_bbox_area__mutmut_14,
}


def calculate_bbox_area(*args, **kwargs):
    result = _mutmut_trampoline(
        x_calculate_bbox_area__mutmut_orig, x_calculate_bbox_area__mutmut_mutants, args, kwargs
    )
    return result


calculate_bbox_area.__signature__ = _mutmut_signature(x_calculate_bbox_area__mutmut_orig)
x_calculate_bbox_area__mutmut_orig.__name__ = "x_calculate_bbox_area"


def x_calculate_bbox_iou__mutmut_orig(
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


def x_calculate_bbox_iou__mutmut_1(
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
    x1_1, y1_1, x2_1, y2_1 = None
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


def x_calculate_bbox_iou__mutmut_2(
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
    x1_2, y1_2, x2_2, y2_2 = None

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


def x_calculate_bbox_iou__mutmut_3(
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
    x1_i = None
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


def x_calculate_bbox_iou__mutmut_4(
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
    x1_i = max(None, x1_2)
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


def x_calculate_bbox_iou__mutmut_5(
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
    x1_i = max(x1_1, None)
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


def x_calculate_bbox_iou__mutmut_6(
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
    x1_i = max(x1_2)
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


def x_calculate_bbox_iou__mutmut_7(
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
    x1_i = max(
        x1_1,
    )
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


def x_calculate_bbox_iou__mutmut_8(
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
    y1_i = None
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


def x_calculate_bbox_iou__mutmut_9(
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
    y1_i = max(None, y1_2)
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


def x_calculate_bbox_iou__mutmut_10(
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
    y1_i = max(y1_1, None)
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


def x_calculate_bbox_iou__mutmut_11(
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
    y1_i = max(y1_2)
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


def x_calculate_bbox_iou__mutmut_12(
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
    y1_i = max(
        y1_1,
    )
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


def x_calculate_bbox_iou__mutmut_13(
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
    x2_i = None
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


def x_calculate_bbox_iou__mutmut_14(
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
    x2_i = min(None, x2_2)
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


def x_calculate_bbox_iou__mutmut_15(
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
    x2_i = min(x2_1, None)
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


def x_calculate_bbox_iou__mutmut_16(
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
    x2_i = min(x2_2)
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


def x_calculate_bbox_iou__mutmut_17(
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
    x2_i = min(
        x2_1,
    )
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


def x_calculate_bbox_iou__mutmut_18(
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
    y2_i = None

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


def x_calculate_bbox_iou__mutmut_19(
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
    y2_i = min(None, y2_2)

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


def x_calculate_bbox_iou__mutmut_20(
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
    y2_i = min(y2_1, None)

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


def x_calculate_bbox_iou__mutmut_21(
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
    y2_i = min(y2_2)

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


def x_calculate_bbox_iou__mutmut_22(
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
    y2_i = min(
        y2_1,
    )

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


def x_calculate_bbox_iou__mutmut_23(
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

    if x2_i <= x1_i and y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_24(
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

    if x2_i < x1_i or y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_25(
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

    if x2_i <= x1_i or y2_i < y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_26(
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
        return 1.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_27(
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

    intersection = None

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_28(
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

    intersection = (x2_i - x1_i) / (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_29(
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

    intersection = (x2_i + x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_30(
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

    intersection = (x2_i - x1_i) * (y2_i + y1_i)

    # Calculate union
    area1 = calculate_bbox_area(bbox1)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_31(
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
    area1 = None
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_32(
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
    area1 = calculate_bbox_area(None)
    area2 = calculate_bbox_area(bbox2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_33(
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
    area2 = None
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_34(
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
    area2 = calculate_bbox_area(None)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_35(
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
    union = None

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_36(
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
    union = area1 + area2 + intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_37(
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
    union = area1 - area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_38(
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

    if union < 0:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_39(
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

    if union <= 1:
        return 0.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_40(
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
        return 1.0

    return intersection / union


def x_calculate_bbox_iou__mutmut_41(
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

    return intersection * union


x_calculate_bbox_iou__mutmut_mutants: ClassVar[MutantDict] = {
    "x_calculate_bbox_iou__mutmut_1": x_calculate_bbox_iou__mutmut_1,
    "x_calculate_bbox_iou__mutmut_2": x_calculate_bbox_iou__mutmut_2,
    "x_calculate_bbox_iou__mutmut_3": x_calculate_bbox_iou__mutmut_3,
    "x_calculate_bbox_iou__mutmut_4": x_calculate_bbox_iou__mutmut_4,
    "x_calculate_bbox_iou__mutmut_5": x_calculate_bbox_iou__mutmut_5,
    "x_calculate_bbox_iou__mutmut_6": x_calculate_bbox_iou__mutmut_6,
    "x_calculate_bbox_iou__mutmut_7": x_calculate_bbox_iou__mutmut_7,
    "x_calculate_bbox_iou__mutmut_8": x_calculate_bbox_iou__mutmut_8,
    "x_calculate_bbox_iou__mutmut_9": x_calculate_bbox_iou__mutmut_9,
    "x_calculate_bbox_iou__mutmut_10": x_calculate_bbox_iou__mutmut_10,
    "x_calculate_bbox_iou__mutmut_11": x_calculate_bbox_iou__mutmut_11,
    "x_calculate_bbox_iou__mutmut_12": x_calculate_bbox_iou__mutmut_12,
    "x_calculate_bbox_iou__mutmut_13": x_calculate_bbox_iou__mutmut_13,
    "x_calculate_bbox_iou__mutmut_14": x_calculate_bbox_iou__mutmut_14,
    "x_calculate_bbox_iou__mutmut_15": x_calculate_bbox_iou__mutmut_15,
    "x_calculate_bbox_iou__mutmut_16": x_calculate_bbox_iou__mutmut_16,
    "x_calculate_bbox_iou__mutmut_17": x_calculate_bbox_iou__mutmut_17,
    "x_calculate_bbox_iou__mutmut_18": x_calculate_bbox_iou__mutmut_18,
    "x_calculate_bbox_iou__mutmut_19": x_calculate_bbox_iou__mutmut_19,
    "x_calculate_bbox_iou__mutmut_20": x_calculate_bbox_iou__mutmut_20,
    "x_calculate_bbox_iou__mutmut_21": x_calculate_bbox_iou__mutmut_21,
    "x_calculate_bbox_iou__mutmut_22": x_calculate_bbox_iou__mutmut_22,
    "x_calculate_bbox_iou__mutmut_23": x_calculate_bbox_iou__mutmut_23,
    "x_calculate_bbox_iou__mutmut_24": x_calculate_bbox_iou__mutmut_24,
    "x_calculate_bbox_iou__mutmut_25": x_calculate_bbox_iou__mutmut_25,
    "x_calculate_bbox_iou__mutmut_26": x_calculate_bbox_iou__mutmut_26,
    "x_calculate_bbox_iou__mutmut_27": x_calculate_bbox_iou__mutmut_27,
    "x_calculate_bbox_iou__mutmut_28": x_calculate_bbox_iou__mutmut_28,
    "x_calculate_bbox_iou__mutmut_29": x_calculate_bbox_iou__mutmut_29,
    "x_calculate_bbox_iou__mutmut_30": x_calculate_bbox_iou__mutmut_30,
    "x_calculate_bbox_iou__mutmut_31": x_calculate_bbox_iou__mutmut_31,
    "x_calculate_bbox_iou__mutmut_32": x_calculate_bbox_iou__mutmut_32,
    "x_calculate_bbox_iou__mutmut_33": x_calculate_bbox_iou__mutmut_33,
    "x_calculate_bbox_iou__mutmut_34": x_calculate_bbox_iou__mutmut_34,
    "x_calculate_bbox_iou__mutmut_35": x_calculate_bbox_iou__mutmut_35,
    "x_calculate_bbox_iou__mutmut_36": x_calculate_bbox_iou__mutmut_36,
    "x_calculate_bbox_iou__mutmut_37": x_calculate_bbox_iou__mutmut_37,
    "x_calculate_bbox_iou__mutmut_38": x_calculate_bbox_iou__mutmut_38,
    "x_calculate_bbox_iou__mutmut_39": x_calculate_bbox_iou__mutmut_39,
    "x_calculate_bbox_iou__mutmut_40": x_calculate_bbox_iou__mutmut_40,
    "x_calculate_bbox_iou__mutmut_41": x_calculate_bbox_iou__mutmut_41,
}


def calculate_bbox_iou(*args, **kwargs):
    result = _mutmut_trampoline(
        x_calculate_bbox_iou__mutmut_orig, x_calculate_bbox_iou__mutmut_mutants, args, kwargs
    )
    return result


calculate_bbox_iou.__signature__ = _mutmut_signature(x_calculate_bbox_iou__mutmut_orig)
x_calculate_bbox_iou__mutmut_orig.__name__ = "x_calculate_bbox_iou"
