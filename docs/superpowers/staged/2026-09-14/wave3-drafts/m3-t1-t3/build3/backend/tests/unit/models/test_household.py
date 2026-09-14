"""Unit tests for Household models (HouseholdMember, PersonEmbedding, RegisteredVehicle).

Tests cover:
- Model initialization and default values
- Field validation and constraints
- String representation (__repr__)
- MemberRole, TrustLevel, VehicleType enums
- JSONB typical_schedule field
- LargeBinary embedding fields
- Relationships between models
- Property-based tests for field values

Implements TDD for NEM-3016: Create HouseholdMember and RegisteredVehicle database models.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.household import (
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)
from backend.tests.factories import (
    HouseholdMemberFactory,
    PersonEmbeddingFactory,
    RegisteredVehicleFactory,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for valid member roles
member_roles = st.sampled_from(list(MemberRole))

# Strategy for valid trust levels
trust_levels = st.sampled_from(list(TrustLevel))

# Strategy for valid vehicle types
vehicle_types = st.sampled_from(list(VehicleType))

# Strategy for confidence values (0-1 range)
confidence_values = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for typical schedule JSONB
typical_schedule_strategy = st.one_of(
    st.none(),
    st.fixed_dictionaries(
        {
            "weekdays": st.sampled_from(["08:00-17:00", "09:00-18:00", "17:00-23:00"]),
            "weekends": st.sampled_from(["all_day", "none", "10:00-20:00"]),
        }
    ),
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_member():
    """Create a sample household member for testing."""
    return HouseholdMemberFactory(
        id=1,
        name="John Doe",
        role=MemberRole.RESIDENT,
        trusted_level=TrustLevel.FULL,
        typical_schedule={"weekdays": "08:00-17:00", "weekends": "all_day"},
        notes="Primary resident",
    )


@pytest.fixture
def service_worker():
    """Create a service worker household member."""
    return HouseholdMemberFactory(
        id=2,
        name="Jane Smith",
        role=MemberRole.SERVICE_WORKER,
        trusted_level=TrustLevel.PARTIAL,
        typical_schedule={"weekdays": "09:00-17:00", "weekends": "none"},
        notes="Weekly gardener",
    )


@pytest.fixture
def sample_embedding(sample_member):
    """Create a sample person embedding."""
    return PersonEmbeddingFactory(
        id=1,
        member_id=sample_member.id,
        embedding=b"\x00\x01\x02\x03",  # Simple byte array
        confidence=0.95,
    )


@pytest.fixture
def sample_vehicle(sample_member):
    """Create a sample registered vehicle."""
    return RegisteredVehicleFactory(
        id=1,
        description="Silver Tesla Model 3",
        license_plate="ABC123",
        vehicle_type=VehicleType.CAR,
        color="silver",
        owner_id=sample_member.id,
        trusted=True,
    )


@pytest.fixture
def unregistered_vehicle():
    """Create a vehicle without an owner."""
    return RegisteredVehicleFactory(
        id=2,
        description="Blue Honda Civic",
        license_plate="XYZ789",
        vehicle_type=VehicleType.CAR,
        color="blue",
        owner_id=None,
        trusted=False,
    )


# =============================================================================
# MemberRole Enum Tests
# =============================================================================


class TestMemberRoleEnum:
    """Tests for MemberRole enum."""

    def test_member_role_resident(self):
        """Test RESIDENT member role."""
        assert MemberRole.RESIDENT.value == "resident"

    def test_member_role_family(self):
        """Test FAMILY member role."""
        assert MemberRole.FAMILY.value == "family"

    def test_member_role_service_worker(self):
        """Test SERVICE_WORKER member role."""
        assert MemberRole.SERVICE_WORKER.value == "service_worker"

    def test_member_role_frequent_visitor(self):
        """Test FREQUENT_VISITOR member role."""
        assert MemberRole.FREQUENT_VISITOR.value == "frequent_visitor"

    def test_member_role_is_string_enum(self):
        """Test MemberRole is a string enum."""
        for role in MemberRole:
            assert isinstance(role, str)
            assert isinstance(role.value, str)

    def test_member_role_count(self):
        """Test MemberRole has expected number of values."""
        assert len(MemberRole) == 4


# =============================================================================
# TrustLevel Enum Tests
# =============================================================================


class TestTrustLevelEnum:
    """Tests for TrustLevel enum."""

    def test_trust_level_full(self):
        """Test FULL trust level."""
        assert TrustLevel.FULL.value == "full"

    def test_trust_level_partial(self):
        """Test PARTIAL trust level."""
        assert TrustLevel.PARTIAL.value == "partial"

    def test_trust_level_monitor(self):
        """Test MONITOR trust level."""
        assert TrustLevel.MONITOR.value == "monitor"

    def test_trust_level_is_string_enum(self):
        """Test TrustLevel is a string enum."""
        for level in TrustLevel:
            assert isinstance(level, str)
            assert isinstance(level.value, str)

    def test_trust_level_count(self):
        """Test TrustLevel has expected number of values."""
        assert len(TrustLevel) == 3


# =============================================================================
# VehicleType Enum Tests
# =============================================================================


class TestVehicleTypeEnum:
    """Tests for VehicleType enum."""

    def test_vehicle_type_car(self):
        """Test CAR vehicle type."""
        assert VehicleType.CAR.value == "car"

    def test_vehicle_type_truck(self):
        """Test TRUCK vehicle type."""
        assert VehicleType.TRUCK.value == "truck"

    def test_vehicle_type_motorcycle(self):
        """Test MOTORCYCLE vehicle type."""
        assert VehicleType.MOTORCYCLE.value == "motorcycle"

    def test_vehicle_type_suv(self):
        """Test SUV vehicle type."""
        assert VehicleType.SUV.value == "suv"

    def test_vehicle_type_van(self):
        """Test VAN vehicle type."""
        assert VehicleType.VAN.value == "van"

    def test_vehicle_type_other(self):
        """Test OTHER vehicle type."""
        assert VehicleType.OTHER.value == "other"

    def test_vehicle_type_is_string_enum(self):
        """Test VehicleType is a string enum."""
        for vtype in VehicleType:
            assert isinstance(vtype, str)
            assert isinstance(vtype.value, str)

    def test_vehicle_type_count(self):
        """Test VehicleType has expected number of values."""
        assert len(VehicleType) == 6


# =============================================================================
# HouseholdMember Model Initialization Tests
# =============================================================================


class TestHouseholdMemberInitialization:
    """Tests for HouseholdMember model initialization."""

    def test_member_creation_minimal(self):
        """Test creating a member with minimal required fields."""
        member = HouseholdMember(
            id=1,
            name="Test Person",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )

        assert member.id == 1
        assert member.name == "Test Person"
        assert member.role == MemberRole.RESIDENT
        assert member.trusted_level == TrustLevel.FULL

    def test_member_with_all_fields(self, sample_member):
        """Test member with all fields populated."""
        assert sample_member.id == 1
        assert sample_member.name == "John Doe"
        assert sample_member.role == MemberRole.RESIDENT
        assert sample_member.trusted_level == TrustLevel.FULL
        assert sample_member.typical_schedule == {
            "weekdays": "08:00-17:00",
            "weekends": "all_day",
        }
        assert sample_member.notes == "Primary resident"

    def test_member_nullable_fields(self):
        """Test member with nullable fields as None."""
        member = HouseholdMember(
            id=3,
            name="No Schedule Person",
            role=MemberRole.FAMILY,
            trusted_level=TrustLevel.PARTIAL,
            typical_schedule=None,
            notes=None,
        )

        assert member.typical_schedule is None
        assert member.notes is None

    def test_member_has_timestamps(self, sample_member):
        """Test member has timestamp fields."""
        assert hasattr(sample_member, "created_at")
        assert hasattr(sample_member, "updated_at")


# =============================================================================
# HouseholdMember Field Tests
# =============================================================================


class TestHouseholdMemberFields:
    """Tests for HouseholdMember fields."""

    def test_member_name_max_length(self):
        """Test name field accepts max length value."""
        long_name = "A" * 100
        member = HouseholdMember(
            id=1,
            name=long_name,
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )
        assert len(member.name) == 100

    def test_member_typical_schedule_jsonb(self, sample_member):
        """Test typical_schedule is properly stored as JSONB."""
        schedule = sample_member.typical_schedule
        assert isinstance(schedule, dict)
        assert "weekdays" in schedule
        assert "weekends" in schedule

    def test_member_role_enum_value(self, service_worker):
        """Test role is stored as enum."""
        assert service_worker.role == MemberRole.SERVICE_WORKER
        assert service_worker.role.value == "service_worker"


# =============================================================================
# HouseholdMember Repr Tests
# =============================================================================


class TestHouseholdMemberRepr:
    """Tests for HouseholdMember string representation."""

    def test_member_repr_contains_class_name(self, sample_member):
        """Test repr contains class name."""
        repr_str = repr(sample_member)
        assert "HouseholdMember" in repr_str

    def test_member_repr_contains_id(self, sample_member):
        """Test repr contains member id."""
        repr_str = repr(sample_member)
        assert "id=1" in repr_str

    def test_member_repr_contains_name(self, sample_member):
        """Test repr contains member name."""
        repr_str = repr(sample_member)
        assert "John Doe" in repr_str

    def test_member_repr_contains_role(self, sample_member):
        """Test repr contains member role."""
        repr_str = repr(sample_member)
        assert "resident" in repr_str.lower()

    def test_member_repr_format(self, sample_member):
        """Test repr has expected format."""
        repr_str = repr(sample_member)
        assert repr_str.startswith("<HouseholdMember(")
        assert repr_str.endswith(")>")


# =============================================================================
# HouseholdMember Relationship Tests
# =============================================================================


class TestHouseholdMemberRelationships:
    """Tests for HouseholdMember relationship definitions."""

    def test_member_has_embeddings_relationship(self, sample_member):
        """Test member has embeddings relationship defined."""
        assert hasattr(sample_member, "embeddings")

    def test_member_embeddings_default_empty(self):
        """Test member embeddings default to empty list."""
        member = HouseholdMember(
            id=1,
            name="Test",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )
        # Note: In-memory, relationships may not be initialized
        # This verifies the attribute exists
        assert hasattr(member, "embeddings")


# =============================================================================
# PersonEmbedding Model Tests
# =============================================================================


class TestPersonEmbeddingInitialization:
    """Tests for PersonEmbedding model initialization."""

    def test_embedding_creation_minimal(self):
        """Test creating an embedding with minimal required fields."""
        embedding = PersonEmbedding(
            id=1,
            member_id=1,
            embedding=b"\x00\x01\x02",
        )

        assert embedding.id == 1
        assert embedding.member_id == 1
        assert embedding.embedding == b"\x00\x01\x02"

    def test_embedding_with_all_fields(self, sample_embedding):
        """Test embedding with all fields populated."""
        assert sample_embedding.id == 1
        assert sample_embedding.member_id == 1
        assert sample_embedding.embedding == b"\x00\x01\x02\x03"
        assert sample_embedding.confidence == 0.95

    def test_embedding_default_confidence_column_definition(self):
        """Test that confidence column has 1.0 as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(PersonEmbedding)
        confidence_col = mapper.columns["confidence"]
        assert confidence_col.default is not None
        assert confidence_col.default.arg == 1.0

    def test_embedding_nullable_source_event(self):
        """Test embedding can have null source_event_id."""
        embedding = PersonEmbedding(
            id=1,
            member_id=1,
            embedding=b"\x00",
            source_event_id=None,
        )
        assert embedding.source_event_id is None


