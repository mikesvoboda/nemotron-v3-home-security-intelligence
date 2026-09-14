"""Unit tests for CameraZone model.

Tests cover:
- Model instantiation with valid data
- Field validation and constraints
- Default values
- Relationship navigation
- String representation (__repr__)
- CheckConstraints for priority and color
- Enum values for zone type and shape
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid zone types
zone_types = st.sampled_from([e.value for e in CameraZoneType])

# Strategy for valid zone shapes
zone_shapes = st.sampled_from([e.value for e in CameraZoneShape])

# Strategy for valid hex colors
hex_colors = st.from_regex(r"^#[0-9A-Fa-f]{6}$", fullmatch=True)

# Strategy for valid priority values
priorities = st.integers(min_value=0, max_value=100)


# =============================================================================
# CameraZone Model Tests
# =============================================================================


class TestCameraZoneModel:
    """Tests for CameraZone model."""

    def test_camera_zone_creation_minimal(self):
        """Test creating a camera zone with required fields."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Driveway",
            coordinates=[[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        )
        assert zone.id == "zone_1"
        assert zone.camera_id == "cam1"
        assert zone.name == "Driveway"
        assert len(zone.coordinates) == 4
        # Defaults apply at DB level, not in-memory
        assert zone.zone_type in (None, CameraZoneType.OTHER)
        assert zone.shape in (None, CameraZoneShape.RECTANGLE)
        assert zone.color in (None, "#3B82F6")
        assert zone.enabled in (None, True)
        assert zone.priority in (None, 0)

    def test_camera_zone_creation_full(self):
        """Test creating a camera zone with all fields."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Front Entry",
            zone_type=CameraZoneType.ENTRY_POINT,
            coordinates=[[0.2, 0.3], [0.5, 0.3], [0.5, 0.7], [0.2, 0.7]],
            shape=CameraZoneShape.RECTANGLE,
            color="#EF4444",
            enabled=True,
            priority=10,
        )
        assert zone.id == "zone_1"
        assert zone.camera_id == "cam1"
        assert zone.name == "Front Entry"
        assert zone.zone_type == CameraZoneType.ENTRY_POINT
        assert len(zone.coordinates) == 4
        assert zone.shape == CameraZoneShape.RECTANGLE
        assert zone.color == "#EF4444"
        assert zone.enabled is True
        assert zone.priority == 10

    def test_camera_zone_default_zone_type(self):
        """Test zone_type has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        zone_type_col = mapper.columns["zone_type"]
        assert zone_type_col.default is not None
        assert zone_type_col.default.arg == CameraZoneType.OTHER

    def test_camera_zone_default_shape(self):
        """Test shape has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        shape_col = mapper.columns["shape"]
        assert shape_col.default is not None
        assert shape_col.default.arg == CameraZoneShape.RECTANGLE

    def test_camera_zone_default_color(self):
        """Test color has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        color_col = mapper.columns["color"]
        assert color_col.default is not None
        assert color_col.default.arg == "#3B82F6"

    def test_camera_zone_default_enabled(self):
        """Test enabled has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

    def test_camera_zone_default_priority(self):
        """Test priority has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        priority_col = mapper.columns["priority"]
        assert priority_col.default is not None
        assert priority_col.default.arg == 0

    def test_camera_zone_repr(self):
        """Test CameraZone __repr__ method."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Driveway",
            zone_type=CameraZoneType.DRIVEWAY,
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        repr_str = repr(zone)
        assert "CameraZone" in repr_str
        assert "id='zone_1'" in repr_str
        assert "camera_id='cam1'" in repr_str
        assert "name='Driveway'" in repr_str
        assert (
            "zone_type=<CameraZoneType.DRIVEWAY:" in repr_str or "zone_type='driveway'" in repr_str
        )

    def test_camera_zone_has_camera_relationship(self):
        """Test CameraZone has camera relationship defined."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        assert hasattr(zone, "camera")

    def test_camera_zone_has_household_config_relationship(self):
        """Test CameraZone has household_config relationship defined."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        assert hasattr(zone, "household_config")

    def test_camera_zone_has_activity_baseline_relationship(self):
        """Test CameraZone has activity_baseline relationship defined."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        assert hasattr(zone, "activity_baseline")

    def test_camera_zone_has_anomalies_relationship(self):
        """Test CameraZone has anomalies relationship defined."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        assert hasattr(zone, "anomalies")

    def test_camera_zone_tablename(self):
        """Test CameraZone has correct table name."""
        assert CameraZone.__tablename__ == "camera_zones"

    def test_camera_zone_has_indexes(self):
        """Test CameraZone has expected indexes."""
        indexes = CameraZone.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_camera_zones_camera_id" in index_names
        assert "idx_camera_zones_enabled" in index_names
        assert "idx_camera_zones_camera_enabled" in index_names


# =============================================================================
# CameraZone Enum Tests
# =============================================================================


class TestCameraZoneEnums:
    """Tests for CameraZone enum classes."""

    def test_camera_zone_type_enum_values(self):
        """Test CameraZoneType enum has expected values."""
        assert CameraZoneType.ENTRY_POINT.value == "entry_point"
        assert CameraZoneType.DRIVEWAY.value == "driveway"
        assert CameraZoneType.SIDEWALK.value == "sidewalk"
        assert CameraZoneType.YARD.value == "yard"
        assert CameraZoneType.OTHER.value == "other"

    def test_camera_zone_shape_enum_values(self):
        """Test CameraZoneShape enum has expected values."""
        assert CameraZoneShape.RECTANGLE.value == "rectangle"
        assert CameraZoneShape.POLYGON.value == "polygon"

    def test_camera_zone_type_is_string_enum(self):
        """Test CameraZoneType inherits from str."""
        assert isinstance(CameraZoneType.ENTRY_POINT, str)

    def test_camera_zone_shape_is_string_enum(self):
        """Test CameraZoneShape inherits from str."""
        assert isinstance(CameraZoneShape.RECTANGLE, str)


# =============================================================================
# CameraZone Type-Specific Tests
# =============================================================================


class TestCameraZoneTypes:
    """Tests for different camera zone types."""

    def test_entry_point_zone(self):
        """Test creating an entry point zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Front Door",
            zone_type=CameraZoneType.ENTRY_POINT,
            coordinates=[[0.4, 0.3], [0.6, 0.3], [0.6, 0.7], [0.4, 0.7]],
            color="#EF4444",  # Red for entry points
            priority=10,
        )
        assert zone.zone_type == CameraZoneType.ENTRY_POINT
        assert zone.color == "#EF4444"
        assert zone.priority == 10

    def test_driveway_zone(self):
        """Test creating a driveway zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Driveway",
            zone_type=CameraZoneType.DRIVEWAY,
            coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            color="#F59E0B",  # Orange for driveways
            priority=5,
        )
        assert zone.zone_type == CameraZoneType.DRIVEWAY
        assert zone.color == "#F59E0B"

    def test_sidewalk_zone(self):
        """Test creating a sidewalk zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Sidewalk",
            zone_type=CameraZoneType.SIDEWALK,
            coordinates=[[0.0, 0.8], [1.0, 0.8], [1.0, 1.0], [0.0, 1.0]],
            color="#10B981",  # Green for sidewalks
            priority=1,
        )
        assert zone.zone_type == CameraZoneType.SIDEWALK
        assert zone.color == "#10B981"

    def test_yard_zone(self):
        """Test creating a yard zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Front Yard",
            zone_type=CameraZoneType.YARD,
            coordinates=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            priority=2,
        )
        assert zone.zone_type == CameraZoneType.YARD


# =============================================================================
# CameraZone Shape Tests
# =============================================================================


class TestCameraZoneShapes:
    """Tests for different camera zone shapes."""

    def test_rectangle_zone(self):
        """Test creating a rectangular zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Rectangle Zone",
            shape=CameraZoneShape.RECTANGLE,
            coordinates=[[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        )
        assert zone.shape == CameraZoneShape.RECTANGLE
        assert len(zone.coordinates) == 4

    def test_polygon_zone(self):
        """Test creating a polygonal zone."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Polygon Zone",
            shape=CameraZoneShape.POLYGON,
            coordinates=[
                [0.2, 0.1],
                [0.5, 0.1],
                [0.6, 0.5],
                [0.4, 0.9],
                [0.1, 0.6],
            ],
        )
        assert zone.shape == CameraZoneShape.POLYGON
        assert len(zone.coordinates) == 5


# =============================================================================
# CameraZone Normalized Coordinates Tests
# =============================================================================


class TestCameraZoneCoordinates:
    """Tests for camera zone normalized coordinates."""

    def test_coordinates_normalized_range(self):
        """Test coordinates are in normalized 0-1 range."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        )
        for point in zone.coordinates:
            assert 0.0 <= point[0] <= 1.0
            assert 0.0 <= point[1] <= 1.0

    def test_coordinates_stored_as_json(self):
        """Test coordinates are stored as JSONB."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.4]],
        )
        assert isinstance(zone.coordinates, list)
        assert isinstance(zone.coordinates[0], list)


# =============================================================================
# CameraZone Disabled/Enabled Tests
# =============================================================================


class TestCameraZoneEnabled:
    """Tests for camera zone enabled/disabled state."""

    def test_zone_enabled_by_default(self):
        """Test zone enabled has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(CameraZone)
        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

    def test_zone_can_be_disabled(self):
        """Test zone can be explicitly disabled."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
            enabled=False,
        )
        assert zone.enabled is False


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestCameraZoneProperties:
    """Property-based tests for CameraZone model."""

    @given(zone_type=zone_types, zone_shape=zone_shapes)
    @settings(max_examples=20)
    def test_zone_type_shape_roundtrip(self, zone_type: str, zone_shape: str):
        """Property: Zone type and shape values roundtrip correctly."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Test Zone",
            zone_type=zone_type,
            shape=zone_shape,
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
        )
        # zone_type and shape are enum instances that compare equal to their string values
        assert zone.zone_type == zone_type
        assert zone.shape == zone_shape

    @given(color=hex_colors)
    @settings(max_examples=30)
    def test_color_roundtrip(self, color: str):
        """Property: Color values roundtrip correctly."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Test Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
            color=color,
        )
        assert zone.color == color

    @given(priority=priorities)
    @settings(max_examples=30)
    def test_priority_roundtrip(self, priority: int):
        """Property: Priority values roundtrip correctly."""
        zone = CameraZone(
            id="zone_1",
            camera_id="cam1",
            name="Test Zone",
            coordinates=[[0.1, 0.2], [0.3, 0.8]],
            priority=priority,
        )
        assert zone.priority == priority


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestCameraZoneBackwardCompatibility:
    """Tests for backward compatibility with Zone alias."""

    def test_zone_alias_exists(self):
        """Test Zone alias exists for backward compatibility."""
        from backend.models.camera_zone import Zone

        assert Zone is CameraZone

    def test_zone_type_alias_exists(self):
        """Test ZoneType alias exists for backward compatibility."""
        from backend.models.camera_zone import ZoneType

        assert ZoneType is CameraZoneType

    def test_zone_shape_alias_exists(self):
        """Test ZoneShape alias exists for backward compatibility."""
        from backend.models.camera_zone import ZoneShape

        assert ZoneShape is CameraZoneShape
