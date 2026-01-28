"""Unit tests for PolygonZoneService.

Tests cover:
- create_zone() - Zone creation with enum handling, logging
- get_zone() - Zone retrieval by ID
- get_zones_by_camera() - Camera-specific zone queries with active filtering
- get_zones_by_type() - Zone type filtering
- update_zone() - Partial updates with enum handling
- delete_zone() - Zone deletion with logging
- update_count() - Count updates with validation
- set_active() - Active state toggling
- reset_all_counts() - Bulk count reset

Edge cases: negative counts, non-existent zones, enum conversions, active filtering.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics_zone import (
    PolygonZoneCreate,
    PolygonZoneType,
    PolygonZoneUpdate,
)
from backend.models.analytics_zone import PolygonZone
from backend.services.polygon_zone_service import (
    PolygonZoneService,
    get_polygon_zone_service,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.delete = AsyncMock()  # Changed to AsyncMock
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def polygon_zone_service(mock_session: AsyncMock) -> PolygonZoneService:
    """Create a PolygonZoneService instance with mocked session."""
    return PolygonZoneService(mock_session)


@pytest.fixture
def sample_zone_create() -> PolygonZoneCreate:
    """Create sample polygon zone creation data."""
    return PolygonZoneCreate(
        camera_id="backyard",
        name="Pool Area",
        polygon=[[100, 200], [400, 200], [400, 500], [100, 500]],
        zone_type=PolygonZoneType.RESTRICTED,
        alert_threshold=1,
        target_classes=["person"],
        is_active=True,
        color="#FF0000",
    )


@pytest.fixture
def sample_zone() -> PolygonZone:
    """Create a sample PolygonZone instance."""
    zone = PolygonZone(
        id=1,
        camera_id="backyard",
        name="Pool Area",
        polygon=[[100, 200], [400, 200], [400, 500], [100, 500]],
        zone_type="restricted",
        alert_threshold=1,
        target_classes=["person"],
        is_active=True,
        color="#FF0000",
        current_count=0,
    )
    return zone


# =============================================================================
# create_zone Tests
# =============================================================================


class TestCreateZone:
    """Tests for create_zone method."""

    @pytest.mark.asyncio
    async def test_create_zone_success(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone_create: PolygonZoneCreate,
    ) -> None:
        """Test successful zone creation."""
        # Act
        result = await polygon_zone_service.create_zone("backyard", sample_zone_create)

        # Assert
        assert mock_session.add.called
        assert mock_session.flush.called
        assert mock_session.refresh.called
        assert result.camera_id == "backyard"
        assert result.name == "Pool Area"
        assert result.zone_type == "restricted"
        assert result.current_count == 0

    @pytest.mark.asyncio
    async def test_create_zone_with_enum_zone_type(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test zone creation with enum zone_type."""
        data = PolygonZoneCreate(
            camera_id="front_door",
            name="Entry Point",
            polygon=[[0, 0], [100, 0], [100, 100]],
            zone_type=PolygonZoneType.ENTRY,
        )

        result = await polygon_zone_service.create_zone("front_door", data)

        assert result.zone_type == "entry"
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_create_zone_with_string_zone_type(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test zone creation with string zone_type."""
        data = PolygonZoneCreate(
            camera_id="garage",
            name="Monitored Area",
            polygon=[[0, 0], [100, 0], [100, 100]],
            zone_type="monitored",  # type: ignore
        )

        result = await polygon_zone_service.create_zone("garage", data)

        assert result.zone_type == "monitored"

    @pytest.mark.asyncio
    async def test_create_zone_with_default_values(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test zone creation uses default values."""
        data = PolygonZoneCreate(
            camera_id="cam1",
            name="Default Zone",
            polygon=[[0, 0], [100, 0], [100, 100]],
        )

        result = await polygon_zone_service.create_zone("cam1", data)

        assert result.alert_threshold == 0
        assert result.target_classes == ["person"]
        assert result.is_active is True
        assert result.color == "#FF0000"

    @pytest.mark.asyncio
    async def test_create_zone_logs_creation(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone_create: PolygonZoneCreate,
    ) -> None:
        """Test zone creation logs the event."""
        with patch("backend.services.polygon_zone_service.logger") as mock_logger:
            await polygon_zone_service.create_zone("backyard", sample_zone_create)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Created polygon zone" in call_args[0][0]


# =============================================================================
# get_zone Tests
# =============================================================================


class TestGetZone:
    """Tests for get_zone method."""

    @pytest.mark.asyncio
    async def test_get_zone_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test getting an existing zone."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_zone
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zone(1)

        assert result == sample_zone
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_zone_not_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting a non-existent zone returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zone(999)

        assert result is None


# =============================================================================
# get_zones_by_camera Tests
# =============================================================================


class TestGetZonesByCamera:
    """Tests for get_zones_by_camera method."""

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_active_only(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test getting only active zones for a camera."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_zone]
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zones_by_camera("backyard", active_only=True)

        assert len(result) == 1
        assert result[0] == sample_zone
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_all_zones(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting all zones including inactive ones."""
        active_zone = PolygonZone(
            id=1, camera_id="cam1", name="Active", polygon=[[0, 0], [1, 1], [1, 0]], is_active=True
        )
        inactive_zone = PolygonZone(
            id=2,
            camera_id="cam1",
            name="Inactive",
            polygon=[[0, 0], [1, 1], [1, 0]],
            is_active=False,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_zone, inactive_zone]
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zones_by_camera("cam1", active_only=False)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_empty_result(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones for camera with no zones."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zones_by_camera("empty_camera")

        assert len(result) == 0


# =============================================================================
# get_zones_by_type Tests
# =============================================================================


class TestGetZonesByType:
    """Tests for get_zones_by_type method."""

    @pytest.mark.asyncio
    async def test_get_zones_by_type_restricted(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test getting zones by type."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_zone]
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zones_by_type("backyard", "restricted")

        assert len(result) == 1
        assert result[0].zone_type == "restricted"

    @pytest.mark.asyncio
    async def test_get_zones_by_type_empty_result(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones by type with no matches."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await polygon_zone_service.get_zones_by_type("cam1", "entry")

        assert len(result) == 0


# =============================================================================
# update_zone Tests
# =============================================================================


class TestUpdateZone:
    """Tests for update_zone method."""

    @pytest.mark.asyncio
    async def test_update_zone_name(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test updating zone name."""
        # Mock get_zone to return the sample zone
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone) as mock_get:
            data = PolygonZoneUpdate(name="Updated Pool Area")

            result = await polygon_zone_service.update_zone(1, data)

            assert result is not None
            assert result.name == "Updated Pool Area"
            assert mock_session.flush.called
            assert mock_session.refresh.called

    @pytest.mark.asyncio
    async def test_update_zone_with_enum(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test updating zone with enum zone_type."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            data = PolygonZoneUpdate(zone_type=PolygonZoneType.MONITORED)

            result = await polygon_zone_service.update_zone(1, data)

            assert result is not None
            assert result.zone_type == "monitored"

    @pytest.mark.asyncio
    async def test_update_zone_multiple_fields(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test updating multiple zone fields."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            data = PolygonZoneUpdate(
                name="Updated Zone",
                alert_threshold=5,
                color="#00FF00",
                is_active=False,
            )

            result = await polygon_zone_service.update_zone(1, data)

            assert result is not None
            assert result.name == "Updated Zone"
            assert result.alert_threshold == 5
            assert result.color == "#00FF00"
            assert result.is_active is False

    @pytest.mark.asyncio
    async def test_update_zone_not_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating non-existent zone returns None."""
        with patch.object(polygon_zone_service, "get_zone", return_value=None):
            data = PolygonZoneUpdate(name="Test")

            result = await polygon_zone_service.update_zone(999, data)

            assert result is None
            assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_update_zone_logs_update(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test zone update logs the event."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                data = PolygonZoneUpdate(name="Updated")

                await polygon_zone_service.update_zone(1, data)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Updated polygon zone" in call_args[0][0]


# =============================================================================
# delete_zone Tests
# =============================================================================


class TestDeleteZone:
    """Tests for delete_zone method."""

    @pytest.mark.asyncio
    async def test_delete_zone_success(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test successful zone deletion."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            result = await polygon_zone_service.delete_zone(1)

            assert result is True
            assert mock_session.delete.called
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_delete_zone_not_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test deleting non-existent zone returns False."""
        with patch.object(polygon_zone_service, "get_zone", return_value=None):
            result = await polygon_zone_service.delete_zone(999)

            assert result is False
            assert not mock_session.delete.called

    @pytest.mark.asyncio
    async def test_delete_zone_logs_deletion(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test zone deletion logs the event."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                await polygon_zone_service.delete_zone(1)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Deleted polygon zone" in call_args[0][0]


# =============================================================================
# update_count Tests
# =============================================================================


class TestUpdateCount:
    """Tests for update_count method."""

    @pytest.mark.asyncio
    async def test_update_count_success(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test successful count update."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            await polygon_zone_service.update_count(1, count=5)

            assert sample_zone.current_count == 5
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_update_count_zero(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test updating count to zero."""
        sample_zone.current_count = 10

        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            await polygon_zone_service.update_count(1, count=0)

            assert sample_zone.current_count == 0

    @pytest.mark.asyncio
    async def test_update_count_negative_raises(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating count to negative value raises ValueError."""
        with pytest.raises(ValueError, match="Count cannot be negative"):
            await polygon_zone_service.update_count(1, count=-5)

        assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_update_count_zone_not_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating count for non-existent zone logs warning."""
        with patch.object(polygon_zone_service, "get_zone", return_value=None):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                await polygon_zone_service.update_count(999, count=5)

                mock_logger.warning.assert_called_once()
                assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_update_count_logs_debug(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test count update logs debug message."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                await polygon_zone_service.update_count(1, count=3)

                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args
                assert "Updated polygon zone" in call_args[0][0]


# =============================================================================
# set_active Tests
# =============================================================================


class TestSetActive:
    """Tests for set_active method."""

    @pytest.mark.asyncio
    async def test_set_active_enable(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test enabling a zone."""
        sample_zone.is_active = False

        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            result = await polygon_zone_service.set_active(1, is_active=True)

            assert result is not None
            assert result.is_active is True
            assert mock_session.flush.called
            assert mock_session.refresh.called

    @pytest.mark.asyncio
    async def test_set_active_disable(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test disabling a zone."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            result = await polygon_zone_service.set_active(1, is_active=False)

            assert result is not None
            assert result.is_active is False

    @pytest.mark.asyncio
    async def test_set_active_zone_not_found(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test setting active for non-existent zone returns None."""
        with patch.object(polygon_zone_service, "get_zone", return_value=None):
            result = await polygon_zone_service.set_active(999, is_active=True)

            assert result is None
            assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_set_active_logs_change(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Test set_active logs the event."""
        with patch.object(polygon_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                await polygon_zone_service.set_active(1, is_active=False)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Set polygon zone" in call_args[0][0]
                assert "active=False" in call_args[0][0]


# =============================================================================
# reset_all_counts Tests
# =============================================================================


class TestResetAllCounts:
    """Tests for reset_all_counts method."""

    @pytest.mark.asyncio
    async def test_reset_all_counts_multiple_zones(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test resetting counts for multiple zones."""
        zone1 = PolygonZone(
            id=1,
            camera_id="cam1",
            name="Zone 1",
            polygon=[[0, 0], [1, 1], [1, 0]],
            current_count=5,
        )
        zone2 = PolygonZone(
            id=2,
            camera_id="cam1",
            name="Zone 2",
            polygon=[[0, 0], [1, 1], [1, 0]],
            current_count=10,
        )

        with patch.object(polygon_zone_service, "get_zones_by_camera", return_value=[zone1, zone2]):
            result = await polygon_zone_service.reset_all_counts("cam1")

            assert result == 2
            assert zone1.current_count == 0
            assert zone2.current_count == 0
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_reset_all_counts_empty(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test resetting counts for camera with no zones."""
        with patch.object(polygon_zone_service, "get_zones_by_camera", return_value=[]):
            result = await polygon_zone_service.reset_all_counts("empty_camera")

            assert result == 0
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_reset_all_counts_logs_reset(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test reset_all_counts logs the event."""
        zone = PolygonZone(
            id=1, camera_id="cam1", name="Zone", polygon=[[0, 0], [1, 1], [1, 0]], current_count=5
        )

        with patch.object(polygon_zone_service, "get_zones_by_camera", return_value=[zone]):
            with patch("backend.services.polygon_zone_service.logger") as mock_logger:
                await polygon_zone_service.reset_all_counts("cam1")

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Reset counts" in call_args[0][0]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetPolygonZoneService:
    """Tests for get_polygon_zone_service factory function."""

    def test_get_polygon_zone_service(self, mock_session: AsyncMock) -> None:
        """Test factory function creates service instance."""
        service = get_polygon_zone_service(mock_session)

        assert isinstance(service, PolygonZoneService)
        assert service.db == mock_session
