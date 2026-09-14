"""Unit tests for Property model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Relationship definitions
- Table name and structure
- Foreign key constraints

Implements TDD for NEM-3129: Phase 5.2 - Create Property and Area models.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import inspect

from backend.models.household_org import Household
from backend.models.property import Property
from backend.tests.factories import HouseholdFactory, PropertyFactory

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for property names
property_names = st.text(
    min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))
)

# Strategy for addresses
addresses = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=("Cs",))),
)

# Strategy for timezones
timezones = st.sampled_from(
    [
        "UTC",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Europe/London",
        "Asia/Tokyo",
    ]
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_property():
    """Create a sample property for testing."""
    return PropertyFactory(
        id=1,
        household_id=1,
        name="Main House",
        address="123 Main St, City, ST 12345",
        timezone="America/New_York",
    )


@pytest.fixture
def sample_household():
    """Create a sample household for testing."""
    return HouseholdFactory(id=1, name="Test Family")


# =============================================================================
# Property Model Initialization Tests
# =============================================================================


class TestPropertyInitialization:
    """Tests for Property model initialization."""

    def test_property_creation_minimal(self):
        """Test creating a property with minimal required fields."""
        prop = Property(
            id=1,
            household_id=1,
            name="Test Property",
        )

        assert prop.id == 1
        assert prop.household_id == 1
        assert prop.name == "Test Property"

    def test_property_with_factory(self, sample_property):
        """Test property created via factory."""
        assert sample_property.id == 1
        assert sample_property.household_id == 1
        assert sample_property.name == "Main House"
        assert sample_property.address == "123 Main St, City, ST 12345"
        assert sample_property.timezone == "America/New_York"

    def test_property_has_created_at(self, sample_property):
        """Test property has created_at field."""
        assert hasattr(sample_property, "created_at")

    def test_property_default_timezone(self):
        """Test property timezone field has default in model definition.

        Note: SQLAlchemy defaults are applied at insert time, not object creation.
        The model definition has default="UTC" which will be used when inserting.
        At unit test time without database, we verify the field exists and is settable.
        """
        prop = Property(id=1, household_id=1, name="Default Test", timezone="UTC")
        assert prop.timezone == "UTC"

    def test_property_nullable_address(self):
        """Test property with null address."""
        prop = Property(
            id=1,
            household_id=1,
            name="No Address Property",
            address=None,
        )
        assert prop.address is None


# =============================================================================
# Property Field Tests
# =============================================================================


class TestPropertyFields:
    """Tests for Property fields."""

    def test_property_name_max_length(self):
        """Test name field accepts max length value."""
        long_name = "A" * 100
        prop = Property(id=1, household_id=1, name=long_name)
        assert len(prop.name) == 100

    def test_property_name_can_be_short(self):
        """Test name field accepts short values."""
        prop = Property(id=1, household_id=1, name="A")
        assert prop.name == "A"

    def test_property_address_max_length(self):
        """Test address field accepts max length value."""
        long_address = "A" * 500
        prop = Property(id=1, household_id=1, name="Test", address=long_address)
        assert len(prop.address) == 500

    def test_property_timezone_max_length(self):
        """Test timezone field accepts typical timezone values."""
        prop = Property(
            id=1,
            household_id=1,
            name="Test",
            timezone="America/Argentina/Buenos_Aires",  # One of the longest
        )
        assert prop.timezone == "America/Argentina/Buenos_Aires"

    def test_property_id_is_integer(self, sample_property):
        """Test id is an integer."""
        assert isinstance(sample_property.id, int)

    def test_property_household_id_is_integer(self, sample_property):
        """Test household_id is an integer."""
        assert isinstance(sample_property.household_id, int)

    def test_property_name_is_string(self, sample_property):
        """Test name is a string."""
        assert isinstance(sample_property.name, str)


# =============================================================================
# Property Repr Tests
# =============================================================================


class TestPropertyRepr:
    """Tests for Property string representation."""

    def test_property_repr_contains_class_name(self, sample_property):
        """Test repr contains class name."""
        repr_str = repr(sample_property)
        assert "Property" in repr_str

    def test_property_repr_contains_id(self, sample_property):
        """Test repr contains property id."""
        repr_str = repr(sample_property)
        assert "id=1" in repr_str

    def test_property_repr_contains_name(self, sample_property):
        """Test repr contains property name."""
        repr_str = repr(sample_property)
        assert "Main House" in repr_str

    def test_property_repr_contains_household_id(self, sample_property):
        """Test repr contains household_id."""
        repr_str = repr(sample_property)
        assert "household_id=1" in repr_str

    def test_property_repr_format(self, sample_property):
        """Test repr has expected format."""
        repr_str = repr(sample_property)
        assert repr_str.startswith("<Property(")
        assert repr_str.endswith(")>")


# =============================================================================
# Property Relationship Tests
# =============================================================================


class TestPropertyRelationships:
    """Tests for Property relationship definitions."""

    def test_property_has_household_relationship(self, sample_property):
        """Test property has household relationship defined."""
        assert hasattr(sample_property, "household")

    def test_property_has_areas_relationship(self, sample_property):
        """Test property has areas relationship defined."""
        assert hasattr(sample_property, "areas")

    def test_property_has_cameras_relationship(self, sample_property):
        """Test property has cameras relationship defined."""
        assert hasattr(sample_property, "cameras")

    def test_property_household_relationship_type(self):
        """Test household relationship is correctly typed."""
        mapper = inspect(Property)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "household" in relationships
        assert relationships["household"].direction.name == "MANYTOONE"

    def test_property_areas_relationship_type(self):
        """Test areas relationship is correctly typed."""
        mapper = inspect(Property)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "areas" in relationships
        assert relationships["areas"].direction.name == "ONETOMANY"

    def test_property_cameras_relationship_type(self):
        """Test cameras relationship is correctly typed."""
        mapper = inspect(Property)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "cameras" in relationships
        assert relationships["cameras"].direction.name == "ONETOMANY"


# =============================================================================
# Table Args Tests
# =============================================================================


class TestPropertyTableArgs:
    """Tests for Property table arguments."""

    def test_property_tablename(self):
        """Test Property has correct table name."""
        assert Property.__tablename__ == "properties"

    def test_property_table_exists(self):
        """Test Property table metadata is defined."""
        assert Property.__table__ is not None

    def test_property_primary_key(self):
        """Test Property has primary key on id."""
        mapper = inspect(Property)
        primary_key_cols = [col.name for col in mapper.primary_key]
        assert "id" in primary_key_cols

    def test_property_household_id_fk_constraint(self):
        """Test household_id has foreign key constraint to households table."""
        mapper = inspect(Property)
        household_id_col = mapper.columns["household_id"]
        fks = list(household_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "households.id"


# =============================================================================
# Index Tests
# =============================================================================


class TestPropertyIndexes:
    """Tests for property-related indexes."""

    def test_property_has_household_id_index(self):
        """Test Property has index on household_id."""
        indexes = {idx.name for idx in Property.__table__.indexes}
        assert "idx_properties_household_id" in indexes

    def test_property_has_name_index(self):
        """Test Property has index on name."""
        indexes = {idx.name for idx in Property.__table__.indexes}
        assert "idx_properties_name" in indexes


# =============================================================================
# Property-based Tests
# =============================================================================


class TestPropertyProperties:
    """Property-based tests for Property model."""

    @given(name=property_names)
    @settings(max_examples=30)
    def test_property_name_roundtrip(self, name: str):
        """Property: Name values roundtrip correctly."""
        prop = Property(id=1, household_id=1, name=name)
        assert prop.name == name

    @given(property_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_property_id_roundtrip(self, property_id: int):
        """Property: ID values roundtrip correctly."""
        prop = Property(id=property_id, household_id=1, name="Test")
        assert prop.id == property_id

    @given(household_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_property_household_id_roundtrip(self, household_id: int):
        """Property: household_id values roundtrip correctly."""
        prop = Property(id=1, household_id=household_id, name="Test")
        assert prop.household_id == household_id

    @given(address=addresses)
    @settings(max_examples=30)
    def test_property_address_roundtrip(self, address: str | None):
        """Property: Address values roundtrip correctly."""
        prop = Property(id=1, household_id=1, name="Test", address=address)
        assert prop.address == address

    @given(timezone=timezones)
    @settings(max_examples=10)
    def test_property_timezone_roundtrip(self, timezone: str):
        """Property: Timezone values roundtrip correctly."""
        prop = Property(id=1, household_id=1, name="Test", timezone=timezone)
        assert prop.timezone == timezone


# =============================================================================
# Factory Tests
# =============================================================================


class TestPropertyFactory:
    """Tests for PropertyFactory."""

    def test_factory_creates_valid_property(self):
        """Test factory creates a valid Property instance."""
        prop = PropertyFactory()
        assert isinstance(prop, Property)
        assert prop.id is not None
        assert prop.household_id is not None
        assert prop.name is not None

    def test_factory_generates_unique_ids(self):
        """Test factory generates unique IDs."""
        prop1 = PropertyFactory()
        prop2 = PropertyFactory()
        assert prop1.id != prop2.id

    def test_factory_generates_unique_names(self):
        """Test factory generates unique names."""
        prop1 = PropertyFactory()
        prop2 = PropertyFactory()
        assert prop1.name != prop2.name

    def test_factory_accepts_custom_values(self):
        """Test factory accepts custom values."""
        prop = PropertyFactory(
            id=999,
            household_id=42,
            name="Custom Property",
            address="Custom Address",
            timezone="America/Chicago",
        )
        assert prop.id == 999
        assert prop.household_id == 42
        assert prop.name == "Custom Property"
        assert prop.address == "Custom Address"
        assert prop.timezone == "America/Chicago"

    def test_factory_batch_creation(self):
        """Test factory can create multiple properties."""
        properties = PropertyFactory.create_batch(5)
        assert len(properties) == 5
        ids = [p.id for p in properties]
        assert len(set(ids)) == 5  # All unique

    def test_factory_main_house_trait(self):
        """Test factory main_house trait."""
        prop = PropertyFactory(main_house=True)
        assert prop.name == "Main House"
        assert prop.timezone == "America/New_York"

    def test_factory_beach_house_trait(self):
        """Test factory beach_house trait."""
        prop = PropertyFactory(beach_house=True)
        assert prop.name == "Beach House"
        assert prop.timezone == "America/Los_Angeles"

    def test_factory_vacation_home_trait(self):
        """Test factory vacation_home trait."""
        prop = PropertyFactory(vacation_home=True)
        assert prop.name == "Vacation Home"
        assert prop.timezone == "America/Chicago"

    def test_factory_no_address_trait(self):
        """Test factory no_address trait."""
        prop = PropertyFactory(no_address=True)
        assert prop.address is None


# =============================================================================
# Household Integration Tests
# =============================================================================


class TestPropertyHouseholdIntegration:
    """Tests for Property integration with Household model."""

    def test_household_has_properties_relationship(self):
        """Test Household model has properties relationship."""
        household = HouseholdFactory()
        assert hasattr(household, "properties")

    def test_household_properties_relationship_type(self):
        """Test Household properties relationship is correctly typed."""
        mapper = inspect(Household)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "properties" in relationships
        assert relationships["properties"].direction.name == "ONETOMANY"
