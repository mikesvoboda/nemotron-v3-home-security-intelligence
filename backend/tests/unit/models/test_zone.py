"""Unit tests for Zone model and related enums.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- ZoneType and ZoneShape enums
- Coordinates field (JSONB)
- Property-based tests for field values
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType
from backend.tests.factories import ZoneFactory

# Aliases for backward compatibility
Zone = CameraZone
ZoneShape = CameraZoneShape
ZoneType = CameraZoneType

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid zone types
zone_types = st.sampled_from(list(ZoneType))

# Strategy for valid zone shapes
zone_shapes = st.sampled_from(list(ZoneShape))

# Strategy for valid hex color codes
hex_colors = st.from_regex(r"#[0-9A-Fa-f]{6}", fullmatch=True)

# Strategy for priority values
priorities = st.integers(min_value=-100, max_value=100)

# Strategy for normalized coordinates (0-1 range)
normalized_coords = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for coordinate points
coordinate_points = st.lists(
    st.lists(normalized_coords, min_size=2, max_size=2), min_size=3, max_size=10
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_zone():
    """Create a sample zone for testing using factory."""
    return ZoneFactory(
        id="zone_001",
        camera_id="front_door",
        name="Driveway",
        zone_type=ZoneType.DRIVEWAY,
        shape=ZoneShape.RECTANGLE,
        color="#3B82F6",
        priority=1,
    )


@pytest.fixture
def polygon_zone():
    """Create a polygon zone for testing using factory."""
    return ZoneFactory(
        id="zone_002",
        camera_id="back_yard",
        name="Garden Path",
        yard=True,  # Use factory trait
        polygon=True,  # Use factory trait for polygon shape
        color="#10B981",
        priority=2,
    )


@pytest.fixture
def minimal_zone():
    """Create a zone with minimal required fields using factory."""
    return ZoneFactory(
        id="zone_min",
        camera_id="test_cam",
        name="Test Zone",
        coordinates=[[0, 0], [1, 0], [1, 1], [0, 1]],
    )


@pytest.fixture
def disabled_zone():
    """Create a disabled zone using factory."""
    return ZoneFactory(
        id="zone_disabled",
        camera_id="test_cam",
        name="Disabled Zone",
        disabled=True,  # Use factory trait
        coordinates=[[0, 0], [1, 0], [1, 1], [0, 1]],
    )


# =============================================================================
# ZoneType Enum Tests
# =============================================================================


class TestZoneTypeEnum:
    """Tests for ZoneType enum."""

    def test_zone_type_entry_point(self):
        """Test ENTRY_POINT zone type."""
        assert ZoneType.ENTRY_POINT.value == "entry_point"

    def test_zone_type_driveway(self):
        """Test DRIVEWAY zone type."""
        assert ZoneType.DRIVEWAY.value == "driveway"

    def test_zone_type_sidewalk(self):
        """Test SIDEWALK zone type."""
        assert ZoneType.SIDEWALK.value == "sidewalk"

    def test_zone_type_yard(self):
        """Test YARD zone type."""
        assert ZoneType.YARD.value == "yard"

    def test_zone_type_other(self):
        """Test OTHER zone type."""
        assert ZoneType.OTHER.value == "other"

    def test_zone_type_is_string_enum(self):
        """Test ZoneType is a string enum."""
        for zone_type in ZoneType:
            assert isinstance(zone_type, str)
            assert isinstance(zone_type.value, str)

    def test_zone_type_count(self):
        """Test ZoneType has expected number of values."""
        assert len(ZoneType) == 5


# =============================================================================
# ZoneShape Enum Tests
# =============================================================================


class TestZoneShapeEnum:
    """Tests for ZoneShape enum."""

    def test_zone_shape_rectangle(self):
        """Test RECTANGLE zone shape."""
        assert ZoneShape.RECTANGLE.value == "rectangle"

    def test_zone_shape_polygon(self):
        """Test POLYGON zone shape."""
        assert ZoneShape.POLYGON.value == "polygon"

    def test_zone_shape_is_string_enum(self):
        """Test ZoneShape is a string enum."""
        for shape in ZoneShape:
            assert isinstance(shape, str)
            assert isinstance(shape.value, str)

    def test_zone_shape_count(self):
        """Test ZoneShape has expected number of values."""
        assert len(ZoneShape) == 2


# =============================================================================
# Zone Model Initialization Tests
# =============================================================================


class TestZoneModelInitialization:
    """Tests for Zone model initialization."""

    def test_zone_creation_minimal(self):
        """Test creating a zone with minimal required fields."""
        zone = Zone(
            id="test_zone",
            camera_id="test_cam",
            name="Test Zone",
            coordinates=[[0, 0], [1, 0], [1, 1], [0, 1]],
        )

        assert zone.id == "test_zone"
        assert zone.camera_id == "test_cam"
        assert zone.name == "Test Zone"
        assert zone.coordinates == [[0, 0], [1, 0], [1, 1], [0, 1]]

    def test_zone_with_all_fields(self, sample_zone):
        """Test zone with all fields populated."""
        assert sample_zone.id == "zone_001"
        assert sample_zone.camera_id == "front_door"
        assert sample_zone.name == "Driveway"
        assert sample_zone.zone_type == ZoneType.DRIVEWAY
        assert sample_zone.shape == ZoneShape.RECTANGLE
        assert sample_zone.color == "#3B82F6"
        assert sample_zone.enabled is True
        assert sample_zone.priority == 1

    def test_zone_default_type_column_definition(self):
        """Test that zone_type column has OTHER as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Zone)
        zone_type_col = mapper.columns["zone_type"]
        assert zone_type_col.default is not None
        assert zone_type_col.default.arg == ZoneType.OTHER

    def test_zone_default_shape_column_definition(self):
        """Test that shape column has RECTANGLE as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Zone)
        shape_col = mapper.columns["shape"]
        assert shape_col.default is not None
        assert shape_col.default.arg == ZoneShape.RECTANGLE

    def test_zone_default_color_column_definition(self):
        """Test that color column has blue as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Zone)
        color_col = mapper.columns["color"]
        assert color_col.default is not None
        assert color_col.default.arg == "#3B82F6"

    def test_zone_default_enabled_column_definition(self):
        """Test that enabled column has True as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Zone)
        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

    def test_zone_default_priority_column_definition(self):
        """Test that priority column has 0 as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(Zone)
        priority_col = mapper.columns["priority"]
        assert priority_col.default is not None
        assert priority_col.default.arg == 0