class TestPersonEmbeddingFields:
    """Tests for PersonEmbedding fields."""

    def test_embedding_bytes_storage(self, sample_embedding):
        """Test embedding field stores bytes correctly."""
        assert isinstance(sample_embedding.embedding, bytes)
        assert len(sample_embedding.embedding) == 4

    def test_embedding_confidence_range(self, sample_embedding):
        """Test confidence is in expected range."""
        assert 0.0 <= sample_embedding.confidence <= 1.0

    def test_embedding_has_created_at(self, sample_embedding):
        """Test embedding has created_at field."""
        assert hasattr(sample_embedding, "created_at")


class TestPersonEmbeddingRepr:
    """Tests for PersonEmbedding string representation."""

    def test_embedding_repr_contains_class_name(self, sample_embedding):
        """Test repr contains class name."""
        repr_str = repr(sample_embedding)
        assert "PersonEmbedding" in repr_str

    def test_embedding_repr_contains_id(self, sample_embedding):
        """Test repr contains embedding id."""
        repr_str = repr(sample_embedding)
        assert "id=1" in repr_str

    def test_embedding_repr_format(self, sample_embedding):
        """Test repr has expected format."""
        repr_str = repr(sample_embedding)
        assert repr_str.startswith("<PersonEmbedding(")
        assert repr_str.endswith(")>")


