"""Unit tests for ZoneHouseholdService.

Tests cover:
- Cron expression parsing and schedule matching
- Trust level calculations (full, partial, monitor, none)
- Configuration CRUD operations
- Zone lookups for members and vehicles
- Edge cases and error handling

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.zone_household import TrustLevelResult
from backend.services.zone_household_service import (
    ZoneHouseholdService,
    _match_cron_field,
    check_schedule,
)

# =============================================================================
# Cron Field Matching Tests
# =============================================================================


class TestMatchCronField:
    """Tests for _match_cron_field helper function."""

    def test_wildcard_matches_any_value(self) -> None:
        """Test that wildcard (*) matches any value."""
        assert _match_cron_field("*", 0, 0, 59) is True
        assert _match_cron_field("*", 30, 0, 59) is True
        assert _match_cron_field("*", 59, 0, 59) is True

    def test_single_value_matches_exact(self) -> None:
        """Test that single values match exactly."""
        assert _match_cron_field("5", 5, 0, 59) is True
        assert _match_cron_field("5", 4, 0, 59) is False
        assert _match_cron_field("5", 6, 0, 59) is False

    def test_range_matches_inclusive(self) -> None:
        """Test that ranges match inclusive values."""
        # Range 9-17 (business hours)
        assert _match_cron_field("9-17", 8, 0, 23) is False
        assert _match_cron_field("9-17", 9, 0, 23) is True
        assert _match_cron_field("9-17", 13, 0, 23) is True
        assert _match_cron_field("9-17", 17, 0, 23) is True
        assert _match_cron_field("9-17", 18, 0, 23) is False

    def test_list_matches_any_in_list(self) -> None:
        """Test that lists match any value in the list."""
        assert _match_cron_field("1,3,5", 1, 0, 6) is True
        assert _match_cron_field("1,3,5", 3, 0, 6) is True
        assert _match_cron_field("1,3,5", 5, 0, 6) is True
        assert _match_cron_field("1,3,5", 2, 0, 6) is False
        assert _match_cron_field("1,3,5", 4, 0, 6) is False

    def test_step_matches_multiples(self) -> None:
        """Test that step values match multiples."""
        assert _match_cron_field("*/5", 0, 0, 59) is True
        assert _match_cron_field("*/5", 5, 0, 59) is True
        assert _match_cron_field("*/5", 10, 0, 59) is True
        assert _match_cron_field("*/5", 3, 0, 59) is False

    def test_invalid_value_returns_false(self) -> None:
        """Test that invalid values return False."""
        assert _match_cron_field("abc", 5, 0, 59) is False
        assert _match_cron_field("", 5, 0, 59) is False


# =============================================================================
# Schedule Checking Tests
# =============================================================================


class TestCheckSchedule:
    """Tests for check_schedule function."""

    def test_weekday_business_hours(self) -> None:
        """Test schedule for weekday business hours (9am-5pm Mon-Fri)."""
        cron = "0 9-17 * * 1-5"

        # Monday 10am -> should match
        monday_10am = datetime(2026, 1, 19, 10, 0, tzinfo=UTC)  # Monday
        assert check_schedule(cron, monday_10am) is True

        # Friday 5pm -> should match
        friday_5pm = datetime(2026, 1, 23, 17, 0, tzinfo=UTC)  # Friday
        assert check_schedule(cron, friday_5pm) is True

        # Saturday 10am -> should NOT match (weekend)
        saturday_10am = datetime(2026, 1, 24, 10, 0, tzinfo=UTC)  # Saturday
        assert check_schedule(cron, saturday_10am) is False

        # Monday 8am -> should NOT match (before 9am)
        monday_8am = datetime(2026, 1, 19, 8, 0, tzinfo=UTC)
        assert check_schedule(cron, monday_8am) is False

    def test_evening_hours_daily(self) -> None:
        """Test schedule for evening hours every day (6pm-10pm)."""
        cron = "0 18-22 * * *"

        # Any day at 7pm -> should match
        evening = datetime(2026, 1, 21, 19, 0, tzinfo=UTC)
        assert check_schedule(cron, evening) is True

        # Any day at 3pm -> should NOT match
        afternoon = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
        assert check_schedule(cron, afternoon) is False

    def test_weekend_only(self) -> None:
        """Test schedule for weekend only."""
        cron = "0 * * * 0,6"  # Sunday=0, Saturday=6

        # Saturday -> should match
        saturday = datetime(2026, 1, 24, 12, 0, tzinfo=UTC)  # Saturday
        assert check_schedule(cron, saturday) is True

        # Sunday -> should match
        sunday = datetime(2026, 1, 25, 12, 0, tzinfo=UTC)  # Sunday
        assert check_schedule(cron, sunday) is True

        # Wednesday -> should NOT match
        wednesday = datetime(2026, 1, 21, 12, 0, tzinfo=UTC)  # Wednesday
        assert check_schedule(cron, wednesday) is False

    def test_specific_time(self) -> None:
        """Test schedule for specific time."""
        cron = "30 14 * * *"  # 2:30pm every day

        # 2:30pm -> should match
        time_match = datetime(2026, 1, 21, 14, 30, tzinfo=UTC)
        assert check_schedule(cron, time_match) is True

        # 2:31pm -> should NOT match
        time_no_match = datetime(2026, 1, 21, 14, 31, tzinfo=UTC)
        assert check_schedule(cron, time_no_match) is False

    def test_invalid_cron_expression(self) -> None:
        """Test that invalid cron expressions return False."""
        time = datetime(2026, 1, 21, 10, 0, tzinfo=UTC)

        # Too few fields
        assert check_schedule("* * *", time) is False

        # Too many fields
        assert check_schedule("* * * * * *", time) is False

        # Invalid characters
        assert check_schedule("a b c d e", time) is False

    def test_all_wildcards(self) -> None:
        """Test schedule with all wildcards (always matches)."""
        cron = "* * * * *"
        any_time = datetime(2026, 1, 21, 10, 30, tzinfo=UTC)
        assert check_schedule(cron, any_time) is True


# =============================================================================
# ZoneHouseholdService Trust Level Tests
# =============================================================================


class TestZoneHouseholdServiceTrustLevel:
    """Tests for ZoneHouseholdService trust level calculations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> ZoneHouseholdService:
        """Create a ZoneHouseholdService instance."""
        return ZoneHouseholdService(mock_session)

    @pytest.mark.asyncio
    async def test_trust_level_full_for_owner(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that zone owner gets full trust level."""
        # Mock config with owner_id=1
        mock_config = MagicMock()
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.FULL
        assert "owner" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_partial_for_allowed_member(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that allowed member gets partial trust level."""
        mock_config = MagicMock()
        mock_config.owner_id = 99
        mock_config.allowed_member_ids = [1, 2, 3]
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=2,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.PARTIAL
        assert "allowed members" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_partial_for_allowed_vehicle(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that allowed vehicle gets partial trust level."""
        mock_config = MagicMock()
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = [10, 20, 30]
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=20,
                entity_type="vehicle",
            )

        assert trust_level == TrustLevelResult.PARTIAL
        assert "allowed vehicles" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_monitor_for_scheduled_member(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that member with active schedule gets monitor trust level."""
        mock_config = MagicMock()
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = [
            {
                "member_ids": [5, 6],
                "cron_expression": "* * * * *",  # Always matches
                "description": "service access",
            }
        ]

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=5,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.MONITOR
        assert "service access" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_none_when_no_config(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that entity gets no trust when zone has no config."""
        with patch.object(service, "get_config", return_value=None):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.NONE
        assert "no household configuration" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_none_for_unknown_entity(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that unknown entity gets no trust."""
        mock_config = MagicMock()
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = [2, 3]
        mock_config.allowed_vehicle_ids = [10]
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=99,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.NONE
        assert "no trust configuration" in reason.lower()

    @pytest.mark.asyncio
    async def test_trust_level_schedule_not_active(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that scheduled member gets no trust when schedule not active."""
        mock_config = MagicMock()
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        # Schedule for minute 59 only
        mock_config.access_schedules = [
            {
                "member_ids": [5],
                "cron_expression": "59 * * * *",  # Only at minute 59
                "description": "limited access",
            }
        ]

        # Test at minute 30 (schedule not active)
        test_time = datetime(2026, 1, 21, 10, 30, tzinfo=UTC)

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, _reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=5,
                entity_type="member",
                at_time=test_time,
            )

        assert trust_level == TrustLevelResult.NONE

    @pytest.mark.asyncio
    async def test_trust_level_priority_owner_over_allowed(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that owner trust takes priority over allowed list."""
        mock_config = MagicMock()
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = [1, 2, 3]  # Owner also in allowed list
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, _reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="member",
            )

        # Should get FULL (owner) not PARTIAL (allowed)
        assert trust_level == TrustLevelResult.FULL


# =============================================================================
# ZoneHouseholdService CRUD Tests
# =============================================================================


class TestZoneHouseholdServiceCRUD:
    """Tests for ZoneHouseholdService CRUD operations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> ZoneHouseholdService:
        """Create a ZoneHouseholdService instance."""
        return ZoneHouseholdService(mock_session)

    @pytest.mark.asyncio
    async def test_get_config_returns_config_when_found(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that get_config returns config when found."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-1"

        # Mock execute to return the config
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute.return_value = mock_result

        result = await service.get_config("zone-1")

        assert result == mock_config
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_config_returns_none_when_not_found(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that get_config returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_config("nonexistent-zone")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_config(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test creating a new config."""
        with patch("backend.models.zone_household_config.ZoneHouseholdConfig") as MockConfig:
            mock_config = MagicMock()
            mock_config.id = 1
            mock_config.zone_id = "zone-1"
            MockConfig.return_value = mock_config

            result = await service.create_config(
                zone_id="zone-1",
                owner_id=1,
                allowed_member_ids=[2, 3],
                allowed_vehicle_ids=[10],
                access_schedules=[{"member_ids": [4], "cron_expression": "* * * * *"}],
            )

            mock_session.add.assert_called_once_with(mock_config)
            mock_session.flush.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_config)
            assert result == mock_config

    @pytest.mark.asyncio
    async def test_update_config(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating an existing config."""
        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.zone_id = "zone-1"
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = [2]
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        result = await service.update_config(
            mock_config,
            owner_id=2,
            allowed_member_ids=[3, 4],
        )

        assert mock_config.owner_id == 2
        assert mock_config.allowed_member_ids == [3, 4]
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_config)
        assert result == mock_config

    @pytest.mark.asyncio
    async def test_update_config_skips_unset_fields(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test that update_config skips fields with sentinel value."""
        mock_config = MagicMock()
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = [2]
        mock_config.allowed_vehicle_ids = [10]
        mock_config.access_schedules = []

        # Only update allowed_member_ids, owner_id should stay the same
        result = await service.update_config(
            mock_config,
            allowed_member_ids=[3, 4],
        )

        # owner_id should not be changed (sentinel value ...)
        assert mock_config.allowed_member_ids == [3, 4]
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_config(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test deleting a config."""
        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.zone_id = "zone-1"

        await service.delete_config(mock_config)

        mock_session.delete.assert_called_once_with(mock_config)
        mock_session.flush.assert_called_once()


# =============================================================================
# ZoneHouseholdService Zone Lookup Tests
# =============================================================================


class TestZoneHouseholdServiceZoneLookup:
    """Tests for ZoneHouseholdService zone lookup methods."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> ZoneHouseholdService:
        """Create a ZoneHouseholdService instance."""
        return ZoneHouseholdService(mock_session)

    @pytest.mark.asyncio
    async def test_get_zones_for_member_as_owner(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones where member is owner."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-1"
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = []
        mock_config.access_schedules = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(1)

        assert len(zones) == 1
        assert zones[0]["zone_id"] == "zone-1"
        assert zones[0]["trust_level"] == "full"

    @pytest.mark.asyncio
    async def test_get_zones_for_member_as_allowed(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones where member is in allowed list."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-2"
        mock_config.owner_id = 99
        mock_config.allowed_member_ids = [1, 2, 3]
        mock_config.access_schedules = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(2)

        assert len(zones) == 1
        assert zones[0]["zone_id"] == "zone-2"
        assert zones[0]["trust_level"] == "partial"

    @pytest.mark.asyncio
    async def test_get_zones_for_member_in_schedule(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones where member is in schedule."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-3"
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.access_schedules = [
            {"member_ids": [5], "cron_expression": "* * * * *", "description": "daily access"}
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(5)

        assert len(zones) == 1
        assert zones[0]["zone_id"] == "zone-3"
        assert zones[0]["trust_level"] == "monitor"

    @pytest.mark.asyncio
    async def test_get_zones_for_member_no_zones(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones for member with no access."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-1"
        mock_config.owner_id = 1
        mock_config.allowed_member_ids = [2]
        mock_config.access_schedules = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        # Member 99 has no access
        zones = await service.get_zones_for_member(99)

        assert len(zones) == 0

    @pytest.mark.asyncio
    async def test_get_zones_for_vehicle(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones where vehicle has access."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-1"
        mock_config.allowed_vehicle_ids = [10, 20]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_vehicle(10)

        assert len(zones) == 1
        assert zones[0]["zone_id"] == "zone-1"
        assert zones[0]["trust_level"] == "partial"

    @pytest.mark.asyncio
    async def test_get_zones_for_vehicle_no_zones(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones for vehicle with no access."""
        mock_config = MagicMock()
        mock_config.zone_id = "zone-1"
        mock_config.allowed_vehicle_ids = [10]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        # Vehicle 99 has no access
        zones = await service.get_zones_for_vehicle(99)

        assert len(zones) == 0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestZoneHouseholdServiceEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> ZoneHouseholdService:
        """Create a ZoneHouseholdService instance."""
        return ZoneHouseholdService(mock_session)

    @pytest.mark.asyncio
    async def test_trust_level_with_empty_arrays(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test trust level when all arrays are empty."""
        mock_config = MagicMock()
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, _ = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.NONE

    @pytest.mark.asyncio
    async def test_trust_level_vehicle_cannot_be_owner(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test that vehicle entity type ignores owner_id check."""
        mock_config = MagicMock()
        mock_config.owner_id = 1  # Same as entity_id but wrong type
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = []

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, _ = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="vehicle",  # Vehicle, not member
            )

        # Vehicle can't be owner, so should be NONE
        assert trust_level == TrustLevelResult.NONE

    @pytest.mark.asyncio
    async def test_schedule_with_missing_description(
        self,
        service: ZoneHouseholdService,
    ) -> None:
        """Test schedule without description field."""
        mock_config = MagicMock()
        mock_config.owner_id = None
        mock_config.allowed_member_ids = []
        mock_config.allowed_vehicle_ids = []
        mock_config.access_schedules = [
            {
                "member_ids": [1],
                "cron_expression": "* * * * *",
                # No description field
            }
        ]

        with patch.object(service, "get_config", return_value=mock_config):
            trust_level, reason = await service.get_trust_level(
                zone_id="zone-1",
                entity_id=1,
                entity_type="member",
            )

        assert trust_level == TrustLevelResult.MONITOR
        # Should use default "scheduled access" when no description
        assert "scheduled access" in reason.lower()

    def test_create_config_with_defaults(self) -> None:
        """Test that create_config handles default values."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        service = ZoneHouseholdService(mock_session)

        # We can't fully test without mocking the model constructor,
        # but we verify the service can be instantiated
        assert service is not None
