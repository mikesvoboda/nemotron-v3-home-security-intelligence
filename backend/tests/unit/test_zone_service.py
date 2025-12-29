"""Unit tests for zone service utility functions.

Tests cover:
- point_in_zone: Check if a point is inside a zone
- bbox_center: Calculate normalized center of a bounding box
- detection_in_zone: Check if a detection is inside a zone
- get_highest_priority_zone: Get the highest priority zone from a list
- zones_to_context: Convert zones to a context dictionary
- calculate_dwell_time: Track detection dwell time in zones
- detect_line_crossing: Detect zone entry events
- detect_line_exit: Detect zone exit events
- calculate_approach_vector: Calculate detection movement toward zones
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from backend.models.detection import Detection
from backend.models.zone import Zone, ZoneShape, ZoneType
from backend.services.zone_service import (
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
    """Create a rectangular zone for testing."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-1"
    zone.camera_id = "front_door"
    zone.name = "Front Door"
    zone.zone_type = ZoneType.ENTRY_POINT
    zone.coordinates = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
    zone.shape = ZoneShape.RECTANGLE
    zone.color = "#3B82F6"
    zone.enabled = True
    zone.priority = 1
    zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
    zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)
    return zone


@pytest.fixture
def polygon_zone() -> Zone:
    """Create a polygon zone for testing."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-2"
    zone.camera_id = "front_door"
    zone.name = "Driveway"
    zone.zone_type = ZoneType.DRIVEWAY
    # Triangle polygon
    zone.coordinates = [[0.5, 0.1], [0.9, 0.5], [0.5, 0.9]]
    zone.shape = ZoneShape.POLYGON
    zone.color = "#EF4444"
    zone.enabled = True
    zone.priority = 2
    zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
    zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)
    return zone


@pytest.fixture
def disabled_zone() -> Zone:
    """Create a disabled zone for testing."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-3"
    zone.camera_id = "front_door"
    zone.name = "Disabled Zone"
    zone.zone_type = ZoneType.OTHER
    zone.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    zone.shape = ZoneShape.RECTANGLE
    zone.color = "#6B7280"
    zone.enabled = False
    zone.priority = 0
    zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
    zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)
    return zone


# =============================================================================
# point_in_zone Tests
# =============================================================================


