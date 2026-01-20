"""Unit tests for Area model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Relationship definitions
- Table name and structure
- Foreign key constraints
- Many-to-many relationship with Camera via camera_areas

Implements TDD for NEM-3129: Phase 5.2 - Create Property and Area models.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import inspect

from backend.models.area import Area, camera_areas
from backend.models.camera import Camera
from backend.models.property import Property
from backend.tests.factories import AreaFactory, CameraFactory, PropertyFactory

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for area names
area_names = st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",)))

# Strategy for descriptions
descriptions = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=1000, alphabet=st.characters(blacklist_categories=("Cs",))),
)

# Strategy for hex colors
hex_colors = st.from_regex(r"^#[0-9A-Fa-f]{6}$", fullmatch=True)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_area():
    """Create a sample area for testing."""
    return AreaFactory(
        id=1,
        property_id=1,
        name="Front Yard",
        description="Main entrance and lawn area",
        color="#10B981",
    )


@pytest.fixture
def sample_property():
    """Create a sample property for testing."""
    return PropertyFactory(id=1, household_id=1, name="Main House")


# =============================================================================
# Area Model Initialization Tests
# =============================================================================


class TestAreaInitialization:
    """Tests for Area model initialization."""

    def test_area_creation_minimal(self):
        """Test creating an area with minimal required fields."""
        area = Area(
            id=1,
            property_id=1,
            name="Test Area",
        )

        assert area.id == 1
        assert area.property_id == 1
        assert area.name == "Test Area"

    def test_area_with_factory(self, sample_area):
        """Test area created via factory."""
        assert sample_area.id == 1
        assert sample_area.property_id == 1
        assert sample_area.name == "Front Yard"
        assert sample_area.description == "Main entrance and lawn area"
        assert sample_area.color == "#10B981"

    def test_area_has_created_at(self, sample_area):
        """Test area has created_at field."""
        assert hasattr(sample_area, "created_at")

    def test_area_default_color(self):
        """Test area color field has default in model definition.

        Note: SQLAlchemy defaults are applied at insert time, not object creation.
        The model definition has default="#76B900" which will be used when inserting.
        At unit test time without database, we verify the field exists and is settable.
        """
        area = Area(id=1, property_id=1, name="Default Test", color="#76B900")
        assert area.color == "#76B900"  # NVIDIA green

    def test_area_nullable_description(self):
        """Test area with null description."""
        area = Area(
            id=1,
            property_id=1,
            name="No Description Area",
            description=None,
        )
        assert area.description is None


# =============================================================================
# Area Field Tests
# =============================================================================


class TestAreaFields:
    """Tests for Area fields."""

    def test_area_name_max_length(self):
        """Test name field accepts max length value."""
        long_name = "A" * 100
        area = Area(id=1, property_id=1, name=long_name)
        assert len(area.name) == 100

    def test_area_name_can_be_short(self):
        """Test name field accepts short values."""
        area = Area(id=1, property_id=1, name="A")
        assert area.name == "A"

    def test_area_color_format(self):
        """Test color field accepts hex format."""
        area = Area(id=1, property_id=1, name="Test", color="#FF5733")
        assert area.color == "#FF5733"

    def test_area_color_length(self):
        """Test color field is correct length (7 chars including #)."""
        area = Area(id=1, property_id=1, name="Test", color="#ABCDEF")
        assert len(area.color) == 7

    def test_area_id_is_integer(self, sample_area):
        """Test id is an integer."""
        assert isinstance(sample_area.id, int)

    def test_area_property_id_is_integer(self, sample_area):
        """Test property_id is an integer."""
        assert isinstance(sample_area.property_id, int)

    def test_area_name_is_string(self, sample_area):
        """Test name is a string."""
        assert isinstance(sample_area.name, str)

    def test_area_color_is_string(self, sample_area):
        """Test color is a string."""
        assert isinstance(sample_area.color, str)


# =============================================================================
# Area Repr Tests
# =============================================================================


class TestAreaRepr:
    """Tests for Area string representation."""

    def test_area_repr_contains_class_name(self, sample_area):
        """Test repr contains class name."""
        repr_str = repr(sample_area)
        assert "Area" in repr_str

    def test_area_repr_contains_id(self, sample_area):
        """Test repr contains area id."""
        repr_str = repr(sample_area)
        assert "id=1" in repr_str

    def test_area_repr_contains_name(self, sample_area):
        """Test repr contains area name."""
        repr_str = repr(sample_area)
        assert "Front Yard" in repr_str

    def test_area_repr_contains_property_id(self, sample_area):
        """Test repr contains property_id."""
        repr_str = repr(sample_area)
        assert "property_id=1" in repr_str

    def test_area_repr_format(self, sample_area):
        """Test repr has expected format."""
        repr_str = repr(sample_area)
        assert repr_str.startswith("<Area(")
        assert repr_str.endswith(")>")


# =============================================================================
# Area Relationship Tests
# =============================================================================


class TestAreaRelationships:
    """Tests for Area relationship definitions."""

    def test_area_has_property_relationship(self, sample_area):
        """Test area has property relationship defined."""
        assert hasattr(sample_area, "property")

    def test_area_has_cameras_relationship(self, sample_area):
        """Test area has cameras relationship defined."""
        assert hasattr(sample_area, "cameras")

    def test_area_property_relationship_type(self):
        """Test property relationship is correctly typed."""
        mapper = inspect(Area)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "property" in relationships
        assert relationships["property"].direction.name == "MANYTOONE"

    def test_area_cameras_relationship_type(self):
        """Test cameras relationship is correctly typed (many-to-many)."""
        mapper = inspect(Area)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "cameras" in relationships
        # Many-to-many relationships are represented as MANYTOMANY in SQLAlchemy
        assert relationships["cameras"].direction.name == "MANYTOMANY"

    def test_area_cameras_uses_secondary_table(self):
        """Test cameras relationship uses camera_areas secondary table."""
        mapper = inspect(Area)
        relationships = {rel.key: rel for rel in mapper.relationships}
        cameras_rel = relationships["cameras"]
        assert cameras_rel.secondary is not None
        assert cameras_rel.secondary.name == "camera_areas"


# =============================================================================
# Table Args Tests
# =============================================================================


class TestAreaTableArgs:
    """Tests for Area table arguments."""

    def test_area_tablename(self):
        """Test Area has correct table name."""
        assert Area.__tablename__ == "areas"

    def test_area_table_exists(self):
        """Test Area table metadata is defined."""
        assert Area.__table__ is not None

    def test_area_primary_key(self):
        """Test Area has primary key on id."""
        mapper = inspect(Area)
        primary_key_cols = [col.name for col in mapper.primary_key]
        assert "id" in primary_key_cols

    def test_area_property_id_fk_constraint(self):
        """Test property_id has foreign key constraint to properties table."""
        mapper = inspect(Area)
        property_id_col = mapper.columns["property_id"]
        fks = list(property_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "properties.id"


# =============================================================================
# Index Tests
# =============================================================================


class TestAreaIndexes:
    """Tests for area-related indexes."""

    def test_area_has_property_id_index(self):
        """Test Area has index on property_id."""
        indexes = {idx.name for idx in Area.__table__.indexes}
        assert "idx_areas_property_id" in indexes

    def test_area_has_name_index(self):
        """Test Area has index on name."""
        indexes = {idx.name for idx in Area.__table__.indexes}
        assert "idx_areas_name" in indexes


# =============================================================================
# Association Table Tests
# =============================================================================


class TestCameraAreasAssociationTable:
    """Tests for camera_areas association table."""

    def test_camera_areas_table_exists(self):
        """Test camera_areas table is defined."""
        assert camera_areas is not None
        assert camera_areas.name == "camera_areas"

    def test_camera_areas_has_camera_id_column(self):
        """Test camera_areas has camera_id column."""
        column_names = [col.name for col in camera_areas.columns]
        assert "camera_id" in column_names

    def test_camera_areas_has_area_id_column(self):
        """Test camera_areas has area_id column."""
        column_names = [col.name for col in camera_areas.columns]
        assert "area_id" in column_names

    def test_camera_areas_camera_id_fk(self):
        """Test camera_id has foreign key to cameras table."""
        camera_id_col = camera_areas.c.camera_id
        fks = list(camera_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "cameras.id"

    def test_camera_areas_area_id_fk(self):
        """Test area_id has foreign key to areas table."""
        area_id_col = camera_areas.c.area_id
        fks = list(area_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "areas.id"

    def test_camera_areas_composite_primary_key(self):
        """Test camera_areas has composite primary key."""
        pk_columns = [col.name for col in camera_areas.primary_key.columns]
        assert "camera_id" in pk_columns
        assert "area_id" in pk_columns
        assert len(pk_columns) == 2


# =============================================================================
# Camera Integration Tests
# =============================================================================


class TestCameraAreaIntegration:
    """Tests for Camera integration with Area model."""

    def test_camera_has_areas_relationship(self):
        """Test Camera model has areas relationship."""
        camera = CameraFactory()
        assert hasattr(camera, "areas")

    def test_camera_has_property_ref_relationship(self):
        """Test Camera model has property_ref relationship."""
        camera = CameraFactory()
        assert hasattr(camera, "property_ref")

    def test_camera_has_property_id_field(self):
        """Test Camera model has property_id field."""
        camera = CameraFactory()
        assert hasattr(camera, "property_id")

    def test_camera_property_id_nullable(self):
        """Test Camera property_id is nullable."""
        camera = CameraFactory()
        assert camera.property_id is None

    def test_camera_areas_relationship_type(self):
        """Test Camera areas relationship is correctly typed (many-to-many)."""
        mapper = inspect(Camera)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "areas" in relationships
        assert relationships["areas"].direction.name == "MANYTOMANY"

    def test_camera_property_ref_relationship_type(self):
        """Test Camera property_ref relationship is correctly typed."""
        mapper = inspect(Camera)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "property_ref" in relationships
        assert relationships["property_ref"].direction.name == "MANYTOONE"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestAreaProperties:
    """Property-based tests for Area model."""

    @given(name=area_names)
    @settings(max_examples=30)
    def test_area_name_roundtrip(self, name: str):
        """Property: Name values roundtrip correctly."""
        area = Area(id=1, property_id=1, name=name)
        assert area.name == name

    @given(area_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_area_id_roundtrip(self, area_id: int):
        """Property: ID values roundtrip correctly."""
        area = Area(id=area_id, property_id=1, name="Test")
        assert area.id == area_id

    @given(property_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_area_property_id_roundtrip(self, property_id: int):
        """Property: property_id values roundtrip correctly."""
        area = Area(id=1, property_id=property_id, name="Test")
        assert area.property_id == property_id

    @given(description=descriptions)
    @settings(max_examples=30)
    def test_area_description_roundtrip(self, description: str | None):
        """Property: Description values roundtrip correctly."""
        area = Area(id=1, property_id=1, name="Test", description=description)
        assert area.description == description

    @given(color=hex_colors)
    @settings(max_examples=30)
    def test_area_color_roundtrip(self, color: str):
        """Property: Color values roundtrip correctly."""
        area = Area(id=1, property_id=1, name="Test", color=color)
        assert area.color == color


# =============================================================================
# Factory Tests
# =============================================================================


class TestAreaFactory:
    """Tests for AreaFactory."""

    def test_factory_creates_valid_area(self):
        """Test factory creates a valid Area instance."""
        area = AreaFactory()
        assert isinstance(area, Area)
        assert area.id is not None
        assert area.property_id is not None
        assert area.name is not None

    def test_factory_generates_unique_ids(self):
        """Test factory generates unique IDs."""
        area1 = AreaFactory()
        area2 = AreaFactory()
        assert area1.id != area2.id

    def test_factory_generates_unique_names(self):
        """Test factory generates unique names."""
        area1 = AreaFactory()
        area2 = AreaFactory()
        assert area1.name != area2.name

    def test_factory_accepts_custom_values(self):
        """Test factory accepts custom values."""
        area = AreaFactory(
            id=999,
            property_id=42,
            name="Custom Area",
            description="Custom Description",
            color="#ABCDEF",
        )
        assert area.id == 999
        assert area.property_id == 42
        assert area.name == "Custom Area"
        assert area.description == "Custom Description"
        assert area.color == "#ABCDEF"

    def test_factory_batch_creation(self):
        """Test factory can create multiple areas."""
        areas = AreaFactory.create_batch(5)
        assert len(areas) == 5
        ids = [a.id for a in areas]
        assert len(set(ids)) == 5  # All unique

    def test_factory_front_yard_trait(self):
        """Test factory front_yard trait."""
        area = AreaFactory(front_yard=True)
        assert area.name == "Front Yard"
        assert area.description == "Main entrance and lawn area"
        assert area.color == "#10B981"

    def test_factory_driveway_trait(self):
        """Test factory driveway trait."""
        area = AreaFactory(driveway=True)
        assert area.name == "Driveway"
        assert area.description == "Vehicle entry and parking area"
        assert area.color == "#F59E0B"

    def test_factory_backyard_trait(self):
        """Test factory backyard trait."""
        area = AreaFactory(backyard=True)
        assert area.name == "Backyard"
        assert area.description == "Rear yard and garden area"
        assert area.color == "#3B82F6"

    def test_factory_garage_trait(self):
        """Test factory garage trait."""
        area = AreaFactory(garage=True)
        assert area.name == "Garage"
        assert area.description == "Vehicle storage and entry"
        assert area.color == "#EF4444"

    def test_factory_pool_area_trait(self):
        """Test factory pool_area trait."""
        area = AreaFactory(pool_area=True)
        assert area.name == "Pool Area"
        assert area.description == "Swimming pool and deck"
        assert area.color == "#8B5CF6"

    def test_factory_with_description_trait(self):
        """Test factory with_description trait."""
        area = AreaFactory(name="Custom Zone", with_description=True)
        assert area.description == "Description for Custom Zone"


# =============================================================================
# Property Integration Tests
# =============================================================================


class TestAreaPropertyIntegration:
    """Tests for Area integration with Property model."""

    def test_property_has_areas_relationship(self):
        """Test Property model has areas relationship."""
        prop = PropertyFactory()
        assert hasattr(prop, "areas")

    def test_property_areas_relationship_type(self):
        """Test Property areas relationship is correctly typed."""
        mapper = inspect(Property)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "areas" in relationships
        assert relationships["areas"].direction.name == "ONETOMANY"
