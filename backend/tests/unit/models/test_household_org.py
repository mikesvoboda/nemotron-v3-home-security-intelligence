"""Unit tests for Household organization model.

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- Relationship definitions
- Table name and structure

Implements TDD for NEM-3128: Phase 5.1 - Create Household organization model.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.household import (
    HouseholdMember,
    MemberRole,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)
from backend.models.household_org import Household
from backend.tests.factories import (
    HouseholdFactory,
    HouseholdMemberFactory,
    RegisteredVehicleFactory,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for household names
household_names = st.text(
    min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_household():
    """Create a sample household for testing."""
    return HouseholdFactory(
        id=1,
        name="Svoboda Family",
    )


@pytest.fixture
def household_with_members():
    """Create a household with members."""
    household = HouseholdFactory(id=1, name="Test Family")
    # Create members linked to this household
    member1 = HouseholdMemberFactory(
        id=1,
        household_id=household.id,
        name="John Doe",
        role=MemberRole.RESIDENT,
        trusted_level=TrustLevel.FULL,
    )
    member2 = HouseholdMemberFactory(
        id=2,
        household_id=household.id,
        name="Jane Doe",
        role=MemberRole.FAMILY,
        trusted_level=TrustLevel.FULL,
    )
    return household, [member1, member2]


@pytest.fixture
def household_with_vehicles():
    """Create a household with vehicles."""
    household = HouseholdFactory(id=1, name="Test Family")
    # Create vehicles linked to this household
    vehicle1 = RegisteredVehicleFactory(
        id=1,
        household_id=household.id,
        description="Silver Tesla Model 3",
        vehicle_type=VehicleType.CAR,
    )
    vehicle2 = RegisteredVehicleFactory(
        id=2,
        household_id=household.id,
        description="Red Honda CRV",
        vehicle_type=VehicleType.SUV,
    )
    return household, [vehicle1, vehicle2]


# =============================================================================
# Household Model Initialization Tests
# =============================================================================


class TestHouseholdInitialization:
    """Tests for Household model initialization."""

    def test_household_creation_minimal(self):
        """Test creating a household with minimal required fields."""
        household = Household(
            id=1,
            name="Test Family",
        )

        assert household.id == 1
        assert household.name == "Test Family"

    def test_household_with_factory(self, sample_household):
        """Test household created via factory."""
        assert sample_household.id == 1
        assert sample_household.name == "Svoboda Family"

    def test_household_has_created_at(self, sample_household):
        """Test household has created_at field."""
        assert hasattr(sample_household, "created_at")

    def test_household_default_values(self):
        """Test household with default values."""
        household = Household(id=1, name="Default Test")
        # created_at should be set by server_default when persisted
        assert hasattr(household, "created_at")


# =============================================================================
# Household Field Tests
# =============================================================================


class TestHouseholdFields:
    """Tests for Household fields."""

    def test_household_name_max_length(self):
        """Test name field accepts max length value."""
        long_name = "A" * 100
        household = Household(id=1, name=long_name)
        assert len(household.name) == 100

    def test_household_name_can_be_short(self):
        """Test name field accepts short values."""
        household = Household(id=1, name="A")
        assert household.name == "A"

    def test_household_id_is_integer(self, sample_household):
        """Test id is an integer."""
        assert isinstance(sample_household.id, int)

    def test_household_name_is_string(self, sample_household):
        """Test name is a string."""
        assert isinstance(sample_household.name, str)


# =============================================================================
# Household Repr Tests
# =============================================================================


class TestHouseholdRepr:
    """Tests for Household string representation."""

    def test_household_repr_contains_class_name(self, sample_household):
        """Test repr contains class name."""
        repr_str = repr(sample_household)
        assert "Household" in repr_str

    def test_household_repr_contains_id(self, sample_household):
        """Test repr contains household id."""
        repr_str = repr(sample_household)
        assert "id=1" in repr_str

    def test_household_repr_contains_name(self, sample_household):
        """Test repr contains household name."""
        repr_str = repr(sample_household)
        assert "Svoboda Family" in repr_str

    def test_household_repr_format(self, sample_household):
        """Test repr has expected format."""
        repr_str = repr(sample_household)
        assert repr_str.startswith("<Household(")
        assert repr_str.endswith(")>")


# =============================================================================
# Household Relationship Tests
# =============================================================================


class TestHouseholdRelationships:
    """Tests for Household relationship definitions."""

    def test_household_has_members_relationship(self, sample_household):
        """Test household has members relationship defined."""
        assert hasattr(sample_household, "members")

    def test_household_has_vehicles_relationship(self, sample_household):
        """Test household has vehicles relationship defined."""
        assert hasattr(sample_household, "vehicles")

    def test_household_members_relationship_type(self):
        """Test members relationship is correctly typed."""
        from sqlalchemy import inspect

        mapper = inspect(Household)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "members" in relationships
        assert relationships["members"].direction.name == "ONETOMANY"

    def test_household_vehicles_relationship_type(self):
        """Test vehicles relationship is correctly typed."""
        from sqlalchemy import inspect

        mapper = inspect(Household)
        relationships = {rel.key: rel for rel in mapper.relationships}
        assert "vehicles" in relationships
        assert relationships["vehicles"].direction.name == "ONETOMANY"


# =============================================================================
# Table Args Tests
# =============================================================================


class TestHouseholdTableArgs:
    """Tests for Household table arguments."""

    def test_household_tablename(self):
        """Test Household has correct table name."""
        assert Household.__tablename__ == "households"

    def test_household_table_exists(self):
        """Test Household table metadata is defined."""
        assert Household.__table__ is not None

    def test_household_primary_key(self):
        """Test Household has primary key on id."""
        from sqlalchemy import inspect

        mapper = inspect(Household)
        primary_key_cols = [col.name for col in mapper.primary_key]
        assert "id" in primary_key_cols


# =============================================================================
# HouseholdMember household_id FK Tests
# =============================================================================


class TestHouseholdMemberHouseholdFK:
    """Tests for HouseholdMember household_id foreign key."""

    def test_member_has_household_id_field(self):
        """Test HouseholdMember has household_id field."""
        member = HouseholdMember(
            id=1,
            name="Test Person",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )
        assert hasattr(member, "household_id")

    def test_member_household_id_nullable(self):
        """Test household_id can be None (for backward compatibility)."""
        member = HouseholdMember(
            id=1,
            name="Test Person",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
            household_id=None,
        )
        assert member.household_id is None

    def test_member_household_id_can_be_set(self):
        """Test household_id can be set to a valid integer."""
        member = HouseholdMember(
            id=1,
            name="Test Person",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
            household_id=42,
        )
        assert member.household_id == 42

    def test_member_has_household_relationship(self):
        """Test HouseholdMember has household relationship defined."""
        member = HouseholdMemberFactory()
        assert hasattr(member, "household")

    def test_member_household_id_fk_constraint(self):
        """Test household_id has foreign key constraint to households table."""
        from sqlalchemy import inspect

        mapper = inspect(HouseholdMember)
        household_id_col = mapper.columns["household_id"]
        fks = list(household_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "households.id"


# =============================================================================
# RegisteredVehicle household_id FK Tests
# =============================================================================


class TestRegisteredVehicleHouseholdFK:
    """Tests for RegisteredVehicle household_id foreign key."""

    def test_vehicle_has_household_id_field(self):
        """Test RegisteredVehicle has household_id field."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test Car",
            vehicle_type=VehicleType.CAR,
        )
        assert hasattr(vehicle, "household_id")

    def test_vehicle_household_id_nullable(self):
        """Test household_id can be None (for backward compatibility)."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test Car",
            vehicle_type=VehicleType.CAR,
            household_id=None,
        )
        assert vehicle.household_id is None

    def test_vehicle_household_id_can_be_set(self):
        """Test household_id can be set to a valid integer."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test Car",
            vehicle_type=VehicleType.CAR,
            household_id=42,
        )
        assert vehicle.household_id == 42

    def test_vehicle_has_household_relationship(self):
        """Test RegisteredVehicle has household relationship defined."""
        vehicle = RegisteredVehicleFactory()
        assert hasattr(vehicle, "household")

    def test_vehicle_household_id_fk_constraint(self):
        """Test household_id has foreign key constraint to households table."""
        from sqlalchemy import inspect

        mapper = inspect(RegisteredVehicle)
        household_id_col = mapper.columns["household_id"]
        fks = list(household_id_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "households.id"


# =============================================================================
# Index Tests
# =============================================================================


class TestHouseholdIndexes:
    """Tests for household-related indexes."""

    def test_member_has_household_id_index(self):
        """Test HouseholdMember has index on household_id."""
        indexes = {idx.name for idx in HouseholdMember.__table__.indexes}
        assert "idx_household_members_household_id" in indexes

    def test_vehicle_has_household_id_index(self):
        """Test RegisteredVehicle has index on household_id."""
        indexes = {idx.name for idx in RegisteredVehicle.__table__.indexes}
        assert "idx_registered_vehicles_household_id" in indexes


# =============================================================================
# Property-based Tests
# =============================================================================


class TestHouseholdProperties:
    """Property-based tests for Household model."""

    @given(name=household_names)
    @settings(max_examples=30)
    def test_household_name_roundtrip(self, name: str):
        """Property: Name values roundtrip correctly."""
        household = Household(id=1, name=name)
        assert household.name == name

    @given(household_id=st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_household_id_roundtrip(self, household_id: int):
        """Property: ID values roundtrip correctly."""
        household = Household(id=household_id, name="Test")
        assert household.id == household_id


# =============================================================================
# Factory Tests
# =============================================================================


class TestHouseholdFactory:
    """Tests for HouseholdFactory."""

    def test_factory_creates_valid_household(self):
        """Test factory creates a valid Household instance."""
        household = HouseholdFactory()
        assert isinstance(household, Household)
        assert household.id is not None
        assert household.name is not None

    def test_factory_generates_unique_ids(self):
        """Test factory generates unique IDs."""
        household1 = HouseholdFactory()
        household2 = HouseholdFactory()
        assert household1.id != household2.id

    def test_factory_generates_unique_names(self):
        """Test factory generates unique names."""
        household1 = HouseholdFactory()
        household2 = HouseholdFactory()
        assert household1.name != household2.name

    def test_factory_accepts_custom_values(self):
        """Test factory accepts custom values."""
        household = HouseholdFactory(id=999, name="Custom Family")
        assert household.id == 999
        assert household.name == "Custom Family"

    def test_factory_batch_creation(self):
        """Test factory can create multiple households."""
        households = HouseholdFactory.create_batch(5)
        assert len(households) == 5
        ids = [h.id for h in households]
        assert len(set(ids)) == 5  # All unique


# =============================================================================
# Integration of Factory Updates Tests
# =============================================================================


class TestUpdatedFactories:
    """Tests for updated factories with household_id support."""

    def test_member_factory_default_household_id_none(self):
        """Test HouseholdMemberFactory defaults household_id to None."""
        member = HouseholdMemberFactory()
        assert member.household_id is None

    def test_member_factory_with_household_trait(self):
        """Test HouseholdMemberFactory with_household trait sets household_id."""
        member = HouseholdMemberFactory(with_household=True)
        assert member.household_id is not None

    def test_member_factory_accepts_custom_household_id(self):
        """Test HouseholdMemberFactory accepts custom household_id."""
        member = HouseholdMemberFactory(household_id=42)
        assert member.household_id == 42

    def test_vehicle_factory_default_household_id_none(self):
        """Test RegisteredVehicleFactory defaults household_id to None."""
        vehicle = RegisteredVehicleFactory()
        assert vehicle.household_id is None

    def test_vehicle_factory_with_household_trait(self):
        """Test RegisteredVehicleFactory with_household trait sets household_id."""
        vehicle = RegisteredVehicleFactory(with_household=True)
        assert vehicle.household_id is not None

    def test_vehicle_factory_accepts_custom_household_id(self):
        """Test RegisteredVehicleFactory accepts custom household_id."""
        vehicle = RegisteredVehicleFactory(household_id=42)
        assert vehicle.household_id == 42