# =============================================================================
# Zone Field Tests
# =============================================================================


class TestZoneCoordinates:
    """Tests for Zone coordinates field."""

    def test_zone_rectangle_coordinates(self, sample_zone):
        """Test zone with rectangle coordinates."""
        coords = sample_zone.coordinates
        assert len(coords) == 4
        assert coords[0] == [0.1, 0.2]
        assert coords[1] == [0.3, 0.2]
        assert coords[2] == [0.3, 0.8]
        assert coords[3] == [0.1, 0.8]

    def test_zone_polygon_coordinates(self, polygon_zone):
        """Test zone with polygon coordinates."""
        coords = polygon_zone.coordinates
        assert len(coords) == 5
        assert coords[0] == [0.2, 0.1]

    def test_zone_coordinates_normalized(self):
        """Test coordinates are in 0-1 range."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        )
        for point in zone.coordinates:
            assert 0.0 <= point[0] <= 1.0
            assert 0.0 <= point[1] <= 1.0

    def test_zone_coordinates_can_be_empty_list(self):
        """Test coordinates can technically be empty (validation elsewhere)."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[],
        )
        assert zone.coordinates == []


class TestZoneColor:
    """Tests for Zone color field."""

    def test_zone_color_explicit(self, sample_zone):
        """Test explicit color value."""
        assert sample_zone.color == "#3B82F6"

    def test_zone_color_custom(self):
        """Test custom color."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            color="#FF5733",
        )
        assert zone.color == "#FF5733"

    def test_zone_color_lowercase(self):
        """Test color with lowercase hex."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            color="#abc123",
        )
        assert zone.color == "#abc123"


class TestZoneEnabled:
    """Tests for Zone enabled field."""

    def test_zone_enabled_explicit(self, sample_zone):
        """Test zone with explicit enabled=True."""
        assert sample_zone.enabled is True

    def test_zone_can_be_disabled(self, disabled_zone):
        """Test zone can be disabled."""
        assert disabled_zone.enabled is False


class TestZonePriority:
    """Tests for Zone priority field."""

    def test_zone_priority_explicit_zero(self):
        """Test zone with explicit priority=0."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            priority=0,
        )
        assert zone.priority == 0

    def test_zone_priority_positive(self, sample_zone):
        """Test zone with positive priority."""
        assert sample_zone.priority == 1

    def test_zone_priority_negative(self):
        """Test zone with negative priority."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            priority=-5,
        )
        assert zone.priority == -5


