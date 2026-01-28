"""Unit tests for bounding box validation utilities.

Tests cover:
- is_valid_bbox function
- validate_bbox function with various error conditions
- clamp_bbox_to_image function
- validate_and_clamp_bbox convenience function
- Coordinate normalization functions
- Area and IoU calculations
- Edge cases and error handling

Related Linear Issues:
- NEM-1122: Bounding boxes exceeding image boundaries
- NEM-1102: Comprehensive bbox validation in estimate_object_distance
- NEM-1073: Bounding box validation in ReIdentificationService
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.services.bbox_validation import (
    BoundingBoxOutOfBoundsError,
    BoundingBoxValidationError,
    BoundingBoxValidationResult,
    InvalidBoundingBoxError,
    calculate_bbox_area,
    calculate_bbox_iou,
    clamp_bbox_to_image,
    is_valid_bbox,
    normalize_bbox_to_float,
    normalize_bbox_to_pixels,
    prepare_bbox_for_crop,
    scale_bbox_to_image,
    validate_and_clamp_bbox,
    validate_bbox,
)
from backend.tests.strategies import (
    bbox_and_image_strategy,
    image_dimensions_strategy,
    invalid_bbox_xyxy_strategy,
    normalized_bbox_strategy,
    valid_bbox_xyxy_strategy,
)

# =============================================================================
# Test is_valid_bbox
# =============================================================================


class TestIsValidBbox:
    """Tests for is_valid_bbox function."""

    def test_valid_bbox_returns_true(self) -> None:
        """Test that valid bounding boxes return True."""
        assert is_valid_bbox((0, 0, 100, 100)) is True
        assert is_valid_bbox((10, 20, 30, 40)) is True
        assert is_valid_bbox((0.5, 0.5, 100.5, 100.5)) is True

    def test_zero_width_returns_false(self) -> None:
        """Test that zero-width boxes return False."""
        assert is_valid_bbox((50, 0, 50, 100)) is False

    def test_zero_height_returns_false(self) -> None:
        """Test that zero-height boxes return False."""
        assert is_valid_bbox((0, 50, 100, 50)) is False

    def test_negative_width_returns_false(self) -> None:
        """Test that negative-width boxes return False."""
        assert is_valid_bbox((100, 0, 50, 100)) is False

    def test_negative_height_returns_false(self) -> None:
        """Test that negative-height boxes return False."""
        assert is_valid_bbox((0, 100, 100, 50)) is False

    @pytest.mark.parametrize(
        "bbox,reason",
        [
            ((-10, 0, 100, 100), "negative x1"),
            ((0, -10, 100, 100), "negative y1"),
            ((-10, -10, 100, 100), "negative x1 and y1"),
        ],
    )
    def test_negative_coordinates_default_invalid(
        self, bbox: tuple[float, float, float, float], reason: str
    ) -> None:
        """Test that negative coordinates are invalid by default."""
        assert is_valid_bbox(bbox) is False, f"Should reject by default: {reason}"

    @pytest.mark.parametrize(
        "bbox,reason",
        [
            ((-10, 0, 100, 100), "negative x1"),
            ((0, -10, 100, 100), "negative y1"),
            ((-10, -10, 100, 100), "negative x1 and y1"),
        ],
    )
    def test_negative_coordinates_allowed_when_enabled(
        self, bbox: tuple[float, float, float, float], reason: str
    ) -> None:
        """Test that negative coordinates can be allowed."""
        assert is_valid_bbox(bbox, allow_negative=True) is True, (
            f"Should allow when enabled: {reason}"
        )

    @pytest.mark.parametrize(
        "invalid_bbox,reason",
        [
            ((float("nan"), 0, 100, 100), "NaN in x1"),
            ((0, float("nan"), 100, 100), "NaN in y1"),
            ((0, 0, float("nan"), 100), "NaN in x2"),
            ((0, 0, 100, float("nan")), "NaN in y2"),
        ],
    )
    def test_nan_values_return_false(
        self, invalid_bbox: tuple[float, float, float, float], reason: str
    ) -> None:
        """Test that NaN values return False."""
        assert is_valid_bbox(invalid_bbox) is False, f"Should reject: {reason}"

    @pytest.mark.parametrize(
        "invalid_bbox,reason",
        [
            ((float("inf"), 0, 100, 100), "inf in x1"),
            ((float("-inf"), 0, 100, 100), "-inf in x1"),
            ((0, 0, float("inf"), 100), "inf in x2"),
        ],
    )
    def test_infinite_values_return_false(
        self, invalid_bbox: tuple[float, float, float, float], reason: str
    ) -> None:
        """Test that infinite values return False."""
        assert is_valid_bbox(invalid_bbox) is False, f"Should reject: {reason}"

    @pytest.mark.parametrize(
        "invalid_input,reason",
        [
            (None, "None value"),
            ((1, 2, 3), "3-tuple"),
            ("invalid", "string value"),
            ((1, 2, 3, 4, 5), "5-tuple"),
        ],
    )
    def test_invalid_type_returns_false(self, invalid_input: object, reason: str) -> None:
        """Test that invalid types return False."""
        assert is_valid_bbox(invalid_input) is False, f"Should reject: {reason}"  # type: ignore[arg-type]


# =============================================================================
# Test validate_bbox
# =============================================================================


class TestValidateBbox:
    """Tests for validate_bbox function."""

    def test_valid_bbox_no_exception(self) -> None:
        """Test that valid bounding boxes pass without exception."""
        validate_bbox((0, 0, 100, 100))  # Should not raise
        validate_bbox((10, 20, 30, 40))  # Should not raise

    def test_zero_width_raises_invalid_error(self) -> None:
        """Test that zero-width boxes raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((50, 0, 50, 100))
        assert "zero or negative width" in str(exc_info.value)
        assert exc_info.value.bbox == (50, 0, 50, 100)

    def test_zero_height_raises_invalid_error(self) -> None:
        """Test that zero-height boxes raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((0, 50, 100, 50))
        assert "zero or negative height" in str(exc_info.value)

    def test_negative_width_raises_invalid_error(self) -> None:
        """Test that negative-width boxes raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((100, 0, 50, 100))
        assert "zero or negative width" in str(exc_info.value)

    def test_negative_coordinates_raises_invalid_error(self) -> None:
        """Test that negative coordinates raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((-10, 0, 100, 100))
        assert "negative coordinates" in str(exc_info.value)

    def test_negative_coordinates_allowed_when_enabled(self) -> None:
        """Test that negative coordinates pass when allowed."""
        validate_bbox((-10, -10, 100, 100), allow_negative=True)  # Should not raise

    def test_nan_values_raise_invalid_error(self) -> None:
        """Test that NaN values raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((float("nan"), 0, 100, 100))
        assert "NaN or infinite" in str(exc_info.value)

    def test_infinite_values_raise_invalid_error(self) -> None:
        """Test that infinite values raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((float("inf"), 0, 100, 100))
        assert "NaN or infinite" in str(exc_info.value)

    def test_invalid_format_raises_invalid_error(self) -> None:
        """Test that invalid format raises InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError) as exc_info:
            validate_bbox((1, 2, 3))  # type: ignore[arg-type]
        assert "Invalid bounding box format" in str(exc_info.value)

    def test_out_of_bounds_strict_mode(self) -> None:
        """Test that out-of-bounds boxes raise error in strict mode."""
        with pytest.raises(BoundingBoxOutOfBoundsError) as exc_info:
            validate_bbox(
                (0, 0, 150, 150),
                image_width=100,
                image_height=100,
                strict_bounds=True,
            )
        assert "exceeds image bounds" in str(exc_info.value)
        assert exc_info.value.image_size == (100, 100)

    def test_out_of_bounds_non_strict_mode_passes(self) -> None:
        """Test that out-of-bounds boxes pass in non-strict mode."""
        # Should not raise when strict_bounds=False (default)
        validate_bbox((0, 0, 150, 150), image_width=100, image_height=100)


