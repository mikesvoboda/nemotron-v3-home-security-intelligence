"""Integration tests for PolygonZoneService.

Tests verify service interactions with database and external dependencies.

Rewritten to the shipped service API (services/polygon_zone_service.py): the
previous version called get_polygon_zone / get_polygon_zones_by_camera /
delete_polygon_zone / update_polygon_zone / toggle_active /
get_all_polygon_zones — none of which exist on the class (run-9: seven
AttributeErrors). Shipped names: get_zone, get_zones_by_camera, delete_zone,
update_zone (PolygonZoneUpdate schema, not bare kwargs), set_active,
get_all_zones. (ledger R-T9-POLYZONE)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics_zone import PolygonZoneUpdate
from backend.services.polygon_zone_service import PolygonZoneService


@pytest.mark.integration
class TestPolygonZoneServiceIntegration:
    """Integration tests for PolygonZoneService."""

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist."""
        service = PolygonZoneService(db_session)
        result = await service.get_zone(zone_id=999999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_empty_for_nonexistent_camera(self, db_session: AsyncSession):
        """Verify empty list returned when camera has no polygon zones."""
        service = PolygonZoneService(db_session)
        result = await service.get_zones_by_camera("nonexistent_camera")
        assert list(result) == []

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_with_active_only_filter(self, db_session: AsyncSession):
        """Verify active_only filter works correctly."""
        service = PolygonZoneService(db_session)
        result = await service.get_zones_by_camera("nonexistent_camera", active_only=True)
        assert list(result) == []

    @pytest.mark.asyncio
    async def test_delete_zone_returns_false_when_not_found(self, db_session: AsyncSession):
        """Verify False returned when polygon zone doesn't exist for delete."""
        service = PolygonZoneService(db_session)
        result = await service.delete_zone(zone_id=999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_zone_returns_none_when_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist for update."""
        service = PolygonZoneService(db_session)
        result = await service.update_zone(
            zone_id=999999, data=PolygonZoneUpdate(name="Updated Name")
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_set_active_returns_none_when_not_found(self, db_session: AsyncSession):
        """Verify None returned when polygon zone doesn't exist for activation toggle."""
        service = PolygonZoneService(db_session)
        result = await service.set_active(zone_id=999999, is_active=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_zones_empty_when_none_exist(self, db_session: AsyncSession):
        """Verify empty list returned when no polygon zones exist."""
        service = PolygonZoneService(db_session)
        result = await service.get_all_zones()
        assert list(result) == []
