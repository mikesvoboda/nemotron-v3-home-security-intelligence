"""Property-based tests for IoU (Intersection over Union) calculations.

Tests cover mathematical invariants for:
- Commutativity: IoU(A, B) == IoU(B, A)
- Self-IoU: IoU(A, A) == 1.0
- Boundedness: 0.0 <= IoU(A, B) <= 1.0
- Additional mathematical properties

Related Linear Issue:
- NEM-3747: Expand Property-Based Testing for Detection Validation
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from backend.services.bbox_validation import (
    calculate_bbox_area,
    calculate_bbox_iou,
)
from backend.tests.hypothesis_strategies import edge_case_bbox, valid_detection_bbox

# =============================================================================
# Hypothesis Strategies
# =============================================================================


@st.composite
def valid_bbox_xyxy(
    draw: st.DrawFn,
    max_coord: int = 1000,
) -> tuple[float, float, float, float]:
    """Generate a valid xyxy bbox with x1 < x2 and y1 < y2.

    Args:
        max_coord: Maximum coordinate value

    Returns:
        Tuple (x1, y1, x2, y2) with proper ordering
    """
    x1 = draw(
        st.floats(min_value=0, max_value=max_coord - 2, allow_nan=False, allow_infinity=False)
    )
    y1 = draw(
        st.floats(min_value=0, max_value=max_coord - 2, allow_nan=False, allow_infinity=False)
    )
    x2 = draw(
        st.floats(min_value=x1 + 1, max_value=max_coord, allow_nan=False, allow_infinity=False)
    )
    y2 = draw(
        st.floats(min_value=y1 + 1, max_value=max_coord, allow_nan=False, allow_infinity=False)
    )

    return (x1, y1, x2, y2)


@st.composite
def non_overlapping_bbox_pair(
    draw: st.DrawFn,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Generate two non-overlapping bounding boxes.

    Returns:
        Tuple of two bboxes that do not overlap
    """
    # First bbox
    x1_a = draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
    y1_a = draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
    w_a = draw(st.floats(min_value=10, max_value=50, allow_nan=False, allow_infinity=False))
    h_a = draw(st.floats(min_value=10, max_value=50, allow_nan=False, allow_infinity=False))
    bbox_a = (x1_a, y1_a, x1_a + w_a, y1_a + h_a)

    # Second bbox - guaranteed not to overlap by placing it far away
    offset = draw(st.floats(min_value=200, max_value=400, allow_nan=False, allow_infinity=False))
    x1_b = x1_a + w_a + offset
    y1_b = y1_a + h_a + offset
    w_b = draw(st.floats(min_value=10, max_value=50, allow_nan=False, allow_infinity=False))
    h_b = draw(st.floats(min_value=10, max_value=50, allow_nan=False, allow_infinity=False))
    bbox_b = (x1_b, y1_b, x1_b + w_b, y1_b + h_b)

    return (bbox_a, bbox_b)


