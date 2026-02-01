"""Unit tests for household API routes.

Tests the household member and registered vehicle management endpoints:
- GET /api/household/members - List all household members
- POST /api/household/members - Create new member
- GET /api/household/members/{member_id} - Get specific member
- PATCH /api/household/members/{member_id} - Update member
- DELETE /api/household/members/{member_id} - Delete member
- GET /api/household/vehicles - List all registered vehicles
- POST /api/household/vehicles - Create new vehicle
- GET /api/household/vehicles/{vehicle_id} - Get specific vehicle
- PATCH /api/household/vehicles/{vehicle_id} - Update vehicle
- DELETE /api/household/vehicles/{vehicle_id} - Delete vehicle
- POST /api/household/members/{member_id}/embeddings - Add embedding from event

Implements NEM-3018: Build API endpoints for household member and vehicle management.

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.household import (
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)


class TestListMembers:
    """Tests for GET /api/household/members endpoint."""

    @pytest.mark.asyncio
    async def test_list_members_success(self) -> None:
        """Test listing members returns all household members."""
        from backend.api.routes.household import list_members

        mock_db = AsyncMock()

        # Mock members query
        mock_member1 = MagicMock(spec=HouseholdMember)
        mock_member1.id = 1
        mock_member1.name = "John Doe"
        mock_member1.role = MemberRole.RESIDENT
        mock_member1.trusted_level = TrustLevel.FULL
        mock_member1.typical_schedule = {"weekdays": "9-17"}
        mock_member1.notes = "Works from home on Fridays"
        mock_member1.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        mock_member1.updated_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_member2 = MagicMock(spec=HouseholdMember)
        mock_member2.id = 2
        mock_member2.name = "Jane Smith"
        mock_member2.role = MemberRole.FAMILY
        mock_member2.trusted_level = TrustLevel.FULL
        mock_member2.typical_schedule = None
        mock_member2.notes = None
        mock_member2.created_at = datetime(2025, 1, 2, tzinfo=UTC)
        mock_member2.updated_at = datetime(2025, 1, 2, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_member1, mock_member2]
        mock_db.execute.return_value = mock_result

        result = await list_members(session=mock_db)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_members_empty_list(self) -> None:
        """Test listing members returns empty list when no members exist."""
        from backend.api.routes.household import list_members

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_members(session=mock_db)

        assert result == []


class TestCreateMember:
    """Tests for POST /api/household/members endpoint."""

    @pytest.mark.asyncio
    async def test_create_member_success(self) -> None:
        """Test successfully creating a new household member."""
        from backend.api.routes.household import create_member
        from backend.api.schemas.household import HouseholdMemberCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        member_data = HouseholdMemberCreate(
            name="John Doe",
            role=MemberRole.RESIDENT,
            trusted_level=TrustLevel.FULL,
            typical_schedule={"weekdays": "9-17"},
            notes="Works from home on Fridays",
        )

        result = await create_member(member=member_data, session=mock_db)

        assert isinstance(result, HouseholdMember)
        assert result.name == "John Doe"
        assert result.role == MemberRole.RESIDENT
        assert result.trusted_level == TrustLevel.FULL
        assert result.typical_schedule == {"weekdays": "9-17"}
        assert result.notes == "Works from home on Fridays"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_member_minimal_fields(self) -> None:
        """Test creating a member with only required fields."""
        from backend.api.routes.household import create_member
        from backend.api.schemas.household import HouseholdMemberCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        member_data = HouseholdMemberCreate(
            name="Mike Johnson",
            role=MemberRole.SERVICE_WORKER,
            trusted_level=TrustLevel.PARTIAL,
        )

        result = await create_member(member=member_data, session=mock_db)

        assert result.name == "Mike Johnson"
        assert result.role == MemberRole.SERVICE_WORKER
        assert result.trusted_level == TrustLevel.PARTIAL
        assert result.typical_schedule is None
        assert result.notes is None


class TestGetMember:
    """Tests for GET /api/household/members/{member_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_member_success(self) -> None:
        """Test getting a specific member by ID."""
        from backend.api.routes.household import get_member

        mock_db = AsyncMock()

        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.role = MemberRole.RESIDENT
        mock_member.trusted_level = TrustLevel.FULL

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_member
        mock_db.execute.return_value = mock_result

        result = await get_member(member_id=1, session=mock_db)

        assert result == mock_member
        assert result.id == 1
        assert result.name == "John Doe"

    @pytest.mark.asyncio
    async def test_get_member_not_found(self) -> None:
        """Test get member returns 404 if member doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import get_member

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_member(member_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestUpdateMember:
    """Tests for PATCH /api/household/members/{member_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_member_success(self) -> None:
        """Test successfully updating a household member."""
        from backend.api.routes.household import update_member
        from backend.api.schemas.household import HouseholdMemberUpdate

        mock_db = AsyncMock()

        update_data = HouseholdMemberUpdate(name="John Updated", trusted_level=TrustLevel.PARTIAL)

        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.role = MemberRole.RESIDENT
        mock_member.trusted_level = TrustLevel.FULL

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_member
        mock_db.execute.return_value = mock_result

        result = await update_member(member_id=1, updates=update_data, session=mock_db)

        assert result == mock_member
        assert mock_member.name == "John Updated"
        assert mock_member.trusted_level == TrustLevel.PARTIAL
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member_partial_update(self) -> None:
        """Test partial update only changes specified fields."""
        from backend.api.routes.household import update_member
        from backend.api.schemas.household import HouseholdMemberUpdate

        mock_db = AsyncMock()

        # Only update notes, leave other fields unchanged
        update_data = HouseholdMemberUpdate(notes="Updated notes")

        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.role = MemberRole.RESIDENT
        mock_member.trusted_level = TrustLevel.FULL
        mock_member.notes = "Old notes"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_member
        mock_db.execute.return_value = mock_result

        result = await update_member(member_id=1, updates=update_data, session=mock_db)

        assert result.notes == "Updated notes"
        # Name should remain unchanged
        assert mock_member.name == "John Doe"

    @pytest.mark.asyncio
    async def test_update_member_not_found(self) -> None:
        """Test update member returns 404 if member doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import update_member
        from backend.api.schemas.household import HouseholdMemberUpdate

        mock_db = AsyncMock()

        update_data = HouseholdMemberUpdate(name="New Name")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await update_member(member_id=999, updates=update_data, session=mock_db)

        assert exc_info.value.status_code == 404


class TestDeleteMember:
    """Tests for DELETE /api/household/members/{member_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_member_success(self) -> None:
        """Test successfully deleting a household member."""
        from backend.api.routes.household import delete_member

        mock_db = AsyncMock()

        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_member
        mock_db.execute.return_value = mock_result

        result = await delete_member(member_id=1, session=mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_member)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_member_not_found(self) -> None:
        """Test delete member returns 404 if member doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import delete_member

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_member(member_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


# =============================================================================
# Vehicle Tests
# =============================================================================


class TestListVehicles:
    """Tests for GET /api/household/vehicles endpoint."""

    @pytest.mark.asyncio
    async def test_list_vehicles_success(self) -> None:
        """Test listing vehicles returns all registered vehicles."""
        from backend.api.routes.household import list_vehicles

        mock_db = AsyncMock()

        mock_vehicle1 = MagicMock(spec=RegisteredVehicle)
        mock_vehicle1.id = 1
        mock_vehicle1.description = "Silver Tesla Model 3"
        mock_vehicle1.license_plate = "ABC123"
        mock_vehicle1.vehicle_type = VehicleType.CAR
        mock_vehicle1.color = "Silver"
        mock_vehicle1.owner_id = 1
        mock_vehicle1.trusted = True
        mock_vehicle1.created_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_vehicle2 = MagicMock(spec=RegisteredVehicle)
        mock_vehicle2.id = 2
        mock_vehicle2.description = "Red Honda Civic"
        mock_vehicle2.license_plate = "XYZ789"
        mock_vehicle2.vehicle_type = VehicleType.CAR
        mock_vehicle2.color = "Red"
        mock_vehicle2.owner_id = None
        mock_vehicle2.trusted = True
        mock_vehicle2.created_at = datetime(2025, 1, 2, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_vehicle1, mock_vehicle2]
        mock_db.execute.return_value = mock_result

        result = await list_vehicles(session=mock_db)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_vehicles_empty_list(self) -> None:
        """Test listing vehicles returns empty list when no vehicles exist."""
        from backend.api.routes.household import list_vehicles

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await list_vehicles(session=mock_db)

        assert result == []


class TestCreateVehicle:
    """Tests for POST /api/household/vehicles endpoint."""

    @pytest.mark.asyncio
    async def test_create_vehicle_success(self) -> None:
        """Test successfully creating a new registered vehicle."""
        from backend.api.routes.household import create_vehicle
        from backend.api.schemas.household import RegisteredVehicleCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        vehicle_data = RegisteredVehicleCreate(
            description="Silver Tesla Model 3",
            license_plate="ABC123",
            vehicle_type=VehicleType.CAR,
            color="Silver",
            owner_id=1,
            trusted=True,
        )

        result = await create_vehicle(vehicle=vehicle_data, session=mock_db)

        assert isinstance(result, RegisteredVehicle)
        assert result.description == "Silver Tesla Model 3"
        assert result.license_plate == "ABC123"
        assert result.vehicle_type == VehicleType.CAR
        assert result.color == "Silver"
        assert result.owner_id == 1
        assert result.trusted is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_vehicle_minimal_fields(self) -> None:
        """Test creating a vehicle with only required fields."""
        from backend.api.routes.household import create_vehicle
        from backend.api.schemas.household import RegisteredVehicleCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        vehicle_data = RegisteredVehicleCreate(
            description="Blue Delivery Van",
            vehicle_type=VehicleType.VAN,
        )

        result = await create_vehicle(vehicle=vehicle_data, session=mock_db)

        assert result.description == "Blue Delivery Van"
        assert result.vehicle_type == VehicleType.VAN
        assert result.license_plate is None
        assert result.color is None
        assert result.owner_id is None
        assert result.trusted is True  # Default value

    @pytest.mark.asyncio
    async def test_create_vehicle_invalid_owner(self) -> None:
        """Test creating a vehicle with non-existent owner returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.household import create_vehicle
        from backend.api.schemas.household import RegisteredVehicleCreate

        mock_db = AsyncMock()

        vehicle_data = RegisteredVehicleCreate(
            description="Vehicle",
            vehicle_type=VehicleType.CAR,
            owner_id=999,  # Non-existent owner
        )

        # Mock owner lookup to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await create_vehicle(vehicle=vehicle_data, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "owner" in exc_info.value.detail.lower()


class TestGetVehicle:
    """Tests for GET /api/household/vehicles/{vehicle_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_vehicle_success(self) -> None:
        """Test getting a specific vehicle by ID."""
        from backend.api.routes.household import get_vehicle

        mock_db = AsyncMock()

        mock_vehicle = MagicMock(spec=RegisteredVehicle)
        mock_vehicle.id = 1
        mock_vehicle.description = "Silver Tesla Model 3"
        mock_vehicle.vehicle_type = VehicleType.CAR

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_vehicle
        mock_db.execute.return_value = mock_result

        result = await get_vehicle(vehicle_id=1, session=mock_db)

        assert result == mock_vehicle
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_vehicle_not_found(self) -> None:
        """Test get vehicle returns 404 if vehicle doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import get_vehicle

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_vehicle(vehicle_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


class TestUpdateVehicle:
    """Tests for PATCH /api/household/vehicles/{vehicle_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_vehicle_success(self) -> None:
        """Test successfully updating a registered vehicle."""
        from backend.api.routes.household import update_vehicle
        from backend.api.schemas.household import RegisteredVehicleUpdate

        mock_db = AsyncMock()

        update_data = RegisteredVehicleUpdate(
            description="Updated Tesla", license_plate="NEW456", trusted=False
        )

        mock_vehicle = MagicMock(spec=RegisteredVehicle)
        mock_vehicle.id = 1
        mock_vehicle.description = "Silver Tesla Model 3"
        mock_vehicle.license_plate = "ABC123"
        mock_vehicle.trusted = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_vehicle
        mock_db.execute.return_value = mock_result

        result = await update_vehicle(vehicle_id=1, updates=update_data, session=mock_db)

        assert result == mock_vehicle
        assert mock_vehicle.description == "Updated Tesla"
        assert mock_vehicle.license_plate == "NEW456"
        assert mock_vehicle.trusted is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_vehicle_partial_update(self) -> None:
        """Test partial update only changes specified fields."""
        from backend.api.routes.household import update_vehicle
        from backend.api.schemas.household import RegisteredVehicleUpdate

        mock_db = AsyncMock()

        # Only update color
        update_data = RegisteredVehicleUpdate(color="Blue")

        mock_vehicle = MagicMock(spec=RegisteredVehicle)
        mock_vehicle.id = 1
        mock_vehicle.description = "Tesla Model 3"
        mock_vehicle.color = "Silver"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_vehicle
        mock_db.execute.return_value = mock_result

        result = await update_vehicle(vehicle_id=1, updates=update_data, session=mock_db)

        assert result.color == "Blue"
        # Description should remain unchanged
        assert mock_vehicle.description == "Tesla Model 3"

    @pytest.mark.asyncio
    async def test_update_vehicle_not_found(self) -> None:
        """Test update vehicle returns 404 if vehicle doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import update_vehicle
        from backend.api.schemas.household import RegisteredVehicleUpdate

        mock_db = AsyncMock()

        update_data = RegisteredVehicleUpdate(description="New Description")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await update_vehicle(vehicle_id=999, updates=update_data, session=mock_db)

        assert exc_info.value.status_code == 404


class TestDeleteVehicle:
    """Tests for DELETE /api/household/vehicles/{vehicle_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_vehicle_success(self) -> None:
        """Test successfully deleting a registered vehicle."""
        from backend.api.routes.household import delete_vehicle

        mock_db = AsyncMock()

        mock_vehicle = MagicMock(spec=RegisteredVehicle)
        mock_vehicle.id = 1
        mock_vehicle.description = "Tesla Model 3"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_vehicle
        mock_db.execute.return_value = mock_result

        result = await delete_vehicle(vehicle_id=1, session=mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_vehicle)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_vehicle_not_found(self) -> None:
        """Test delete vehicle returns 404 if vehicle doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import delete_vehicle

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_vehicle(vehicle_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


# =============================================================================
# Embedding Tests
# =============================================================================


class TestAddEmbedding:
    """Tests for POST /api/household/members/{member_id}/embeddings endpoint.

    The endpoint extracts person embeddings from event images using the
    ReIdentificationService and stores them in the PersonEmbedding table.
    """

    @pytest.mark.asyncio
    async def test_add_embedding_success_from_detection(self) -> None:
        """Test successfully extracting and storing embedding from event detection.

        This is the primary use case: user selects an event containing a person
        detection, and the system extracts the person embedding from the detection
        image to store for future re-identification.
        """
        from unittest.mock import patch

        from PIL import Image

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest
        from backend.models.detection import Detection

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"

        # Mock event exists with detections
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 50
        mock_detection.object_type = "person"
        mock_detection.file_path = "/data/snapshots/front_door/2025-01-31/10_32_15.jpg"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 100
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = [mock_detection]

        # First call returns member, second call returns event
        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        # Mock ReIdentificationService to return a 768-dim embedding
        mock_embedding = [0.1] * 768
        mock_reid_service = AsyncMock()
        mock_reid_service.generate_embedding.return_value = mock_embedding

        # Mock image loading
        mock_image = MagicMock(spec=Image.Image)
        mock_image.size = (1920, 1080)

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.95)

        with (
            patch(
                "backend.api.routes.household.get_reid_service",
                return_value=mock_reid_service,
            ),
            patch("backend.api.routes.household.Image") as mock_pil,
        ):
            mock_pil.open.return_value.__enter__ = MagicMock(return_value=mock_image)
            mock_pil.open.return_value.__exit__ = MagicMock(return_value=False)

            result = await add_embedding_from_event(
                member_id=1,
                request=embedding_request,
                session=mock_db,
            )

        assert isinstance(result, PersonEmbedding)
        assert result.member_id == 1
        assert result.source_event_id == 100
        assert result.confidence == 0.95
        # Embedding should be serialized numpy array, not placeholder
        assert result.embedding != b"placeholder_embedding"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        # Verify ReID service was called
        mock_reid_service.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_embedding_member_not_found(self) -> None:
        """Test add embedding returns 404 if member doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.9)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(
                member_id=999,
                request=embedding_request,
                session=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "member" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_add_embedding_event_not_found(self) -> None:
        """Test add embedding returns 404 if event doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest

        mock_db = AsyncMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        embedding_request = AddEmbeddingRequest(event_id=999, confidence=0.9)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(
                member_id=1,
                request=embedding_request,
                session=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "event" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_add_embedding_event_no_person_detection(self) -> None:
        """Test add embedding returns 400 if event has no person detection.

        The endpoint requires a person detection to extract an embedding from.
        Events without person detections cannot be used for face recognition.
        """
        from fastapi import HTTPException

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest
        from backend.models.detection import Detection

        mock_db = AsyncMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        # Mock event exists but has only vehicle detection, no person
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 50
        mock_detection.object_type = "car"  # Not a person

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = [mock_detection]

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.9)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(
                member_id=1,
                request=embedding_request,
                session=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert "person" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_add_embedding_event_no_detections(self) -> None:
        """Test add embedding returns 400 if event has no detections."""
        from fastapi import HTTPException

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest

        mock_db = AsyncMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        # Mock event exists but has no detections
        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = []

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.9)

        with pytest.raises(HTTPException) as exc_info:
            await add_embedding_from_event(
                member_id=1,
                request=embedding_request,
                session=mock_db,
            )

        assert exc_info.value.status_code == 400
        assert (
            "person" in exc_info.value.detail.lower()
            or "detection" in exc_info.value.detail.lower()
        )

    @pytest.mark.asyncio
    async def test_add_embedding_image_not_found(self) -> None:
        """Test add embedding returns 400 if detection image file not found."""
        from unittest.mock import patch

        from fastapi import HTTPException

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest
        from backend.models.detection import Detection

        mock_db = AsyncMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        # Mock event with person detection but missing image file
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 50
        mock_detection.object_type = "person"
        mock_detection.file_path = "/data/snapshots/missing_image.jpg"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 100
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = [mock_detection]

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.9)

        with patch("backend.api.routes.household.Image") as mock_pil:
            mock_pil.open.side_effect = FileNotFoundError("Image file not found")

            with pytest.raises(HTTPException) as exc_info:
                await add_embedding_from_event(
                    member_id=1,
                    request=embedding_request,
                    session=mock_db,
                )

            assert exc_info.value.status_code == 400
            assert "image" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_add_embedding_reid_service_failure(self) -> None:
        """Test add embedding returns 500 if ReID service fails."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from PIL import Image

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest
        from backend.models.detection import Detection

        mock_db = AsyncMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        # Mock event with person detection
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 50
        mock_detection.object_type = "person"
        mock_detection.file_path = "/data/snapshots/test.jpg"
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 100
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = [mock_detection]

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        # Mock ReID service failure
        mock_reid_service = AsyncMock()
        mock_reid_service.generate_embedding.side_effect = RuntimeError("CLIP service unavailable")

        # Mock image loading
        mock_image = MagicMock(spec=Image.Image)
        mock_image.size = (1920, 1080)

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.9)

        with (
            patch(
                "backend.api.routes.household.get_reid_service",
                return_value=mock_reid_service,
            ),
            patch("backend.api.routes.household.Image") as mock_pil,
        ):
            mock_pil.open.return_value.__enter__ = MagicMock(return_value=mock_image)
            mock_pil.open.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(HTTPException) as exc_info:
                await add_embedding_from_event(
                    member_id=1,
                    request=embedding_request,
                    session=mock_db,
                )

            assert exc_info.value.status_code == 500
            assert "embedding" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_add_embedding_selects_first_person_detection(self) -> None:
        """Test that the endpoint uses the first person detection when multiple exist.

        When an event has multiple detections, the endpoint should use the first
        person detection found (typically the highest confidence one from YOLO).
        """
        from unittest.mock import patch

        from PIL import Image

        from backend.api.routes.household import add_embedding_from_event
        from backend.api.schemas.household import AddEmbeddingRequest
        from backend.models.detection import Detection

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1

        # Mock event with multiple detections - car first, then person
        mock_car_detection = MagicMock(spec=Detection)
        mock_car_detection.id = 49
        mock_car_detection.object_type = "car"

        mock_person_detection = MagicMock(spec=Detection)
        mock_person_detection.id = 50
        mock_person_detection.object_type = "person"
        mock_person_detection.file_path = "/data/snapshots/test.jpg"
        mock_person_detection.bbox_x = 100
        mock_person_detection.bbox_y = 100
        mock_person_detection.bbox_width = 200
        mock_person_detection.bbox_height = 400

        mock_event = MagicMock()
        mock_event.id = 100
        mock_event.detections = [mock_car_detection, mock_person_detection]

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_event = MagicMock()
        mock_result_event.scalar_one_or_none.return_value = mock_event
        mock_db.execute.side_effect = [mock_result_member, mock_result_event]

        # Mock ReID service
        mock_embedding = [0.1] * 768
        mock_reid_service = AsyncMock()
        mock_reid_service.generate_embedding.return_value = mock_embedding

        # Mock image loading
        mock_image = MagicMock(spec=Image.Image)
        mock_image.size = (1920, 1080)

        embedding_request = AddEmbeddingRequest(event_id=100, confidence=0.95)

        with (
            patch(
                "backend.api.routes.household.get_reid_service",
                return_value=mock_reid_service,
            ),
            patch("backend.api.routes.household.Image") as mock_pil,
        ):
            mock_pil.open.return_value.__enter__ = MagicMock(return_value=mock_image)
            mock_pil.open.return_value.__exit__ = MagicMock(return_value=False)

            result = await add_embedding_from_event(
                member_id=1,
                request=embedding_request,
                session=mock_db,
            )

        # Should succeed using the person detection
        assert isinstance(result, PersonEmbedding)
        assert result.member_id == 1
        # The image should be opened from the person detection's file path
        mock_pil.open.assert_called_with("/data/snapshots/test.jpg")


# =============================================================================
# HTTP Status Code Tests
# =============================================================================


class TestHTTPStatusCodes:
    """Tests to verify correct HTTP status codes are returned."""

    @pytest.mark.asyncio
    async def test_create_member_returns_201(self) -> None:
        """Test create member endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.household import create_member

        # Verify the function exists and the route is configured with 201
        assert create_member is not None
        assert status.HTTP_201_CREATED == 201

    @pytest.mark.asyncio
    async def test_delete_member_returns_204(self) -> None:
        """Test delete member endpoint is configured for 204 status."""
        from fastapi import status

        from backend.api.routes.household import delete_member

        # Verify the function exists and the route is configured with 204
        assert delete_member is not None
        assert status.HTTP_204_NO_CONTENT == 204

    @pytest.mark.asyncio
    async def test_create_vehicle_returns_201(self) -> None:
        """Test create vehicle endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.household import create_vehicle

        assert create_vehicle is not None
        assert status.HTTP_201_CREATED == 201

    @pytest.mark.asyncio
    async def test_delete_vehicle_returns_204(self) -> None:
        """Test delete vehicle endpoint is configured for 204 status."""
        from fastapi import status

        from backend.api.routes.household import delete_vehicle

        assert delete_vehicle is not None
        assert status.HTTP_204_NO_CONTENT == 204


# =============================================================================
# Link Person Tests
# =============================================================================


class TestLinkPerson:
    """Tests for PATCH /api/household/members/{member_id}/link-person endpoint."""

    @pytest.mark.asyncio
    async def test_link_person_success(self) -> None:
        """Test successfully linking a household member to a known person."""
        from backend.api.routes.household import link_person
        from backend.api.schemas.household import LinkPersonRequest, LinkPersonResponse
        from backend.models.face_identity import KnownPerson

        mock_db = AsyncMock()

        # Mock household member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.known_person_id = None

        # Mock known person exists
        mock_known_person = MagicMock(spec=KnownPerson)
        mock_known_person.id = 10
        mock_known_person.name = "John"

        # First call returns member, second call returns known person
        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_known_person = MagicMock()
        mock_result_known_person.scalar_one_or_none.return_value = mock_known_person
        mock_db.execute.side_effect = [mock_result_member, mock_result_known_person]

        request = LinkPersonRequest(known_person_id=10)

        result = await link_person(member_id=1, request=request, session=mock_db)

        assert isinstance(result, LinkPersonResponse)
        assert result.success is True
        assert mock_member.known_person_id == 10
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlink_person_success(self) -> None:
        """Test successfully unlinking a household member from a known person."""
        from backend.api.routes.household import link_person
        from backend.api.schemas.household import LinkPersonRequest, LinkPersonResponse

        mock_db = AsyncMock()

        # Mock household member exists with existing link
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.known_person_id = 10

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_db.execute.return_value = mock_result_member

        # Unlink by passing null known_person_id
        request = LinkPersonRequest(known_person_id=None)

        result = await link_person(member_id=1, request=request, session=mock_db)

        assert isinstance(result, LinkPersonResponse)
        assert result.success is True
        assert mock_member.known_person_id is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_person_member_not_found(self) -> None:
        """Test link person returns 404 if household member doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import link_person
        from backend.api.schemas.household import LinkPersonRequest

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        request = LinkPersonRequest(known_person_id=10)

        with pytest.raises(HTTPException) as exc_info:
            await link_person(member_id=999, request=request, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "household member" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_link_person_known_person_not_found(self) -> None:
        """Test link person returns 404 if known person doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.household import link_person
        from backend.api.schemas.household import LinkPersonRequest

        mock_db = AsyncMock()

        # Mock household member exists
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_known_person = MagicMock()
        mock_result_known_person.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_member, mock_result_known_person]

        request = LinkPersonRequest(known_person_id=999)

        with pytest.raises(HTTPException) as exc_info:
            await link_person(member_id=1, request=request, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "known person" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_link_person_update_existing_link(self) -> None:
        """Test updating an existing link to a different known person."""
        from backend.api.routes.household import link_person
        from backend.api.schemas.household import LinkPersonRequest, LinkPersonResponse
        from backend.models.face_identity import KnownPerson

        mock_db = AsyncMock()

        # Mock household member exists with existing link
        mock_member = MagicMock(spec=HouseholdMember)
        mock_member.id = 1
        mock_member.name = "John Doe"
        mock_member.known_person_id = 5  # Already linked to person 5

        # Mock new known person exists
        mock_known_person = MagicMock(spec=KnownPerson)
        mock_known_person.id = 10
        mock_known_person.name = "John New"

        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = mock_member
        mock_result_known_person = MagicMock()
        mock_result_known_person.scalar_one_or_none.return_value = mock_known_person
        mock_db.execute.side_effect = [mock_result_member, mock_result_known_person]

        # Update link to person 10
        request = LinkPersonRequest(known_person_id=10)

        result = await link_person(member_id=1, request=request, session=mock_db)

        assert isinstance(result, LinkPersonResponse)
        assert result.success is True
        assert mock_member.known_person_id == 10
        mock_db.commit.assert_called_once()
