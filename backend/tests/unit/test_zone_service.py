"""Unit tests for zone service utility functions.

Tests cover:
- point_in_zone: Check if a point is inside a zone
- bbox_center: Calculate normalized center of a bounding box
- detection_in_zone: Check if a detection is inside a zone
- get_highest_priority_zone: Get the highest priority zone from a list
- zones_to_context: Convert zones to a context dictionary
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.models.zone import Zone, ZoneShape, ZoneType
from backend.services.zone_service import (
    bbox_center,
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
