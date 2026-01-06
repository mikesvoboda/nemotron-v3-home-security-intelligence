"""Unit tests for zone service.

Tests cover:
- point_in_zone() - Ray casting algorithm, polygon vs rectangle
- bbox_center() - Coordinate normalization, clamping
- detection_in_zone() - Full detection integration
- calculate_dwell_time() - Time calculation logic
- detect_line_crossing() - Vector math, direction detection
- calculate_approach_vector() - Distance/speed calculations

Edge cases: point on boundary, self-intersecting polygons, zero-size bbox, very small zones.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from backend.models.detection import Detection
from backend.models.zone import Zone, ZoneShape, ZoneType
from backend.services.zone_service import (
    ApproachVector,
    _distance,
    _distance_to_zone_boundary,
    _get_detection_center,
    _get_zone_centroid,
    _point_to_segment_distance,
    bbox_center,
    calculate_approach_vector,
    calculate_dwell_time,
    detect_line_crossing,
    detect_line_exit,
    detection_in_zone,
    get_highest_priority_zone,
    point_in_zone,
    zones_to_context,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def rectangle_zone() -> Zone:
    """Create a rectangular zone for testing (bottom-left quadrant)."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-rectangle"
    zone.camera_id = "cam-1"
    zone.name = "Driveway"
    zone.zone_type = ZoneType.DRIVEWAY
    zone.shape = ZoneShape.RECTANGLE
    # Rectangle from (0.1, 0.1) to (0.4, 0.4)
    zone.coordinates = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
    zone.enabled = True
    zone.priority = 1
    return zone


@pytest.fixture
def triangle_zone() -> Zone:
    """Create a triangular polygon zone for testing."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-triangle"
    zone.camera_id = "cam-1"
    zone.name = "Entry Point"
    zone.zone_type = ZoneType.ENTRY_POINT
    zone.shape = ZoneShape.POLYGON
    # Triangle with vertices at (0.5, 0.1), (0.9, 0.1), (0.7, 0.5)
    zone.coordinates = [[0.5, 0.1], [0.9, 0.1], [0.7, 0.5]]
    zone.enabled = True
    zone.priority = 2
    return zone


@pytest.fixture
def concave_zone() -> Zone:
    """Create a concave (L-shaped) polygon zone for testing."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-concave"
    zone.camera_id = "cam-1"
    zone.name = "Yard"
    zone.zone_type = ZoneType.YARD
    zone.shape = ZoneShape.POLYGON
    # L-shaped polygon
    zone.coordinates = [
        [0.1, 0.5],
        [0.4, 0.5],
        [0.4, 0.7],
        [0.2, 0.7],
        [0.2, 0.9],
        [0.1, 0.9],
    ]
    zone.enabled = True
    zone.priority = 3
    return zone


@pytest.fixture
def disabled_zone() -> Zone:
    """Create a disabled zone."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-disabled"
    zone.camera_id = "cam-1"
    zone.name = "Disabled Zone"
    zone.zone_type = ZoneType.OTHER
    zone.shape = ZoneShape.RECTANGLE
    zone.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    zone.enabled = False
    zone.priority = 0
    return zone


@pytest.fixture
def empty_coordinates_zone() -> Zone:
    """Create a zone with empty coordinates."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-empty"
    zone.camera_id = "cam-1"
    zone.name = "Empty Zone"
    zone.zone_type = ZoneType.OTHER
    zone.shape = ZoneShape.POLYGON
    zone.coordinates = []
    zone.enabled = True
    zone.priority = 0
    return zone


