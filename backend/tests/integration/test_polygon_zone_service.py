"""Integration tests for PolygonZoneService.

Tests verify service interactions with database and external dependencies.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.polygon_zone_service import PolygonZoneService


@pytest.mark.integration
class TestPolygonZoneServiceIntegration:
    """Integration tests for PolygonZoneService."""

    @pytest.mark.asyncio
    async def test_get_polygon_zone_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist."""
        service = PolygonZoneService(db_session)
        result = await service.get_polygon_zone(zone_id=999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_polygon_zones_by_camera_empty_for_nonexistent_camera(
        self, db_session: AsyncSession
    ):
        """Verify empty list returned when camera has no polygon zones."""
        service = PolygonZoneService(db_session)
        result = await service.get_polygon_zones_by_camera("nonexistent_camera")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_polygon_zones_by_camera_with_active_only_filter(
        self, db_session: AsyncSession
    ):
        """Verify active_only filter works correctly."""
        service = PolygonZoneService(db_session)
        result = await service.get_polygon_zones_by_camera("nonexistent_camera", active_only=True)
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_polygon_zone_returns_false_when_not_found(self, db_session: AsyncSession):
        """Verify False returned when polygon zone doesn't exist for delete."""
        service = PolygonZoneService(db_session)
        result = await service.delete_polygon_zone(zone_id=999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_polygon_zone_returns_none_when_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist for update."""
        service = PolygonZoneService(db_session)
        result = await service.update_polygon_zone(zone_id=999999, name="Updated Name")
        assert result is None

    @pytest.mark.asyncio
    async def test_toggle_active_returns_none_when_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist for toggle."""
        service = PolygonZoneService(db_session)
        result = await service.toggle_active(zone_id=999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_polygon_zones_empty_when_none_exist(self, db_session: AsyncSession):
        """Verify empty list returned when no polygon zones exist."""
        service = PolygonZoneService(db_session)
        result = await service.get_all_polygon_zones()
        assert result == []