class TestZoneTimestamps:
    """Tests for Zone timestamp fields."""

    def test_zone_has_created_at(self, sample_zone):
        """Test zone has created_at field."""
        assert hasattr(sample_zone, "created_at")

    def test_zone_has_updated_at(self, sample_zone):
        """Test zone has updated_at field."""
        assert hasattr(sample_zone, "updated_at")


# =============================================================================
# Zone Repr Tests
# =============================================================================


class TestZoneRepr:
    """Tests for Zone string representation."""

    def test_zone_repr_contains_class_name(self, sample_zone):
        """Test repr contains class name."""
        repr_str = repr(sample_zone)
        assert "CameraZone" in repr_str

    def test_zone_repr_contains_id(self, sample_zone):
        """Test repr contains zone id."""
        repr_str = repr(sample_zone)
        assert "zone_001" in repr_str

    def test_zone_repr_contains_camera_id(self, sample_zone):
        """Test repr contains camera_id."""
        repr_str = repr(sample_zone)
        assert "front_door" in repr_str

    def test_zone_repr_contains_name(self, sample_zone):
        """Test repr contains zone name."""
        repr_str = repr(sample_zone)
        assert "Driveway" in repr_str

    def test_zone_repr_contains_zone_type(self, sample_zone):
        """Test repr contains zone_type."""
        repr_str = repr(sample_zone)
        # Zone type value or enum should be present
        assert "driveway" in repr_str.lower()

    def test_zone_repr_format(self, sample_zone):
        """Test repr has expected format."""
        repr_str = repr(sample_zone)
        assert repr_str.startswith("<CameraZone(")
        assert repr_str.endswith(")>")


# =============================================================================
# Zone Relationship Tests
# =============================================================================


class TestZoneRelationships:
    """Tests for Zone relationship definitions."""

    def test_zone_has_camera_relationship(self, sample_zone):
        """Test zone has camera relationship defined."""
        assert hasattr(sample_zone, "camera")


# =============================================================================
# Zone Table Args Tests
# =============================================================================


class TestZoneTableArgs:
    """Tests for Zone table arguments (indexes)."""

    def test_zone_has_table_args(self):
        """Test Zone model has __table_args__."""
        assert hasattr(Zone, "__table_args__")

    def test_zone_tablename(self):
        """Test CameraZone has correct table name."""
        assert Zone.__tablename__ == "camera_zones"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestZoneProperties:
    """Property-based tests for Zone model."""

    @given(zone_type=zone_types)
    @settings(max_examples=10)
    def test_zone_type_roundtrip(self, zone_type: ZoneType):
        """Property: Zone type values roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            zone_type=zone_type,
        )
        assert zone.zone_type == zone_type

    @given(shape=zone_shapes)
    @settings(max_examples=10)
    def test_zone_shape_roundtrip(self, shape: ZoneShape):
        """Property: Zone shape values roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            shape=shape,
        )
        assert zone.shape == shape

    @given(color=hex_colors)
    @settings(max_examples=30)
    def test_zone_color_roundtrip(self, color: str):
        """Property: Color values roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            color=color,
        )
        assert zone.color == color

    @given(priority=priorities)
    @settings(max_examples=30)
    def test_zone_priority_roundtrip(self, priority: int):
        """Property: Priority values roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            priority=priority,
        )
        assert zone.priority == priority

    @given(enabled=st.booleans())
    @settings(max_examples=10)
    def test_zone_enabled_roundtrip(self, enabled: bool):
        """Property: Enabled values roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=[[0, 0], [1, 0], [1, 1]],
            enabled=enabled,
        )
        assert zone.enabled == enabled

    @given(coordinates=coordinate_points)
    @settings(max_examples=50)
    def test_zone_coordinates_roundtrip(self, coordinates: list):
        """Property: Coordinates roundtrip correctly."""
        zone = Zone(
            id="test",
            camera_id="cam",
            name="Test",
            coordinates=coordinates,
        )
        assert zone.coordinates == coordinates

    @given(
        zone_id=st.text(min_size=1, max_size=50),
        camera_id=st.text(min_size=1, max_size=50),
        name=st.text(min_size=1, max_size=255),
    )
    @settings(max_examples=50)
    def test_required_fields_roundtrip(self, zone_id: str, camera_id: str, name: str):
        """Property: Required fields roundtrip correctly."""
        zone = Zone(
            id=zone_id,
            camera_id=camera_id,
            name=name,
            coordinates=[[0, 0], [1, 0], [1, 1]],
        )
        assert zone.id == zone_id
        assert zone.camera_id == camera_id
        assert zone.name == name
