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
    async def test_get_zone_statistics_zero_for_nonexistent_zone(self, db_session: AsyncSession):
        """Verify zero-filled stats when zone has no dwell data.

        Shipped contract (services/dwell_time_service.py:498): the method is
        get_zone_statistics (get_dwell_statistics never existed) and the
        no-records path returns {"total_records": 0, "avg_dwell_seconds": 0.0,
        ...} — never None. (ledger R-T9-DWELL)
        """
        from datetime import UTC, datetime, timedelta

        service = DwellTimeService(db_session)
        now = datetime.now(UTC)
        result = await service.get_zone_statistics(
            zone_id=999999,
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert result == {
            "total_records": 0,
            "avg_dwell_seconds": 0.0,
            "max_dwell_seconds": 0.0,
            "min_dwell_seconds": 0.0,
            "alerts_triggered": 0,
        }

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
    async def test_cleanup_stale_records_returns_zero_for_empty_table(
        self, db_session: AsyncSession
    ):
        """Verify zero cleaned when no stale dwell records exist.

        Shipped contract (ledger R-T9-DWELL): the retention helper is
        cleanup_stale_records(zone_id, max_age_seconds) -> int
        (dwell_time_service.py:440) — there is no delete_old_records().
        """
        service = DwellTimeService(db_session)
        result = await service.cleanup_stale_records(zone_id=999999, max_age_seconds=3600.0)
        assert result == 0