@pytest.fixture
def very_small_zone() -> Zone:
    """Create a very small zone (micro-region)."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-small"
    zone.camera_id = "cam-1"
    zone.name = "Small Zone"
    zone.zone_type = ZoneType.OTHER
    zone.shape = ZoneShape.RECTANGLE
    # Very small rectangle: 0.001 x 0.001
    zone.coordinates = [[0.5, 0.5], [0.501, 0.5], [0.501, 0.501], [0.5, 0.501]]
    zone.enabled = True
    zone.priority = 0
    return zone


def make_detection(
    bbox_x: int | None = 100,
    bbox_y: int | None = 100,
    bbox_width: int | None = 50,
    bbox_height: int | None = 50,
    detected_at: datetime | None = None,
    camera_id: str = "cam-1",
) -> Detection:
    """Factory function to create Detection objects for testing."""
    detection = MagicMock(spec=Detection)
    detection.id = 1
    detection.camera_id = camera_id
    detection.file_path = "/path/to/image.jpg"
    detection.bbox_x = bbox_x
    detection.bbox_y = bbox_y
    detection.bbox_width = bbox_width
    detection.bbox_height = bbox_height
    detection.detected_at = detected_at or datetime.now(UTC)
    detection.object_type = "person"
    detection.confidence = 0.95
    return detection


# =============================================================================
# point_in_zone Tests
# =============================================================================


class TestPointInZone:
    """Tests for point_in_zone function."""

    def test_point_inside_rectangle(self, rectangle_zone: Zone) -> None:
        """Test point clearly inside a rectangular zone."""
        # Center of the rectangle (0.25, 0.25)
        assert point_in_zone(0.25, 0.25, rectangle_zone) is True

    def test_point_outside_rectangle(self, rectangle_zone: Zone) -> None:
        """Test point clearly outside a rectangular zone."""
        # Outside to the right of the rectangle
        assert point_in_zone(0.6, 0.25, rectangle_zone) is False

    def test_point_inside_triangle(self, triangle_zone: Zone) -> None:
        """Test point inside a triangular zone."""
        # Point roughly in center of triangle
        assert point_in_zone(0.7, 0.2, triangle_zone) is True

    def test_point_outside_triangle(self, triangle_zone: Zone) -> None:
        """Test point outside a triangular zone."""
        # Point below the triangle
        assert point_in_zone(0.7, 0.6, triangle_zone) is False

    def test_point_inside_concave_polygon(self, concave_zone: Zone) -> None:
        """Test point inside an L-shaped (concave) zone."""
        # Point in the vertical arm of the L
        assert point_in_zone(0.15, 0.85, concave_zone) is True
        # Point in the horizontal arm of the L
        assert point_in_zone(0.35, 0.6, concave_zone) is True

    def test_point_in_concave_notch(self, concave_zone: Zone) -> None:
        """Test point in the notch of an L-shaped zone (should be outside)."""
        # Point in the concave notch (upper-right of the L)
        assert point_in_zone(0.35, 0.8, concave_zone) is False

    def test_point_on_boundary_horizontal_edge(self, rectangle_zone: Zone) -> None:
        """Test point on horizontal boundary edge."""
        # Point on top edge (y=0.1)
        # Ray casting behavior may vary on boundary
        result = point_in_zone(0.25, 0.1, rectangle_zone)
        # Boundary behavior depends on implementation; typically exclusive
        assert isinstance(result, bool)

    def test_point_on_boundary_vertical_edge(self, rectangle_zone: Zone) -> None:
        """Test point on vertical boundary edge."""
        # Point on left edge (x=0.1)
        result = point_in_zone(0.1, 0.25, rectangle_zone)
        # Boundary behavior depends on implementation
        assert isinstance(result, bool)

    def test_point_on_vertex(self, rectangle_zone: Zone) -> None:
        """Test point exactly on a vertex."""
        # Vertex at (0.1, 0.1)
        result = point_in_zone(0.1, 0.1, rectangle_zone)
        assert isinstance(result, bool)

    def test_disabled_zone_always_false(self, disabled_zone: Zone) -> None:
        """Test that disabled zones always return False."""
        # Even though point would be inside, zone is disabled
        assert point_in_zone(0.5, 0.5, disabled_zone) is False

    def test_empty_coordinates_returns_false(self, empty_coordinates_zone: Zone) -> None:
        """Test that zones with empty coordinates return False."""
        assert point_in_zone(0.5, 0.5, empty_coordinates_zone) is False

    def test_insufficient_coordinates_returns_false(self) -> None:
        """Test that zones with less than 3 coordinates return False."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        zone.coordinates = [[0.1, 0.1], [0.4, 0.4]]  # Only 2 points (a line)
        assert point_in_zone(0.25, 0.25, zone) is False

    def test_point_in_very_small_zone(self, very_small_zone: Zone) -> None:
        """Test point detection in a very small zone."""
        # Point exactly at center of small zone
        assert point_in_zone(0.5005, 0.5005, very_small_zone) is True
        # Point just outside
        assert point_in_zone(0.502, 0.502, very_small_zone) is False

    def test_point_at_origin(self, rectangle_zone: Zone) -> None:
        """Test point at origin (0, 0)."""
        assert point_in_zone(0.0, 0.0, rectangle_zone) is False

    def test_point_at_max_coordinates(self, rectangle_zone: Zone) -> None:
        """Test point at maximum coordinates (1, 1)."""
        assert point_in_zone(1.0, 1.0, rectangle_zone) is False

    def test_negative_coordinates(self, rectangle_zone: Zone) -> None:
        """Test point with negative coordinates."""
        assert point_in_zone(-0.1, -0.1, rectangle_zone) is False

    def test_coordinates_beyond_normalized_range(self, rectangle_zone: Zone) -> None:
        """Test point with coordinates > 1."""
        assert point_in_zone(1.5, 1.5, rectangle_zone) is False


