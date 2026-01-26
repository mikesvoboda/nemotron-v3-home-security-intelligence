"""Integration tests for HeatmapService.

Tests verify service interactions with database and external dependencies.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.heatmap_service import HeatmapService


@pytest.mark.integration
class TestHeatmapServiceIntegration:
    """Integration tests for HeatmapService."""

    @pytest.mark.asyncio
    async def test_get_current_heatmap_camera_not_found(self, db_session: AsyncSession):
        """Verify None returned when camera doesn't exist."""
        service = HeatmapService(db_session)
        result = await service.get_current_heatmap("nonexistent_camera")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_heatmap_history_empty_for_nonexistent_camera(self, db_session: AsyncSession):
        """Verify empty list returned when camera has no heatmaps."""
        from datetime import UTC, datetime, timedelta

        service = HeatmapService(db_session)
        now = datetime.now(UTC)
        result = await service.get_heatmap_history(
            camera_id="nonexistent_camera",
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_get_heatmap_statistics_none_for_nonexistent_camera(
        self, db_session: AsyncSession
    ):
        """Verify None returned when camera has no heatmap data."""
        service = HeatmapService(db_session)
        result = await service.get_heatmap_statistics("nonexistent_camera")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_old_heatmaps_returns_zero_for_empty_table(self, db_session: AsyncSession):
        """Verify zero deleted when no old heatmaps exist."""
        from datetime import UTC, datetime, timedelta

        service = HeatmapService(db_session)
        cutoff = datetime.now(UTC) - timedelta(days=30)
        result = await service.delete_old_heatmaps(cutoff)
        assert result == 0