class TestPersonEmbeddingRelationships:
    """Tests for PersonEmbedding relationship definitions."""

    def test_embedding_has_member_relationship(self, sample_embedding):
        """Test embedding has member relationship defined."""
        assert hasattr(sample_embedding, "member")


# =============================================================================
# RegisteredVehicle Model Tests
# =============================================================================


class TestRegisteredVehicleInitialization:
    """Tests for RegisteredVehicle model initialization."""

    def test_vehicle_creation_minimal(self):
        """Test creating a vehicle with minimal required fields."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Blue Car",
            vehicle_type=VehicleType.CAR,
        )

        assert vehicle.id == 1
        assert vehicle.description == "Blue Car"
        assert vehicle.vehicle_type == VehicleType.CAR

    def test_vehicle_with_all_fields(self, sample_vehicle):
        """Test vehicle with all fields populated."""
        assert sample_vehicle.id == 1
        assert sample_vehicle.description == "Silver Tesla Model 3"
        assert sample_vehicle.license_plate == "ABC123"
        assert sample_vehicle.vehicle_type == VehicleType.CAR
        assert sample_vehicle.color == "silver"
        assert sample_vehicle.owner_id == 1
        assert sample_vehicle.trusted is True

    def test_vehicle_default_trusted_column_definition(self):
        """Test that trusted column has True as default.

        Note: SQLAlchemy defaults apply at database level, not in-memory.
        This test verifies the column default is correctly defined.
        """
        from sqlalchemy import inspect

        mapper = inspect(RegisteredVehicle)
        trusted_col = mapper.columns["trusted"]
        assert trusted_col.default is not None
        assert trusted_col.default.arg is True

    def test_vehicle_nullable_fields(self, unregistered_vehicle):
        """Test vehicle with nullable fields as None."""
        assert unregistered_vehicle.owner_id is None
        # license_plate can be null
        vehicle = RegisteredVehicle(
            id=3,
            description="Mystery Van",
            vehicle_type=VehicleType.VAN,
            license_plate=None,
            color=None,
        )
        assert vehicle.license_plate is None
        assert vehicle.color is None


class TestRegisteredVehicleFields:
    """Tests for RegisteredVehicle fields."""

    def test_vehicle_description_max_length(self):
        """Test description field accepts max length value."""
        long_desc = "A" * 200
        vehicle = RegisteredVehicle(
            id=1,
            description=long_desc,
            vehicle_type=VehicleType.CAR,
        )
        assert len(vehicle.description) == 200

    def test_vehicle_license_plate_max_length(self):
        """Test license_plate field accepts max length value."""
        plate = "A" * 20
        vehicle = RegisteredVehicle(
            id=1,
            description="Test",
            vehicle_type=VehicleType.CAR,
            license_plate=plate,
        )
        assert len(vehicle.license_plate) == 20

    def test_vehicle_reid_embedding_bytes(self):
        """Test reid_embedding stores bytes correctly."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test",
            vehicle_type=VehicleType.CAR,
            reid_embedding=b"\x00\x01\x02\x03",
        )
        assert isinstance(vehicle.reid_embedding, bytes)
        assert len(vehicle.reid_embedding) == 4

    def test_vehicle_has_created_at(self, sample_vehicle):
        """Test vehicle has created_at field."""
        assert hasattr(sample_vehicle, "created_at")


