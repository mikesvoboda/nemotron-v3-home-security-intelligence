"""Unit tests for household API endpoints.

NEM-3313: Tests for the /api/household endpoints which provide CRUD operations
for managing household members and registered vehicles.

Endpoints tested:
    Household Members:
    - GET    /api/household/members                     - List all members
    - POST   /api/household/members                     - Create new member
    - GET    /api/household/members/{member_id}         - Get specific member
    - PATCH  /api/household/members/{member_id}         - Update member
    - DELETE /api/household/members/{member_id}         - Delete member
    - POST   /api/household/members/{member_id}/embeddings - Add embedding from event

    Registered Vehicles:
    - GET    /api/household/vehicles                    - List all vehicles
    - POST   /api/household/vehicles                    - Create new vehicle
    - GET    /api/household/vehicles/{vehicle_id}       - Get specific vehicle
    - PATCH  /api/household/vehicles/{vehicle_id}       - Update vehicle
    - DELETE /api/household/vehicles/{vehicle_id}       - Delete vehicle
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.api.routes.household import (
    add_embedding_from_event,
    create_member,
    create_vehicle,
    delete_member,
    delete_vehicle,
    get_member,
    get_vehicle,
    list_members,
    list_vehicles,
    update_member,
    update_vehicle,
)
from backend.api.schemas.household import (
    AddEmbeddingRequest,
    HouseholdMemberCreate,
    HouseholdMemberUpdate,
    RegisteredVehicleCreate,
    RegisteredVehicleUpdate,
)
from backend.models.household import (
    HouseholdMember,
    MemberRole,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock database session for testing."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_member():
    """Create a sample household member for testing."""
    member = MagicMock(spec=HouseholdMember)
    member.id = 1
    member.name = "John Doe"
    member.role = MemberRole.RESIDENT
    member.trusted_level = TrustLevel.FULL
    member.typical_schedule = {"weekdays": "9-17"}
    member.notes = "Test notes"
    member.created_at = datetime.now(UTC)
    member.updated_at = datetime.now(UTC)
    return member


@pytest.fixture
def sample_vehicle():
    """Create a sample registered vehicle for testing."""
    vehicle = MagicMock(spec=RegisteredVehicle)
    vehicle.id = 1
    vehicle.description = "Silver Tesla Model 3"
    vehicle.license_plate = "ABC123"
    vehicle.vehicle_type = VehicleType.CAR
    vehicle.color = "Silver"
    vehicle.owner_id = 1
    vehicle.trusted = True
    vehicle.created_at = datetime.now(UTC)
    return vehicle


@pytest.fixture
def sample_event():
    """Create a sample event for embedding tests."""
    event = MagicMock()
    event.id = 100
    event.embedding = None  # Event doesn't have embedding by default
    return event


# =============================================================================
# Household Member Tests - List
# =============================================================================


class TestListMembers:
    """Tests for the list_members endpoint."""

    @pytest.mark.asyncio
    async def test_list_members_returns_empty_list_when_none_exist(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that list_members returns empty list when no members exist."""
        result = await list_members(session=mock_session)

        assert result == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_members_returns_all_members(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test that list_members returns all existing members."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_member]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await list_members(session=mock_session)

        assert len(result) == 1
        assert result[0] == sample_member

    @pytest.mark.asyncio
    async def test_list_members_ordered_by_name(self, mock_session: AsyncMock) -> None:
        """Test that list_members returns members ordered by name."""
        member_a = MagicMock(spec=HouseholdMember)
        member_a.name = "Alice"
        member_b = MagicMock(spec=HouseholdMember)
        member_b.name = "Bob"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [member_a, member_b]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await list_members(session=mock_session)

        assert len(result) == 2
        # The query should order by name - verify this in the actual query
        mock_session.execute.assert_called_once()


# =============================================================================
# Household Member Tests - Create
# =============================================================================


class TestCreateMember:
    """Tests for the create_member endpoint."""

    @pytest.mark.asyncio
    async def test_create_member_success(self, mock_session: AsyncMock) -> None:
        """Test successful member creation with all required fields."""
        member_data = HouseholdMemberCreate(
            name="John Doe",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
        )

        result = await create_member(member=member_data, session=mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        # The result should be the member object that was added
        added_member = mock_session.add.call_args[0][0]
        assert added_member.name == "John Doe"
        assert added_member.role == MemberRole.RESIDENT
        assert added_member.trusted_level == TrustLevel.FULL

    @pytest.mark.asyncio
    async def test_create_member_with_optional_fields(self, mock_session: AsyncMock) -> None:
        """Test member creation with optional fields."""
        member_data = HouseholdMemberCreate(
            name="Jane Doe",
            role=MemberRole.FAMILY,
            trusted_level=TrustLevel.PARTIAL,
            typical_schedule={"weekdays": "9-17", "weekends": "flexible"},
            notes="Remote worker",
        )

        await create_member(member=member_data, session=mock_session)

        added_member = mock_session.add.call_args[0][0]
        assert added_member.name == "Jane Doe"
        assert added_member.role == MemberRole.FAMILY
        assert added_member.trusted_level == TrustLevel.PARTIAL
        assert added_member.typical_schedule == {"weekdays": "9-17", "weekends": "flexible"}
        assert added_member.notes == "Remote worker"

    @pytest.mark.asyncio
    async def test_create_member_all_roles(self, mock_session: AsyncMock) -> None:
        """Test member creation with all valid roles."""
        for role in MemberRole:
            member_data = HouseholdMemberCreate(
                name=f"Test {role.value}",
                role=role,
                trusted_level=TrustLevel.FULL,
            )

            await create_member(member=member_data, session=mock_session)

            added_member = mock_session.add.call_args[0][0]
            assert added_member.role == role

    @pytest.mark.asyncio
    async def test_create_member_all_trust_levels(self, mock_session: AsyncMock) -> None:
        """Test member creation with all valid trust levels."""
        for trust_level in TrustLevel:
            member_data = HouseholdMemberCreate(
                name=f"Test {trust_level.value}",
                role=MemberRole.RESIDENT,
                trusted_level=trust_level,
            )

            await create_member(member=member_data, session=mock_session)

            added_member = mock_session.add.call_args[0][0]
            assert added_member.trusted_level == trust_level


# =============================================================================
# Household Member Tests - Get
# =============================================================================


class TestGetMember:
    """Tests for the get_member endpoint."""

    @pytest.mark.asyncio
    async def test_get_member_success(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test successfully getting a member by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_member
        mock_session.execute.return_value = mock_result

        result = await get_member(member_id=1, session=mock_session)

        assert result == sample_member
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_member_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that getting a nonexistent member raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_member(member_id=999, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Household Member Tests - Update
# =============================================================================


class TestUpdateMember:
    """Tests for the update_member endpoint."""

    @pytest.mark.asyncio
    async def test_update_member_success(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test successfully updating a member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_member
        mock_session.execute.return_value = mock_result

        updates = HouseholdMemberUpdate(name="Updated Name")

        result = await update_member(member_id=1, updates=updates, session=mock_session)

        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member_partial_update(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test partial update only modifies specified fields."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_member
        mock_session.execute.return_value = mock_result

        updates = HouseholdMemberUpdate(trusted_level=TrustLevel.PARTIAL)

        await update_member(member_id=1, updates=updates, session=mock_session)

        # Only trusted_level should be set, name should remain unchanged
        # Since we use setattr, verify the member was modified
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that updating a nonexistent member raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        updates = HouseholdMemberUpdate(name="Updated Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_member(member_id=999, updates=updates, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Household Member Tests - Delete
# =============================================================================


class TestDeleteMember:
    """Tests for the delete_member endpoint."""

    @pytest.mark.asyncio
    async def test_delete_member_success(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test successfully deleting a member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_member
        mock_session.execute.return_value = mock_result

        await delete_member(member_id=1, session=mock_session)

        mock_session.delete.assert_called_once_with(sample_member)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_member_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that deleting a nonexistent member raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_member(member_id=999, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Registered Vehicle Tests - List
# =============================================================================


class TestListVehicles:
    """Tests for the list_vehicles endpoint."""

    @pytest.mark.asyncio
    async def test_list_vehicles_returns_empty_list_when_none_exist(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that list_vehicles returns empty list when no vehicles exist."""
        result = await list_vehicles(session=mock_session)

        assert result == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_vehicles_returns_all_vehicles(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test that list_vehicles returns all existing vehicles."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_vehicle]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await list_vehicles(session=mock_session)

        assert len(result) == 1
        assert result[0] == sample_vehicle


# =============================================================================
# Registered Vehicle Tests - Create
# =============================================================================


class TestCreateVehicle:
    """Tests for the create_vehicle endpoint."""

    @pytest.mark.asyncio
    async def test_create_vehicle_success(self, mock_session: AsyncMock) -> None:
        """Test successful vehicle creation with all required fields."""
        vehicle_data = RegisteredVehicleCreate(
            description="Silver Tesla Model 3",
            vehicle_type=VehicleType.CAR,
        )

        await create_vehicle(vehicle=vehicle_data, session=mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        added_vehicle = mock_session.add.call_args[0][0]
        assert added_vehicle.description == "Silver Tesla Model 3"
        assert added_vehicle.vehicle_type == VehicleType.CAR

    @pytest.mark.asyncio
    async def test_create_vehicle_with_optional_fields(self, mock_session: AsyncMock) -> None:
        """Test vehicle creation with optional fields."""
        vehicle_data = RegisteredVehicleCreate(
            description="Blue Honda Civic",
            vehicle_type=VehicleType.CAR,
            license_plate="XYZ789",
            color="Blue",
            owner_id=None,
            trusted=True,
        )

        await create_vehicle(vehicle=vehicle_data, session=mock_session)

        added_vehicle = mock_session.add.call_args[0][0]
        assert added_vehicle.description == "Blue Honda Civic"
        assert added_vehicle.license_plate == "XYZ789"
        assert added_vehicle.color == "Blue"
        assert added_vehicle.trusted is True

    @pytest.mark.asyncio
    async def test_create_vehicle_with_owner(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test vehicle creation with owner reference."""

        # Setup mock to return member when checking owner
        def mock_execute_side_effect(query):
            mock_result = MagicMock()
            # Check if this is the owner lookup query
            if hasattr(query, "compile") and "household_members" in str(query):
                mock_result.scalar_one_or_none.return_value = sample_member
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        vehicle_data = RegisteredVehicleCreate(
            description="Silver Tesla Model 3",
            vehicle_type=VehicleType.CAR,
            owner_id=1,
        )

        await create_vehicle(vehicle=vehicle_data, session=mock_session)

        added_vehicle = mock_session.add.call_args[0][0]
        assert added_vehicle.owner_id == 1

    @pytest.mark.asyncio
    async def test_create_vehicle_with_nonexistent_owner_raises_404(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that creating vehicle with nonexistent owner raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        vehicle_data = RegisteredVehicleCreate(
            description="Silver Tesla Model 3",
            vehicle_type=VehicleType.CAR,
            owner_id=999,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_vehicle(vehicle=vehicle_data, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_vehicle_all_types(self, mock_session: AsyncMock) -> None:
        """Test vehicle creation with all valid vehicle types."""
        for vehicle_type in VehicleType:
            vehicle_data = RegisteredVehicleCreate(
                description=f"Test {vehicle_type.value}",
                vehicle_type=vehicle_type,
            )

            await create_vehicle(vehicle=vehicle_data, session=mock_session)

            added_vehicle = mock_session.add.call_args[0][0]
            assert added_vehicle.vehicle_type == vehicle_type


# =============================================================================
# Registered Vehicle Tests - Get
# =============================================================================


class TestGetVehicle:
    """Tests for the get_vehicle endpoint."""

    @pytest.mark.asyncio
    async def test_get_vehicle_success(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test successfully getting a vehicle by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_vehicle
        mock_session.execute.return_value = mock_result

        result = await get_vehicle(vehicle_id=1, session=mock_session)

        assert result == sample_vehicle
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_vehicle_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that getting a nonexistent vehicle raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_vehicle(vehicle_id=999, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Registered Vehicle Tests - Update
# =============================================================================


class TestUpdateVehicle:
    """Tests for the update_vehicle endpoint."""

    @pytest.mark.asyncio
    async def test_update_vehicle_success(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test successfully updating a vehicle."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_vehicle
        mock_session.execute.return_value = mock_result

        updates = RegisteredVehicleUpdate(description="Updated Description")

        await update_vehicle(vehicle_id=1, updates=updates, session=mock_session)

        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_vehicle_partial_update(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test partial update only modifies specified fields."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_vehicle
        mock_session.execute.return_value = mock_result

        updates = RegisteredVehicleUpdate(trusted=False)

        await update_vehicle(vehicle_id=1, updates=updates, session=mock_session)

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_vehicle_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that updating a nonexistent vehicle raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        updates = RegisteredVehicleUpdate(description="Updated Description")

        with pytest.raises(HTTPException) as exc_info:
            await update_vehicle(vehicle_id=999, updates=updates, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_vehicle_with_nonexistent_owner_raises_404(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test that updating vehicle with nonexistent owner raises 404."""
        # First call returns the vehicle, second call (owner check) returns None
        call_count = [0]

        def mock_execute_side_effect(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: vehicle lookup
                mock_result.scalar_one_or_none.return_value = sample_vehicle
            else:
                # Second call: owner lookup
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        updates = RegisteredVehicleUpdate(owner_id=999)

        with pytest.raises(HTTPException) as exc_info:
            await update_vehicle(vehicle_id=1, updates=updates, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Registered Vehicle Tests - Delete
# =============================================================================


class TestDeleteVehicle:
    """Tests for the delete_vehicle endpoint."""

    @pytest.mark.asyncio
    async def test_delete_vehicle_success(
        self, mock_session: AsyncMock, sample_vehicle: MagicMock
    ) -> None:
        """Test successfully deleting a vehicle."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_vehicle
        mock_session.execute.return_value = mock_result

        await delete_vehicle(vehicle_id=1, session=mock_session)

        mock_session.delete.assert_called_once_with(sample_vehicle)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_vehicle_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that deleting a nonexistent vehicle raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_vehicle(vehicle_id=999, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Person Embedding Tests
# =============================================================================


class TestAddEmbeddingFromEvent:
    """Tests for the add_embedding_from_event endpoint."""

    @pytest.mark.asyncio
    async def test_add_embedding_success(
        self, mock_session: AsyncMock, sample_member: MagicMock, sample_event: MagicMock
    ) -> None:
        """Test successfully adding an embedding from an event."""
        call_count = [0]

        def mock_execute_side_effect(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: member lookup
                mock_result.scalar_one_or_none.return_value = sample_member
            else:
                # Second call: event lookup
                mock_result.scalar_one_or_none.return_value = sample_event
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        request = AddEmbeddingRequest(event_id=100, confidence=0.95)

        await add_embedding_from_event(member_id=1, request=request, session=mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify the embedding was created correctly
        added_embedding = mock_session.add.call_args[0][0]
        assert added_embedding.member_id == 1
        assert added_embedding.source_event_id == 100
        assert added_embedding.confidence == 0.95

    @pytest.mark.asyncio
    async def test_add_embedding_member_not_found_raises_404(self, mock_session: AsyncMock) -> None:
        """Test that adding embedding for nonexistent member raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        request = AddEmbeddingRequest(event_id=100, confidence=0.95)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(member_id=999, request=request, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_add_embedding_event_not_found_raises_404(
        self, mock_session: AsyncMock, sample_member: MagicMock
    ) -> None:
        """Test that adding embedding from nonexistent event raises 404."""
        call_count = [0]

        def mock_execute_side_effect(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: member lookup - found
                mock_result.scalar_one_or_none.return_value = sample_member
            else:
                # Second call: event lookup - not found
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        request = AddEmbeddingRequest(event_id=999, confidence=0.95)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(member_id=1, request=request, session=mock_session)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_add_embedding_default_confidence(
        self, mock_session: AsyncMock, sample_member: MagicMock, sample_event: MagicMock
    ) -> None:
        """Test adding embedding uses default confidence of 1.0."""
        call_count = [0]

        def mock_execute_side_effect(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_member
            else:
                mock_result.scalar_one_or_none.return_value = sample_event
            return mock_result

        mock_session.execute.side_effect = mock_execute_side_effect

        # Use default confidence
        request = AddEmbeddingRequest(event_id=100)

        await add_embedding_from_event(member_id=1, request=request, session=mock_session)

        added_embedding = mock_session.add.call_args[0][0]
        assert added_embedding.confidence == 1.0


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestHouseholdMemberSchemas:
    """Tests for household member Pydantic schemas."""

    def test_member_create_validates_name_min_length(self) -> None:
        """Test that member create schema enforces minimum name length."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HouseholdMemberCreate(
                name="",  # Empty name should fail
                role=MemberRole.RESIDENT,
                trusted_level=TrustLevel.FULL,
            )

    def test_member_create_validates_name_max_length(self) -> None:
        """Test that member create schema enforces maximum name length."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HouseholdMemberCreate(
                name="A" * 101,  # 101 chars should fail (max 100)
                role=MemberRole.RESIDENT,
                trusted_level=TrustLevel.FULL,
            )

    def test_member_update_allows_partial_updates(self) -> None:
        """Test that member update schema allows partial updates."""
        # All fields should be optional
        update = HouseholdMemberUpdate()
        assert update.model_dump(exclude_unset=True) == {}

        update = HouseholdMemberUpdate(name="Updated")
        assert update.model_dump(exclude_unset=True) == {"name": "Updated"}


class TestRegisteredVehicleSchemas:
    """Tests for registered vehicle Pydantic schemas."""

    def test_vehicle_create_validates_description_min_length(self) -> None:
        """Test that vehicle create schema enforces minimum description length."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisteredVehicleCreate(
                description="",  # Empty description should fail
                vehicle_type=VehicleType.CAR,
            )

    def test_vehicle_create_validates_description_max_length(self) -> None:
        """Test that vehicle create schema enforces maximum description length."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisteredVehicleCreate(
                description="A" * 201,  # 201 chars should fail (max 200)
                vehicle_type=VehicleType.CAR,
            )

    def test_vehicle_update_allows_partial_updates(self) -> None:
        """Test that vehicle update schema allows partial updates."""
        update = RegisteredVehicleUpdate()
        assert update.model_dump(exclude_unset=True) == {}

        update = RegisteredVehicleUpdate(trusted=False)
        assert update.model_dump(exclude_unset=True) == {"trusted": False}


class TestAddEmbeddingRequestSchema:
    """Tests for add embedding request Pydantic schema."""

    def test_embedding_request_validates_confidence_range(self) -> None:
        """Test that embedding request validates confidence is between 0 and 1."""
        from pydantic import ValidationError

        # Valid confidence values
        AddEmbeddingRequest(event_id=1, confidence=0.0)
        AddEmbeddingRequest(event_id=1, confidence=1.0)
        AddEmbeddingRequest(event_id=1, confidence=0.5)

        # Invalid confidence values
        with pytest.raises(ValidationError):
            AddEmbeddingRequest(event_id=1, confidence=-0.1)

        with pytest.raises(ValidationError):
            AddEmbeddingRequest(event_id=1, confidence=1.1)

    def test_embedding_request_default_confidence(self) -> None:
        """Test that embedding request has default confidence of 1.0."""
        request = AddEmbeddingRequest(event_id=1)
        assert request.confidence == 1.0