# =============================================================================
# Test clamp_bbox_to_image
# =============================================================================


class TestClampBboxToImage:
    """Tests for clamp_bbox_to_image function."""

    def test_clamp_bbox_within_bounds(self) -> None:
        """Test that boxes within bounds are unchanged."""
        result = clamp_bbox_to_image((10, 20, 80, 90), 100, 100)
        assert result == (10, 20, 80, 90)

    def test_clamp_negative_coordinates(self) -> None:
        """Test that negative coordinates are clamped to 0."""
        result = clamp_bbox_to_image((-10, -20, 80, 90), 100, 100)
        assert result == (0, 0, 80, 90)

    def test_clamp_exceeding_coordinates(self) -> None:
        """Test that exceeding coordinates are clamped to image bounds."""
        result = clamp_bbox_to_image((10, 20, 150, 160), 100, 100)
        assert result == (10, 20, 100, 100)

    def test_clamp_both_sides(self) -> None:
        """Test clamping on both sides."""
        result = clamp_bbox_to_image((-10, -10, 150, 150), 100, 100)
        assert result == (0, 0, 100, 100)

    def test_clamp_completely_outside_returns_none(self) -> None:
        """Test that completely outside boxes return None."""
        result = clamp_bbox_to_image((200, 200, 300, 300), 100, 100)
        assert result is None

    def test_clamp_too_small_returns_none(self) -> None:
        """Test that boxes too small after clamping return None."""
        # Box that after clamping would have width < 1
        result = clamp_bbox_to_image((99.5, 0, 100.5, 100), 100, 100, min_size=1.0)
        assert result is None

    def test_clamp_preserves_integer_type(self) -> None:
        """Test that integer input produces integer output."""
        result = clamp_bbox_to_image((-5, -5, 50, 50), 100, 100)
        assert result == (0, 0, 50, 50)
        assert all(isinstance(v, int) for v in result)  # type: ignore[union-attr]

    def test_clamp_preserves_float_type(self) -> None:
        """Test that float input produces float output."""
        result = clamp_bbox_to_image((-5.0, -5.0, 50.0, 50.0), 100, 100)
        assert result == (0.0, 0.0, 50.0, 50.0)

    def test_clamp_with_custom_min_size(self) -> None:
        """Test clamping with custom minimum size."""
        # Box that would be 2x2 after clamping, with min_size=5
        result = clamp_bbox_to_image((98, 98, 102, 102), 100, 100, min_size=5.0)
        assert result is None

    def test_clamp_return_minimal_box_when_not_none(self) -> None:
        """Test that return_none_if_empty=False returns minimal box."""
        result = clamp_bbox_to_image(
            (99, 99, 100, 100), 100, 100, min_size=5.0, return_none_if_empty=False
        )
        # Should return a box starting at (99, 99) with min_size dimensions
        assert result is not None
        x1, y1, _x2, _y2 = result
        assert x1 == 99
        assert y1 == 99


# =============================================================================
# Test validate_and_clamp_bbox
# =============================================================================


class TestValidateAndClampBbox:
    """Tests for validate_and_clamp_bbox function."""

    def test_valid_bbox_returns_valid_result(self) -> None:
        """Test that valid boxes return valid result."""
        result = validate_and_clamp_bbox((10, 20, 80, 90), 100, 100)
        assert result.is_valid is True
        assert result.clamped_bbox == (10, 20, 80, 90)
        assert result.original_bbox == (10, 20, 80, 90)
        assert result.warnings == []
        assert result.was_clamped is False

    def test_clamped_bbox_returns_warnings(self) -> None:
        """Test that clamped boxes include warnings."""
        result = validate_and_clamp_bbox((-10, -10, 150, 150), 100, 100)
        assert result.is_valid is True
        assert result.clamped_bbox == (0, 0, 100, 100)
        assert result.was_clamped is True
        assert len(result.warnings) > 0

    def test_invalid_dimensions_returns_invalid(self) -> None:
        """Test that invalid dimensions return invalid result."""
        result = validate_and_clamp_bbox((50, 50, 50, 50), 100, 100)  # Zero size
        assert result.is_valid is False
        assert result.clamped_bbox is None
        assert "invalid dimensions" in result.warnings[0]

    def test_nan_values_return_invalid(self) -> None:
        """Test that NaN values return invalid result."""
        result = validate_and_clamp_bbox((float("nan"), 0, 100, 100), 100, 100)
        assert result.is_valid is False
        assert result.clamped_bbox is None
        assert "NaN" in result.warnings[0]

    def test_completely_outside_returns_invalid(self) -> None:
        """Test that boxes completely outside return invalid."""
        result = validate_and_clamp_bbox((200, 200, 300, 300), 100, 100)
        assert result.is_valid is False
        assert result.was_empty_after_clamp is True

    def test_result_dataclass_attributes(self) -> None:
        """Test BoundingBoxValidationResult has all expected attributes."""
        result = validate_and_clamp_bbox((10, 20, 80, 90), 100, 100)
        assert isinstance(result, BoundingBoxValidationResult)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "clamped_bbox")
        assert hasattr(result, "original_bbox")
        assert hasattr(result, "warnings")
        assert hasattr(result, "was_clamped")
        assert hasattr(result, "was_empty_after_clamp")