class TestRegisteredVehicleRepr:
    """Tests for RegisteredVehicle string representation."""

    def test_vehicle_repr_contains_class_name(self, sample_vehicle):
        """Test repr contains class name."""
        repr_str = repr(sample_vehicle)
        assert "RegisteredVehicle" in repr_str

    def test_vehicle_repr_contains_id(self, sample_vehicle):
        """Test repr contains vehicle id."""
        repr_str = repr(sample_vehicle)
        assert "id=1" in repr_str

    def test_vehicle_repr_contains_description(self, sample_vehicle):
        """Test repr contains vehicle description."""
        repr_str = repr(sample_vehicle)
        assert "Silver Tesla Model 3" in repr_str

    def test_vehicle_repr_contains_vehicle_type(self, sample_vehicle):
        """Test repr contains vehicle_type."""
        repr_str = repr(sample_vehicle)
        assert "car" in repr_str.lower()

    def test_vehicle_repr_format(self, sample_vehicle):
        """Test repr has expected format."""
        repr_str = repr(sample_vehicle)
        assert repr_str.startswith("<RegisteredVehicle(")
        assert repr_str.endswith(")>")


class TestRegisteredVehicleRelationships:
    """Tests for RegisteredVehicle relationship definitions."""

    def test_vehicle_has_owner_relationship(self, sample_vehicle):
        """Test vehicle has owner relationship defined."""
        assert hasattr(sample_vehicle, "owner")


# =============================================================================
# Table Args Tests
# =============================================================================


