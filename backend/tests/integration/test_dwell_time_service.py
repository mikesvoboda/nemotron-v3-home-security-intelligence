"""Integration tests for DwellTimeService.

Tests verify service interactions with database and external dependencies.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.dwell_time_service import DwellTimeService


@pytest.mark.integration
class TestDwellTimeServiceIntegration:
    """Integration tests for DwellTimeService."""

    @pytest.mark.asyncio
    async def test_get_dwell_history_empty_for_nonexistent_zone(self, db_session: AsyncSession):
        """Verify empty list returned when zone has no dwell records."""
        from datetime import UTC, datetime, timedelta

        service = DwellTimeService(db_session)
        now = datetime.now(UTC)
        result = await service.get_dwell_history(
            zone_id=999999,
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_get_dwell_statistics_none_for_nonexistent_zone(self, db_session: AsyncSession):
        """Verify None returned when zone has no dwell data."""
        from datetime import UTC, datetime, timedelta

        service = DwellTimeService(db_session)
        now = datetime.now(UTC)
        result = await service.get_dwell_statistics(
            zone_id=999999,
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_dwellers_empty_for_nonexistent_zone(self, db_session: AsyncSession):
        """Verify empty list returned when zone has no active dwellers."""
        service = DwellTimeService(db_session)
        result = await service.get_active_dwellers(zone_id=999999)
        assert result == []

    @pytest.mark.asyncio
    async def test_check_loitering_empty_for_nonexistent_zone(self, db_session: AsyncSession):
        """Verify empty list returned when zone has no loitering objects."""
        service = DwellTimeService(db_session)
        result = await service.check_loitering(zone_id=999999, threshold_seconds=60.0)
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_old_dwell_records_returns_zero_for_empty_table(
        self, db_session: AsyncSession
    ):
        """Verify zero deleted when no old dwell records exist."""
        from datetime import UTC, datetime, timedelta

        service = DwellTimeService(db_session)
        cutoff = datetime.now(UTC) - timedelta(days=30)
        result = await service.delete_old_records(cutoff)
        assert result == 0