# =============================================================================
# Test normalize_bbox functions
# =============================================================================


class TestNormalizeBboxToPixels:
    """Tests for normalize_bbox_to_pixels function."""

    def test_normalize_full_image(self) -> None:
        """Test normalizing a full-image bbox."""
        result = normalize_bbox_to_pixels((0.0, 0.0, 1.0, 1.0), 640, 480)
        assert result == (0, 0, 640, 480)

    def test_normalize_center_region(self) -> None:
        """Test normalizing a center region."""
        result = normalize_bbox_to_pixels((0.25, 0.25, 0.75, 0.75), 100, 100)
        assert result == (25, 25, 75, 75)

    def test_normalize_returns_integers(self) -> None:
        """Test that result is always integers."""
        result = normalize_bbox_to_pixels((0.333, 0.333, 0.666, 0.666), 100, 100)
        assert all(isinstance(v, int) for v in result)


class TestNormalizeBboxToFloat:
    """Tests for normalize_bbox_to_float function."""

    def test_normalize_full_image(self) -> None:
        """Test normalizing a full-image bbox."""
        result = normalize_bbox_to_float((0, 0, 640, 480), 640, 480)
        assert result == (0.0, 0.0, 1.0, 1.0)

    def test_normalize_center_region(self) -> None:
        """Test normalizing a center region."""
        result = normalize_bbox_to_float((25, 25, 75, 75), 100, 100)
        assert result == (0.25, 0.25, 0.75, 0.75)


# =============================================================================
# Test calculate_bbox_area
# =============================================================================


class TestCalculateBboxArea:
    """Tests for calculate_bbox_area function."""

    def test_calculate_area_basic(self) -> None:
        """Test basic area calculation."""
        assert calculate_bbox_area((0, 0, 10, 10)) == 100
        assert calculate_bbox_area((0, 0, 5, 20)) == 100
        assert calculate_bbox_area((10, 10, 20, 30)) == 200

    def test_calculate_area_with_offset(self) -> None:
        """Test area calculation with offset coordinates."""
        assert calculate_bbox_area((100, 100, 110, 110)) == 100

    def test_calculate_area_float(self) -> None:
        """Test area calculation with float coordinates."""
        assert calculate_bbox_area((0.0, 0.0, 10.5, 10.5)) == pytest.approx(110.25)

    def test_calculate_area_invalid_bbox_returns_zero(self) -> None:
        """Test that invalid bboxes return zero area."""
        assert calculate_bbox_area((10, 10, 5, 5)) == 0  # Inverted
        assert calculate_bbox_area((10, 10, 10, 20)) == 0  # Zero width


# =============================================================================
# Test calculate_bbox_iou
# =============================================================================


class TestCalculateBboxIou:
    """Tests for calculate_bbox_iou function."""

    def test_iou_identical_boxes(self) -> None:
        """Test IoU of identical boxes is 1.0."""
        bbox = (10, 10, 50, 50)
        assert calculate_bbox_iou(bbox, bbox) == pytest.approx(1.0)

    def test_iou_no_overlap(self) -> None:
        """Test IoU of non-overlapping boxes is 0.0."""
        bbox1 = (0, 0, 10, 10)
        bbox2 = (20, 20, 30, 30)
        assert calculate_bbox_iou(bbox1, bbox2) == 0.0

    def test_iou_partial_overlap(self) -> None:
        """Test IoU of partially overlapping boxes."""
        bbox1 = (0, 0, 20, 20)  # Area = 400
        bbox2 = (10, 10, 30, 30)  # Area = 400
        # Intersection: (10, 10) to (20, 20) = 10x10 = 100
        # Union: 400 + 400 - 100 = 700
        # IoU: 100/700 = 0.1428...
        assert calculate_bbox_iou(bbox1, bbox2) == pytest.approx(100 / 700)

    def test_iou_one_inside_other(self) -> None:
        """Test IoU when one box is inside the other."""
        bbox1 = (0, 0, 100, 100)  # Area = 10000
        bbox2 = (25, 25, 75, 75)  # Area = 2500
        # Intersection: 2500
        # Union: 10000 + 2500 - 2500 = 10000
        # IoU: 2500/10000 = 0.25
        assert calculate_bbox_iou(bbox1, bbox2) == pytest.approx(0.25)

    def test_iou_touching_boxes(self) -> None:
        """Test IoU of touching (but not overlapping) boxes."""
        bbox1 = (0, 0, 10, 10)
        bbox2 = (10, 0, 20, 10)  # Touching at x=10
        assert calculate_bbox_iou(bbox1, bbox2) == 0.0


# =============================================================================
# Test Exception Classes
# =============================================================================


class TestExceptionClasses:
    """Tests for exception classes."""

    def test_bounding_box_validation_error_is_value_error(self) -> None:
        """Test BoundingBoxValidationError inherits from ValueError."""
        error = BoundingBoxValidationError("test error")
        assert isinstance(error, ValueError)

    def test_invalid_bounding_box_error_stores_bbox(self) -> None:
        """Test InvalidBoundingBoxError stores the bbox."""
        bbox = (1, 2, 3, 4)
        error = InvalidBoundingBoxError("test", bbox=bbox)
        assert error.bbox == bbox

    def test_out_of_bounds_error_stores_image_size(self) -> None:
        """Test BoundingBoxOutOfBoundsError stores image size."""
        error = BoundingBoxOutOfBoundsError("test", bbox=(0, 0, 100, 100), image_size=(50, 50))
        assert error.image_size == (50, 50)
        assert error.bbox == (0, 0, 100, 100)

    def test_exceptions_can_be_raised_and_caught(self) -> None:
        """Test that exceptions can be raised and caught properly."""
        with pytest.raises(InvalidBoundingBoxError):
            raise InvalidBoundingBoxError("test")

        with pytest.raises(BoundingBoxOutOfBoundsError):
            raise BoundingBoxOutOfBoundsError("test")

        # Both should be catchable as BoundingBoxValidationError
        with pytest.raises(BoundingBoxValidationError):
            raise InvalidBoundingBoxError("test")


# =============================================================================
# Test prepare_bbox_for_crop
# =============================================================================


