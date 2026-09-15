"""Integration tests for HeatmapService.

Tests verify service interactions with database and external dependencies.

Rewritten to the shipped service API (services/heatmap_service.py). The
previous version constructed HeatmapService(db_session) and called
get_current_heatmap / get_heatmap_history / get_heatmap_statistics /
delete_old_heatmaps — none of which exist: the shipped constructor takes
grid dimensions only (sessions are per-call arguments), and the shipped
query surface is get_heatmap_data / get_merged_heatmap / reset_accumulator
(ledger R-T9-HEATMAP).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.heatmap_service import HeatmapService


@pytest.mark.integration
class TestHeatmapServiceIntegration:
    """Integration tests for HeatmapService."""

    @pytest.mark.asyncio
    async def test_get_merged_heatmap_none_for_nonexistent_camera(self, db_session: AsyncSession):
        """Verify None returned when camera has no heatmap records."""
        service = HeatmapService()
        now = datetime.now(UTC)
        result = await service.get_merged_heatmap(
            db_session,
            camera_id="nonexistent_camera",
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_heatmap_data_empty_for_nonexistent_camera(self, db_session: AsyncSession):
        """Verify empty page and zero total when camera has no heatmaps."""
        service = HeatmapService()
        now = datetime.now(UTC)
        records, total = await service.get_heatmap_data(
            db_session,
            camera_id="nonexistent_camera",
            start_time=now - timedelta(days=7),
            end_time=now,
        )
        assert list(records) == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_reset_accumulator_false_for_unknown_camera(self):
        """Verify False when no accumulator exists for the camera.

        Replaces the ghost delete_old_heatmaps test — the shipped service
        has no DB-record deletion API; the closest shipped "no-op on
        nonexistent state" contract is reset_accumulator.
        """
        service = HeatmapService()
        assert service.reset_accumulator("nonexistent_camera") is False

    @pytest.mark.asyncio
    async def test_get_accumulator_stats_none_for_unknown_camera(self):
        """Verify None stats for a camera that has never fed detections."""
        service = HeatmapService()
        assert service.get_accumulator_stats("nonexistent_camera") is None