class TestPointInZoneSelfIntersecting:
    """Tests for point_in_zone with self-intersecting polygons."""

    def test_self_intersecting_figure_eight(self) -> None:
        """Test point in a self-intersecting figure-8 polygon."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        # Figure-8 shape that crosses itself
        zone.coordinates = [
            [0.2, 0.2],
            [0.8, 0.8],
            [0.2, 0.8],
            [0.8, 0.2],
        ]
        # Ray casting may give unexpected results for self-intersecting polygons
        result = point_in_zone(0.5, 0.5, zone)
        assert isinstance(result, bool)

    def test_bowtie_polygon(self) -> None:
        """Test point in a bowtie-shaped self-intersecting polygon."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        # Bowtie shape
        zone.coordinates = [
            [0.3, 0.3],
            [0.7, 0.3],
            [0.3, 0.7],
            [0.7, 0.7],
        ]
        # Test center of bowtie (at intersection)
        center_result = point_in_zone(0.5, 0.5, zone)
        assert isinstance(center_result, bool)


# =============================================================================
# bbox_center Tests
# =============================================================================


class TestBboxCenter:
    """Tests for bbox_center function."""

    def test_standard_bbox_center(self) -> None:
        """Test center calculation for standard bounding box."""
        x, y = bbox_center(100, 100, 50, 50, 1920, 1080)
        # Center should be at (125, 125) in pixels
        # Normalized: (125/1920, 125/1080) = (0.0651..., 0.1157...)
        assert 0.064 < x < 0.066
        assert 0.115 < y < 0.116

    def test_bbox_at_origin(self) -> None:
        """Test bbox starting at origin."""
        x, y = bbox_center(0, 0, 100, 100, 1000, 1000)
        # Center at (50, 50), normalized: (0.05, 0.05)
        assert x == 0.05
        assert y == 0.05

    def test_bbox_at_image_edge(self) -> None:
        """Test bbox at the edge of the image."""
        x, y = bbox_center(1800, 1000, 120, 80, 1920, 1080)
        # Center at (1860, 1040) in pixels
        # Normalized: (1860/1920, 1040/1080) = (0.96875, 0.963...)
        # Since center is within image bounds, no clamping needed
        assert 0.96 < x < 0.98
        assert 0.96 < y < 0.97

    def test_bbox_partially_outside_image(self) -> None:
        """Test bbox that extends outside image bounds."""
        x, y = bbox_center(1900, 1000, 100, 200, 1920, 1080)
        # Center at (1950, 1100) - outside image, clamped
        assert x == 1.0
        assert y == 1.0

    def test_bbox_center_clamping(self) -> None:
        """Test that bbox center is clamped to 0-1 range."""
        # Large bbox extending beyond image
        x, y = bbox_center(1800, 900, 300, 300, 1920, 1080)
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0

    def test_zero_image_width_raises(self) -> None:
        """Test that zero image width raises ValueError."""
        with pytest.raises(ValueError, match="Image dimensions must be positive"):
            bbox_center(100, 100, 50, 50, 0, 1080)

    def test_zero_image_height_raises(self) -> None:
        """Test that zero image height raises ValueError."""
        with pytest.raises(ValueError, match="Image dimensions must be positive"):
            bbox_center(100, 100, 50, 50, 1920, 0)

    def test_negative_image_dimensions_raises(self) -> None:
        """Test that negative image dimensions raise ValueError."""
        with pytest.raises(ValueError, match="Image dimensions must be positive"):
            bbox_center(100, 100, 50, 50, -1920, 1080)

    def test_negative_bbox_x_raises(self) -> None:
        """Test that negative bbox x raises ValueError."""
        with pytest.raises(ValueError, match="Bounding box coordinates must be non-negative"):
            bbox_center(-10, 100, 50, 50, 1920, 1080)

    def test_negative_bbox_y_raises(self) -> None:
        """Test that negative bbox y raises ValueError."""
        with pytest.raises(ValueError, match="Bounding box coordinates must be non-negative"):
            bbox_center(100, -10, 50, 50, 1920, 1080)

    def test_zero_bbox_width_raises(self) -> None:
        """Test that zero bbox width raises ValueError."""
        with pytest.raises(ValueError, match="Bounding box dimensions must be positive"):
            bbox_center(100, 100, 0, 50, 1920, 1080)

    def test_zero_bbox_height_raises(self) -> None:
        """Test that zero bbox height raises ValueError."""
        with pytest.raises(ValueError, match="Bounding box dimensions must be positive"):
            bbox_center(100, 100, 50, 0, 1920, 1080)

    def test_negative_bbox_width_raises(self) -> None:
        """Test that negative bbox width raises ValueError."""
        with pytest.raises(ValueError, match="Bounding box dimensions must be positive"):
            bbox_center(100, 100, -50, 50, 1920, 1080)

    def test_small_image_dimensions(self) -> None:
        """Test with small image dimensions."""
        x, y = bbox_center(5, 5, 10, 10, 100, 100)
        assert x == 0.1  # Center at (10, 10), normalized: (0.1, 0.1)
        assert y == 0.1

    def test_single_pixel_bbox(self) -> None:
        """Test with single pixel bounding box."""
        x, y = bbox_center(500, 500, 1, 1, 1000, 1000)
        # Center at (500.5, 500.5), normalized: (0.5005, 0.5005)
        assert 0.500 < x < 0.501
        assert 0.500 < y < 0.501