class TestPrepareBboxForCrop:
    """Tests for prepare_bbox_for_crop function.

    This function is used for safe PIL Image.crop() operations, handling
    edge cases that would otherwise cause ValueError.
    """

    def test_valid_bbox_returns_tuple(self) -> None:
        """Test that valid bbox returns proper tuple."""
        result = prepare_bbox_for_crop((10, 10, 90, 90), 100, 100)
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_inverted_x_coordinates_swapped(self) -> None:
        """Test that inverted X coordinates are swapped."""
        # x2 < x1 should be swapped
        result = prepare_bbox_for_crop((90, 10, 10, 90), 100, 100)
        assert result is not None
        x1, _y1, x2, _y2 = result
        assert x1 < x2, f"Expected x1 < x2, got x1={x1}, x2={x2}"

    def test_inverted_y_coordinates_swapped(self) -> None:
        """Test that inverted Y coordinates are swapped."""
        # y2 < y1 should be swapped
        result = prepare_bbox_for_crop((10, 90, 90, 10), 100, 100)
        assert result is not None
        _x1, y1, _x2, y2 = result
        assert y1 < y2, f"Expected y1 < y2, got y1={y1}, y2={y2}"

    def test_fully_inverted_coordinates_swapped(self) -> None:
        """Test that fully inverted coordinates (both X and Y) are swapped."""
        result = prepare_bbox_for_crop((90, 80, 10, 20), 100, 100)
        assert result is not None
        x1, y1, x2, y2 = result
        assert x1 < x2, f"Expected x1 < x2, got x1={x1}, x2={x2}"
        assert y1 < y2, f"Expected y1 < y2, got y1={y1}, y2={y2}"

    def test_out_of_bounds_coordinates_clamped(self) -> None:
        """Test that out-of-bounds coordinates are clamped."""
        result = prepare_bbox_for_crop((-50, -50, 150, 150), 100, 100)
        assert result is not None
        x1, y1, x2, y2 = result
        assert x1 >= 0
        assert y1 >= 0
        assert x2 <= 100
        assert y2 <= 100

    def test_padding_applied_correctly(self) -> None:
        """Test that padding expands the box."""
        # Without padding
        result_no_pad = prepare_bbox_for_crop((20, 20, 80, 80), 100, 100, padding=0)
        # With padding
        result_with_pad = prepare_bbox_for_crop((20, 20, 80, 80), 100, 100, padding=10)

        assert result_no_pad is not None
        assert result_with_pad is not None

        # Padding should expand the box (or clamp to bounds)
        x1_no_pad, y1_no_pad, x2_no_pad, y2_no_pad = result_no_pad
        x1_pad, y1_pad, x2_pad, y2_pad = result_with_pad

        assert x1_pad <= x1_no_pad
        assert y1_pad <= y1_no_pad
        assert x2_pad >= x2_no_pad
        assert y2_pad >= y2_no_pad

    def test_zero_dimension_box_returns_none(self) -> None:
        """Test that zero-width or zero-height boxes return None."""
        # Zero width (after int conversion)
        result = prepare_bbox_for_crop((50, 10, 50, 90), 100, 100)
        assert result is None

        # Zero height
        result = prepare_bbox_for_crop((10, 50, 90, 50), 100, 100)
        assert result is None

    def test_completely_outside_image_returns_none(self) -> None:
        """Test that bbox completely outside image returns None."""
        result = prepare_bbox_for_crop((200, 200, 300, 300), 100, 100)
        assert result is None

    def test_min_size_filter(self) -> None:
        """Test that boxes smaller than min_size return None."""
        # Very small box
        result = prepare_bbox_for_crop((50, 50, 51, 51), 100, 100, min_size=5)
        assert result is None

    def test_result_integers(self) -> None:
        """Test that result contains integers suitable for PIL crop."""
        result = prepare_bbox_for_crop((10.5, 20.7, 80.3, 90.1), 100, 100)
        assert result is not None
        for val in result:
            assert isinstance(val, int), f"Expected int, got {type(val)}"

    def test_pil_crop_compatible(self) -> None:
        """Test that result can be used with PIL Image.crop()."""
        from PIL import Image

        # Create a test image
        img = Image.new("RGB", (100, 100), color="red")

        # Test with various edge cases that previously caused errors
        test_cases = [
            (10, 10, 90, 90),  # Normal
            (90, 10, 10, 90),  # Inverted X
            (10, 90, 90, 10),  # Inverted Y
            (90, 90, 10, 10),  # Fully inverted
            (-10, -10, 50, 50),  # Negative start
            (80, 80, 120, 120),  # Out of bounds end
        ]

        for bbox in test_cases:
            safe_bbox = prepare_bbox_for_crop(bbox, 100, 100)
            if safe_bbox is not None:
                # Should not raise
                cropped = img.crop(safe_bbox)
                assert cropped is not None
                # Verify cropped image has positive dimensions
                assert cropped.width > 0
                assert cropped.height > 0


# =============================================================================
# Test Edge Cases and Integration
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_bbox(self) -> None:
        """Test handling of very small bounding boxes."""
        result = clamp_bbox_to_image((0, 0, 0.5, 0.5), 100, 100, min_size=1.0)
        assert result is None  # Too small

    def test_very_large_bbox(self) -> None:
        """Test handling of very large bounding boxes."""
        result = clamp_bbox_to_image((-1000, -1000, 2000, 2000), 100, 100)
        assert result == (0, 0, 100, 100)

    def test_bbox_at_exact_boundaries(self) -> None:
        """Test bbox exactly at image boundaries."""
        result = clamp_bbox_to_image((0, 0, 100, 100), 100, 100)
        assert result == (0, 0, 100, 100)

    def test_float_precision(self) -> None:
        """Test handling of float precision issues."""
        # Very small differences should still work
        bbox = (0.0000001, 0.0000001, 99.9999999, 99.9999999)
        result = clamp_bbox_to_image(bbox, 100, 100)
        assert result is not None

    def test_zero_image_dimensions_handling(self) -> None:
        """Test behavior with zero image dimensions."""
        # Edge case: zero-size image should clamp everything
        result = clamp_bbox_to_image((0, 0, 50, 50), 0, 0)
        assert result is None  # Should become invalid

    def test_single_pixel_image(self) -> None:
        """Test with a single-pixel image."""
        result = clamp_bbox_to_image((0, 0, 100, 100), 1, 1, min_size=1.0)
        assert result == (0, 0, 1, 1)


