"""Property-based tests for bounding box normalization.

Tests cover mathematical invariants for:
- Normalization to [0, 1] range
- Denormalization roundtrip (normalize -> denormalize approximately equals identity)
- Boundary conditions and edge cases

Related Linear Issue:
- NEM-3747: Expand Property-Based Testing for Detection Validation
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.services.bbox_validation import (
    normalize_bbox_to_float,
    normalize_bbox_to_pixels,
)
from backend.tests.hypothesis_strategies import edge_case_bbox, valid_detection_bbox

# =============================================================================
# Hypothesis Strategies
# =============================================================================


@st.composite
def valid_pixel_bbox_with_image(
    draw: st.DrawFn,
) -> tuple[tuple[int, int, int, int], int, int]:
    """Generate a valid pixel bbox with matching image dimensions.

    Ensures the bbox is valid (x1 < x2, y1 < y2) and fits within the image.

    Returns:
        Tuple of (bbox, image_width, image_height)
    """
    # Generate image dimensions first
    image_width = draw(st.integers(min_value=10, max_value=4096))
    image_height = draw(st.integers(min_value=10, max_value=4096))

    # Generate bbox coordinates that fit within image
    x1 = draw(st.integers(min_value=0, max_value=image_width - 2))
    y1 = draw(st.integers(min_value=0, max_value=image_height - 2))
    x2 = draw(st.integers(min_value=x1 + 1, max_value=image_width))
    y2 = draw(st.integers(min_value=y1 + 1, max_value=image_height))

    return ((x1, y1, x2, y2), image_width, image_height)


@st.composite
def valid_normalized_bbox_with_image(
    draw: st.DrawFn,
) -> tuple[tuple[float, float, float, float], int, int]:
    """Generate a valid normalized bbox ([0, 1] range) with image dimensions.

    Ensures the normalized bbox has x1 < x2 and y1 < y2.

    Returns:
        Tuple of (normalized_bbox, image_width, image_height)
    """
    # Generate image dimensions
    image_width = draw(st.integers(min_value=10, max_value=4096))
    image_height = draw(st.integers(min_value=10, max_value=4096))

    # Generate normalized coordinates [0, 1]
    x1 = draw(st.floats(min_value=0.0, max_value=0.98, allow_nan=False, allow_infinity=False))
    y1 = draw(st.floats(min_value=0.0, max_value=0.98, allow_nan=False, allow_infinity=False))
    x2 = draw(st.floats(min_value=x1 + 0.01, max_value=1.0, allow_nan=False, allow_infinity=False))
    y2 = draw(st.floats(min_value=y1 + 0.01, max_value=1.0, allow_nan=False, allow_infinity=False))

    return ((x1, y1, x2, y2), image_width, image_height)


# =============================================================================
# Normalization Properties
# =============================================================================


class TestBboxNormalizationProperties:
    """Property-based tests for bbox normalization to [0, 1] range."""

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_valid_bbox_always_normalizes(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: Any valid bbox normalizes to [0, 1] range.

        Given a valid pixel bbox within image bounds, normalizing it should
        produce coordinates that are all within [0.0, 1.0].
        """
        bbox, image_width, image_height = data

        # Normalize to float [0, 1]
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)

        # All coordinates should be in [0, 1]
        nx1, ny1, nx2, ny2 = normalized
        assert 0.0 <= nx1 <= 1.0, f"nx1={nx1} not in [0, 1]"
        assert 0.0 <= ny1 <= 1.0, f"ny1={ny1} not in [0, 1]"
        assert 0.0 <= nx2 <= 1.0, f"nx2={nx2} not in [0, 1]"
        assert 0.0 <= ny2 <= 1.0, f"ny2={ny2} not in [0, 1]"

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_normalized_bbox_preserves_ordering(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: Normalization preserves coordinate ordering (x1 < x2, y1 < y2).

        If the input bbox has x1 < x2 and y1 < y2, the normalized bbox
        should maintain this ordering.
        """
        bbox, image_width, image_height = data
        x1, y1, x2, y2 = bbox

        # Verify input has proper ordering
        assume(x1 < x2 and y1 < y2)

        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        nx1, ny1, nx2, ny2 = normalized

        assert nx1 < nx2, f"Normalized x ordering violated: nx1={nx1}, nx2={nx2}"
        assert ny1 < ny2, f"Normalized y ordering violated: ny1={ny1}, ny2={ny2}"

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_denormalize_inverts_normalize(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: denormalize(normalize(bbox)) approximately equals bbox.

        Normalizing a pixel bbox and then denormalizing should recover
        approximately the original bbox (within integer rounding error).
        """
        bbox, image_width, image_height = data
        x1, y1, x2, y2 = bbox

        # Normalize to [0, 1]
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)

        # Denormalize back to pixels
        denormalized = normalize_bbox_to_pixels(normalized, image_width, image_height)

        # Should approximately equal original (within rounding error)
        dx1, dy1, dx2, dy2 = denormalized

        assert abs(dx1 - x1) <= 1, f"x1 mismatch: original={x1}, recovered={dx1}"
        assert abs(dy1 - y1) <= 1, f"y1 mismatch: original={y1}, recovered={dy1}"
        assert abs(dx2 - x2) <= 1, f"x2 mismatch: original={x2}, recovered={dx2}"
        assert abs(dy2 - y2) <= 1, f"y2 mismatch: original={y2}, recovered={dy2}"

    @given(data=valid_normalized_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_normalize_inverts_denormalize(
        self,
        data: tuple[tuple[float, float, float, float], int, int],
    ) -> None:
        """Property: normalize(denormalize(bbox)) approximately equals bbox.

        Denormalizing a normalized bbox and then normalizing should recover
        approximately the original normalized bbox (within floating point error).
        """
        norm_bbox, image_width, image_height = data
        nx1, ny1, nx2, ny2 = norm_bbox

        # Denormalize to pixels
        pixel_bbox = normalize_bbox_to_pixels(norm_bbox, image_width, image_height)

        # Normalize back to [0, 1]
        recovered = normalize_bbox_to_float(pixel_bbox, image_width, image_height)

        # Should approximately equal original (within rounding error)
        rx1, ry1, rx2, ry2 = recovered

        # Tolerance depends on image size (larger images = smaller relative error)
        tolerance = max(0.02, 2.0 / min(image_width, image_height))

        assert abs(rx1 - nx1) < tolerance, f"x1 mismatch: original={nx1}, recovered={rx1}"
        assert abs(ry1 - ny1) < tolerance, f"y1 mismatch: original={ny1}, recovered={ry1}"
        assert abs(rx2 - nx2) < tolerance, f"x2 mismatch: original={nx2}, recovered={rx2}"
        assert abs(ry2 - ny2) < tolerance, f"y2 mismatch: original={ny2}, recovered={ry2}"

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_normalization_preserves_relative_dimensions(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: Normalization preserves relative bbox dimensions.

        The ratio of normalized dimensions should match the ratio of pixel dimensions
        relative to image size.
        """
        bbox, image_width, image_height = data
        x1, y1, x2, y2 = bbox

        # Skip if bbox is too small for meaningful comparison
        assume(x2 - x1 >= 2 and y2 - y1 >= 2)

        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        nx1, ny1, nx2, ny2 = normalized

        # Check width ratio
        expected_norm_width = (x2 - x1) / image_width
        actual_norm_width = nx2 - nx1
        assert abs(actual_norm_width - expected_norm_width) < 0.001, (
            f"Width ratio mismatch: expected={expected_norm_width}, actual={actual_norm_width}"
        )

        # Check height ratio
        expected_norm_height = (y2 - y1) / image_height
        actual_norm_height = ny2 - ny1
        assert abs(actual_norm_height - expected_norm_height) < 0.001, (
            f"Height ratio mismatch: expected={expected_norm_height}, actual={actual_norm_height}"
        )

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_denormalize_produces_integers(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: normalize_bbox_to_pixels always produces integers."""
        bbox, image_width, image_height = data

        # Normalize and denormalize
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        denormalized = normalize_bbox_to_pixels(normalized, image_width, image_height)

        assert all(isinstance(v, int) for v in denormalized), (
            f"Expected all integers, got types: {[type(v) for v in denormalized]}"
        )


# =============================================================================
# Edge Case Normalization Properties
# =============================================================================


class TestBboxNormalizationEdgeCases:
    """Property-based tests for edge case normalization scenarios."""

    @given(bbox_dict=edge_case_bbox())
    @hypothesis_settings(max_examples=500)
    def test_edge_case_bbox_normalizes(self, bbox_dict: dict[str, int]) -> None:
        """Property: Edge case bboxes normalize to valid [0, 1] range.

        Edge cases include:
        - Top-left corner (0, 0)
        - Bottom-right corner (1820, 980)
        - Full frame (0, 0, 1920, 1080)
        - Minimum size (1x1 pixel)
        """
        # Convert dict to tuple format (x, y, width, height) -> (x1, y1, x2, y2)
        x1 = bbox_dict["x"]
        y1 = bbox_dict["y"]
        x2 = x1 + bbox_dict["width"]
        y2 = y1 + bbox_dict["height"]
        bbox = (x1, y1, x2, y2)

        # Use standard image dimensions
        image_width, image_height = 1920, 1080

        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        nx1, ny1, nx2, ny2 = normalized

        # All coordinates should be in [0, 1]
        assert 0.0 <= nx1 <= 1.0, f"nx1={nx1} not in [0, 1]"
        assert 0.0 <= ny1 <= 1.0, f"ny1={ny1} not in [0, 1]"
        assert 0.0 <= nx2 <= 1.0, f"nx2={nx2} not in [0, 1]"
        assert 0.0 <= ny2 <= 1.0, f"ny2={ny2} not in [0, 1]"

    @given(bbox_dict=valid_detection_bbox())
    @hypothesis_settings(max_examples=500)
    def test_detection_bbox_normalizes(self, bbox_dict: dict[str, int]) -> None:
        """Property: Detection bboxes from hypothesis strategies normalize correctly.

        Uses the valid_detection_bbox strategy from hypothesis_strategies.py.
        """
        # Convert dict format to tuple format
        x1 = bbox_dict["x"]
        y1 = bbox_dict["y"]
        x2 = x1 + bbox_dict["width"]
        y2 = y1 + bbox_dict["height"]
        bbox = (x1, y1, x2, y2)

        # Use Full HD dimensions (the default for valid_detection_bbox)
        image_width, image_height = 1920, 1080

        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        nx1, ny1, nx2, ny2 = normalized

        # All coordinates should be in [0, 1]
        assert 0.0 <= nx1 <= 1.0, f"nx1={nx1} not in [0, 1]"
        assert 0.0 <= ny1 <= 1.0, f"ny1={ny1} not in [0, 1]"
        assert 0.0 <= nx2 <= 1.0, f"nx2={nx2} not in [0, 1]"
        assert 0.0 <= ny2 <= 1.0, f"ny2={ny2} not in [0, 1]"

        # Ordering should be preserved
        assert nx1 < nx2, f"x ordering violated: nx1={nx1}, nx2={nx2}"
        assert ny1 < ny2, f"y ordering violated: ny1={ny1}, ny2={ny2}"

    @given(
        scale=st.integers(min_value=1, max_value=10),
        base_width=st.integers(min_value=100, max_value=500),
        base_height=st.integers(min_value=100, max_value=500),
    )
    @hypothesis_settings(max_examples=500)
    def test_normalization_scale_invariance(
        self,
        scale: int,
        base_width: int,
        base_height: int,
    ) -> None:
        """Property: Scaling both bbox and image by same factor preserves normalized result.

        If we scale both the bbox and image dimensions by the same factor,
        the normalized coordinates should remain the same.
        """
        # Create a base bbox
        x1, y1 = 10, 20
        x2, y2 = 50, 60
        base_bbox = (x1, y1, x2, y2)

        # Ensure bbox fits in base image
        assume(x2 <= base_width and y2 <= base_height)

        # Normalize with base dimensions
        base_normalized = normalize_bbox_to_float(base_bbox, base_width, base_height)

        # Scale everything by the same factor
        scaled_bbox = (x1 * scale, y1 * scale, x2 * scale, y2 * scale)
        scaled_width = base_width * scale
        scaled_height = base_height * scale

        # Normalize with scaled dimensions
        scaled_normalized = normalize_bbox_to_float(scaled_bbox, scaled_width, scaled_height)

        # Normalized coordinates should be the same
        for i in range(4):
            assert abs(base_normalized[i] - scaled_normalized[i]) < 0.001, (
                f"Scale invariance violated at index {i}: "
                f"base={base_normalized[i]}, scaled={scaled_normalized[i]}"
            )


# =============================================================================
# Mathematical Properties
# =============================================================================


class TestNormalizationMathematicalProperties:
    """Property-based tests for mathematical properties of normalization."""

    @given(
        image_width=st.integers(min_value=10, max_value=4096),
        image_height=st.integers(min_value=10, max_value=4096),
    )
    @hypothesis_settings(max_examples=500)
    def test_full_image_bbox_normalizes_to_unit_square(
        self,
        image_width: int,
        image_height: int,
    ) -> None:
        """Property: A full-image bbox normalizes to (0, 0, 1, 1).

        The bbox covering the entire image should normalize to the unit square.
        """
        bbox = (0, 0, image_width, image_height)
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)

        assert normalized == pytest.approx((0.0, 0.0, 1.0, 1.0), abs=0.001), (
            f"Full image bbox {bbox} did not normalize to unit square, got {normalized}"
        )

    @given(
        image_width=st.integers(min_value=10, max_value=4096),
        image_height=st.integers(min_value=10, max_value=4096),
    )
    @hypothesis_settings(max_examples=500)
    def test_origin_bbox_starts_at_zero(
        self,
        image_width: int,
        image_height: int,
    ) -> None:
        """Property: A bbox at origin (0, 0, w, h) normalizes to start at (0, 0)."""
        # Small bbox at origin
        w, h = min(10, image_width), min(10, image_height)
        bbox = (0, 0, w, h)
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)

        assert normalized[0] == pytest.approx(0.0, abs=0.001), (
            f"x1 should be 0, got {normalized[0]}"
        )
        assert normalized[1] == pytest.approx(0.0, abs=0.001), (
            f"y1 should be 0, got {normalized[1]}"
        )

    @given(data=valid_pixel_bbox_with_image())
    @hypothesis_settings(max_examples=500)
    def test_normalized_area_ratio(
        self,
        data: tuple[tuple[int, int, int, int], int, int],
    ) -> None:
        """Property: Normalized bbox area equals pixel area ratio.

        The area of the normalized bbox should equal:
        (pixel_area) / (image_width * image_height)
        """
        bbox, image_width, image_height = data
        x1, y1, x2, y2 = bbox

        # Calculate pixel area
        pixel_area = (x2 - x1) * (y2 - y1)
        image_area = image_width * image_height

        # Calculate normalized area
        normalized = normalize_bbox_to_float(bbox, image_width, image_height)
        nx1, ny1, nx2, ny2 = normalized
        normalized_area = (nx2 - nx1) * (ny2 - ny1)

        # Areas should match as ratios
        expected_normalized_area = pixel_area / image_area

        assert abs(normalized_area - expected_normalized_area) < 0.001, (
            f"Area ratio mismatch: expected={expected_normalized_area}, actual={normalized_area}"
        )