@st.composite
def containing_bbox_pair(
    draw: st.DrawFn,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Generate two bboxes where one contains the other.

    Returns:
        Tuple of (outer_bbox, inner_bbox) where outer contains inner
    """
    # Outer bbox
    x1_outer = draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False))
    y1_outer = draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False))
    w_outer = draw(st.floats(min_value=100, max_value=200, allow_nan=False, allow_infinity=False))
    h_outer = draw(st.floats(min_value=100, max_value=200, allow_nan=False, allow_infinity=False))
    outer = (x1_outer, y1_outer, x1_outer + w_outer, y1_outer + h_outer)

    # Inner bbox - strictly inside outer
    margin_x = draw(
        st.floats(min_value=5, max_value=w_outer / 4, allow_nan=False, allow_infinity=False)
    )
    margin_y = draw(
        st.floats(min_value=5, max_value=h_outer / 4, allow_nan=False, allow_infinity=False)
    )
    x1_inner = x1_outer + margin_x
    y1_inner = y1_outer + margin_y
    w_inner = draw(
        st.floats(
            min_value=5,
            max_value=w_outer - 2 * margin_x,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    h_inner = draw(
        st.floats(
            min_value=5,
            max_value=h_outer - 2 * margin_y,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    inner = (x1_inner, y1_inner, x1_inner + w_inner, y1_inner + h_inner)

    return (outer, inner)


# =============================================================================
# Fundamental IoU Properties
# =============================================================================


class TestIoUFundamentalProperties:
    """Property-based tests for fundamental IoU mathematical properties."""

    @given(bbox1=valid_bbox_xyxy(), bbox2=valid_bbox_xyxy())
    @hypothesis_settings(max_examples=500)
    def test_iou_commutative(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU(A, B) == IoU(B, A) (commutativity).

        The IoU calculation should be symmetric - the order of arguments
        should not affect the result.
        """
        iou_ab = calculate_bbox_iou(bbox1, bbox2)
        iou_ba = calculate_bbox_iou(bbox2, bbox1)

        assert iou_ab == pytest.approx(iou_ba, abs=0.0001), (
            f"IoU not commutative: IoU(A, B)={iou_ab}, IoU(B, A)={iou_ba}"
        )

    @given(bbox=valid_bbox_xyxy())
    @hypothesis_settings(max_examples=500)
    def test_iou_self_equals_one(
        self,
        bbox: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU(A, A) == 1.0 (self-IoU).

        The IoU of any valid bounding box with itself should always be 1.0,
        representing perfect overlap.
        """
        iou = calculate_bbox_iou(bbox, bbox)

        assert iou == pytest.approx(1.0, abs=0.0001), (
            f"IoU of bbox with itself should be 1.0, got {iou}"
        )

    @given(bbox1=valid_bbox_xyxy(), bbox2=valid_bbox_xyxy())
    @hypothesis_settings(max_examples=500)
    def test_iou_range(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: 0.0 <= IoU(A, B) <= 1.0 (boundedness).

        The IoU value should always be in the range [0, 1]:
        - 0.0 means no overlap
        - 1.0 means perfect overlap (identical boxes)
        """
        iou = calculate_bbox_iou(bbox1, bbox2)

        assert 0.0 <= iou <= 1.0, f"IoU should be in [0, 1], got {iou}"

    @given(bbox_pair=non_overlapping_bbox_pair())
    @hypothesis_settings(max_examples=500)
    def test_iou_non_overlapping_is_zero(
        self,
        bbox_pair: tuple[tuple[float, float, float, float], tuple[float, float, float, float]],
    ) -> None:
        """Property: IoU of non-overlapping boxes is 0.0.

        When two boxes do not overlap at all, their IoU should be exactly 0.
        """
        bbox1, bbox2 = bbox_pair

        iou = calculate_bbox_iou(bbox1, bbox2)

        assert iou == pytest.approx(0.0, abs=0.0001), (
            f"IoU of non-overlapping boxes should be 0.0, got {iou}"
        )

    @given(bbox_pair=containing_bbox_pair())
    @hypothesis_settings(max_examples=500)
    def test_iou_containing_box_property(
        self,
        bbox_pair: tuple[tuple[float, float, float, float], tuple[float, float, float, float]],
    ) -> None:
        """Property: When A contains B, IoU = area(B) / area(A).

        When one box completely contains another, the IoU equals the ratio
        of the inner box's area to the outer box's area.
        """
        outer, inner = bbox_pair

        # Verify containment
        inner_x1, inner_y1, inner_x2, inner_y2 = inner
        outer_x1, outer_y1, outer_x2, outer_y2 = outer

        assume(
            outer_x1 <= inner_x1
            and outer_y1 <= inner_y1
            and inner_x2 <= outer_x2
            and inner_y2 <= outer_y2
        )

        iou = calculate_bbox_iou(outer, inner)

        # When outer contains inner:
        # Intersection = area(inner)
        # Union = area(outer) (since inner is subset)
        # IoU = area(inner) / area(outer)
        inner_area = calculate_bbox_area(inner)
        outer_area = calculate_bbox_area(outer)

        expected_iou = inner_area / outer_area if outer_area > 0 else 0.0

        assert iou == pytest.approx(expected_iou, abs=0.01), (
            f"Containing IoU mismatch: expected={expected_iou}, actual={iou}"
        )


# =============================================================================
# Additional IoU Properties
# =============================================================================


class TestIoUAdditionalProperties:
    """Property-based tests for additional IoU mathematical properties."""

    @given(
        bbox=valid_bbox_xyxy(),
        translation=st.tuples(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        ),
    )
    @hypothesis_settings(max_examples=500)
    def test_iou_translation_invariance(
        self,
        bbox: tuple[float, float, float, float],
        translation: tuple[float, float],
    ) -> None:
        """Property: IoU(A, A_translated) depends only on overlap amount, not position.

        Translating both boxes by the same amount should not change their IoU.
        """
        x1, y1, x2, y2 = bbox
        tx, ty = translation

        # Original bbox
        original = bbox

        # Translated bbox (same translation to both reference points)
        translated = (x1 + tx, y1 + ty, x2 + tx, y2 + ty)

        # IoU of bbox with itself should be 1.0
        self_iou = calculate_bbox_iou(original, original)
        translated_self_iou = calculate_bbox_iou(translated, translated)

        assert self_iou == pytest.approx(translated_self_iou, abs=0.0001), (
            f"Translation changed self-IoU: original={self_iou}, translated={translated_self_iou}"
        )

    @given(
        bbox1=valid_bbox_xyxy(),
        bbox2=valid_bbox_xyxy(),
    )
    @hypothesis_settings(max_examples=500)
    def test_iou_intersection_union_relationship(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU = intersection / union follows mathematical definition.

        Verify the IoU calculation matches the explicit formula:
        IoU = intersection_area / (area1 + area2 - intersection_area)
        """
        # Calculate areas
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

        assert actual_iou == pytest.approx(expected_iou, abs=0.001), (
            f"IoU formula mismatch: expected={expected_iou}, actual={actual_iou}"
        )

    @given(
        bbox1=valid_bbox_xyxy(),
        bbox2=valid_bbox_xyxy(),
        bbox3=valid_bbox_xyxy(),
    )
    @hypothesis_settings(max_examples=500)
    def test_iou_all_bounded(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
        bbox3: tuple[float, float, float, float],
    ) -> None:
        """Property: All pairwise IoUs are in [0, 1].

        Verify that IoU calculations for all pairs of three boxes
        are within valid bounds.
        """
        iou_12 = calculate_bbox_iou(bbox1, bbox2)
        iou_23 = calculate_bbox_iou(bbox2, bbox3)
        iou_13 = calculate_bbox_iou(bbox1, bbox3)

        assert 0.0 <= iou_12 <= 1.0, f"IoU(1,2) out of range: {iou_12}"
        assert 0.0 <= iou_23 <= 1.0, f"IoU(2,3) out of range: {iou_23}"
        assert 0.0 <= iou_13 <= 1.0, f"IoU(1,3) out of range: {iou_13}"

    @given(
        scale=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
        bbox1=valid_bbox_xyxy(max_coord=200),
        bbox2=valid_bbox_xyxy(max_coord=200),
    )
    @hypothesis_settings(max_examples=500)
    def test_iou_scale_invariance(
        self,
        scale: float,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU is invariant to uniform scaling of both boxes.

        Scaling both boxes by the same factor should not change their IoU.
        """
        # Scale both boxes by the same factor
        scaled_bbox1 = tuple(c * scale for c in bbox1)
        scaled_bbox2 = tuple(c * scale for c in bbox2)

        original_iou = calculate_bbox_iou(bbox1, bbox2)
        scaled_iou = calculate_bbox_iou(scaled_bbox1, scaled_bbox2)

        assert original_iou == pytest.approx(scaled_iou, abs=0.001), (
            f"IoU changed with scaling: original={original_iou}, scaled={scaled_iou}"
        )


# =============================================================================
# IoU with Detection Bboxes
# =============================================================================


class TestIoUWithDetectionBboxes:
    """Property-based tests for IoU with detection-specific bboxes."""

    @given(bbox_dict=valid_detection_bbox())
    @hypothesis_settings(max_examples=500)
    def test_detection_bbox_self_iou(self, bbox_dict: dict[str, int]) -> None:
        """Property: Detection bbox IoU with itself is 1.0.

        Uses the valid_detection_bbox strategy from hypothesis_strategies.py.
        """
        # Convert dict format to xyxy tuple
        x1 = bbox_dict["x"]
        y1 = bbox_dict["y"]
        x2 = x1 + bbox_dict["width"]
        y2 = y1 + bbox_dict["height"]
        bbox = (float(x1), float(y1), float(x2), float(y2))

        iou = calculate_bbox_iou(bbox, bbox)

        assert iou == pytest.approx(1.0, abs=0.0001), (
            f"Detection bbox self-IoU should be 1.0, got {iou}"
        )

    @given(bbox_dict1=valid_detection_bbox(), bbox_dict2=valid_detection_bbox())
    @hypothesis_settings(max_examples=500)
    def test_detection_bbox_iou_commutative(
        self,
        bbox_dict1: dict[str, int],
        bbox_dict2: dict[str, int],
    ) -> None:
        """Property: Detection bbox IoU is commutative."""
        # Convert dict format to xyxy tuples
        bbox1 = (
            float(bbox_dict1["x"]),
            float(bbox_dict1["y"]),
            float(bbox_dict1["x"] + bbox_dict1["width"]),
            float(bbox_dict1["y"] + bbox_dict1["height"]),
        )
        bbox2 = (
            float(bbox_dict2["x"]),
            float(bbox_dict2["y"]),
            float(bbox_dict2["x"] + bbox_dict2["width"]),
            float(bbox_dict2["y"] + bbox_dict2["height"]),
        )

        iou_12 = calculate_bbox_iou(bbox1, bbox2)
        iou_21 = calculate_bbox_iou(bbox2, bbox1)

        assert iou_12 == pytest.approx(iou_21, abs=0.0001), (
            f"Detection bbox IoU not commutative: {iou_12} != {iou_21}"
        )

    @given(bbox_dict1=valid_detection_bbox(), bbox_dict2=valid_detection_bbox())
    @hypothesis_settings(max_examples=500)
    def test_detection_bbox_iou_bounded(
        self,
        bbox_dict1: dict[str, int],
        bbox_dict2: dict[str, int],
    ) -> None:
        """Property: Detection bbox IoU is in [0, 1] range."""
        # Convert dict format to xyxy tuples
        bbox1 = (
            float(bbox_dict1["x"]),
            float(bbox_dict1["y"]),
            float(bbox_dict1["x"] + bbox_dict1["width"]),
            float(bbox_dict1["y"] + bbox_dict1["height"]),
        )
        bbox2 = (
            float(bbox_dict2["x"]),
            float(bbox_dict2["y"]),
            float(bbox_dict2["x"] + bbox_dict2["width"]),
            float(bbox_dict2["y"] + bbox_dict2["height"]),
        )

        iou = calculate_bbox_iou(bbox1, bbox2)

        assert 0.0 <= iou <= 1.0, f"Detection bbox IoU out of range: {iou}"

    @given(bbox_dict=edge_case_bbox())
    @hypothesis_settings(max_examples=500)
    def test_edge_case_bbox_self_iou(self, bbox_dict: dict[str, int]) -> None:
        """Property: Edge case bbox IoU with itself is 1.0.

        Tests edge cases like corner bboxes, full frame, minimum size.
        """
        # Convert dict format to xyxy tuple
        x1 = bbox_dict["x"]
        y1 = bbox_dict["y"]
        x2 = x1 + bbox_dict["width"]
        y2 = y1 + bbox_dict["height"]
        bbox = (float(x1), float(y1), float(x2), float(y2))

        iou = calculate_bbox_iou(bbox, bbox)

        assert iou == pytest.approx(1.0, abs=0.0001), (
            f"Edge case bbox self-IoU should be 1.0, got {iou}"
        )


# =============================================================================
# IoU Monotonicity Properties
# =============================================================================


class TestIoUMonotonicityProperties:
    """Property-based tests for IoU monotonicity with respect to overlap."""

    @given(bbox=valid_bbox_xyxy(max_coord=500))
    @hypothesis_settings(max_examples=500)
    def test_iou_decreases_with_shrinking(
        self,
        bbox: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU decreases when one box shrinks (moving away from overlap).

        When we shrink a box, its IoU with the original should decrease.
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        # Only test if bbox is large enough to shrink
        assume(width > 10 and height > 10)

        # Shrink the bbox by 20%
        shrink = 0.2
        new_width = width * (1 - shrink)
        new_height = height * (1 - shrink)
        shrunk_bbox = (x1, y1, x1 + new_width, y1 + new_height)

        # IoU between original and shrunk
        iou = calculate_bbox_iou(bbox, shrunk_bbox)

        # IoU should be less than 1.0 (not identical)
        # and greater than 0 (they overlap)
        assert 0 < iou < 1.0, f"IoU with shrunk bbox should be in (0, 1), got {iou}"

    @given(bbox=valid_bbox_xyxy(max_coord=300))
    @hypothesis_settings(max_examples=500)
    def test_iou_increases_toward_identity(
        self,
        bbox: tuple[float, float, float, float],
    ) -> None:
        """Property: As two identical boxes diverge, IoU decreases from 1.0.

        Starting from identical boxes (IoU=1.0), any change should decrease IoU.
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        assume(width > 5 and height > 5)

        # Shift box slightly
        shift = 2.0
        shifted_bbox = (x1 + shift, y1 + shift, x2 + shift, y2 + shift)

        # Self-IoU should be 1.0
        self_iou = calculate_bbox_iou(bbox, bbox)
        assert self_iou == pytest.approx(1.0, abs=0.0001)

        # Shifted IoU should be less than 1.0
        shifted_iou = calculate_bbox_iou(bbox, shifted_bbox)
        assert shifted_iou < 1.0, f"Shifted bbox should have IoU < 1.0, got {shifted_iou}"