class TestRealWorldScenarios:
    """Tests for real-world usage scenarios."""

    def test_detection_bbox_exceeds_image(self) -> None:
        """Test scenario: detector returns bbox exceeding image bounds.

        This is the scenario described in NEM-1122.
        """
        # Detection model returns a bbox that slightly exceeds image
        detection_bbox = (590.5, 440.2, 645.8, 485.3)
        image_width, image_height = 640, 480

        result = validate_and_clamp_bbox(detection_bbox, image_width, image_height)

        assert result.is_valid is True
        assert result.was_clamped is True
        assert result.clamped_bbox is not None

        # Verify clamped bbox is within bounds
        x1, y1, x2, y2 = result.clamped_bbox
        assert 0 <= x1 <= image_width
        assert 0 <= y1 <= image_height
        assert 0 <= x2 <= image_width
        assert 0 <= y2 <= image_height

    def test_reid_service_bbox_validation(self) -> None:
        """Test scenario: ReID service receives invalid bbox.

        This is the scenario described in NEM-1073.
        """
        # Various invalid bboxes that could cause issues
        test_cases = [
            ((100, 100, 50, 50), "inverted coordinates"),
            ((0, 0, 0, 0), "zero-size box"),
            ((float("nan"), 0, 100, 100), "NaN coordinate"),
        ]

        for bbox, description in test_cases:
            is_valid = is_valid_bbox(bbox, allow_negative=True)
            assert not is_valid, f"Should be invalid: {description}"

    def test_distance_estimation_bbox_validation(self) -> None:
        """Test scenario: distance estimation with various bbox inputs.

        This is the scenario described in NEM-1102.
        """
        # Valid bbox for distance estimation
        valid_bbox = (100, 100, 200, 200)
        assert is_valid_bbox(valid_bbox) is True

        # Invalid cases that should be handled
        invalid_cases = [
            (-50, -50, 100, 100),  # Negative start
            (100, 100, 50, 50),  # Inverted
            (0, 0, 0, 50),  # Zero width
        ]

        for bbox in invalid_cases:
            result = validate_and_clamp_bbox(bbox, 640, 480)
            # Should either be invalid or clamped appropriately
            if result.is_valid:
                assert result.clamped_bbox is not None


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================