class TestPointInZone:
    """Tests for point_in_zone function."""

    def test_point_inside_rectangle(self, rectangle_zone: Zone) -> None:
        """Test that a point inside a rectangle returns True."""
        # Point at center of rectangle (0.25, 0.25) is inside
        assert point_in_zone(0.25, 0.25, rectangle_zone) is True

    def test_point_outside_rectangle(self, rectangle_zone: Zone) -> None:
        """Test that a point outside a rectangle returns False."""
        # Point (0.5, 0.5) is outside the rectangle
        assert point_in_zone(0.5, 0.5, rectangle_zone) is False

    def test_point_on_edge_rectangle(self, rectangle_zone: Zone) -> None:
        """Test point on edge of rectangle."""
        # Point on the edge may be inside or outside depending on algorithm
        # Ray casting typically considers points on horizontal edges as outside
        result = point_in_zone(0.1, 0.1, rectangle_zone)
        # We accept either True or False since edge cases are implementation-dependent
        assert isinstance(result, bool)

    def test_point_inside_polygon(self, polygon_zone: Zone) -> None:
        """Test that a point inside a triangle polygon returns True."""
        # Point approximately at center of triangle
        assert point_in_zone(0.6, 0.5, polygon_zone) is True

    def test_point_outside_polygon(self, polygon_zone: Zone) -> None:
        """Test that a point outside a triangle polygon returns False."""
        # Point (0.1, 0.5) is outside the triangle
        assert point_in_zone(0.1, 0.5, polygon_zone) is False

    def test_point_in_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test that point_in_zone returns False for disabled zones."""
        # Even though point (0.5, 0.5) is inside, zone is disabled
        assert point_in_zone(0.5, 0.5, disabled_zone) is False

    def test_point_in_zone_empty_coordinates(self, rectangle_zone: Zone) -> None:
        """Test that empty coordinates returns False."""
        rectangle_zone.coordinates = []
        assert point_in_zone(0.5, 0.5, rectangle_zone) is False

    def test_point_in_zone_insufficient_coordinates(self, rectangle_zone: Zone) -> None:
        """Test that less than 3 coordinates returns False."""
        rectangle_zone.coordinates = [[0.0, 0.0], [1.0, 1.0]]  # Only 2 points
        assert point_in_zone(0.5, 0.5, rectangle_zone) is False

    def test_point_in_zone_boundary_values(self, rectangle_zone: Zone) -> None:
        """Test boundary values (0 and 1)."""
        # Create a zone covering the entire frame
        rectangle_zone.coordinates = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        # Point at center should be inside
        assert point_in_zone(0.5, 0.5, rectangle_zone) is True


# =============================================================================
# bbox_center Tests
# =============================================================================


class TestBboxCenter:
    """Tests for bbox_center function."""

    def test_bbox_center_standard(self) -> None:
        """Test center calculation for a standard bounding box."""
        # 100x100 bbox starting at (100, 100) on a 640x480 image
        x, y = bbox_center(100, 100, 100, 100, 640, 480)
        assert x == pytest.approx(0.234375, rel=1e-5)  # (100 + 50) / 640
        assert y == pytest.approx(0.3125, rel=1e-5)  # (100 + 50) / 480

    def test_bbox_center_at_origin(self) -> None:
        """Test center calculation for bbox at origin."""
        x, y = bbox_center(0, 0, 200, 200, 1000, 1000)
        assert x == pytest.approx(0.1, rel=1e-5)  # (0 + 100) / 1000
        assert y == pytest.approx(0.1, rel=1e-5)  # (0 + 100) / 1000

    def test_bbox_center_at_bottom_right(self) -> None:
        """Test center calculation for bbox at bottom right."""
        x, y = bbox_center(800, 600, 200, 200, 1000, 800)
        # Center x: (800 + 100) / 1000 = 0.9, but clamped to 1.0
        # Center y: (600 + 100) / 800 = 0.875
        assert x == pytest.approx(0.9, rel=1e-5)
        assert y == pytest.approx(0.875, rel=1e-5)

    def test_bbox_center_clamping(self) -> None:
        """Test that results are clamped to 0-1 range."""
        # Bbox extends beyond image bounds
        x, y = bbox_center(900, 700, 200, 200, 1000, 800)
        # Center would be (900 + 100) / 1000 = 1.0, (700 + 100) / 800 = 1.0
        assert x <= 1.0
        assert y <= 1.0
        assert x >= 0.0
        assert y >= 0.0

    def test_bbox_center_small_values(self) -> None:
        """Test with small bounding box."""
        x, y = bbox_center(10, 10, 10, 10, 100, 100)
        assert x == pytest.approx(0.15, rel=1e-5)  # (10 + 5) / 100
        assert y == pytest.approx(0.15, rel=1e-5)  # (10 + 5) / 100

    def test_bbox_center_invalid_dimensions(self) -> None:
        """Test that invalid image dimensions raise ValueError."""
        with pytest.raises(ValueError, match="positive"):
            bbox_center(10, 10, 10, 10, 0, 100)

        with pytest.raises(ValueError, match="positive"):
            bbox_center(10, 10, 10, 10, 100, 0)

        with pytest.raises(ValueError, match="positive"):
            bbox_center(10, 10, 10, 10, -100, 100)


# =============================================================================
# detection_in_zone Tests
# =============================================================================


class TestDetectionInZone:
    """Tests for detection_in_zone function."""

    def test_detection_inside_zone(self, rectangle_zone: Zone) -> None:
        """Test detection with center inside zone."""
        # Bbox center at (0.25, 0.25) which is inside the rectangle zone
        result = detection_in_zone(
            bbox_x=140,  # Results in center x = 160/640 = 0.25
            bbox_y=108,  # Results in center y = 120/480 = 0.25
            bbox_width=40,
            bbox_height=24,
            image_width=640,
            image_height=480,
            zone=rectangle_zone,
        )
        assert result is True

    def test_detection_outside_zone(self, rectangle_zone: Zone) -> None:
        """Test detection with center outside zone."""
        # Bbox center at (0.75, 0.75) which is outside the rectangle zone
        result = detection_in_zone(
            bbox_x=460,  # Results in center x = 480/640 = 0.75
            bbox_y=348,  # Results in center y = 360/480 = 0.75
            bbox_width=40,
            bbox_height=24,
            image_width=640,
            image_height=480,
            zone=rectangle_zone,
        )
        assert result is False

    def test_detection_disabled_zone(self, disabled_zone: Zone) -> None:
        """Test detection against disabled zone returns False."""
        result = detection_in_zone(
            bbox_x=300,
            bbox_y=220,
            bbox_width=40,
            bbox_height=40,
            image_width=640,
            image_height=480,
            zone=disabled_zone,
        )
        assert result is False


# =============================================================================
# get_highest_priority_zone Tests
# =============================================================================


class TestGetHighestPriorityZone:
    """Tests for get_highest_priority_zone function."""

    def test_single_zone(self, rectangle_zone: Zone) -> None:
        """Test with single zone."""
        result = get_highest_priority_zone([rectangle_zone])
        assert result == rectangle_zone

    def test_multiple_zones_different_priorities(
        self, rectangle_zone: Zone, polygon_zone: Zone
    ) -> None:
        """Test returns zone with highest priority."""
        # polygon_zone has priority 2, rectangle_zone has priority 1
        result = get_highest_priority_zone([rectangle_zone, polygon_zone])
        assert result == polygon_zone

    def test_empty_list(self) -> None:
        """Test with empty list returns None."""
        result = get_highest_priority_zone([])
        assert result is None

    def test_zones_same_priority(self) -> None:
        """Test with zones having same priority."""
        zone1 = MagicMock(spec=Zone)
        zone1.priority = 5
        zone2 = MagicMock(spec=Zone)
        zone2.priority = 5

        result = get_highest_priority_zone([zone1, zone2])
        # Should return one of them (max behavior)
        assert result in [zone1, zone2]


# =============================================================================
# zones_to_context Tests
# =============================================================================


class TestZonesToContext:
    """Tests for zones_to_context function."""

    def test_single_zone(self, rectangle_zone: Zone) -> None:
        """Test with single zone."""
        result = zones_to_context([rectangle_zone])
        assert "entry_point" in result
        assert "Front Door" in result["entry_point"]

    def test_multiple_zones_same_type(self) -> None:
        """Test with multiple zones of same type."""
        zone1 = MagicMock(spec=Zone)
        zone1.zone_type = ZoneType.DRIVEWAY
        zone1.name = "Main Driveway"

        zone2 = MagicMock(spec=Zone)
        zone2.zone_type = ZoneType.DRIVEWAY
        zone2.name = "Side Driveway"

        result = zones_to_context([zone1, zone2])
        assert "driveway" in result
        assert len(result["driveway"]) == 2
        assert "Main Driveway" in result["driveway"]
        assert "Side Driveway" in result["driveway"]

    def test_multiple_zones_different_types(self, rectangle_zone: Zone, polygon_zone: Zone) -> None:
        """Test with multiple zones of different types."""
        result = zones_to_context([rectangle_zone, polygon_zone])
        assert "entry_point" in result
        assert "driveway" in result
        assert "Front Door" in result["entry_point"]
        assert "Driveway" in result["driveway"]

    def test_empty_list(self) -> None:
        """Test with empty list returns empty dict."""
        result = zones_to_context([])
        assert result == {}

    def test_all_zone_types(self) -> None:
        """Test with all zone types."""
        zones = []
        for zone_type in ZoneType:
            zone = MagicMock(spec=Zone)
            zone.zone_type = zone_type
            zone.name = f"{zone_type.value} Zone"
            zones.append(zone)

        result = zones_to_context(zones)

        for zone_type in ZoneType:
            assert zone_type.value in result
            assert f"{zone_type.value} Zone" in result[zone_type.value]


# =============================================================================
# Spatial Heuristics Fixtures
# =============================================================================


def _create_detection_mock(
    bbox_x: int | None,
    bbox_y: int | None,
    bbox_width: int | None,
    bbox_height: int | None,
    detected_at: datetime,
) -> Detection:
    """Helper to create a mock Detection with bbox coordinates."""
    detection = MagicMock(spec=Detection)
    detection.bbox_x = bbox_x
    detection.bbox_y = bbox_y
    detection.bbox_width = bbox_width
    detection.bbox_height = bbox_height
    detection.detected_at = detected_at
    return detection


@pytest.fixture
def large_center_zone() -> Zone:
    """Create a zone in the center of the image for spatial heuristics tests."""
    zone = MagicMock(spec=Zone)
    zone.id = "zone-center"
    zone.camera_id = "front_door"
    zone.name = "Center Zone"
    zone.zone_type = ZoneType.ENTRY_POINT
    # Zone covering center area (0.3, 0.3) to (0.7, 0.7)
    zone.coordinates = [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]
    zone.shape = ZoneShape.RECTANGLE
    zone.color = "#3B82F6"
    zone.enabled = True
    zone.priority = 1
    zone.created_at = datetime(2025, 12, 23, 10, 0, 0)
    zone.updated_at = datetime(2025, 12, 23, 10, 0, 0)
    return zone


# =============================================================================
# calculate_dwell_time Tests
# =============================================================================


class TestCalculateDwellTime:
    """Tests for calculate_dwell_time function."""

    def test_empty_detections(self, large_center_zone: Zone) -> None:
        """Test with empty detections list."""
        result = calculate_dwell_time([], large_center_zone)
        assert result == 0.0

    def test_disabled_zone(self, large_center_zone: Zone) -> None:
        """Test with disabled zone."""
        large_center_zone.enabled = False
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(480, 270, 100, 100, base_time),  # In zone center
            _create_detection_mock(480, 270, 100, 100, base_time + timedelta(seconds=10)),
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        assert result == 0.0

    def test_single_detection(self, large_center_zone: Zone) -> None:
        """Test with single detection."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(480, 270, 100, 100, base_time),  # In zone center
        ]
        # Single detection can't have dwell time (no time span)
        result = calculate_dwell_time(detections, large_center_zone)
        assert result == 0.0

    def test_continuous_dwell_in_zone(self, large_center_zone: Zone) -> None:
        """Test continuous dwell time when object stays in zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Image: 1920x1080, zone center at (0.5, 0.5) = (960, 540)
        # Detections with center in zone (0.5, 0.5)
        detections = [
            _create_detection_mock(910, 490, 100, 100, base_time),  # Center: (960, 540)
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=5)),
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=10)),
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        assert result == pytest.approx(10.0, rel=1e-3)

    def test_partial_dwell_enters_leaves(self, large_center_zone: Zone) -> None:
        """Test dwell time when object enters and leaves zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Start outside (left side), enter zone, then leave (right side)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Outside (0.05, 0.5)
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=5)),  # Inside
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=10)),  # Inside
            _create_detection_mock(
                1770, 490, 100, 100, base_time + timedelta(seconds=15)
            ),  # Outside
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        # Dwell from t=5 to t=15 (when it leaves) = 10 seconds
        assert result == pytest.approx(10.0, rel=1e-3)

    def test_never_enters_zone(self, large_center_zone: Zone) -> None:
        """Test when object never enters zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # All detections outside zone (left edge)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Outside
            _create_detection_mock(100, 490, 100, 100, base_time + timedelta(seconds=5)),  # Outside
            _create_detection_mock(
                150, 490, 100, 100, base_time + timedelta(seconds=10)
            ),  # Outside
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        assert result == 0.0

    def test_multiple_enter_exit_cycles(self, large_center_zone: Zone) -> None:
        """Test with multiple enter/exit cycles."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Outside
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=5)),  # Inside
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=10)),  # Inside
            _create_detection_mock(50, 490, 100, 100, base_time + timedelta(seconds=15)),  # Outside
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=20)),  # Inside
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=25)),  # Inside
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        # First dwell: 5-15 = 10s, Second dwell: 20-25 = 5s
        assert result == pytest.approx(15.0, rel=1e-3)

    def test_detection_with_missing_bbox(self, large_center_zone: Zone) -> None:
        """Test with detections missing bbox coordinates."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(910, 490, 100, 100, base_time),  # Valid, in zone
            _create_detection_mock(
                None, None, None, None, base_time + timedelta(seconds=5)
            ),  # Invalid
            _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=10)),  # Valid
        ]
        result = calculate_dwell_time(detections, large_center_zone)
        # Should skip invalid detection and calculate time from first to last valid
        assert result == pytest.approx(10.0, rel=1e-3)


# =============================================================================
# detect_line_crossing Tests
# =============================================================================


class TestDetectLineCrossing:
    """Tests for detect_line_crossing function."""

    def test_crossing_into_zone(self, large_center_zone: Zone) -> None:
        """Test detection of crossing into zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)  # Outside
        curr = _create_detection_mock(
            910, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Inside

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is True

    def test_no_crossing_both_outside(self, large_center_zone: Zone) -> None:
        """Test when both detections are outside zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)  # Outside
        curr = _create_detection_mock(
            100, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Outside

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False

    def test_no_crossing_both_inside(self, large_center_zone: Zone) -> None:
        """Test when both detections are inside zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(910, 490, 100, 100, base_time)  # Inside
        curr = _create_detection_mock(
            920, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Inside

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False

    def test_no_crossing_exiting_zone(self, large_center_zone: Zone) -> None:
        """Test that exiting zone is not detected as crossing."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(910, 490, 100, 100, base_time)  # Inside
        curr = _create_detection_mock(
            50, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Outside

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False

    def test_disabled_zone(self, large_center_zone: Zone) -> None:
        """Test with disabled zone."""
        large_center_zone.enabled = False
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)  # Outside
        curr = _create_detection_mock(
            910, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Inside

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False

    def test_missing_prev_bbox(self, large_center_zone: Zone) -> None:
        """Test with missing bbox on previous detection."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(None, None, None, None, base_time)
        curr = _create_detection_mock(910, 490, 100, 100, base_time + timedelta(seconds=1))

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False

    def test_missing_curr_bbox(self, large_center_zone: Zone) -> None:
        """Test with missing bbox on current detection."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)
        curr = _create_detection_mock(None, None, None, None, base_time + timedelta(seconds=1))

        result = detect_line_crossing(prev, curr, large_center_zone)
        assert result is False


# =============================================================================
# detect_line_exit Tests
# =============================================================================


class TestDetectLineExit:
    """Tests for detect_line_exit function."""

    def test_exiting_zone(self, large_center_zone: Zone) -> None:
        """Test detection of exiting zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(910, 490, 100, 100, base_time)  # Inside
        curr = _create_detection_mock(
            50, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Outside

        result = detect_line_exit(prev, curr, large_center_zone)
        assert result is True

    def test_no_exit_both_outside(self, large_center_zone: Zone) -> None:
        """Test when both detections are outside zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)  # Outside
        curr = _create_detection_mock(
            100, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Outside

        result = detect_line_exit(prev, curr, large_center_zone)
        assert result is False

    def test_no_exit_both_inside(self, large_center_zone: Zone) -> None:
        """Test when both detections are inside zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(910, 490, 100, 100, base_time)  # Inside
        curr = _create_detection_mock(
            920, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Inside

        result = detect_line_exit(prev, curr, large_center_zone)
        assert result is False

    def test_no_exit_entering_zone(self, large_center_zone: Zone) -> None:
        """Test that entering zone is not detected as exit."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(50, 490, 100, 100, base_time)  # Outside
        curr = _create_detection_mock(
            910, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Inside

        result = detect_line_exit(prev, curr, large_center_zone)
        assert result is False

    def test_disabled_zone(self, large_center_zone: Zone) -> None:
        """Test with disabled zone."""
        large_center_zone.enabled = False
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        prev = _create_detection_mock(910, 490, 100, 100, base_time)  # Inside
        curr = _create_detection_mock(
            50, 490, 100, 100, base_time + timedelta(seconds=1)
        )  # Outside

        result = detect_line_exit(prev, curr, large_center_zone)
        assert result is False


# =============================================================================
# calculate_approach_vector Tests
# =============================================================================


class TestCalculateApproachVector:
    """Tests for calculate_approach_vector function."""

    def test_approaching_zone_from_left(self, large_center_zone: Zone) -> None:
        """Test detection approaching zone from left."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Move from left toward center zone
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Far left (0.05, 0.5)
            _create_detection_mock(250, 490, 100, 100, base_time + timedelta(seconds=5)),  # Closer
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        assert result.is_approaching is True
        # Direction should be roughly 90 degrees (moving right)
        assert 85 <= result.direction_degrees <= 95
        assert result.speed_normalized > 0
        assert result.distance_to_zone > 0

    def test_moving_away_from_zone(self, large_center_zone: Zone) -> None:
        """Test detection moving away from zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Move from near zone to far left
        detections = [
            _create_detection_mock(450, 490, 100, 100, base_time),  # Near zone
            _create_detection_mock(50, 490, 100, 100, base_time + timedelta(seconds=5)),  # Far left
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        assert result.is_approaching is False
        # Direction should be roughly 270 degrees (moving left)
        assert 265 <= result.direction_degrees <= 275

    def test_already_in_zone(self, large_center_zone: Zone) -> None:
        """Test when detection is already in zone."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Both detections inside zone
        detections = [
            _create_detection_mock(910, 490, 100, 100, base_time),  # Inside
            _create_detection_mock(920, 490, 100, 100, base_time + timedelta(seconds=5)),  # Inside
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        assert result.distance_to_zone == 0.0
        assert result.estimated_arrival_seconds == 0.0

    def test_empty_detections(self, large_center_zone: Zone) -> None:
        """Test with empty detections list."""
        result = calculate_approach_vector([], large_center_zone)
        assert result is None

    def test_single_detection(self, large_center_zone: Zone) -> None:
        """Test with single detection."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [_create_detection_mock(50, 490, 100, 100, base_time)]

        result = calculate_approach_vector(detections, large_center_zone)
        assert result is None

    def test_disabled_zone(self, large_center_zone: Zone) -> None:
        """Test with disabled zone."""
        large_center_zone.enabled = False
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),
            _create_detection_mock(250, 490, 100, 100, base_time + timedelta(seconds=5)),
        ]

        result = calculate_approach_vector(detections, large_center_zone)
        assert result is None

    def test_same_timestamp_detections(self, large_center_zone: Zone) -> None:
        """Test with same timestamp (zero time delta)."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),
            _create_detection_mock(250, 490, 100, 100, base_time),  # Same time
        ]

        result = calculate_approach_vector(detections, large_center_zone)
        assert result is None

    def test_movement_direction_up(self, large_center_zone: Zone) -> None:
        """Test movement direction calculation for upward movement."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Move from bottom to top (y decreases)
        detections = [
            _create_detection_mock(910, 900, 100, 100, base_time),  # Bottom
            _create_detection_mock(910, 100, 100, 100, base_time + timedelta(seconds=5)),  # Top
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        # Direction should be roughly 0 degrees (moving up)
        assert result.direction_degrees < 10 or result.direction_degrees > 350

    def test_movement_direction_down(self, large_center_zone: Zone) -> None:
        """Test movement direction calculation for downward movement."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Move from top to bottom (y increases)
        detections = [
            _create_detection_mock(910, 100, 100, 100, base_time),  # Top
            _create_detection_mock(910, 900, 100, 100, base_time + timedelta(seconds=5)),  # Bottom
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        # Direction should be roughly 180 degrees (moving down)
        assert 175 <= result.direction_degrees <= 185

    def test_estimated_arrival_calculation(self, large_center_zone: Zone) -> None:
        """Test estimated arrival time calculation."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # Move toward zone at a steady pace
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Far
            _create_detection_mock(200, 490, 100, 100, base_time + timedelta(seconds=10)),  # Closer
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        assert result.is_approaching is True
        assert result.estimated_arrival_seconds is not None
        assert result.estimated_arrival_seconds > 0

    def test_speed_calculation(self, large_center_zone: Zone) -> None:
        """Test speed calculation in normalized units."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        # 1920x1080 image, move 192 pixels in 1 second = 0.1 normalized units/sec
        detections = [
            _create_detection_mock(0, 490, 100, 100, base_time),  # x=0
            _create_detection_mock(192, 490, 100, 100, base_time + timedelta(seconds=1)),  # x=192
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        # Speed should be approximately 0.1 normalized units per second
        # (192 pixels / 1920 width = 0.1 normalized units)
        assert result.speed_normalized == pytest.approx(0.1, rel=0.1)

    def test_all_detections_missing_bbox(self, large_center_zone: Zone) -> None:
        """Test when all detections have missing bboxes."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(None, None, None, None, base_time),
            _create_detection_mock(None, None, None, None, base_time + timedelta(seconds=5)),
        ]

        result = calculate_approach_vector(detections, large_center_zone)
        assert result is None

    def test_mixed_valid_invalid_detections(self, large_center_zone: Zone) -> None:
        """Test with some valid and some invalid detections."""
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),  # Valid
            _create_detection_mock(
                None, None, None, None, base_time + timedelta(seconds=2)
            ),  # Invalid
            _create_detection_mock(
                None, None, None, None, base_time + timedelta(seconds=4)
            ),  # Invalid
            _create_detection_mock(250, 490, 100, 100, base_time + timedelta(seconds=6)),  # Valid
        ]

        result = calculate_approach_vector(detections, large_center_zone)

        assert result is not None
        # Should calculate from first valid to last valid
        assert result.is_approaching is True

    def test_zone_with_insufficient_coordinates(self, large_center_zone: Zone) -> None:
        """Test with zone having insufficient coordinates."""
        large_center_zone.coordinates = [[0.5, 0.5]]  # Only 1 point
        base_time = datetime(2025, 12, 23, 12, 0, 0)
        detections = [
            _create_detection_mock(50, 490, 100, 100, base_time),
            _create_detection_mock(250, 490, 100, 100, base_time + timedelta(seconds=5)),
        ]

        result = calculate_approach_vector(detections, large_center_zone)
        assert result is None