class TestHouseholdMemberTableArgs:
    """Tests for HouseholdMember table arguments."""

    def test_member_has_table_args(self):
        """Test HouseholdMember model has __table_args__."""
        assert hasattr(HouseholdMember, "__table_args__")

    def test_member_tablename(self):
        """Test HouseholdMember has correct table name."""
        assert HouseholdMember.__tablename__ == "household_members"


class TestPersonEmbeddingTableArgs:
    """Tests for PersonEmbedding table arguments."""

    def test_embedding_has_table_args(self):
        """Test PersonEmbedding model has __table_args__."""
        assert hasattr(PersonEmbedding, "__table_args__")

    def test_embedding_tablename(self):
        """Test PersonEmbedding has correct table name."""
        assert PersonEmbedding.__tablename__ == "person_embeddings"


class TestRegisteredVehicleTableArgs:
    """Tests for RegisteredVehicle table arguments."""

    def test_vehicle_has_table_args(self):
        """Test RegisteredVehicle model has __table_args__."""
        assert hasattr(RegisteredVehicle, "__table_args__")

    def test_vehicle_tablename(self):
        """Test RegisteredVehicle has correct table name."""
        assert RegisteredVehicle.__tablename__ == "registered_vehicles"


# =============================================================================
# Property-based Tests
# =============================================================================


class TestHouseholdMemberProperties:
    """Property-based tests for HouseholdMember model."""

    @given(role=member_roles)
    @settings(max_examples=10)
    def test_member_role_roundtrip(self, role: MemberRole):
        """Property: Member role values roundtrip correctly."""
        member = HouseholdMember(
            id=1,
            name="Test",
            role=role,
            trusted_level=TrustLevel.FULL,
        )
        assert member.role == role

    @given(trust_level=trust_levels)
    @settings(max_examples=10)
    def test_member_trust_level_roundtrip(self, trust_level: TrustLevel):
        """Property: Trust level values roundtrip correctly."""
        member = HouseholdMember(
            id=1,
            name="Test",
            role=MemberRole.RESIDENT,
            trusted_level=trust_level,
        )
        assert member.trusted_level == trust_level

    @given(schedule=typical_schedule_strategy)
    @settings(max_examples=20)
    def test_member_schedule_roundtrip(self, schedule: dict | None):
        """Property: Schedule values roundtrip correctly."""
        member = HouseholdMember(
            id=1,
            name="Test",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
            typical_schedule=schedule,
        )
        assert member.typical_schedule == schedule


class TestPersonEmbeddingProperties:
    """Property-based tests for PersonEmbedding model."""

    @given(confidence=confidence_values)
    @settings(max_examples=30)
    def test_embedding_confidence_roundtrip(self, confidence: float):
        """Property: Confidence values roundtrip correctly."""
        embedding = PersonEmbedding(
            id=1,
            member_id=1,
            embedding=b"\x00",
            confidence=confidence,
        )
        assert embedding.confidence == confidence

    @given(data=st.binary(min_size=1, max_size=1000))
    @settings(max_examples=30)
    def test_embedding_bytes_roundtrip(self, data: bytes):
        """Property: Embedding bytes roundtrip correctly."""
        embedding = PersonEmbedding(
            id=1,
            member_id=1,
            embedding=data,
        )
        assert embedding.embedding == data


class TestRegisteredVehicleProperties:
    """Property-based tests for RegisteredVehicle model."""

    @given(vehicle_type=vehicle_types)
    @settings(max_examples=10)
    def test_vehicle_type_roundtrip(self, vehicle_type: VehicleType):
        """Property: Vehicle type values roundtrip correctly."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test",
            vehicle_type=vehicle_type,
        )
        assert vehicle.vehicle_type == vehicle_type

    @given(trusted=st.booleans())
    @settings(max_examples=10)
    def test_vehicle_trusted_roundtrip(self, trusted: bool):
        """Property: Trusted values roundtrip correctly."""
        vehicle = RegisteredVehicle(
            id=1,
            description="Test",
            vehicle_type=VehicleType.CAR,
            trusted=trusted,
        )
        assert vehicle.trusted == trusted

    @given(
        description=st.text(min_size=1, max_size=200),
        license_plate=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
        color=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=30)
    def test_vehicle_string_fields_roundtrip(
        self, description: str, license_plate: str | None, color: str | None
    ):
        """Property: String fields roundtrip correctly."""
        vehicle = RegisteredVehicle(
            id=1,
            description=description,
            vehicle_type=VehicleType.CAR,
            license_plate=license_plate,
            color=color,
        )
        assert vehicle.description == description
        assert vehicle.license_plate == license_plate
        assert vehicle.color == color