class TestBboxValidationProperties:
    """Property-based tests for bounding box validation using Hypothesis."""

    # -------------------------------------------------------------------------
    # is_valid_bbox Properties
    # -------------------------------------------------------------------------

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_valid_bbox_always_passes_validation(
        self, bbox: tuple[float, float, float, float]
    ) -> None:
        """Property: Valid bboxes (x1 < x2, y1 < y2, non-negative) are always valid."""
        assert is_valid_bbox(bbox) is True

    @given(bbox=invalid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_invalid_bbox_always_fails_validation(
        self, bbox: tuple[float, float, float, float]
    ) -> None:
        """Property: Invalid bboxes (x2 <= x1 or y2 <= y1) are always invalid."""
        assert is_valid_bbox(bbox) is False

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=50)
    def test_is_valid_bbox_is_idempotent(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: Calling is_valid_bbox multiple times gives same result."""
        result1 = is_valid_bbox(bbox)
        result2 = is_valid_bbox(bbox)
        result3 = is_valid_bbox(bbox)
        assert result1 == result2 == result3

    # -------------------------------------------------------------------------
    # clamp_bbox_to_image Properties
    # -------------------------------------------------------------------------

    @given(data=bbox_and_image_strategy())
    @hypothesis_settings(max_examples=100)
    def test_clamped_bbox_within_bounds(
        self, data: tuple[tuple[float, float, float, float], int, int]
    ) -> None:
        """Property: Clamped bbox is always within image bounds."""
        bbox, width, height = data
        result = clamp_bbox_to_image(bbox, width, height)

        if result is not None:
            x1, y1, x2, y2 = result
            assert 0 <= x1 <= width, f"x1={x1} not in [0, {width}]"
            assert 0 <= y1 <= height, f"y1={y1} not in [0, {height}]"
            assert 0 <= x2 <= width, f"x2={x2} not in [0, {width}]"
            assert 0 <= y2 <= height, f"y2={y2} not in [0, {height}]"

    @given(data=bbox_and_image_strategy())
    @hypothesis_settings(max_examples=100)
    def test_clamped_bbox_has_positive_dimensions(
        self, data: tuple[tuple[float, float, float, float], int, int]
    ) -> None:
        """Property: Clamped bbox always has positive width and height (or is None)."""
        bbox, width, height = data
        result = clamp_bbox_to_image(bbox, width, height)

        if result is not None:
            x1, y1, x2, y2 = result
            assert x2 > x1, f"width={x2 - x1} should be positive"
            assert y2 > y1, f"height={y2 - y1} should be positive"

    @given(data=bbox_and_image_strategy())
    @hypothesis_settings(max_examples=50)
    def test_clamping_is_idempotent(
        self, data: tuple[tuple[float, float, float, float], int, int]
    ) -> None:
        """Property: Clamping an already-clamped bbox gives equivalent result.

        Note: The function converts floats to ints, so we compare the second clamp
        (which operates on ints) to the int version of the first clamp.
        """
        bbox, width, height = data
        first_clamp = clamp_bbox_to_image(bbox, width, height)

        if first_clamp is not None:
            # Convert first result to integers (as the function internally does)
            first_as_ints = tuple(int(v) for v in first_clamp)
            second_clamp = clamp_bbox_to_image(first_as_ints, width, height)

            # The second clamp should equal the int version of the first
            assert second_clamp is not None
            for i in range(4):
                assert int(first_clamp[i]) == second_clamp[i], (
                    f"Clamping should be idempotent at index {i}: {int(first_clamp[i])} != {second_clamp[i]}"
                )

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        dims=image_dimensions_strategy(),
    )
    @hypothesis_settings(max_examples=50)
    def test_clamping_never_increases_area(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: Clamping never increases the area of a bbox."""
        width, height = dims
        original_area = calculate_bbox_area(bbox)
        result = clamp_bbox_to_image(bbox, width, height)

        if result is not None:
            clamped_area = calculate_bbox_area(result)
            assert clamped_area <= original_area, (
                f"Clamped area {clamped_area} > original {original_area}"
            )

    # -------------------------------------------------------------------------
    # validate_bbox Properties
    # -------------------------------------------------------------------------

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_valid_bbox_passes_validate(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: Valid bboxes pass validate_bbox without raising."""
        # Should not raise
        validate_bbox(bbox, allow_negative=True)

    @given(bbox=invalid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_invalid_bbox_fails_validate(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: Invalid bboxes (bad dimensions) raise InvalidBoundingBoxError."""
        with pytest.raises(InvalidBoundingBoxError):
            validate_bbox(bbox, allow_negative=True)

    # -------------------------------------------------------------------------
    # Normalization Roundtrip Properties
    # -------------------------------------------------------------------------

    @given(bbox=normalized_bbox_strategy(), dims=image_dimensions_strategy())
    @hypothesis_settings(max_examples=100)
    def test_normalization_roundtrip(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: normalize_to_pixels -> normalize_to_float is approximately identity."""
        width, height = dims
        x1, y1, x2, y2 = bbox

        # Normalize to pixels
        pixel_bbox = normalize_bbox_to_pixels(bbox, width, height)

        # Normalize back to float
        float_bbox = normalize_bbox_to_float(pixel_bbox, width, height)

        # Should be approximately equal (within rounding error)
        fx1, fy1, fx2, fy2 = float_bbox
        assert abs(fx1 - x1) < 0.02, f"x1 mismatch: {fx1} vs {x1}"
        assert abs(fy1 - y1) < 0.02, f"y1 mismatch: {fy1} vs {y1}"
        # x2, y2 can have more error due to integer rounding
        assert abs(fx2 - x2) < 0.02, f"x2 mismatch: {fx2} vs {x2}"
        assert abs(fy2 - y2) < 0.02, f"y2 mismatch: {fy2} vs {y2}"

    @given(bbox=normalized_bbox_strategy(), dims=image_dimensions_strategy())
    @hypothesis_settings(max_examples=50)
    def test_normalized_to_pixels_produces_integers(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: normalize_bbox_to_pixels always produces integers."""
        width, height = dims
        result = normalize_bbox_to_pixels(bbox, width, height)
        assert all(isinstance(v, int) for v in result)

    # -------------------------------------------------------------------------
    # Area Calculation Properties
    # -------------------------------------------------------------------------

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_area_is_non_negative(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: Area is always non-negative for valid bboxes."""
        area = calculate_bbox_area(bbox)
        assert area >= 0, f"Area should be non-negative, got {area}"

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_area_equals_width_times_height(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: Area equals (x2 - x1) * (y2 - y1)."""
        x1, y1, x2, y2 = bbox
        expected = (x2 - x1) * (y2 - y1)
        actual = calculate_bbox_area(bbox)
        assert actual == pytest.approx(expected)

    # -------------------------------------------------------------------------
    # IoU Properties
    # -------------------------------------------------------------------------

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_iou_with_self_is_one(self, bbox: tuple[float, float, float, float]) -> None:
        """Property: IoU of a bbox with itself is 1.0."""
        iou = calculate_bbox_iou(bbox, bbox)
        assert iou == pytest.approx(1.0)

    @given(bbox1=valid_bbox_xyxy_strategy(), bbox2=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_iou_is_symmetric(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU(a, b) == IoU(b, a) (symmetric)."""
        iou1 = calculate_bbox_iou(bbox1, bbox2)
        iou2 = calculate_bbox_iou(bbox2, bbox1)
        assert iou1 == pytest.approx(iou2)

    @given(bbox1=valid_bbox_xyxy_strategy(), bbox2=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_iou_is_bounded(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU is always in [0, 1] range."""
        iou = calculate_bbox_iou(bbox1, bbox2)
        assert 0.0 <= iou <= 1.0, f"IoU should be in [0, 1], got {iou}"

    # -------------------------------------------------------------------------
    # validate_and_clamp_bbox Properties
    # -------------------------------------------------------------------------

    @given(data=bbox_and_image_strategy())
    @hypothesis_settings(max_examples=100)
    def test_validate_and_clamp_returns_valid_result(
        self, data: tuple[tuple[float, float, float, float], int, int]
    ) -> None:
        """Property: validate_and_clamp always returns a BoundingBoxValidationResult."""
        bbox, width, height = data
        result = validate_and_clamp_bbox(bbox, width, height)

        assert isinstance(result, BoundingBoxValidationResult)
        assert result.original_bbox == bbox

    @given(data=bbox_and_image_strategy())
    @hypothesis_settings(max_examples=100)
    def test_validate_and_clamp_valid_result_is_clamped(
        self, data: tuple[tuple[float, float, float, float], int, int]
    ) -> None:
        """Property: If result is valid, clamped_bbox is within image bounds."""
        bbox, width, height = data
        result = validate_and_clamp_bbox(bbox, width, height)

        if result.is_valid and result.clamped_bbox is not None:
            x1, y1, x2, y2 = result.clamped_bbox
            assert 0 <= x1 <= width
            assert 0 <= y1 <= height
            assert 0 <= x2 <= width
            assert 0 <= y2 <= height
            assert x2 > x1
            assert y2 > y1

    @given(bbox=invalid_bbox_xyxy_strategy(), dims=image_dimensions_strategy())
    @hypothesis_settings(max_examples=100)
    def test_validate_and_clamp_invalid_dimensions(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: Invalid dimension bboxes return is_valid=False."""
        width, height = dims
        result = validate_and_clamp_bbox(bbox, width, height)
        assert result.is_valid is False
        assert result.clamped_bbox is None

    # -------------------------------------------------------------------------
    # Edge Cases with Special Float Values
    # -------------------------------------------------------------------------

    @given(
        normal_coords=st.tuples(
            st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            st.floats(min_value=101, max_value=200, allow_nan=False, allow_infinity=False),
            st.floats(min_value=101, max_value=200, allow_nan=False, allow_infinity=False),
        )
    )
    @hypothesis_settings(max_examples=50)
    def test_valid_floats_are_valid(self, normal_coords: tuple[float, float, float, float]) -> None:
        """Property: Finite, non-NaN floats with proper ordering are valid."""
        assert is_valid_bbox(normal_coords) is True

    @given(
        coord_index=st.integers(min_value=0, max_value=3),
    )
    @hypothesis_settings(max_examples=20)
    def test_nan_in_any_position_is_invalid(self, coord_index: int) -> None:
        """Property: NaN in any coordinate position makes bbox invalid."""
        coords = [10.0, 10.0, 100.0, 100.0]
        coords[coord_index] = float("nan")
        bbox = tuple(coords)  # type: ignore[arg-type]
        assert is_valid_bbox(bbox) is False

    @given(
        coord_index=st.integers(min_value=0, max_value=3),
    )
    @hypothesis_settings(max_examples=20)
    def test_infinity_in_any_position_is_invalid(self, coord_index: int) -> None:
        """Property: Infinity in any coordinate position makes bbox invalid."""
        coords = [10.0, 10.0, 100.0, 100.0]
        coords[coord_index] = float("inf")
        bbox = tuple(coords)  # type: ignore[arg-type]
        assert is_valid_bbox(bbox) is False

    # -------------------------------------------------------------------------
    # Additional Mathematical Properties (NEM-1698)
    # -------------------------------------------------------------------------

    @given(bbox1=valid_bbox_xyxy_strategy(), bbox2=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_area_sum_property(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: Area calculation should follow geometric properties.

        The area of a bbox is always width * height.
        """
        area = calculate_bbox_area(bbox1)
        x1, y1, x2, y2 = bbox1

        width = x2 - x1
        height = y2 - y1
        expected_area = width * height

        assert abs(area - expected_area) < 0.01, f"Area mismatch: {area} vs {expected_area}"

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        scale=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=50)
    def test_area_scales_quadratically(
        self,
        bbox: tuple[float, float, float, float],
        scale: float,
    ) -> None:
        """Property: Scaling a bbox by factor k should scale area by k^2."""
        x1, y1, x2, y2 = bbox

        # Scale the bbox
        width = x2 - x1
        height = y2 - y1
        scaled_bbox = (x1, y1, x1 + width * scale, y1 + height * scale)

        original_area = calculate_bbox_area(bbox)
        scaled_area = calculate_bbox_area(scaled_bbox)

        # Area should scale by scale^2
        expected_scaled_area = original_area * (scale**2)

        assert abs(scaled_area - expected_scaled_area) < 0.1, (
            f"Scaled area {scaled_area} doesn't match expected {expected_scaled_area}"
        )

    @given(
        bbox1=valid_bbox_xyxy_strategy(),
        bbox2=valid_bbox_xyxy_strategy(),
        bbox3=valid_bbox_xyxy_strategy(),
    )
    @hypothesis_settings(max_examples=50)
    def test_iou_transitive_property(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
        bbox3: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU should follow transitivity-like properties.

        If IoU(A, B) > 0 and IoU(B, C) > 0, then A, B, C are somewhat related.
        This tests the logical consistency of IoU calculations.
        """
        iou_ab = calculate_bbox_iou(bbox1, bbox2)
        iou_bc = calculate_bbox_iou(bbox2, bbox3)
        iou_ac = calculate_bbox_iou(bbox1, bbox3)

        # All IoU values should be in [0, 1]
        assert 0.0 <= iou_ab <= 1.0
        assert 0.0 <= iou_bc <= 1.0
        assert 0.0 <= iou_ac <= 1.0

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        dims=image_dimensions_strategy(),
    )
    @hypothesis_settings(max_examples=100)
    def test_normalize_roundtrip_approximately_identity(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: normalize_to_float -> normalize_to_pixels is approximately identity.

        Converting to normalized coordinates and back should give approximately
        the original bbox (within rounding error).
        """
        width, height = dims

        # Normalize to [0, 1]
        norm_bbox = normalize_bbox_to_float(bbox, width, height)

        # Convert back to pixels
        pixel_bbox = normalize_bbox_to_pixels(norm_bbox, width, height)

        # Should be approximately equal to original
        for i in range(4):
            # Allow rounding error
            assert abs(pixel_bbox[i] - bbox[i]) < 2.0, (
                f"Roundtrip failed at index {i}: {pixel_bbox[i]} vs {bbox[i]}"
            )

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        dims=image_dimensions_strategy(),
    )
    @hypothesis_settings(max_examples=100)
    def test_clamping_area_never_exceeds_original(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
    ) -> None:
        """Property: Clamping a bbox to image bounds never increases its area.

        This is a fundamental geometric property - restricting to a smaller
        region can only maintain or decrease area, never increase it.
        """
        width, height = dims

        original_area = calculate_bbox_area(bbox)

        clamped = clamp_bbox_to_image(bbox, width, height)

        if clamped is not None:
            clamped_area = calculate_bbox_area(clamped)

            assert clamped_area <= original_area + 0.01, (
                f"Clamped area {clamped_area} > original {original_area}"
            )

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        dims=image_dimensions_strategy(),
        min_size=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @hypothesis_settings(max_examples=50)
    def test_clamped_bbox_respects_min_size(
        self,
        bbox: tuple[float, float, float, float],
        dims: tuple[int, int],
        min_size: float,
    ) -> None:
        """Property: Clamped bbox respects minimum size constraint.

        If a bbox is too small after clamping, it should return None.
        Otherwise, it should have at least min_size in both dimensions.
        """
        width, height = dims

        clamped = clamp_bbox_to_image(bbox, width, height, min_size=min_size)

        if clamped is not None:
            x1, y1, x2, y2 = clamped
            clamped_width = x2 - x1
            clamped_height = y2 - y1

            assert clamped_width >= min_size - 0.01, (
                f"Clamped width {clamped_width} < min_size {min_size}"
            )
            assert clamped_height >= min_size - 0.01, (
                f"Clamped height {clamped_height} < min_size {min_size}"
            )

    @given(
        bbox1=valid_bbox_xyxy_strategy(),
        bbox2=valid_bbox_xyxy_strategy(),
    )
    @hypothesis_settings(max_examples=100)
    def test_iou_symmetric_property(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU should be symmetric: IoU(A, B) == IoU(B, A).

        This is already tested elsewhere but worth including in properties.
        """
        iou_ab = calculate_bbox_iou(bbox1, bbox2)
        iou_ba = calculate_bbox_iou(bbox2, bbox1)

        assert abs(iou_ab - iou_ba) < 0.001, f"IoU not symmetric: {iou_ab} vs {iou_ba}"

    @given(
        bbox1=valid_bbox_xyxy_strategy(),
        bbox2=valid_bbox_xyxy_strategy(),
    )
    @hypothesis_settings(max_examples=100)
    def test_iou_union_property(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU formula consistency check.

        IoU = intersection_area / union_area
        union_area = area1 + area2 - intersection_area
        """
        area1 = calculate_bbox_area(bbox1)
        area2 = calculate_bbox_area(bbox2)

        # Calculate intersection manually
        x1_max = max(bbox1[0], bbox2[0])
        y1_max = max(bbox1[1], bbox2[1])
        x2_min = min(bbox1[2], bbox2[2])
        y2_min = min(bbox1[3], bbox2[3])

        if x1_max < x2_min and y1_max < y2_min:
            intersection_area = (x2_min - x1_max) * (y2_min - y1_max)
        else:
            intersection_area = 0.0

        union_area = area1 + area2 - intersection_area

        expected_iou = intersection_area / union_area if union_area > 0 else 0.0
        actual_iou = calculate_bbox_iou(bbox1, bbox2)

        assert abs(actual_iou - expected_iou) < 0.01, (
            f"IoU mismatch: actual={actual_iou}, expected={expected_iou}"
        )


# =============================================================================
# Test scale_bbox_to_image (NEM-3903)
# =============================================================================


class TestScaleBboxToImage:
    """Tests for scale_bbox_to_image function.

    NEM-3903: YOLO detection coordinates may be relative to a different
    image resolution than what the enrichment pipeline loads. This function
    scales bboxes proportionally between source and target dimensions.
    """

    def test_no_scaling_when_dimensions_match(self) -> None:
        """Test that identical dimensions return the same bbox."""
        bbox = (100.0, 100.0, 200.0, 200.0)
        result = scale_bbox_to_image(bbox, 640, 480, 640, 480)
        assert result == bbox

    def test_downscale_2x(self) -> None:
        """Test scaling down by factor of 2."""
        # YOLO returned bbox for 640x480 image, but we loaded 320x240
        bbox = (100.0, 100.0, 200.0, 200.0)
        result = scale_bbox_to_image(bbox, 640, 480, 320, 240)
        assert result == (50.0, 50.0, 100.0, 100.0)

    def test_upscale_2x(self) -> None:
        """Test scaling up by factor of 2."""
        # bbox from 320x240 to 640x480
        bbox = (50.0, 50.0, 100.0, 100.0)
        result = scale_bbox_to_image(bbox, 320, 240, 640, 480)
        assert result == (100.0, 100.0, 200.0, 200.0)

    def test_non_uniform_scaling(self) -> None:
        """Test scaling with different X and Y ratios."""
        # Source: 640x480, Target: 320x480 (only X scaled)
        bbox = (100.0, 100.0, 200.0, 200.0)
        result = scale_bbox_to_image(bbox, 640, 480, 320, 480)
        assert result == (50.0, 100.0, 100.0, 200.0)

    def test_real_world_scenario_yolo_inference_size(self) -> None:
        """Test the real-world scenario from NEM-3903.

        YOLO bbox (416, 146, 641, 665) for a 640x640 inference image
        needs to be scaled to the actual 320x240 image.
        """
        # Note: The original bbox (416, 146, 641, 665) exceeds 640x640
        # so let's use a valid bbox within inference bounds
        bbox = (416.0, 146.0, 600.0, 600.0)
        # Scaling from 640x640 (YOLO inference) to 320x240 (actual image)
        result = scale_bbox_to_image(bbox, 640, 640, 320, 240)

        # Expected: x scaled by 320/640=0.5, y scaled by 240/640=0.375
        expected_x1 = 416.0 * (320 / 640)  # 208.0
        expected_y1 = 146.0 * (240 / 640)  # 54.75
        expected_x2 = 600.0 * (320 / 640)  # 300.0
        expected_y2 = 600.0 * (240 / 640)  # 225.0

        assert result[0] == pytest.approx(expected_x1)
        assert result[1] == pytest.approx(expected_y1)
        assert result[2] == pytest.approx(expected_x2)
        assert result[3] == pytest.approx(expected_y2)

    def test_invalid_source_dimensions_returns_original(self) -> None:
        """Test that invalid source dimensions return original bbox."""
        bbox = (100.0, 100.0, 200.0, 200.0)

        # Zero source width
        result = scale_bbox_to_image(bbox, 0, 480, 320, 240)
        assert result == bbox

        # Zero source height
        result = scale_bbox_to_image(bbox, 640, 0, 320, 240)
        assert result == bbox

        # Negative source dimensions
        result = scale_bbox_to_image(bbox, -640, 480, 320, 240)
        assert result == bbox

    def test_invalid_target_dimensions_returns_original(self) -> None:
        """Test that invalid target dimensions return original bbox."""
        bbox = (100.0, 100.0, 200.0, 200.0)

        # Zero target width
        result = scale_bbox_to_image(bbox, 640, 480, 0, 240)
        assert result == bbox

        # Zero target height
        result = scale_bbox_to_image(bbox, 640, 480, 320, 0)
        assert result == bbox

        # Negative target dimensions
        result = scale_bbox_to_image(bbox, 640, 480, -320, 240)
        assert result == bbox

    def test_preserves_aspect_ratio_of_bbox(self) -> None:
        """Test that uniform scaling preserves bbox aspect ratio."""
        bbox = (100.0, 100.0, 200.0, 150.0)  # 100x50 bbox (2:1 aspect ratio)

        # Uniform scale 2x
        result = scale_bbox_to_image(bbox, 640, 480, 1280, 960)

        # Check scaled dimensions
        original_width = bbox[2] - bbox[0]
        original_height = bbox[3] - bbox[1]
        scaled_width = result[2] - result[0]
        scaled_height = result[3] - result[1]

        original_aspect = original_width / original_height
        scaled_aspect = scaled_width / scaled_height

        assert original_aspect == pytest.approx(scaled_aspect)

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        source_dims=image_dimensions_strategy(),
        target_dims=image_dimensions_strategy(),
    )
    @hypothesis_settings(max_examples=100)
    def test_scale_preserves_relative_position(
        self,
        bbox: tuple[float, float, float, float],
        source_dims: tuple[int, int],
        target_dims: tuple[int, int],
    ) -> None:
        """Property: Relative position within image is preserved after scaling."""
        src_w, src_h = source_dims
        tgt_w, tgt_h = target_dims

        x1, y1, x2, y2 = bbox

        # Skip if bbox is out of source bounds (can't compute relative position)
        if x1 >= src_w or y1 >= src_h:
            return

        result = scale_bbox_to_image(bbox, src_w, src_h, tgt_w, tgt_h)
        rx1, ry1, rx2, ry2 = result

        # Relative X position should be preserved
        original_rel_x = x1 / src_w
        scaled_rel_x = rx1 / tgt_w if tgt_w > 0 else 0

        assert abs(original_rel_x - scaled_rel_x) < 0.01, (
            f"Relative X position changed: {original_rel_x} -> {scaled_rel_x}"
        )

    @given(
        bbox=valid_bbox_xyxy_strategy(),
        scale_factor=st.floats(
            min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False
        ),
    )
    @hypothesis_settings(max_examples=50)
    def test_scale_then_inverse_roundtrip(
        self,
        bbox: tuple[float, float, float, float],
        scale_factor: float,
    ) -> None:
        """Property: Scaling then inverse scaling returns approximately original bbox."""
        src_w, src_h = 640, 480
        tgt_w = int(src_w * scale_factor)
        tgt_h = int(src_h * scale_factor)

        # Skip invalid target dimensions
        if tgt_w <= 0 or tgt_h <= 0:
            return

        # Scale to target
        scaled = scale_bbox_to_image(bbox, src_w, src_h, tgt_w, tgt_h)

        # Scale back to source
        roundtrip = scale_bbox_to_image(scaled, tgt_w, tgt_h, src_w, src_h)

        # Should be approximately equal
        for i in range(4):
            assert abs(roundtrip[i] - bbox[i]) < 1.0, (
                f"Roundtrip error at index {i}: {roundtrip[i]} != {bbox[i]}"
            )
