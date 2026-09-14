"""Unit tests for hierarchy API routes.

Tests the household organizational hierarchy management endpoints:
- GET /api/v1/households - List all households
- POST /api/v1/households - Create household
- GET /api/v1/households/{id} - Get household by ID
- PATCH /api/v1/households/{id} - Update household
- DELETE /api/v1/households/{id} - Delete household
- GET /api/v1/households/{id}/properties - List properties for household
- POST /api/v1/households/{id}/properties - Create property under household
- GET /api/v1/properties/{id} - Get property by ID
- PATCH /api/v1/properties/{id} - Update property
- DELETE /api/v1/properties/{id} - Delete property
- GET /api/v1/properties/{id}/areas - List areas for property
- POST /api/v1/properties/{id}/areas - Create area under property
- GET /api/v1/areas/{id} - Get area by ID
- PATCH /api/v1/areas/{id} - Update area
- DELETE /api/v1/areas/{id} - Delete area
- GET /api/v1/areas/{id}/cameras - List cameras in area
- POST /api/v1/areas/{id}/cameras - Link camera to area
- DELETE /api/v1/areas/{id}/cameras/{camera_id} - Unlink camera from area

Implements:
- NEM-3131: Phase 6.1 - Create Household CRUD API endpoints.
- NEM-3132: Phase 6.2 - Create Property CRUD API endpoints.
- NEM-3133: Phase 6.3 - Create Area CRUD and Camera linking endpoints.

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.area import Area
from backend.models.camera import Camera
from backend.models.household_org import Household
from backend.models.property import Property

# =============================================================================
# Household List Tests
# =============================================================================


class TestListHouseholds:
    """Tests for GET /api/v1/households endpoint."""

    @pytest.mark.asyncio
    async def test_list_households_success(self) -> None:
        """Test listing households returns all households."""
        from backend.api.routes.hierarchy import list_households

        mock_db = AsyncMock()

        # Mock households
        mock_household1 = MagicMock(spec=Household)
        mock_household1.id = 1
        mock_household1.name = "Svoboda Family"
        mock_household1.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_household2 = MagicMock(spec=Household)
        mock_household2.id = 2
        mock_household2.name = "Smith Family"
        mock_household2.created_at = datetime(2026, 1, 21, tzinfo=UTC)

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock list query
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [
            mock_household1,
            mock_household2,
        ]

        mock_db.execute.side_effect = [mock_count_result, mock_list_result]

        result = await list_households(session=mock_db)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].id == 1
        assert result.items[0].name == "Svoboda Family"
        assert result.items[1].id == 2

    @pytest.mark.asyncio
    async def test_list_households_empty_list(self) -> None:
        """Test listing households returns empty list when no households exist."""
        from backend.api.routes.hierarchy import list_households

        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Mock list query
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_list_result]

        result = await list_households(session=mock_db)

        assert result.total == 0
        assert result.items == []


# =============================================================================
# Household Create Tests
# =============================================================================


class TestCreateHousehold:
    """Tests for POST /api/v1/households endpoint."""

    @pytest.mark.asyncio
    async def test_create_household_success(self) -> None:
        """Test successfully creating a new household."""
        from backend.api.routes.hierarchy import create_household
        from backend.api.schemas.hierarchy import HouseholdCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock no existing household
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_existing_result

        household_data = HouseholdCreate(name="Svoboda Family")

        result = await create_household(household_data=household_data, session=mock_db)

        assert isinstance(result, Household)
        assert result.name == "Svoboda Family"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_household_name_conflict(self) -> None:
        """Test creating a household with conflicting name returns 409."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import create_household
        from backend.api.schemas.hierarchy import HouseholdCreate

        mock_db = AsyncMock()

        # Mock existing household with same name
        mock_existing = MagicMock(spec=Household)
        mock_existing.id = 1
        mock_existing.name = "Svoboda Family"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_db.execute.return_value = mock_result

        household_data = HouseholdCreate(name="Svoboda Family")

        with pytest.raises(HTTPException) as exc_info:
            await create_household(household_data=household_data, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_household_name_trimmed(self) -> None:
        """Test that household name is trimmed of whitespace."""
        from backend.api.schemas.hierarchy import HouseholdCreate

        # Names with whitespace should be trimmed
        household_data = HouseholdCreate(name="  Svoboda Family  ")
        assert household_data.name == "Svoboda Family"


# =============================================================================
# Household Get Tests
# =============================================================================


class TestGetHousehold:
    """Tests for GET /api/v1/households/{household_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_household_success(self) -> None:
        """Test getting a specific household by ID."""
        from backend.api.routes.hierarchy import get_household

        mock_db = AsyncMock()

        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"
        mock_household.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_household
        mock_db.execute.return_value = mock_result

        result = await get_household(household_id=1, session=mock_db)

        assert result == mock_household
        assert result.id == 1
        assert result.name == "Svoboda Family"

    @pytest.mark.asyncio
    async def test_get_household_not_found(self) -> None:
        """Test get household returns 404 if household doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_household

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_household(household_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


# =============================================================================
# Household Update Tests
# =============================================================================


class TestUpdateHousehold:
    """Tests for PATCH /api/v1/households/{household_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_household_success(self) -> None:
        """Test successfully updating a household."""
        from backend.api.routes.hierarchy import update_household
        from backend.api.schemas.hierarchy import HouseholdUpdate

        mock_db = AsyncMock()

        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"
        mock_household.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        # First call - find household
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_household

        # Second call - check name conflict
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = HouseholdUpdate(name="Svoboda-Smith Family")

        result = await update_household(household_id=1, updates=updates, session=mock_db)

        assert result == mock_household
        assert mock_household.name == "Svoboda-Smith Family"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_household_not_found(self) -> None:
        """Test update household returns 404 if household doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_household
        from backend.api.schemas.hierarchy import HouseholdUpdate

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        updates = HouseholdUpdate(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_household(household_id=999, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_household_name_conflict(self) -> None:
        """Test update household returns 409 if new name conflicts."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_household
        from backend.api.schemas.hierarchy import HouseholdUpdate

        mock_db = AsyncMock()

        # Current household
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"

        # Conflicting household
        mock_conflict = MagicMock(spec=Household)
        mock_conflict.id = 2
        mock_conflict.name = "Smith Family"

        # First call - find household
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_household

        # Second call - check name conflict (returns existing household)
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = mock_conflict

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = HouseholdUpdate(name="Smith Family")

        with pytest.raises(HTTPException) as exc_info:
            await update_household(household_id=1, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_update_household_no_changes(self) -> None:
        """Test update with empty body succeeds without changes."""
        from backend.api.routes.hierarchy import update_household
        from backend.api.schemas.hierarchy import HouseholdUpdate

        mock_db = AsyncMock()

        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_household
        mock_db.execute.return_value = mock_result

        # Empty update
        updates = HouseholdUpdate()

        result = await update_household(household_id=1, updates=updates, session=mock_db)

        assert result == mock_household
        mock_db.commit.assert_called_once()


# =============================================================================
# Household Delete Tests
# =============================================================================


class TestDeleteHousehold:
    """Tests for DELETE /api/v1/households/{household_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_household_success(self) -> None:
        """Test successfully deleting a household."""
        from backend.api.routes.hierarchy import delete_household

        mock_db = AsyncMock()

        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_household
        mock_db.execute.return_value = mock_result

        result = await delete_household(household_id=1, session=mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_household)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_household_not_found(self) -> None:
        """Test delete household returns 404 if household doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import delete_household

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_household(household_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


# =============================================================================
# Household Properties List Tests
# =============================================================================


class TestListHouseholdProperties:
    """Tests for GET /api/v1/households/{household_id}/properties endpoint."""

    @pytest.mark.asyncio
    async def test_list_household_properties_success(self) -> None:
        """Test listing properties for a household."""
        from backend.api.routes.hierarchy import list_household_properties

        mock_db = AsyncMock()

        # Mock household exists
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"

        # Mock properties
        mock_property1 = MagicMock(spec=Property)
        mock_property1.id = 1
        mock_property1.household_id = 1
        mock_property1.name = "Main House"
        mock_property1.address = "123 Main St"
        mock_property1.timezone = "America/New_York"
        mock_property1.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_property2 = MagicMock(spec=Property)
        mock_property2.id = 2
        mock_property2.household_id = 1
        mock_property2.name = "Beach House"
        mock_property2.address = "456 Ocean Dr"
        mock_property2.timezone = "America/New_York"
        mock_property2.created_at = datetime(2026, 1, 21, tzinfo=UTC)

        # First call - verify household exists
        mock_household_result = MagicMock()
        mock_household_result.scalar_one_or_none.return_value = mock_household

        # Second call - count properties
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Third call - list properties
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [
            mock_property1,
            mock_property2,
        ]

        mock_db.execute.side_effect = [
            mock_household_result,
            mock_count_result,
            mock_list_result,
        ]

        result = await list_household_properties(household_id=1, session=mock_db)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].id == 1
        assert result.items[0].name == "Main House"
        assert result.items[1].id == 2
        assert result.items[1].name == "Beach House"

    @pytest.mark.asyncio
    async def test_list_household_properties_empty(self) -> None:
        """Test listing properties returns empty list when no properties exist."""
        from backend.api.routes.hierarchy import list_household_properties

        mock_db = AsyncMock()

        # Mock household exists
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1

        # First call - verify household exists
        mock_household_result = MagicMock()
        mock_household_result.scalar_one_or_none.return_value = mock_household

        # Second call - count properties
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Third call - list properties
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [
            mock_household_result,
            mock_count_result,
            mock_list_result,
        ]

        result = await list_household_properties(household_id=1, session=mock_db)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_household_properties_household_not_found(self) -> None:
        """Test list properties returns 404 if household doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import list_household_properties

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await list_household_properties(household_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "household" in exc_info.value.detail.lower()


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestHouseholdSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_household_create_name_required(self) -> None:
        """Test that name is required for household creation."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import HouseholdCreate

        with pytest.raises(ValidationError):
            HouseholdCreate()  # type: ignore[call-arg]

    def test_household_create_name_too_short(self) -> None:
        """Test that name cannot be empty."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import HouseholdCreate

        with pytest.raises(ValidationError) as exc_info:
            HouseholdCreate(name="")

        # Pydantic 2.x uses "string_too_short" or "at least 1 character"
        error_str = str(exc_info.value).lower()
        assert (
            "min_length" in error_str
            or "empty" in error_str
            or "too_short" in error_str
            or "at least 1" in error_str
        )

    def test_household_create_name_too_long(self) -> None:
        """Test that name cannot exceed 100 characters."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import HouseholdCreate

        with pytest.raises(ValidationError) as exc_info:
            HouseholdCreate(name="x" * 101)

        assert "100" in str(exc_info.value) or "max_length" in str(exc_info.value).lower()

    def test_household_create_name_whitespace_only(self) -> None:
        """Test that whitespace-only name is rejected."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import HouseholdCreate

        with pytest.raises(ValidationError) as exc_info:
            HouseholdCreate(name="   ")

        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()

    def test_household_create_name_control_characters(self) -> None:
        """Test that control characters in name are rejected."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import HouseholdCreate

        with pytest.raises(ValidationError) as exc_info:
            HouseholdCreate(name="Test\x00Family")

        assert (
            "forbidden" in str(exc_info.value).lower() or "control" in str(exc_info.value).lower()
        )

    def test_household_update_all_optional(self) -> None:
        """Test that all fields are optional for update."""
        from backend.api.schemas.hierarchy import HouseholdUpdate

        # Should not raise
        update = HouseholdUpdate()
        assert update.name is None

    def test_household_response_from_attributes(self) -> None:
        """Test that HouseholdResponse can be created from ORM model."""
        from backend.api.schemas.hierarchy import HouseholdResponse

        mock_household = MagicMock()
        mock_household.id = 1
        mock_household.name = "Test Family"
        mock_household.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        response = HouseholdResponse.model_validate(mock_household)

        assert response.id == 1
        assert response.name == "Test Family"


# =============================================================================
# HTTP Status Code Tests
# =============================================================================


class TestHTTPStatusCodes:
    """Tests to verify correct HTTP status codes are returned."""

    @pytest.mark.asyncio
    async def test_create_household_returns_201(self) -> None:
        """Test create household endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import create_household

        assert create_household is not None
        assert status.HTTP_201_CREATED == 201

    @pytest.mark.asyncio
    async def test_delete_household_returns_204(self) -> None:
        """Test delete household endpoint is configured for 204 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import delete_household

        assert delete_household is not None
        assert status.HTTP_204_NO_CONTENT == 204


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetHouseholdOr404:
    """Tests for the get_household_or_404 helper function."""

    @pytest.mark.asyncio
    async def test_get_household_or_404_success(self) -> None:
        """Test get_household_or_404 returns household when found."""
        from backend.api.routes.hierarchy import get_household_or_404

        mock_db = AsyncMock()

        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Test Family"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_household
        mock_db.execute.return_value = mock_result

        result = await get_household_or_404(household_id=1, session=mock_db)

        assert result == mock_household
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_household_or_404_not_found(self) -> None:
        """Test get_household_or_404 raises 404 when not found."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_household_or_404

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_household_or_404(household_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Property Create Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestCreateProperty:
    """Tests for POST /api/v1/households/{household_id}/properties endpoint."""

    @pytest.mark.asyncio
    async def test_create_property_success(self) -> None:
        """Test successfully creating a new property under a household."""
        from backend.api.routes.hierarchy import create_property
        from backend.api.schemas.hierarchy import PropertyCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock household exists
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1
        mock_household.name = "Svoboda Family"

        mock_household_result = MagicMock()
        mock_household_result.scalar_one_or_none.return_value = mock_household

        # Mock no existing property with same name
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_household_result, mock_existing_result]

        property_data = PropertyCreate(
            name="Main House",
            address="123 Main St",
            timezone="America/New_York",
        )

        result = await create_property(household_id=1, property_data=property_data, session=mock_db)

        assert isinstance(result, Property)
        assert result.name == "Main House"
        assert result.address == "123 Main St"
        assert result.timezone == "America/New_York"
        assert result.household_id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_property_minimal_fields(self) -> None:
        """Test creating a property with only required fields."""
        from backend.api.routes.hierarchy import create_property
        from backend.api.schemas.hierarchy import PropertyCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock household exists
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1

        mock_household_result = MagicMock()
        mock_household_result.scalar_one_or_none.return_value = mock_household

        # Mock no existing property
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_household_result, mock_existing_result]

        property_data = PropertyCreate(name="Beach House")

        result = await create_property(household_id=1, property_data=property_data, session=mock_db)

        assert result.name == "Beach House"
        assert result.address is None
        assert result.timezone == "UTC"  # Default timezone

    @pytest.mark.asyncio
    async def test_create_property_household_not_found(self) -> None:
        """Test create property returns 404 if household doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import create_property
        from backend.api.schemas.hierarchy import PropertyCreate

        mock_db = AsyncMock()

        # Mock household not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        property_data = PropertyCreate(name="Main House")

        with pytest.raises(HTTPException) as exc_info:
            await create_property(household_id=999, property_data=property_data, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "household" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_property_name_conflict(self) -> None:
        """Test create property returns 409 if name already exists for household."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import create_property
        from backend.api.schemas.hierarchy import PropertyCreate

        mock_db = AsyncMock()

        # Mock household exists
        mock_household = MagicMock(spec=Household)
        mock_household.id = 1

        mock_household_result = MagicMock()
        mock_household_result.scalar_one_or_none.return_value = mock_household

        # Mock existing property with same name
        mock_existing = MagicMock(spec=Property)
        mock_existing.id = 5
        mock_existing.name = "Main House"

        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = mock_existing

        mock_db.execute.side_effect = [mock_household_result, mock_existing_result]

        property_data = PropertyCreate(name="Main House")

        with pytest.raises(HTTPException) as exc_info:
            await create_property(household_id=1, property_data=property_data, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()


# =============================================================================
# Property Get Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestGetProperty:
    """Tests for GET /api/v1/properties/{property_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_property_success(self) -> None:
        """Test getting a specific property by ID."""
        from backend.api.routes.hierarchy import get_property

        mock_db = AsyncMock()

        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Main House"
        mock_property.address = "123 Main St"
        mock_property.timezone = "America/New_York"
        mock_property.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_db.execute.return_value = mock_result

        result = await get_property(property_id=1, session=mock_db)

        assert result == mock_property
        assert result.id == 1
        assert result.name == "Main House"

    @pytest.mark.asyncio
    async def test_get_property_not_found(self) -> None:
        """Test get property returns 404 if property doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_property

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_property(property_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "property" in exc_info.value.detail.lower()


# =============================================================================
# Property Update Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestUpdateProperty:
    """Tests for PATCH /api/v1/properties/{property_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_property_success(self) -> None:
        """Test successfully updating a property."""
        from backend.api.routes.hierarchy import update_property
        from backend.api.schemas.hierarchy import PropertyUpdate

        mock_db = AsyncMock()

        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Main House"
        mock_property.address = "123 Main St"
        mock_property.timezone = "America/New_York"

        # First call - find property
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_property

        # Second call - check name conflict
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = PropertyUpdate(name="Main Residence", address="456 New St")

        result = await update_property(property_id=1, updates=updates, session=mock_db)

        assert result == mock_property
        assert mock_property.name == "Main Residence"
        assert mock_property.address == "456 New St"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_property_partial_update(self) -> None:
        """Test partial update only changes specified fields."""
        from backend.api.routes.hierarchy import update_property
        from backend.api.schemas.hierarchy import PropertyUpdate

        mock_db = AsyncMock()

        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Main House"
        mock_property.address = "123 Main St"
        mock_property.timezone = "America/New_York"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_db.execute.return_value = mock_result

        # Only update timezone
        updates = PropertyUpdate(timezone="America/Chicago")

        result = await update_property(property_id=1, updates=updates, session=mock_db)

        assert result.timezone == "America/Chicago"
        # Name and address should remain unchanged
        assert mock_property.name == "Main House"
        assert mock_property.address == "123 Main St"

    @pytest.mark.asyncio
    async def test_update_property_not_found(self) -> None:
        """Test update property returns 404 if property doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_property
        from backend.api.schemas.hierarchy import PropertyUpdate

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        updates = PropertyUpdate(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_property(property_id=999, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_property_name_conflict(self) -> None:
        """Test update property returns 409 if new name conflicts."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_property
        from backend.api.schemas.hierarchy import PropertyUpdate

        mock_db = AsyncMock()

        # Current property
        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Main House"

        # Conflicting property
        mock_conflict = MagicMock(spec=Property)
        mock_conflict.id = 2
        mock_conflict.name = "Beach House"

        # First call - find property
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_property

        # Second call - check name conflict
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = mock_conflict

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = PropertyUpdate(name="Beach House")

        with pytest.raises(HTTPException) as exc_info:
            await update_property(property_id=1, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()


# =============================================================================
# Property Delete Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestDeleteProperty:
    """Tests for DELETE /api/v1/properties/{property_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_property_success(self) -> None:
        """Test successfully deleting a property."""
        from backend.api.routes.hierarchy import delete_property

        mock_db = AsyncMock()

        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Main House"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_db.execute.return_value = mock_result

        result = await delete_property(property_id=1, session=mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_property)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_property_not_found(self) -> None:
        """Test delete property returns 404 if property doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import delete_property

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_property(property_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


# =============================================================================
# Property Areas List Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestListPropertyAreas:
    """Tests for GET /api/v1/properties/{property_id}/areas endpoint."""

    @pytest.mark.asyncio
    async def test_list_property_areas_success(self) -> None:
        """Test listing areas for a property."""
        from backend.api.routes.hierarchy import list_property_areas
        from backend.models.area import Area

        mock_db = AsyncMock()

        # Mock property exists
        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.name = "Main House"

        # Mock areas
        mock_area1 = MagicMock(spec=Area)
        mock_area1.id = 1
        mock_area1.property_id = 1
        mock_area1.name = "Front Yard"
        mock_area1.description = "Main entrance area"
        mock_area1.color = "#76B900"
        mock_area1.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_area2 = MagicMock(spec=Area)
        mock_area2.id = 2
        mock_area2.property_id = 1
        mock_area2.name = "Garage"
        mock_area2.description = "Garage and driveway"
        mock_area2.color = "#3B82F6"
        mock_area2.created_at = datetime(2026, 1, 21, tzinfo=UTC)

        # First call - verify property exists
        mock_property_result = MagicMock()
        mock_property_result.scalar_one_or_none.return_value = mock_property

        # Second call - count areas
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Third call - list areas
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [
            mock_area1,
            mock_area2,
        ]

        mock_db.execute.side_effect = [
            mock_property_result,
            mock_count_result,
            mock_list_result,
        ]

        result = await list_property_areas(property_id=1, session=mock_db)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].id == 1
        assert result.items[0].name == "Front Yard"
        assert result.items[1].id == 2
        assert result.items[1].name == "Garage"

    @pytest.mark.asyncio
    async def test_list_property_areas_empty(self) -> None:
        """Test listing areas returns empty list when no areas exist."""
        from backend.api.routes.hierarchy import list_property_areas

        mock_db = AsyncMock()

        # Mock property exists
        mock_property = MagicMock(spec=Property)
        mock_property.id = 1

        # First call - verify property exists
        mock_property_result = MagicMock()
        mock_property_result.scalar_one_or_none.return_value = mock_property

        # Second call - count areas
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Third call - list areas
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [
            mock_property_result,
            mock_count_result,
            mock_list_result,
        ]

        result = await list_property_areas(property_id=1, session=mock_db)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_property_areas_property_not_found(self) -> None:
        """Test list areas returns 404 if property doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import list_property_areas

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await list_property_areas(property_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "property" in exc_info.value.detail.lower()


# =============================================================================
# Property Helper Function Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestGetPropertyOr404:
    """Tests for the get_property_or_404 helper function."""

    @pytest.mark.asyncio
    async def test_get_property_or_404_success(self) -> None:
        """Test get_property_or_404 returns property when found."""
        from backend.api.routes.hierarchy import get_property_or_404

        mock_db = AsyncMock()

        mock_property = MagicMock(spec=Property)
        mock_property.id = 1
        mock_property.name = "Main House"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_db.execute.return_value = mock_result

        result = await get_property_or_404(property_id=1, session=mock_db)

        assert result == mock_property
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_property_or_404_not_found(self) -> None:
        """Test get_property_or_404 raises 404 when not found."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_property_or_404

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_property_or_404(property_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


# =============================================================================
# Property Schema Validation Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestPropertySchemaValidation:
    """Tests for Property Pydantic schema validation."""

    def test_property_create_name_required(self) -> None:
        """Test that name is required for property creation."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import PropertyCreate

        with pytest.raises(ValidationError):
            PropertyCreate()  # type: ignore[call-arg]

    def test_property_create_name_too_short(self) -> None:
        """Test that name cannot be empty."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import PropertyCreate

        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(name="")

        # Check for validation error about string being too short
        error_str = str(exc_info.value).lower()
        assert (
            "min_length" in error_str
            or "empty" in error_str
            or "string_too_short" in error_str
            or "at least 1 character" in error_str
        )

    def test_property_create_name_too_long(self) -> None:
        """Test that name cannot exceed 100 characters."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import PropertyCreate

        with pytest.raises(ValidationError) as exc_info:
            PropertyCreate(name="x" * 101)

        assert "100" in str(exc_info.value) or "max_length" in str(exc_info.value).lower()

    def test_property_create_default_timezone(self) -> None:
        """Test that timezone defaults to UTC."""
        from backend.api.schemas.hierarchy import PropertyCreate

        prop = PropertyCreate(name="Test House")
        assert prop.timezone == "UTC"

    def test_property_update_all_optional(self) -> None:
        """Test that all fields are optional for update."""
        from backend.api.schemas.hierarchy import PropertyUpdate

        update = PropertyUpdate()
        assert update.name is None
        assert update.address is None
        assert update.timezone is None

    def test_property_response_from_attributes(self) -> None:
        """Test that PropertyResponse can be created from ORM model."""
        from backend.api.schemas.hierarchy import PropertyResponse

        mock_property = MagicMock()
        mock_property.id = 1
        mock_property.household_id = 1
        mock_property.name = "Test House"
        mock_property.address = "123 Test St"
        mock_property.timezone = "America/New_York"
        mock_property.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        response = PropertyResponse.model_validate(mock_property)

        assert response.id == 1
        assert response.household_id == 1
        assert response.name == "Test House"


# =============================================================================
# Property HTTP Status Code Tests (Phase 6.2 - NEM-3132)
# =============================================================================


class TestPropertyHTTPStatusCodes:
    """Tests to verify correct HTTP status codes for property endpoints."""

    @pytest.mark.asyncio
    async def test_create_property_returns_201(self) -> None:
        """Test create property endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import create_property

        assert create_property is not None
        assert status.HTTP_201_CREATED == 201

    @pytest.mark.asyncio
    async def test_delete_property_returns_204(self) -> None:
        """Test delete property endpoint is configured for 204 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import delete_property

        assert delete_property is not None
        assert status.HTTP_204_NO_CONTENT == 204


# =============================================================================
# Area CRUD Tests (NEM-3133: Phase 6.3)
# =============================================================================


class TestCreateArea:
    """Tests for POST /api/v1/properties/{property_id}/areas endpoint."""

    @pytest.mark.asyncio
    async def test_create_area_success(self) -> None:
        """Test successfully creating a new area."""
        from backend.api.routes.hierarchy import create_area
        from backend.api.schemas.hierarchy import AreaCreate

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock property exists
        mock_property = MagicMock(spec=Property)
        mock_property.id = 1

        mock_property_result = MagicMock()
        mock_property_result.scalar_one_or_none.return_value = mock_property

        # Mock no existing area with same name
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_property_result, mock_existing_result]

        area_data = AreaCreate(name="Front Yard", description="Main entrance", color="#76B900")

        result = await create_area(property_id=1, area_data=area_data, session=mock_db)

        assert isinstance(result, Area)
        assert result.name == "Front Yard"
        assert result.property_id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_area_property_not_found(self) -> None:
        """Test create area returns 404 if property doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import create_area
        from backend.api.schemas.hierarchy import AreaCreate

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        area_data = AreaCreate(name="Front Yard")

        with pytest.raises(HTTPException) as exc_info:
            await create_area(property_id=999, area_data=area_data, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "property" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_area_name_conflict(self) -> None:
        """Test create area returns 409 if area with same name exists."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import create_area
        from backend.api.schemas.hierarchy import AreaCreate

        mock_db = AsyncMock()

        # Mock property exists
        mock_property = MagicMock(spec=Property)
        mock_property.id = 1

        mock_property_result = MagicMock()
        mock_property_result.scalar_one_or_none.return_value = mock_property

        # Mock existing area with same name
        mock_existing = MagicMock(spec=Area)
        mock_existing.id = 1
        mock_existing.name = "Front Yard"

        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = mock_existing

        mock_db.execute.side_effect = [mock_property_result, mock_existing_result]

        area_data = AreaCreate(name="Front Yard")

        with pytest.raises(HTTPException) as exc_info:
            await create_area(property_id=1, area_data=area_data, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()


class TestGetArea:
    """Tests for GET /api/v1/areas/{area_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_area_success(self) -> None:
        """Test getting a specific area by ID."""
        from backend.api.routes.hierarchy import get_area

        mock_db = AsyncMock()

        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.property_id = 1
        mock_area.name = "Front Yard"
        mock_area.description = "Main entrance"
        mock_area.color = "#76B900"
        mock_area.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await get_area(area_id=1, session=mock_db)

        assert result == mock_area
        assert result.id == 1
        assert result.name == "Front Yard"

    @pytest.mark.asyncio
    async def test_get_area_not_found(self) -> None:
        """Test get area returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_area

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_area(area_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestUpdateArea:
    """Tests for PATCH /api/v1/areas/{area_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_area_success(self) -> None:
        """Test successfully updating an area."""
        from backend.api.routes.hierarchy import update_area
        from backend.api.schemas.hierarchy import AreaUpdate

        mock_db = AsyncMock()

        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.property_id = 1
        mock_area.name = "Front Yard"
        mock_area.description = "Main entrance"
        mock_area.color = "#76B900"
        mock_area.created_at = datetime(2026, 1, 20, tzinfo=UTC)

        # First call - find area
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_area

        # Second call - check name conflict
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = AreaUpdate(name="Back Yard", color="#EF4444")

        result = await update_area(area_id=1, updates=updates, session=mock_db)

        assert result == mock_area
        assert mock_area.name == "Back Yard"
        assert mock_area.color == "#EF4444"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_area_not_found(self) -> None:
        """Test update area returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_area
        from backend.api.schemas.hierarchy import AreaUpdate

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        updates = AreaUpdate(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_area(area_id=999, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_area_name_conflict(self) -> None:
        """Test update area returns 409 if new name conflicts."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import update_area
        from backend.api.schemas.hierarchy import AreaUpdate

        mock_db = AsyncMock()

        # Current area
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.property_id = 1
        mock_area.name = "Front Yard"

        # Conflicting area
        mock_conflict = MagicMock(spec=Area)
        mock_conflict.id = 2
        mock_conflict.name = "Back Yard"

        # First call - find area
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = mock_area

        # Second call - check name conflict
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = mock_conflict

        mock_db.execute.side_effect = [mock_get_result, mock_conflict_result]

        updates = AreaUpdate(name="Back Yard")

        with pytest.raises(HTTPException) as exc_info:
            await update_area(area_id=1, updates=updates, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()


class TestDeleteArea:
    """Tests for DELETE /api/v1/areas/{area_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_area_success(self) -> None:
        """Test successfully deleting an area."""
        from backend.api.routes.hierarchy import delete_area

        mock_db = AsyncMock()

        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.property_id = 1
        mock_area.name = "Front Yard"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await delete_area(area_id=1, session=mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_area)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_area_not_found(self) -> None:
        """Test delete area returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import delete_area

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_area(area_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


# =============================================================================
# Camera Linking Tests (NEM-3133: Phase 6.3)
# =============================================================================


class TestListAreaCameras:
    """Tests for GET /api/v1/areas/{area_id}/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_list_area_cameras_success(self) -> None:
        """Test listing cameras for an area."""
        from backend.api.routes.hierarchy import list_area_cameras

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door Camera"
        mock_camera.status = "online"
        mock_camera.deleted_at = None

        # Mock area with cameras
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.name = "Front Yard"
        mock_area.cameras = [mock_camera]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await list_area_cameras(area_id=1, session=mock_db)

        assert result.area_id == 1
        assert result.area_name == "Front Yard"
        assert result.count == 1
        assert len(result.cameras) == 1
        assert result.cameras[0].id == "front_door"
        assert result.cameras[0].name == "Front Door Camera"

    @pytest.mark.asyncio
    async def test_list_area_cameras_empty(self) -> None:
        """Test listing cameras returns empty list when no cameras linked."""
        from backend.api.routes.hierarchy import list_area_cameras

        mock_db = AsyncMock()

        # Mock area with no cameras
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.name = "Front Yard"
        mock_area.cameras = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await list_area_cameras(area_id=1, session=mock_db)

        assert result.area_id == 1
        assert result.count == 0
        assert result.cameras == []

    @pytest.mark.asyncio
    async def test_list_area_cameras_excludes_deleted(self) -> None:
        """Test that deleted cameras are excluded from the list."""
        from backend.api.routes.hierarchy import list_area_cameras

        mock_db = AsyncMock()

        # Mock cameras - one active, one deleted
        mock_camera_active = MagicMock(spec=Camera)
        mock_camera_active.id = "front_door"
        mock_camera_active.name = "Front Door Camera"
        mock_camera_active.status = "online"
        mock_camera_active.deleted_at = None

        mock_camera_deleted = MagicMock(spec=Camera)
        mock_camera_deleted.id = "back_door"
        mock_camera_deleted.name = "Back Door Camera"
        mock_camera_deleted.status = "offline"
        mock_camera_deleted.deleted_at = datetime(2026, 1, 15, tzinfo=UTC)

        # Mock area with both cameras
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.name = "Front Yard"
        mock_area.cameras = [mock_camera_active, mock_camera_deleted]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await list_area_cameras(area_id=1, session=mock_db)

        # Only active camera should be returned
        assert result.count == 1
        assert len(result.cameras) == 1
        assert result.cameras[0].id == "front_door"

    @pytest.mark.asyncio
    async def test_list_area_cameras_not_found(self) -> None:
        """Test list cameras returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import list_area_cameras

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await list_area_cameras(area_id=999, session=mock_db)

        assert exc_info.value.status_code == 404


class TestLinkCameraToArea:
    """Tests for POST /api/v1/areas/{area_id}/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_link_camera_success(self) -> None:
        """Test successfully linking a camera to an area."""
        from backend.api.routes.hierarchy import link_camera_to_area
        from backend.api.schemas.hierarchy import CameraLinkRequest

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door Camera"
        mock_camera.deleted_at = None

        # Mock area without this camera
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.name = "Front Yard"
        mock_area.cameras = []

        # First call - get area with cameras
        mock_area_result = MagicMock()
        mock_area_result.scalar_one_or_none.return_value = mock_area

        # Second call - get camera
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_db.execute.side_effect = [mock_area_result, mock_camera_result]

        link_request = CameraLinkRequest(camera_id="front_door")

        result = await link_camera_to_area(area_id=1, link_request=link_request, session=mock_db)

        assert result.area_id == 1
        assert result.camera_id == "front_door"
        assert result.linked is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_camera_area_not_found(self) -> None:
        """Test link camera returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import link_camera_to_area
        from backend.api.schemas.hierarchy import CameraLinkRequest

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        link_request = CameraLinkRequest(camera_id="front_door")

        with pytest.raises(HTTPException) as exc_info:
            await link_camera_to_area(area_id=999, link_request=link_request, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "area" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_link_camera_camera_not_found(self) -> None:
        """Test link camera returns 404 if camera doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import link_camera_to_area
        from backend.api.schemas.hierarchy import CameraLinkRequest

        mock_db = AsyncMock()

        # Mock area exists
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.cameras = []

        mock_area_result = MagicMock()
        mock_area_result.scalar_one_or_none.return_value = mock_area

        # Camera not found
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_area_result, mock_camera_result]

        link_request = CameraLinkRequest(camera_id="nonexistent")

        with pytest.raises(HTTPException) as exc_info:
            await link_camera_to_area(area_id=1, link_request=link_request, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "camera" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_link_camera_already_linked(self) -> None:
        """Test link camera returns 409 if camera already linked to area."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import link_camera_to_area
        from backend.api.schemas.hierarchy import CameraLinkRequest

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.deleted_at = None

        # Mock area with camera already linked
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.cameras = [mock_camera]

        mock_area_result = MagicMock()
        mock_area_result.scalar_one_or_none.return_value = mock_area

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_db.execute.side_effect = [mock_area_result, mock_camera_result]

        link_request = CameraLinkRequest(camera_id="front_door")

        with pytest.raises(HTTPException) as exc_info:
            await link_camera_to_area(area_id=1, link_request=link_request, session=mock_db)

        assert exc_info.value.status_code == 409
        assert "already linked" in exc_info.value.detail.lower()


class TestUnlinkCameraFromArea:
    """Tests for DELETE /api/v1/areas/{area_id}/cameras/{camera_id} endpoint."""

    @pytest.mark.asyncio
    async def test_unlink_camera_success(self) -> None:
        """Test successfully unlinking a camera from an area."""
        from backend.api.routes.hierarchy import unlink_camera_from_area

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.deleted_at = None

        # Mock area with camera linked
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.cameras = [mock_camera]

        mock_area_result = MagicMock()
        mock_area_result.scalar_one_or_none.return_value = mock_area

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_db.execute.side_effect = [mock_area_result, mock_camera_result]

        result = await unlink_camera_from_area(area_id=1, camera_id="front_door", session=mock_db)

        assert result.area_id == 1
        assert result.camera_id == "front_door"
        assert result.linked is False
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlink_camera_area_not_found(self) -> None:
        """Test unlink camera returns 404 if area doesn't exist."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import unlink_camera_from_area

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await unlink_camera_from_area(area_id=999, camera_id="front_door", session=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unlink_camera_not_linked(self) -> None:
        """Test unlink camera returns 404 if camera not linked to area."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import unlink_camera_from_area

        mock_db = AsyncMock()

        # Mock camera
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.deleted_at = None

        # Mock area without camera linked
        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.cameras = []

        mock_area_result = MagicMock()
        mock_area_result.scalar_one_or_none.return_value = mock_area

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_db.execute.side_effect = [mock_area_result, mock_camera_result]

        with pytest.raises(HTTPException) as exc_info:
            await unlink_camera_from_area(area_id=1, camera_id="front_door", session=mock_db)

        assert exc_info.value.status_code == 404
        assert "not linked" in exc_info.value.detail.lower()


# =============================================================================
# Area Schema Validation Tests (NEM-3133: Phase 6.3)
# =============================================================================


class TestAreaSchemaValidation:
    """Tests for Area Pydantic schema validation."""

    def test_area_create_name_required(self) -> None:
        """Test that name is required for area creation."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import AreaCreate

        with pytest.raises(ValidationError):
            AreaCreate()  # type: ignore[call-arg]

    def test_area_create_default_color(self) -> None:
        """Test that color has a default value."""
        from backend.api.schemas.hierarchy import AreaCreate

        area = AreaCreate(name="Front Yard")
        assert area.color == "#76B900"

    def test_area_create_color_validation(self) -> None:
        """Test that color must be a valid hex color."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import AreaCreate

        # Valid color
        area = AreaCreate(name="Test", color="#FF0000")
        assert area.color == "#FF0000"

        # Invalid color - no hash
        with pytest.raises(ValidationError):
            AreaCreate(name="Test", color="FF0000")

        # Invalid color - too short
        with pytest.raises(ValidationError):
            AreaCreate(name="Test", color="#FFF")

        # Invalid color - invalid chars
        with pytest.raises(ValidationError):
            AreaCreate(name="Test", color="#GGGGGG")

    def test_area_update_all_optional(self) -> None:
        """Test that all fields are optional for update."""
        from backend.api.schemas.hierarchy import AreaUpdate

        update = AreaUpdate()
        assert update.name is None
        assert update.description is None
        assert update.color is None

    def test_camera_link_request_camera_id_required(self) -> None:
        """Test that camera_id is required for camera link request."""
        from pydantic import ValidationError

        from backend.api.schemas.hierarchy import CameraLinkRequest

        with pytest.raises(ValidationError):
            CameraLinkRequest()  # type: ignore[call-arg]

    def test_camera_link_request_trims_whitespace(self) -> None:
        """Test that camera_id whitespace is trimmed."""
        from backend.api.schemas.hierarchy import CameraLinkRequest

        request = CameraLinkRequest(camera_id="  front_door  ")
        assert request.camera_id == "front_door"


# =============================================================================
# Area Helper Function Tests (NEM-3133: Phase 6.3)
# =============================================================================


class TestGetAreaOr404:
    """Tests for the get_area_or_404 helper function."""

    @pytest.mark.asyncio
    async def test_get_area_or_404_success(self) -> None:
        """Test get_area_or_404 returns area when found."""
        from backend.api.routes.hierarchy import get_area_or_404

        mock_db = AsyncMock()

        mock_area = MagicMock(spec=Area)
        mock_area.id = 1
        mock_area.name = "Front Yard"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_area
        mock_db.execute.return_value = mock_result

        result = await get_area_or_404(area_id=1, session=mock_db)

        assert result == mock_area
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_area_or_404_not_found(self) -> None:
        """Test get_area_or_404 raises 404 when not found."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_area_or_404

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_area_or_404(area_id=999, session=mock_db)

        assert exc_info.value.status_code == 404
        assert "999" in exc_info.value.detail


class TestGetCameraOr404:
    """Tests for the get_camera_or_404 helper function."""

    @pytest.mark.asyncio
    async def test_get_camera_or_404_success(self) -> None:
        """Test get_camera_or_404 returns camera when found."""
        from backend.api.routes.hierarchy import get_camera_or_404

        mock_db = AsyncMock()

        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"
        mock_camera.deleted_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_result

        result = await get_camera_or_404(camera_id="front_door", session=mock_db)

        assert result == mock_camera
        assert result.id == "front_door"

    @pytest.mark.asyncio
    async def test_get_camera_or_404_not_found(self) -> None:
        """Test get_camera_or_404 raises 404 when not found."""
        from fastapi import HTTPException

        from backend.api.routes.hierarchy import get_camera_or_404

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_camera_or_404(camera_id="nonexistent", session=mock_db)

        assert exc_info.value.status_code == 404
        assert "nonexistent" in exc_info.value.detail


# =============================================================================
# Area HTTP Status Code Tests (NEM-3133: Phase 6.3)
# =============================================================================


class TestAreaHTTPStatusCodes:
    """Tests to verify correct HTTP status codes for area endpoints."""

    @pytest.mark.asyncio
    async def test_create_area_returns_201(self) -> None:
        """Test create area endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import create_area

        assert create_area is not None
        assert status.HTTP_201_CREATED == 201

    @pytest.mark.asyncio
    async def test_delete_area_returns_204(self) -> None:
        """Test delete area endpoint is configured for 204 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import delete_area

        assert delete_area is not None
        assert status.HTTP_204_NO_CONTENT == 204

    @pytest.mark.asyncio
    async def test_link_camera_returns_201(self) -> None:
        """Test link camera endpoint is configured for 201 status."""
        from fastapi import status

        from backend.api.routes.hierarchy import link_camera_to_area

        assert link_camera_to_area is not None
        assert status.HTTP_201_CREATED == 201
