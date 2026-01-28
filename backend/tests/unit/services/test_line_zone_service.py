"""Unit tests for LineZoneService.

Tests cover:
- create_zone() - Zone creation with logging
- get_zone() - Zone retrieval by ID
- get_zones_by_camera() - Camera-specific zone queries
- get_all_zones() - Retrieval of all zones across cameras
- update_zone() - Partial updates with field validation
- delete_zone() - Zone deletion with logging
- increment_count() - Count increment with direction validation
- reset_counts() - Count reset for individual zones

Edge cases: invalid directions, non-existent zones, target class conversion, empty results.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.analytics_zone import LineZoneCreate, LineZoneUpdate
from backend.models.analytics_zone import LineZone
from backend.services.line_zone_service import LineZoneService, get_line_zone_service


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
def line_zone_service(mock_session: AsyncMock) -> LineZoneService:
    """Create a LineZoneService instance with mocked session."""
    return LineZoneService(mock_session)


@pytest.fixture
def sample_zone_create() -> LineZoneCreate:
    """Create sample line zone creation data."""
    return LineZoneCreate(
        camera_id="front_door",
        name="Driveway Entrance",
        start_x=100,
        start_y=400,
        end_x=500,
        end_y=400,
        alert_on_cross=True,
        target_classes=["person", "car"],
    )


@pytest.fixture
def sample_zone() -> LineZone:
    """Create a sample LineZone instance."""
    zone = LineZone(
        id=1,
        camera_id="front_door",
        name="Driveway Entrance",
        start_x=100,
        start_y=400,
        end_x=500,
        end_y=400,
        in_count=0,
        out_count=0,
        alert_on_cross=True,
        target_classes=["person", "car"],
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
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone_create: LineZoneCreate,
    ) -> None:
        """Test successful zone creation."""
        # Act
        result = await line_zone_service.create_zone("front_door", sample_zone_create)

        # Assert
        assert mock_session.add.called
        assert mock_session.flush.called
        assert mock_session.refresh.called
        assert result.camera_id == "front_door"
        assert result.name == "Driveway Entrance"
        assert result.start_x == 100
        assert result.start_y == 400
        assert result.end_x == 500
        assert result.end_y == 400

    @pytest.mark.asyncio
    async def test_create_zone_with_default_values(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test zone creation uses default values."""
        data = LineZoneCreate(
            camera_id="cam1",
            name="Entry Line",
            start_x=0,
            start_y=0,
            end_x=100,
            end_y=0,
        )

        result = await line_zone_service.create_zone("cam1", data)

        assert result.alert_on_cross is True
        assert result.target_classes == ["person"]

    @pytest.mark.asyncio
    async def test_create_zone_converts_target_classes_to_list(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test zone creation converts target_classes to list."""
        data = LineZoneCreate(
            camera_id="cam1",
            name="Test Line",
            start_x=0,
            start_y=0,
            end_x=100,
            end_y=0,
            target_classes=["person", "car"],
        )

        result = await line_zone_service.create_zone("cam1", data)

        assert isinstance(result.target_classes, list)
        assert "person" in result.target_classes
        assert "car" in result.target_classes

    @pytest.mark.asyncio
    async def test_create_zone_logs_creation(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone_create: LineZoneCreate,
    ) -> None:
        """Test zone creation logs the event."""
        with patch("backend.services.line_zone_service.logger") as mock_logger:
            await line_zone_service.create_zone("front_door", sample_zone_create)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Created line zone" in call_args[0][0]


# =============================================================================
# get_zone Tests
# =============================================================================


class TestGetZone:
    """Tests for get_zone method."""

    @pytest.mark.asyncio
    async def test_get_zone_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test getting an existing zone."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_zone
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zone(1)

        assert result == sample_zone
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_zone_not_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting a non-existent zone returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zone(999)

        assert result is None


# =============================================================================
# get_zones_by_camera Tests
# =============================================================================


class TestGetZonesByCamera:
    """Tests for get_zones_by_camera method."""

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_single_zone(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test getting zones for a camera."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_zone]
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zones_by_camera("front_door")

        assert len(result) == 1
        assert result[0] == sample_zone
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_multiple_zones(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting multiple zones for a camera."""
        zone1 = LineZone(
            id=1, camera_id="cam1", name="Line 1", start_x=0, start_y=0, end_x=100, end_y=0
        )
        zone2 = LineZone(
            id=2, camera_id="cam1", name="Line 2", start_x=0, start_y=100, end_x=100, end_y=100
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [zone1, zone2]
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zones_by_camera("cam1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_zones_by_camera_empty_result(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting zones for camera with no zones."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zones_by_camera("empty_camera")

        assert len(result) == 0


# =============================================================================
# get_all_zones Tests
# =============================================================================


class TestGetAllZones:
    """Tests for get_all_zones method."""

    @pytest.mark.asyncio
    async def test_get_all_zones_multiple_cameras(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting all zones across multiple cameras."""
        zone1 = LineZone(
            id=1, camera_id="cam1", name="Line 1", start_x=0, start_y=0, end_x=100, end_y=0
        )
        zone2 = LineZone(
            id=2, camera_id="cam2", name="Line 2", start_x=0, start_y=0, end_x=100, end_y=0
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [zone1, zone2]
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_all_zones()

        assert len(result) == 2
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_all_zones_empty(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting all zones when none exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_all_zones()

        assert len(result) == 0


# =============================================================================
# update_zone Tests
# =============================================================================


class TestUpdateZone:
    """Tests for update_zone method."""

    @pytest.mark.asyncio
    async def test_update_zone_name(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test updating zone name."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            data = LineZoneUpdate(name="Updated Entry Line")

            result = await line_zone_service.update_zone(1, data)

            assert result is not None
            assert result.name == "Updated Entry Line"
            assert mock_session.flush.called
            assert mock_session.refresh.called

    @pytest.mark.asyncio
    async def test_update_zone_coordinates(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test updating zone coordinates."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            data = LineZoneUpdate(start_x=200, start_y=300, end_x=600, end_y=300)

            result = await line_zone_service.update_zone(1, data)

            assert result is not None
            assert result.start_x == 200
            assert result.start_y == 300
            assert result.end_x == 600
            assert result.end_y == 300

    @pytest.mark.asyncio
    async def test_update_zone_alert_flag(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test updating alert_on_cross flag."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            data = LineZoneUpdate(alert_on_cross=False)

            result = await line_zone_service.update_zone(1, data)

            assert result is not None
            assert result.alert_on_cross is False

    @pytest.mark.asyncio
    async def test_update_zone_target_classes(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test updating target classes."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            data = LineZoneUpdate(target_classes=["person", "bicycle", "car"])

            result = await line_zone_service.update_zone(1, data)

            assert result is not None
            assert len(result.target_classes) == 3

    @pytest.mark.asyncio
    async def test_update_zone_not_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test updating non-existent zone returns None."""
        with patch.object(line_zone_service, "get_zone", return_value=None):
            data = LineZoneUpdate(name="Test")

            result = await line_zone_service.update_zone(999, data)

            assert result is None
            assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_update_zone_logs_update(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test zone update logs the event."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                data = LineZoneUpdate(name="Updated")

                await line_zone_service.update_zone(1, data)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Updated line zone" in call_args[0][0]


# =============================================================================
# delete_zone Tests
# =============================================================================


class TestDeleteZone:
    """Tests for delete_zone method."""

    @pytest.mark.asyncio
    async def test_delete_zone_success(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test successful zone deletion."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            result = await line_zone_service.delete_zone(1)

            assert result is True
            assert mock_session.delete.called
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_delete_zone_not_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test deleting non-existent zone returns False."""
        with patch.object(line_zone_service, "get_zone", return_value=None):
            result = await line_zone_service.delete_zone(999)

            assert result is False
            assert not mock_session.delete.called

    @pytest.mark.asyncio
    async def test_delete_zone_logs_deletion(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test zone deletion logs the event."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                await line_zone_service.delete_zone(1)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Deleted line zone" in call_args[0][0]


# =============================================================================
# increment_count Tests
# =============================================================================


class TestIncrementCount:
    """Tests for increment_count method."""

    @pytest.mark.asyncio
    async def test_increment_count_in_direction(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test incrementing in_count."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            await line_zone_service.increment_count(1, direction="in")

            assert sample_zone.in_count == 1
            assert sample_zone.out_count == 0
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_increment_count_out_direction(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test incrementing out_count."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            await line_zone_service.increment_count(1, direction="out")

            assert sample_zone.in_count == 0
            assert sample_zone.out_count == 1

    @pytest.mark.asyncio
    async def test_increment_count_multiple_times(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test incrementing count multiple times."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            await line_zone_service.increment_count(1, direction="in")
            await line_zone_service.increment_count(1, direction="in")
            await line_zone_service.increment_count(1, direction="out")

            assert sample_zone.in_count == 2
            assert sample_zone.out_count == 1

    @pytest.mark.asyncio
    async def test_increment_count_invalid_direction_raises(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test incrementing with invalid direction raises ValueError."""
        with pytest.raises(ValueError, match="Direction must be 'in' or 'out'"):
            await line_zone_service.increment_count(1, direction="invalid")

        assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_increment_count_zone_not_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test incrementing count for non-existent zone logs warning."""
        with patch.object(line_zone_service, "get_zone", return_value=None):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                await line_zone_service.increment_count(999, direction="in")

                mock_logger.warning.assert_called_once()
                assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_increment_count_logs_debug(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test count increment logs debug message."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                await line_zone_service.increment_count(1, direction="in")

                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args
                assert "Incremented" in call_args[0][0]


# =============================================================================
# reset_counts Tests
# =============================================================================


class TestResetCounts:
    """Tests for reset_counts method."""

    @pytest.mark.asyncio
    async def test_reset_counts_success(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test successful count reset."""
        sample_zone.in_count = 10
        sample_zone.out_count = 5

        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            await line_zone_service.reset_counts(1)

            assert sample_zone.in_count == 0
            assert sample_zone.out_count == 0
            assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_reset_counts_already_zero(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test resetting counts that are already zero."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            await line_zone_service.reset_counts(1)

            assert sample_zone.in_count == 0
            assert sample_zone.out_count == 0

    @pytest.mark.asyncio
    async def test_reset_counts_zone_not_found(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Test resetting counts for non-existent zone logs warning."""
        with patch.object(line_zone_service, "get_zone", return_value=None):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                await line_zone_service.reset_counts(999)

                mock_logger.warning.assert_called_once()
                assert not mock_session.flush.called

    @pytest.mark.asyncio
    async def test_reset_counts_logs_info(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Test count reset logs info message."""
        with patch.object(line_zone_service, "get_zone", return_value=sample_zone):
            with patch("backend.services.line_zone_service.logger") as mock_logger:
                await line_zone_service.reset_counts(1)

                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "Reset counts" in call_args[0][0]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetLineZoneService:
    """Tests for get_line_zone_service factory function."""

    def test_get_line_zone_service(self, mock_session: AsyncMock) -> None:
        """Test factory function creates service instance."""
        service = get_line_zone_service(mock_session)

        assert isinstance(service, LineZoneService)
        assert service.db == mock_session