# =============================================================================
# detection_in_zone Tests
# =============================================================================


class TestDetectionInZone:
    """Tests for detection_in_zone function."""

    def test_detection_inside_zone(self, rectangle_zone: Zone) -> None:
        """Test detection clearly inside a zone."""
        # Bbox at (192, 108) with size (96, 108) on 1920x1080 image
        # Center at (240, 162) -> normalized (0.125, 0.15) which is inside the rectangle
        result = detection_in_zone(192, 108, 96, 108, 1920, 1080, rectangle_zone)
        assert result is True

    def test_detection_outside_zone(self, rectangle_zone: Zone) -> None:
        """Test detection clearly outside a zone."""
        # Bbox centered at (0.8, 0.8) - outside the rectangle zone
        result = detection_in_zone(1400, 800, 100, 100, 1920, 1080, rectangle_zone)
        assert result is False

    def test_detection_in_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test that disabled zones always return False."""
        result = detection_in_zone(500, 500, 100, 100, 1920, 1080, disabled_zone)
        assert result is False

    def test_detection_in_triangle_zone(self, triangle_zone: Zone) -> None:
        """Test detection inside a triangular zone."""
        # Center roughly at (0.7, 0.2) which is inside the triangle
        result = detection_in_zone(1296, 180, 100, 100, 1920, 1080, triangle_zone)
        assert result is True

    def test_detection_bbox_edge_case(self, rectangle_zone: Zone) -> None:
        """Test detection when bbox center is exactly on zone boundary."""
        # This tests the interaction between bbox_center and point_in_zone
        result = detection_in_zone(173, 97, 58, 32, 1920, 1080, rectangle_zone)
        assert isinstance(result, bool)


# =============================================================================
# calculate_dwell_time Tests
# =============================================================================


class TestCalculateDwellTime:
    """Tests for calculate_dwell_time function."""

    def test_dwell_time_no_detections(self, rectangle_zone: Zone) -> None:
        """Test dwell time with empty detection list."""
        result = calculate_dwell_time([], rectangle_zone)
        assert result == 0.0

    def test_dwell_time_single_detection(self, rectangle_zone: Zone) -> None:
        """Test dwell time with single detection (no time span)."""
        detection = make_detection(bbox_x=250, bbox_y=150, bbox_width=100, bbox_height=100)
        result = calculate_dwell_time([detection], rectangle_zone)
        assert result == 0.0

    def test_dwell_time_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test dwell time with disabled zone."""
        now = datetime.now(UTC)
        detections = [
            make_detection(detected_at=now),
            make_detection(detected_at=now + timedelta(seconds=10)),
        ]
        result = calculate_dwell_time(detections, disabled_zone)
        assert result == 0.0

    def test_dwell_time_continuous_inside(self, rectangle_zone: Zone) -> None:
        """Test dwell time for continuous presence inside zone."""
        now = datetime.now(UTC)
        # Create detections inside the zone (normalized center ~0.2, 0.2)
        detections = [
            make_detection(
                bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=310,
                bbox_y=160,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
            make_detection(
                bbox_x=320,
                bbox_y=170,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=10),
            ),
        ]
        result = calculate_dwell_time(detections, rectangle_zone, 1920, 1080)
        assert result == 10.0

    def test_dwell_time_entry_and_exit(self, rectangle_zone: Zone) -> None:
        """Test dwell time when object enters and exits zone."""
        now = datetime.now(UTC)
        # First detection outside zone
        d1 = make_detection(
            bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now
        )
        # Second detection inside zone
        d2 = make_detection(
            bbox_x=300,
            bbox_y=150,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=5),
        )
        # Third detection still inside zone
        d3 = make_detection(
            bbox_x=310,
            bbox_y=160,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=10),
        )
        # Fourth detection outside zone again
        d4 = make_detection(
            bbox_x=1500,
            bbox_y=800,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=15),
        )

        result = calculate_dwell_time([d1, d2, d3, d4], rectangle_zone, 1920, 1080)
        # Dwell from d2 (5s) to d4 (15s) = 10s total (inside for 10 seconds)
        assert result == 10.0

    def test_dwell_time_multiple_entries(self, rectangle_zone: Zone) -> None:
        """Test dwell time with multiple entry/exit cycles."""
        now = datetime.now(UTC)
        detections = [
            # First inside period
            make_detection(
                bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=310,
                bbox_y=160,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
            # Exit
            make_detection(
                bbox_x=1500,
                bbox_y=800,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=10),
            ),
            # Second inside period
            make_detection(
                bbox_x=300,
                bbox_y=150,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=15),
            ),
            make_detection(
                bbox_x=310,
                bbox_y=160,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=20),
            ),
        ]
        result = calculate_dwell_time(detections, rectangle_zone, 1920, 1080)
        # First period: 0-10s = 10s (but we exit at 10s, so it's 5s from entry to exit)
        # Actually: enter at t=0, stay at t=5, exit at t=10 -> dwell = 10s
        # Second period: enter at t=15, stay at t=20 -> dwell = 5s
        # Total: 15s
        assert result == 15.0

    def test_dwell_time_detection_without_bbox(self, rectangle_zone: Zone) -> None:
        """Test dwell time with detection missing bbox data."""
        now = datetime.now(UTC)
        detections = [
            make_detection(
                bbox_x=None, bbox_y=None, bbox_width=None, bbox_height=None, detected_at=now
            ),
            make_detection(
                bbox_x=300,
                bbox_y=150,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
        ]
        # Should handle missing bbox gracefully
        result = calculate_dwell_time(detections, rectangle_zone, 1920, 1080)
        assert result == 0.0  # Only one valid detection


# =============================================================================
# detect_line_crossing Tests
# =============================================================================


class TestDetectLineCrossing:
    """Tests for detect_line_crossing function."""

    def test_line_crossing_outside_to_inside(self, rectangle_zone: Zone) -> None:
        """Test crossing from outside to inside the zone."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=300,
            bbox_y=150,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_crossing(prev, curr, rectangle_zone, 1920, 1080)
        assert result is True

    def test_line_crossing_inside_to_inside(self, rectangle_zone: Zone) -> None:
        """Test movement that stays inside the zone."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=350,
            bbox_y=180,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_crossing(prev, curr, rectangle_zone, 1920, 1080)
        assert result is False  # No crossing, already inside

    def test_line_crossing_outside_to_outside(self, rectangle_zone: Zone) -> None:
        """Test movement that stays outside the zone."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=1550,
            bbox_y=850,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_crossing(prev, curr, rectangle_zone, 1920, 1080)
        assert result is False  # No crossing

    def test_line_crossing_inside_to_outside_is_exit(self, rectangle_zone: Zone) -> None:
        """Test crossing from inside to outside (exit, not entry)."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=1500,
            bbox_y=800,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_crossing(prev, curr, rectangle_zone, 1920, 1080)
        assert result is False  # This is an exit, not an entry

    def test_line_crossing_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test line crossing with disabled zone."""
        now = datetime.now(UTC)
        prev = make_detection(detected_at=now)
        curr = make_detection(detected_at=now + timedelta(seconds=1))
        result = detect_line_crossing(prev, curr, disabled_zone, 1920, 1080)
        assert result is False

    def test_line_crossing_missing_bbox(self, rectangle_zone: Zone) -> None:
        """Test line crossing with missing bbox data."""
        now = datetime.now(UTC)
        prev = make_detection(bbox_x=None, bbox_y=None, detected_at=now)
        curr = make_detection(detected_at=now + timedelta(seconds=1))
        result = detect_line_crossing(prev, curr, rectangle_zone, 1920, 1080)
        assert result is False


# =============================================================================
# detect_line_exit Tests
# =============================================================================


class TestDetectLineExit:
    """Tests for detect_line_exit function."""

    def test_line_exit_inside_to_outside(self, rectangle_zone: Zone) -> None:
        """Test exit from inside to outside the zone."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=1500,
            bbox_y=800,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_exit(prev, curr, rectangle_zone, 1920, 1080)
        assert result is True

    def test_line_exit_outside_to_inside(self, rectangle_zone: Zone) -> None:
        """Test exit function when entering (should be False)."""
        now = datetime.now(UTC)
        prev = make_detection(
            bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now
        )
        curr = make_detection(
            bbox_x=300,
            bbox_y=150,
            bbox_width=100,
            bbox_height=100,
            detected_at=now + timedelta(seconds=1),
        )
        result = detect_line_exit(prev, curr, rectangle_zone, 1920, 1080)
        assert result is False  # This is an entry, not an exit

    def test_line_exit_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test line exit with disabled zone."""
        now = datetime.now(UTC)
        prev = make_detection(detected_at=now)
        curr = make_detection(detected_at=now + timedelta(seconds=1))
        result = detect_line_exit(prev, curr, disabled_zone, 1920, 1080)
        assert result is False


# =============================================================================
# calculate_approach_vector Tests
# =============================================================================


class TestCalculateApproachVector:
    """Tests for calculate_approach_vector function."""

    def test_approach_vector_no_detections(self, rectangle_zone: Zone) -> None:
        """Test approach vector with empty detection list."""
        result = calculate_approach_vector([], rectangle_zone)
        assert result is None

    def test_approach_vector_single_detection(self, rectangle_zone: Zone) -> None:
        """Test approach vector with single detection."""
        detection = make_detection()
        result = calculate_approach_vector([detection], rectangle_zone)
        assert result is None

    def test_approach_vector_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test approach vector with disabled zone."""
        now = datetime.now(UTC)
        detections = [
            make_detection(detected_at=now),
            make_detection(detected_at=now + timedelta(seconds=1)),
        ]
        result = calculate_approach_vector(detections, disabled_zone)
        assert result is None

    def test_approach_vector_approaching(self, rectangle_zone: Zone) -> None:
        """Test approach vector when moving toward zone."""
        now = datetime.now(UTC)
        # Start far from zone, move toward it
        detections = [
            make_detection(
                bbox_x=1500, bbox_y=800, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=1000,
                bbox_y=500,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.is_approaching is True
        assert result.speed_normalized > 0
        assert result.estimated_arrival_seconds is not None

    def test_approach_vector_moving_away(self, rectangle_zone: Zone) -> None:
        """Test approach vector when moving away from zone."""
        now = datetime.now(UTC)
        # Start near zone, move away
        detections = [
            make_detection(
                bbox_x=500, bbox_y=300, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=1500,
                bbox_y=800,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=5),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.is_approaching is False
        assert result.estimated_arrival_seconds is None  # Not approaching, no ETA

    def test_approach_vector_zero_time_delta(self, rectangle_zone: Zone) -> None:
        """Test approach vector when time delta is zero."""
        now = datetime.now(UTC)
        detections = [
            make_detection(bbox_x=1500, bbox_y=800, detected_at=now),
            make_detection(bbox_x=1000, bbox_y=500, detected_at=now),  # Same time
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is None

    def test_approach_vector_direction_calculation(self, rectangle_zone: Zone) -> None:
        """Test that direction is calculated correctly."""
        now = datetime.now(UTC)
        # Move purely right (increasing x, same y)
        detections = [
            make_detection(
                bbox_x=500, bbox_y=500, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=700,
                bbox_y=500,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=2),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        # Moving right should be approximately 90 degrees
        assert 85 < result.direction_degrees < 95

    def test_approach_vector_inside_zone(self, rectangle_zone: Zone) -> None:
        """Test approach vector when already inside zone."""
        now = datetime.now(UTC)
        # Both detections inside zone
        detections = [
            make_detection(
                bbox_x=300, bbox_y=150, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=310,
                bbox_y=160,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=2),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.distance_to_zone == 0.0  # Already inside
        assert result.estimated_arrival_seconds == 0.0

    def test_approach_vector_missing_bbox(self, rectangle_zone: Zone) -> None:
        """Test approach vector with all detections missing bbox."""
        now = datetime.now(UTC)
        detections = [
            make_detection(
                bbox_x=None, bbox_y=None, bbox_width=None, bbox_height=None, detected_at=now
            ),
            make_detection(
                bbox_x=None,
                bbox_y=None,
                bbox_width=None,
                bbox_height=None,
                detected_at=now + timedelta(seconds=1),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is None


class TestApproachVectorDataclass:
    """Tests for ApproachVector dataclass."""

    def test_approach_vector_fields(self) -> None:
        """Test ApproachVector has all expected fields."""
        vector = ApproachVector(
            is_approaching=True,
            direction_degrees=45.0,
            speed_normalized=0.1,
            distance_to_zone=0.5,
            estimated_arrival_seconds=5.0,
        )
        assert vector.is_approaching is True
        assert vector.direction_degrees == 45.0
        assert vector.speed_normalized == 0.1
        assert vector.distance_to_zone == 0.5
        assert vector.estimated_arrival_seconds == 5.0

    def test_approach_vector_none_arrival(self) -> None:
        """Test ApproachVector with None estimated arrival."""
        vector = ApproachVector(
            is_approaching=False,
            direction_degrees=180.0,
            speed_normalized=0.2,
            distance_to_zone=1.0,
            estimated_arrival_seconds=None,
        )
        assert vector.estimated_arrival_seconds is None


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestDistance:
    """Tests for _distance helper function."""

    def test_distance_same_point(self) -> None:
        """Test distance between same point is zero."""
        assert _distance((0.5, 0.5), (0.5, 0.5)) == 0.0

    def test_distance_horizontal(self) -> None:
        """Test horizontal distance."""
        result = _distance((0.0, 0.0), (1.0, 0.0))
        assert result == 1.0

    def test_distance_vertical(self) -> None:
        """Test vertical distance."""
        result = _distance((0.0, 0.0), (0.0, 1.0))
        assert result == 1.0

    def test_distance_diagonal(self) -> None:
        """Test diagonal distance (3-4-5 triangle)."""
        result = _distance((0.0, 0.0), (3.0, 4.0))
        assert result == 5.0


class TestPointToSegmentDistance:
    """Tests for _point_to_segment_distance helper function."""

    def test_point_on_segment(self) -> None:
        """Test point directly on segment."""
        result = _point_to_segment_distance(0.5, 0.0, 0.0, 0.0, 1.0, 0.0)
        assert result == 0.0

    def test_point_at_segment_endpoint(self) -> None:
        """Test point at segment endpoint."""
        result = _point_to_segment_distance(0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        assert result == 0.0

    def test_point_perpendicular_to_segment(self) -> None:
        """Test point perpendicular to segment."""
        result = _point_to_segment_distance(0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
        assert result == 1.0

    def test_point_beyond_segment_endpoint(self) -> None:
        """Test point beyond segment endpoint."""
        result = _point_to_segment_distance(2.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        assert result == 1.0

    def test_degenerate_segment(self) -> None:
        """Test with degenerate segment (single point)."""
        result = _point_to_segment_distance(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert result == 1.0


class TestDistanceToZoneBoundary:
    """Tests for _distance_to_zone_boundary helper function."""

    def test_point_inside_zone(self, rectangle_zone: Zone) -> None:
        """Test distance is 0 when point is inside zone."""
        result = _distance_to_zone_boundary(0.25, 0.25, rectangle_zone)
        assert result == 0.0

    def test_point_outside_zone(self, rectangle_zone: Zone) -> None:
        """Test distance to boundary from outside zone."""
        result = _distance_to_zone_boundary(0.6, 0.25, rectangle_zone)
        # Distance should be approximately 0.2 (from x=0.6 to x=0.4)
        assert 0.15 < result < 0.25

    def test_empty_coordinates(self, empty_coordinates_zone: Zone) -> None:
        """Test distance with empty coordinates returns infinity."""
        result = _distance_to_zone_boundary(0.5, 0.5, empty_coordinates_zone)
        assert result == float("inf")


class TestGetZoneCentroid:
    """Tests for _get_zone_centroid helper function."""

    def test_rectangle_centroid(self, rectangle_zone: Zone) -> None:
        """Test centroid of rectangle."""
        result = _get_zone_centroid(rectangle_zone)
        assert result is not None
        # Rectangle from (0.1, 0.1) to (0.4, 0.4), centroid at (0.25, 0.25)
        assert result[0] == pytest.approx(0.25, abs=0.01)
        assert result[1] == pytest.approx(0.25, abs=0.01)

    def test_triangle_centroid(self, triangle_zone: Zone) -> None:
        """Test centroid of triangle."""
        result = _get_zone_centroid(triangle_zone)
        assert result is not None
        # Triangle with vertices at (0.5, 0.1), (0.9, 0.1), (0.7, 0.5)
        # Centroid = ((0.5+0.9+0.7)/3, (0.1+0.1+0.5)/3) = (0.7, 0.233...)
        assert result[0] == pytest.approx(0.7, abs=0.01)
        assert result[1] == pytest.approx(0.233, abs=0.01)

    def test_empty_coordinates_centroid(self, empty_coordinates_zone: Zone) -> None:
        """Test centroid with empty coordinates."""
        result = _get_zone_centroid(empty_coordinates_zone)
        assert result is None


class TestGetDetectionCenter:
    """Tests for _get_detection_center helper function."""

    def test_valid_detection(self) -> None:
        """Test getting center of valid detection."""
        detection = make_detection(bbox_x=100, bbox_y=100, bbox_width=50, bbox_height=50)
        result = _get_detection_center(detection, 1000, 1000)
        assert result is not None
        assert result[0] == pytest.approx(0.125, abs=0.01)
        assert result[1] == pytest.approx(0.125, abs=0.01)

    def test_missing_bbox(self) -> None:
        """Test detection with missing bbox returns None."""
        detection = make_detection(bbox_x=None, bbox_y=100, bbox_width=50, bbox_height=50)
        result = _get_detection_center(detection, 1000, 1000)
        assert result is None


# =============================================================================
# zones_to_context Tests
# =============================================================================


class TestZonesToContext:
    """Tests for zones_to_context function."""

    def test_empty_zones_list(self) -> None:
        """Test with empty zones list."""
        result = zones_to_context([])
        assert result == {}

    def test_single_zone(self, rectangle_zone: Zone) -> None:
        """Test with single zone."""
        result = zones_to_context([rectangle_zone])
        assert "driveway" in result
        assert "Driveway" in result["driveway"]

    def test_multiple_zones_same_type(self, rectangle_zone: Zone) -> None:
        """Test with multiple zones of same type."""
        zone2 = MagicMock(spec=Zone)
        zone2.zone_type = ZoneType.DRIVEWAY
        zone2.name = "Driveway 2"

        result = zones_to_context([rectangle_zone, zone2])
        assert "driveway" in result
        assert len(result["driveway"]) == 2

    def test_multiple_zones_different_types(
        self, rectangle_zone: Zone, triangle_zone: Zone
    ) -> None:
        """Test with zones of different types."""
        result = zones_to_context([rectangle_zone, triangle_zone])
        assert "driveway" in result
        assert "entry_point" in result


# =============================================================================
# get_highest_priority_zone Tests
# =============================================================================


class TestGetHighestPriorityZone:
    """Tests for get_highest_priority_zone function."""

    def test_empty_list(self) -> None:
        """Test with empty zones list."""
        result = get_highest_priority_zone([])
        assert result is None

    def test_single_zone(self, rectangle_zone: Zone) -> None:
        """Test with single zone."""
        result = get_highest_priority_zone([rectangle_zone])
        assert result == rectangle_zone

    def test_multiple_zones(
        self, rectangle_zone: Zone, triangle_zone: Zone, concave_zone: Zone
    ) -> None:
        """Test returns zone with highest priority."""
        # concave_zone has priority 3, triangle_zone has priority 2, rectangle_zone has priority 1
        result = get_highest_priority_zone([rectangle_zone, triangle_zone, concave_zone])
        assert result == concave_zone

    def test_same_priority(self) -> None:
        """Test with zones having same priority."""
        zone1 = MagicMock(spec=Zone)
        zone1.priority = 5
        zone2 = MagicMock(spec=Zone)
        zone2.priority = 5

        result = get_highest_priority_zone([zone1, zone2])
        # Should return one of them (implementation may vary)
        assert result in [zone1, zone2]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_collinear_polygon_points(self) -> None:
        """Test zone with collinear points (degenerate polygon)."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        # All points on a line
        zone.coordinates = [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]
        # This is essentially a line, not a polygon
        result = point_in_zone(0.5, 0.5, zone)
        assert isinstance(result, bool)

    def test_zone_covering_entire_image(self) -> None:
        """Test zone that covers the entire normalized space."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        zone.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        # Any point should be inside
        assert point_in_zone(0.5, 0.5, zone) is True
        assert point_in_zone(0.01, 0.01, zone) is True
        assert point_in_zone(0.99, 0.99, zone) is True

    def test_very_long_thin_zone(self) -> None:
        """Test very thin rectangular zone."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        # Very thin horizontal strip
        zone.coordinates = [[0.0, 0.499], [1.0, 0.499], [1.0, 0.501], [0.0, 0.501]]
        assert point_in_zone(0.5, 0.5, zone) is True
        assert point_in_zone(0.5, 0.4, zone) is False
        assert point_in_zone(0.5, 0.6, zone) is False

    def test_large_number_of_vertices(self) -> None:
        """Test polygon with many vertices (approximating a circle)."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        # Create a polygon approximating a circle

        n_vertices = 36
        radius = 0.3
        center = (0.5, 0.5)
        coordinates = []
        for i in range(n_vertices):
            angle = 2 * math.pi * i / n_vertices
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            coordinates.append([x, y])
        zone.coordinates = coordinates

        # Center should be inside
        assert point_in_zone(0.5, 0.5, zone) is True
        # Far outside should be outside
        assert point_in_zone(0.0, 0.0, zone) is False
        assert point_in_zone(1.0, 1.0, zone) is False

    def test_float_precision_boundary(self) -> None:
        """Test with float precision issues near boundary."""
        zone = MagicMock(spec=Zone)
        zone.enabled = True
        zone.coordinates = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]
        # Point very close to boundary
        result = point_in_zone(0.1 + 1e-10, 0.15, zone)
        assert isinstance(result, bool)

    def test_direction_degrees_wrapping(self, rectangle_zone: Zone) -> None:
        """Test direction calculation wraps correctly around 360 degrees."""
        now = datetime.now(UTC)
        # Move purely upward (negative y change in image coordinates)
        detections = [
            make_detection(
                bbox_x=500, bbox_y=600, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=500,
                bbox_y=400,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=2),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        # Moving up should be approximately 0 degrees
        assert result.direction_degrees < 10 or result.direction_degrees > 350

    def test_stationary_detection(self, rectangle_zone: Zone) -> None:
        """Test approach vector with stationary detection (no movement)."""
        now = datetime.now(UTC)
        # Both detections at same position
        detections = [
            make_detection(
                bbox_x=500, bbox_y=500, bbox_width=100, bbox_height=100, detected_at=now
            ),
            make_detection(
                bbox_x=500,
                bbox_y=500,
                bbox_width=100,
                bbox_height=100,
                detected_at=now + timedelta(seconds=2),
            ),
        ]
        result = calculate_approach_vector(detections, rectangle_zone, 1920, 1080)
        assert result is not None
        assert result.speed_normalized == 0.0
        # When stationary, not approaching
        assert result.is_approaching is False
