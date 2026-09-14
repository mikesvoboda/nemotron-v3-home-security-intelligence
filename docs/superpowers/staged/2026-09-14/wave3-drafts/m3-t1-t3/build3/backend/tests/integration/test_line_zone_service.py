"""Integration tests for LineZoneService.

Tests verify service interactions with database and external dependencies.

Rewritten (ledger R-T7-LINEZONE) from a draft written against a never-shipped
API (get_line_zone / get_line_zones_by_camera / delete_line_zone /
update_line_zone / get_all_line_zones, with reset_counts answering False).
The shipped service (backend/services/line_zone_service.py) names its methods
get_zone / get_zones_by_camera / delete_zone / update_zone / get_all_zones,
update_zone takes a LineZoneUpdate schema, and reset_counts returns None —
a not-found reset logs a warning, it has no boolean channel.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics_zone import LineZoneUpdate
from backend.services.line_zone_service import LineZoneService


@pytest.mark.integration
class TestLineZoneServiceIntegration:
    """Integration tests for LineZoneService."""

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, db_session: AsyncSession):
        """Verify None returned when line zone doesn't exist."""
        service = LineZoneService(db_session)
        result = await service.get_zone(zone_id=999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_empty_for_nonexistent_camera(self, db_session: AsyncSession):
        """Verify empty list returned when camera has no line zones."""
        service = LineZoneService(db_session)
        result = await service.get_zones_by_camera("nonexistent_camera")
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_zone_returns_false_when_not_found(self, db_session: AsyncSession):
        """Verify False returned when line zone doesn't exist for delete."""
        service = LineZoneService(db_session)
        result = await service.delete_zone(zone_id=999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_zone_returns_none_when_not_found(self, db_session: AsyncSession):
        """Verify None returned when line zone doesn't exist for update."""
        service = LineZoneService(db_session)
        result = await service.update_zone(zone_id=999999, data=LineZoneUpdate(name="Updated Name"))
        assert result is None

    @pytest.mark.asyncio
    async def test_reset_counts_returns_none_when_not_found(self, db_session: AsyncSession):
        """Shipped reset_counts is None-returning (logs a warning on miss);
        there is no False-on-not-found contract."""
        service = LineZoneService(db_session)
        result = await service.reset_counts(zone_id=999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_zones_empty_when_none_exist(self, db_session: AsyncSession):
        """Verify empty list returned when no line zones exist."""
        service = LineZoneService(db_session)
        result = await service.get_all_zones()
        assert result == []
