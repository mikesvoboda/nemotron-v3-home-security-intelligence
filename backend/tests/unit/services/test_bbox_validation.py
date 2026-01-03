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
    validate_and_clamp_bbox,
    validate_bbox,
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

    def test_negative_coordinates_default_invalid(self) -> None:
        """Test that negative coordinates are invalid by default."""
        assert is_valid_bbox((-10, 0, 100, 100)) is False
        assert is_valid_bbox((0, -10, 100, 100)) is False
        assert is_valid_bbox((-10, -10, 100, 100)) is False

    def test_negative_coordinates_allowed_when_enabled(self) -> None:
        """Test that negative coordinates can be allowed."""
        assert is_valid_bbox((-10, 0, 100, 100), allow_negative=True) is True
        assert is_valid_bbox((0, -10, 100, 100), allow_negative=True) is True
        assert is_valid_bbox((-10, -10, 100, 100), allow_negative=True) is True

    def test_nan_values_return_false(self) -> None:
        """Test that NaN values return False."""
        assert is_valid_bbox((float("nan"), 0, 100, 100)) is False
        assert is_valid_bbox((0, float("nan"), 100, 100)) is False
        assert is_valid_bbox((0, 0, float("nan"), 100)) is False
        assert is_valid_bbox((0, 0, 100, float("nan"))) is False

    def test_infinite_values_return_false(self) -> None:
        """Test that infinite values return False."""
        assert is_valid_bbox((float("inf"), 0, 100, 100)) is False
        assert is_valid_bbox((float("-inf"), 0, 100, 100)) is False
        assert is_valid_bbox((0, 0, float("inf"), 100)) is False

    def test_invalid_type_returns_false(self) -> None:
        """Test that invalid types return False."""
        assert is_valid_bbox(None) is False  # type: ignore[arg-type]
        assert is_valid_bbox((1, 2, 3)) is False  # type: ignore[arg-type]
        assert is_valid_bbox("invalid") is False  # type: ignore[arg-type]
        assert is_valid_bbox((1, 2, 3, 4, 5)) is False  # type: ignore[arg-type]


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
