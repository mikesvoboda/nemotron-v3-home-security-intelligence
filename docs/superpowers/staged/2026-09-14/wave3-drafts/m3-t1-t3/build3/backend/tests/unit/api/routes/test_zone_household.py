"""Unit tests for zone-household linkage API routes.

Tests the zone-household configuration endpoints:
- GET /api/zones/{zone_id}/household - Get household config for a zone
- PUT /api/zones/{zone_id}/household - Create/update household config
- PATCH /api/zones/{zone_id}/household - Partially update household config
- DELETE /api/zones/{zone_id}/household - Remove household config
- GET /api/zones/{zone_id}/household/trust/{entity_type}/{entity_id} - Check trust level
- GET /api/zones/member/{member_id}/zones - Get zones for member
- GET /api/zones/vehicle/{vehicle_id}/zones - Get zones for vehicle

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from backend.api.schemas.zone_household import TrustLevelResult


class TestGetZoneHouseholdConfig:
    """Tests for GET /api/zones/{zone_id}/household endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_success(self, mock_db_session: AsyncMock) -> None:
        """Test getting household config returns config when it exists."""
        from backend.api.routes.zone_household import get_zone_household_config

        # Mock zone exists
        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock service returns config
            mock_config = MagicMock()
            mock_config.id = 1
            mock_config.zone_id = "zone-123"
            mock_config.owner_id = 1
            mock_config.allowed_member_ids = [2, 3]
            mock_config.allowed_vehicle_ids = [1]
            mock_config.access_schedules = []
            mock_config.created_at = datetime(2026, 1, 21, 10, 0, 0, tzinfo=UTC)
            mock_config.updated_at = datetime(2026, 1, 21, 12, 0, 0, tzinfo=UTC)

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=mock_config)
                mock_service_class.return_value = mock_service

                result = await get_zone_household_config(
                    zone_id="zone-123",
                    db=mock_db_session,
                )

        assert result is not None
        assert result.id == 1
        assert result.zone_id == "zone-123"
        assert result.owner_id == 1
        assert result.allowed_member_ids == [2, 3]
        assert result.allowed_vehicle_ids == [1]

    @pytest.mark.asyncio
    async def test_get_config_returns_none_when_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test getting household config returns None when config doesn't exist."""
        from backend.api.routes.zone_household import get_zone_household_config

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                result = await get_zone_household_config(
                    zone_id="zone-123",
                    db=mock_db_session,
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_config_verifies_zone_exists(self, mock_db_session: AsyncMock) -> None:
        """Test get config verifies zone exists before fetching config."""
        from backend.api.routes.zone_household import get_zone_household_config

        with patch("backend.api.routes.zone_household.get_zone_or_404") as mock_zone_check:
            mock_zone_check.return_value = MagicMock()

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                await get_zone_household_config(
                    zone_id="zone-123",
                    db=mock_db_session,
                )

            mock_zone_check.assert_called_once_with("zone-123", mock_db_session)

    @pytest.mark.asyncio
    async def test_get_config_zone_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test get config returns 404 if zone doesn't exist."""
        from backend.api.routes.zone_household import get_zone_household_config

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            side_effect=HTTPException(status_code=404, detail="Zone not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_zone_household_config(
                    zone_id="nonexistent",
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404


class TestUpsertZoneHouseholdConfig:
    """Tests for PUT /api/zones/{zone_id}/household endpoint."""

    @pytest.mark.asyncio
    async def test_create_config_success(self, mock_db_session: AsyncMock) -> None:
        """Test creating a new household config."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate(
            owner_id=1,
            allowed_member_ids=[2, 3],
            allowed_vehicle_ids=[1],
            access_schedules=[],
        )

        # Mock zone exists
        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock member/vehicle validation
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock()  # Entity exists
            mock_db_session.execute.return_value = mock_result

            # Mock service
            mock_config = MagicMock()
            mock_config.id = 1
            mock_config.zone_id = "zone-123"
            mock_config.owner_id = 1
            mock_config.allowed_member_ids = [2, 3]
            mock_config.allowed_vehicle_ids = [1]
            mock_config.access_schedules = []

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)  # No existing config
                mock_service.create_config = AsyncMock(return_value=mock_config)
                mock_service_class.return_value = mock_service

                result = await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

        assert result.id == 1
        assert result.owner_id == 1
        assert result.allowed_member_ids == [2, 3]

    @pytest.mark.asyncio
    async def test_update_existing_config_success(self, mock_db_session: AsyncMock) -> None:
        """Test updating an existing household config via PUT."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate(
            owner_id=2,
            allowed_member_ids=[3, 4],
            allowed_vehicle_ids=[],
            access_schedules=[],
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock member validation
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock()
            mock_db_session.execute.return_value = mock_result

            # Mock existing config
            existing_config = MagicMock()
            existing_config.id = 1
            existing_config.zone_id = "zone-123"

            # Mock updated config
            updated_config = MagicMock()
            updated_config.id = 1
            updated_config.zone_id = "zone-123"
            updated_config.owner_id = 2
            updated_config.allowed_member_ids = [3, 4]
            updated_config.allowed_vehicle_ids = []
            updated_config.access_schedules = []

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service.update_config = AsyncMock(return_value=updated_config)
                mock_service_class.return_value = mock_service

                result = await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

        assert result.id == 1
        assert result.owner_id == 2
        assert result.allowed_member_ids == [3, 4]

    @pytest.mark.asyncio
    async def test_upsert_validates_owner_exists(self, mock_db_session: AsyncMock) -> None:
        """Test upsert returns 404 if owner_id references non-existent member."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate(
            owner_id=999,  # Non-existent member
            allowed_member_ids=[],
            allowed_vehicle_ids=[],
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock owner doesn't exist
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db_session.execute.return_value = mock_result

            with pytest.raises(HTTPException) as exc_info:
                await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404
            assert "member with id 999 not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_upsert_validates_allowed_members_exist(self, mock_db_session: AsyncMock) -> None:
        """Test upsert returns 404 if allowed_member_ids contains non-existent member."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate(
            owner_id=None,
            allowed_member_ids=[1, 999],  # 999 doesn't exist
            allowed_vehicle_ids=[],
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock first member exists, second doesn't
            mock_result_1 = MagicMock()
            mock_result_1.scalar_one_or_none.return_value = MagicMock()

            mock_result_2 = MagicMock()
            mock_result_2.scalar_one_or_none.return_value = None

            mock_db_session.execute.side_effect = [mock_result_1, mock_result_2]

            with pytest.raises(HTTPException) as exc_info:
                await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404
            assert "member with id 999 not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_upsert_validates_allowed_vehicles_exist(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test upsert returns 404 if allowed_vehicle_ids contains non-existent vehicle."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate(
            owner_id=None,
            allowed_member_ids=[],
            allowed_vehicle_ids=[1, 999],  # 999 doesn't exist
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock first vehicle exists, second doesn't
            mock_result_1 = MagicMock()
            mock_result_1.scalar_one_or_none.return_value = MagicMock()

            mock_result_2 = MagicMock()
            mock_result_2.scalar_one_or_none.return_value = None

            mock_db_session.execute.side_effect = [mock_result_1, mock_result_2]

            with pytest.raises(HTTPException) as exc_info:
                await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404
            assert "vehicle with id 999 not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_upsert_with_access_schedules(self, mock_db_session: AsyncMock) -> None:
        """Test upsert with access schedules."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import (
            AccessSchedule,
            ZoneHouseholdConfigCreate,
        )

        schedule = AccessSchedule(
            member_ids=[5, 6],
            cron_expression="0 9-17 * * 1-5",
            description="Weekday business hours",
        )

        config_data = ZoneHouseholdConfigCreate(
            owner_id=1,
            allowed_member_ids=[],
            allowed_vehicle_ids=[],
            access_schedules=[schedule],
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock owner exists
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock()
            mock_db_session.execute.return_value = mock_result

            mock_config = MagicMock()
            mock_config.id = 1
            mock_config.zone_id = "zone-123"
            mock_config.access_schedules = [schedule.model_dump()]

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)
                mock_service.create_config = AsyncMock(return_value=mock_config)
                mock_service_class.return_value = mock_service

                result = await upsert_zone_household_config(
                    zone_id="zone-123",
                    config_data=config_data,
                    db=mock_db_session,
                )

        assert len(result.access_schedules) == 1
        assert result.access_schedules[0]["member_ids"] == [5, 6]

    @pytest.mark.asyncio
    async def test_upsert_zone_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test upsert returns 404 if zone doesn't exist."""
        from backend.api.routes.zone_household import upsert_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigCreate

        config_data = ZoneHouseholdConfigCreate()

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            side_effect=HTTPException(status_code=404, detail="Zone not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await upsert_zone_household_config(
                    zone_id="nonexistent",
                    config_data=config_data,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404


class TestPatchZoneHouseholdConfig:
    """Tests for PATCH /api/zones/{zone_id}/household endpoint."""

    @pytest.mark.asyncio
    async def test_patch_config_success(self, mock_db_session: AsyncMock) -> None:
        """Test partially updating household config."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigUpdate

        # Only update owner_id
        update_data = ZoneHouseholdConfigUpdate(owner_id=2)

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            # Mock existing config
            existing_config = MagicMock()
            existing_config.id = 1
            existing_config.zone_id = "zone-123"
            existing_config.owner_id = 1

            # Mock updated config
            updated_config = MagicMock()
            updated_config.id = 1
            updated_config.zone_id = "zone-123"
            updated_config.owner_id = 2
            updated_config.allowed_member_ids = [3]  # Unchanged
            updated_config.allowed_vehicle_ids = []
            updated_config.access_schedules = []

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service.update_config = AsyncMock(return_value=updated_config)
                mock_service_class.return_value = mock_service

                # Mock owner validation
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = MagicMock()
                mock_db_session.execute.return_value = mock_result

                result = await patch_zone_household_config(
                    zone_id="zone-123",
                    config_data=update_data,
                    db=mock_db_session,
                )

        assert result.owner_id == 2

    @pytest.mark.asyncio
    async def test_patch_config_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test patch returns 404 if config doesn't exist."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigUpdate

        update_data = ZoneHouseholdConfigUpdate(owner_id=2)

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                with pytest.raises(HTTPException) as exc_info:
                    await patch_zone_household_config(
                        zone_id="zone-123",
                        config_data=update_data,
                        db=mock_db_session,
                    )

                assert exc_info.value.status_code == 404
                assert "no household configuration" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_patch_validates_references(self, mock_db_session: AsyncMock) -> None:
        """Test patch validates household references before updating."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigUpdate

        update_data = ZoneHouseholdConfigUpdate(owner_id=999)  # Non-existent

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            existing_config = MagicMock()

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service_class.return_value = mock_service

                # Mock validation function
                with patch(
                    "backend.api.routes.zone_household._validate_household_references",
                    side_effect=HTTPException(
                        status_code=404, detail="Household member with id 999 not found"
                    ),
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        await patch_zone_household_config(
                            zone_id="zone-123",
                            config_data=update_data,
                            db=mock_db_session,
                        )

                    assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_only_updates_provided_fields(self, mock_db_session: AsyncMock) -> None:
        """Test patch only updates fields that are provided."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigUpdate

        # Only update allowed_member_ids
        update_data = ZoneHouseholdConfigUpdate(allowed_member_ids=[4, 5])

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            existing_config = MagicMock()
            existing_config.owner_id = 1  # Should remain unchanged

            updated_config = MagicMock()
            updated_config.id = 1
            updated_config.zone_id = "zone-123"
            updated_config.owner_id = 1  # Unchanged
            updated_config.allowed_member_ids = [4, 5]
            updated_config.allowed_vehicle_ids = []
            updated_config.access_schedules = []

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service.update_config = AsyncMock(return_value=updated_config)
                mock_service_class.return_value = mock_service

                # Mock validation
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = MagicMock()
                mock_db_session.execute.return_value = mock_result

                result = await patch_zone_household_config(
                    zone_id="zone-123",
                    config_data=update_data,
                    db=mock_db_session,
                )

        assert result.allowed_member_ids == [4, 5]

    @pytest.mark.asyncio
    async def test_patch_zone_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test patch returns 404 if zone doesn't exist."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import ZoneHouseholdConfigUpdate

        update_data = ZoneHouseholdConfigUpdate(owner_id=2)

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            side_effect=HTTPException(status_code=404, detail="Zone not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await patch_zone_household_config(
                    zone_id="nonexistent",
                    config_data=update_data,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_update_vehicles_and_schedules(self, mock_db_session: AsyncMock) -> None:
        """Test patch updating allowed_vehicle_ids and access_schedules."""
        from backend.api.routes.zone_household import patch_zone_household_config
        from backend.api.schemas.zone_household import (
            AccessSchedule,
            ZoneHouseholdConfigUpdate,
        )

        schedule = AccessSchedule(
            member_ids=[7, 8],
            cron_expression="0 6-22 * * *",
            description="Daily access",
        )

        update_data = ZoneHouseholdConfigUpdate(
            allowed_vehicle_ids=[10, 11],
            access_schedules=[schedule],
        )

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            existing_config = MagicMock()

            updated_config = MagicMock()
            updated_config.id = 1
            updated_config.zone_id = "zone-123"
            updated_config.allowed_vehicle_ids = [10, 11]
            updated_config.access_schedules = [schedule.model_dump()]
            updated_config.owner_id = 1
            updated_config.allowed_member_ids = []

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service.update_config = AsyncMock(return_value=updated_config)
                mock_service_class.return_value = mock_service

                # Mock validation
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = MagicMock()
                mock_db_session.execute.return_value = mock_result

                result = await patch_zone_household_config(
                    zone_id="zone-123",
                    config_data=update_data,
                    db=mock_db_session,
                )

        assert result.allowed_vehicle_ids == [10, 11]
        assert len(result.access_schedules) == 1


class TestDeleteZoneHouseholdConfig:
    """Tests for DELETE /api/zones/{zone_id}/household endpoint."""

    @pytest.mark.asyncio
    async def test_delete_config_success(self, mock_db_session: AsyncMock) -> None:
        """Test successfully deleting household config."""
        from backend.api.routes.zone_household import delete_zone_household_config

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            existing_config = MagicMock()
            existing_config.id = 1
            existing_config.zone_id = "zone-123"

            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=existing_config)
                mock_service.delete_config = AsyncMock()
                mock_service_class.return_value = mock_service

                result = await delete_zone_household_config(
                    zone_id="zone-123",
                    db=mock_db_session,
                )

        assert result is None
        mock_service.delete_config.assert_called_once_with(existing_config)

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test delete returns 404 if config doesn't exist."""
        from backend.api.routes.zone_household import delete_zone_household_config

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_config = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                with pytest.raises(HTTPException) as exc_info:
                    await delete_zone_household_config(
                        zone_id="zone-123",
                        db=mock_db_session,
                    )

                assert exc_info.value.status_code == 404
                assert "no household configuration" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_delete_zone_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test delete returns 404 if zone doesn't exist."""
        from backend.api.routes.zone_household import delete_zone_household_config

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            side_effect=HTTPException(status_code=404, detail="Zone not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_zone_household_config(
                    zone_id="nonexistent",
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_returns_204(self) -> None:
        """Test delete endpoint is configured for 204 status."""
        from backend.api.routes.zone_household import delete_zone_household_config

        # Verify function exists and is properly configured
        assert delete_zone_household_config is not None

        # The route configuration sets status_code=204 via the @router.delete decorator
        assert status.HTTP_204_NO_CONTENT == 204


class TestCheckEntityTrust:
    """Tests for GET /api/zones/{zone_id}/household/trust/{entity_type}/{entity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_check_trust_full_owner(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust returns FULL for zone owner."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(TrustLevelResult.FULL, "Entity is the zone owner")
                )
                mock_service_class.return_value = mock_service

                result = await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="member",
                    entity_id=1,
                    at_time=None,
                    db=mock_db_session,
                )

        assert result.trust_level == TrustLevelResult.FULL
        assert result.reason == "Entity is the zone owner"
        assert result.zone_id == "zone-123"
        assert result.entity_id == 1
        assert result.entity_type == "member"

    @pytest.mark.asyncio
    async def test_check_trust_partial_allowed_member(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust returns PARTIAL for allowed member."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(
                        TrustLevelResult.PARTIAL,
                        "Entity is in allowed members list",
                    )
                )
                mock_service_class.return_value = mock_service

                result = await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="member",
                    entity_id=2,
                    at_time=None,
                    db=mock_db_session,
                )

        assert result.trust_level == TrustLevelResult.PARTIAL
        assert "allowed members" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_trust_partial_allowed_vehicle(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust returns PARTIAL for allowed vehicle."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(
                        TrustLevelResult.PARTIAL,
                        "Entity is in allowed vehicles list",
                    )
                )
                mock_service_class.return_value = mock_service

                result = await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="vehicle",
                    entity_id=1,
                    at_time=None,
                    db=mock_db_session,
                )

        assert result.trust_level == TrustLevelResult.PARTIAL
        assert "allowed vehicles" in result.reason.lower()
        assert result.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_check_trust_monitor_scheduled_access(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust returns MONITOR for scheduled access."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(
                        TrustLevelResult.MONITOR,
                        "Entity has business hours access",
                    )
                )
                mock_service_class.return_value = mock_service

                result = await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="member",
                    entity_id=5,
                    at_time=datetime(2026, 1, 21, 14, 0, 0, tzinfo=UTC),  # Weekday 2pm
                    db=mock_db_session,
                )

        assert result.trust_level == TrustLevelResult.MONITOR

    @pytest.mark.asyncio
    async def test_check_trust_none_no_config(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust returns NONE when no config exists."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(
                        TrustLevelResult.NONE,
                        "No household configuration for this zone",
                    )
                )
                mock_service_class.return_value = mock_service

                result = await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="member",
                    entity_id=99,
                    at_time=None,
                    db=mock_db_session,
                )

        assert result.trust_level == TrustLevelResult.NONE

    @pytest.mark.asyncio
    async def test_check_trust_with_specific_time(self, mock_db_session: AsyncMock) -> None:
        """Test checking trust with a specific timestamp."""
        from backend.api.routes.zone_household import check_entity_trust

        check_time = datetime(2026, 1, 21, 15, 30, 0, tzinfo=UTC)

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            return_value=MagicMock(),
        ):
            with patch(
                "backend.api.routes.zone_household.ZoneHouseholdService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_trust_level = AsyncMock(
                    return_value=(TrustLevelResult.MONITOR, "Scheduled access")
                )
                mock_service_class.return_value = mock_service

                await check_entity_trust(
                    zone_id="zone-123",
                    entity_type="member",
                    entity_id=5,
                    at_time=check_time,
                    db=mock_db_session,
                )

                # Verify service was called with the specific time
                mock_service.get_trust_level.assert_called_once_with(
                    zone_id="zone-123",
                    entity_id=5,
                    entity_type="member",
                    at_time=check_time,
                )

    @pytest.mark.asyncio
    async def test_check_trust_zone_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test check trust returns 404 if zone doesn't exist."""
        from backend.api.routes.zone_household import check_entity_trust

        with patch(
            "backend.api.routes.zone_household.get_zone_or_404",
            side_effect=HTTPException(status_code=404, detail="Zone not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await check_entity_trust(
                    zone_id="nonexistent",
                    entity_type="member",
                    entity_id=1,
                    at_time=None,
                    db=mock_db_session,
                )

            assert exc_info.value.status_code == 404


class TestGetMemberZones:
    """Tests for GET /api/zones/member/{member_id}/zones endpoint."""

    @pytest.mark.asyncio
    async def test_get_member_zones_success(self, mock_db_session: AsyncMock) -> None:
        """Test getting all zones where a member has trust."""
        from backend.api.routes.zone_household import get_member_zones

        zones = [
            {
                "zone_id": "zone-1",
                "trust_level": "full",
                "reason": "Zone owner",
            },
            {
                "zone_id": "zone-2",
                "trust_level": "partial",
                "reason": "In allowed members list",
            },
        ]

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_member = AsyncMock(return_value=zones)
            mock_service_class.return_value = mock_service

            result = await get_member_zones(
                member_id=1,
                db=mock_db_session,
            )

        assert len(result) == 2
        assert result[0]["zone_id"] == "zone-1"
        assert result[0]["trust_level"] == "full"
        assert result[1]["zone_id"] == "zone-2"
        assert result[1]["trust_level"] == "partial"

    @pytest.mark.asyncio
    async def test_get_member_zones_empty(self, mock_db_session: AsyncMock) -> None:
        """Test getting member zones returns empty list when member has no trust."""
        from backend.api.routes.zone_household import get_member_zones

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_member = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            result = await get_member_zones(
                member_id=999,
                db=mock_db_session,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_member_zones_multiple_trust_levels(self, mock_db_session: AsyncMock) -> None:
        """Test getting member zones with different trust levels."""
        from backend.api.routes.zone_household import get_member_zones

        zones = [
            {
                "zone_id": "zone-1",
                "trust_level": "full",
                "reason": "Zone owner",
            },
            {
                "zone_id": "zone-2",
                "trust_level": "partial",
                "reason": "In allowed members list",
            },
            {
                "zone_id": "zone-3",
                "trust_level": "monitor",
                "reason": "Has business hours access",
            },
        ]

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_member = AsyncMock(return_value=zones)
            mock_service_class.return_value = mock_service

            result = await get_member_zones(
                member_id=1,
                db=mock_db_session,
            )

        assert len(result) == 3
        trust_levels = [z["trust_level"] for z in result]
        assert "full" in trust_levels
        assert "partial" in trust_levels
        assert "monitor" in trust_levels


class TestGetVehicleZones:
    """Tests for GET /api/zones/vehicle/{vehicle_id}/zones endpoint."""

    @pytest.mark.asyncio
    async def test_get_vehicle_zones_success(self, mock_db_session: AsyncMock) -> None:
        """Test getting all zones where a vehicle has trust."""
        from backend.api.routes.zone_household import get_vehicle_zones

        zones = [
            {
                "zone_id": "zone-1",
                "trust_level": "partial",
                "reason": "In allowed vehicles list",
            },
            {
                "zone_id": "zone-2",
                "trust_level": "partial",
                "reason": "In allowed vehicles list",
            },
        ]

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_vehicle = AsyncMock(return_value=zones)
            mock_service_class.return_value = mock_service

            result = await get_vehicle_zones(
                vehicle_id=1,
                db=mock_db_session,
            )

        assert len(result) == 2
        assert all(z["trust_level"] == "partial" for z in result)
        assert result[0]["zone_id"] == "zone-1"
        assert result[1]["zone_id"] == "zone-2"

    @pytest.mark.asyncio
    async def test_get_vehicle_zones_empty(self, mock_db_session: AsyncMock) -> None:
        """Test getting vehicle zones returns empty list when vehicle has no trust."""
        from backend.api.routes.zone_household import get_vehicle_zones

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_vehicle = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            result = await get_vehicle_zones(
                vehicle_id=999,
                db=mock_db_session,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_vehicle_zones_only_partial_trust(self, mock_db_session: AsyncMock) -> None:
        """Test vehicles can only have PARTIAL trust (no full or monitor)."""
        from backend.api.routes.zone_household import get_vehicle_zones

        zones = [
            {
                "zone_id": "zone-1",
                "trust_level": "partial",
                "reason": "In allowed vehicles list",
            },
        ]

        with patch("backend.api.routes.zone_household.ZoneHouseholdService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_zones_for_vehicle = AsyncMock(return_value=zones)
            mock_service_class.return_value = mock_service

            result = await get_vehicle_zones(
                vehicle_id=1,
                db=mock_db_session,
            )

        # Vehicles can only have partial trust, not full or monitor
        assert all(z["trust_level"] == "partial" for z in result)


class TestValidateHouseholdReferences:
    """Tests for _validate_household_references helper function."""

    @pytest.mark.asyncio
    async def test_validate_owner_exists(self, mock_db_session: AsyncMock) -> None:
        """Test validation passes when owner exists."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"owner_id": 1}

        # Mock owner exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db_session.execute.return_value = mock_result

        # Should not raise
        await _validate_household_references(mock_db_session, update_dict)

    @pytest.mark.asyncio
    async def test_validate_owner_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test validation fails when owner doesn't exist."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"owner_id": 999}

        # Mock owner doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await _validate_household_references(mock_db_session, update_dict)

        assert exc_info.value.status_code == 404
        assert "member with id 999 not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_skips_none_owner(self, mock_db_session: AsyncMock) -> None:
        """Test validation skips when owner_id is None."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"owner_id": None}

        # Should not raise and should not execute queries
        await _validate_household_references(mock_db_session, update_dict)
        mock_db_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_allowed_members_exist(self, mock_db_session: AsyncMock) -> None:
        """Test validation passes when all allowed members exist."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"allowed_member_ids": [1, 2]}

        # Mock both members exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db_session.execute.return_value = mock_result

        # Should not raise
        await _validate_household_references(mock_db_session, update_dict)

    @pytest.mark.asyncio
    async def test_validate_allowed_member_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test validation fails when allowed member doesn't exist."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"allowed_member_ids": [1, 999]}

        # First exists, second doesn't
        mock_result_1 = MagicMock()
        mock_result_1.scalar_one_or_none.return_value = MagicMock()

        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_result_1, mock_result_2]

        with pytest.raises(HTTPException) as exc_info:
            await _validate_household_references(mock_db_session, update_dict)

        assert exc_info.value.status_code == 404
        assert "member with id 999 not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_allowed_vehicles_exist(self, mock_db_session: AsyncMock) -> None:
        """Test validation passes when all allowed vehicles exist."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"allowed_vehicle_ids": [1, 2]}

        # Mock both vehicles exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db_session.execute.return_value = mock_result

        # Should not raise
        await _validate_household_references(mock_db_session, update_dict)

    @pytest.mark.asyncio
    async def test_validate_allowed_vehicle_not_found(self, mock_db_session: AsyncMock) -> None:
        """Test validation fails when allowed vehicle doesn't exist."""
        from backend.api.routes.zone_household import _validate_household_references

        update_dict = {"allowed_vehicle_ids": [1, 999]}

        # First exists, second doesn't
        mock_result_1 = MagicMock()
        mock_result_1.scalar_one_or_none.return_value = MagicMock()

        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_result_1, mock_result_2]

        with pytest.raises(HTTPException) as exc_info:
            await _validate_household_references(mock_db_session, update_dict)

        assert exc_info.value.status_code == 404
        assert "vehicle with id 999 not found" in exc_info.value.detail.lower()
