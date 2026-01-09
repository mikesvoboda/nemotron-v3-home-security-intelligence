"""Unit tests for CameraService.

Tests the camera service's optimistic concurrency control logic
using mocked dependencies.

Run with: uv run pytest backend/tests/unit/services/test_camera_service.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.camera_service import CameraService, get_camera_service


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_camera():
    """Create a mock camera object."""
    camera = MagicMock()
    camera.id = "front_door"
    camera.name = "Front Door Camera"
    camera.status = "online"
    camera.last_seen_at = datetime.now(UTC)
    camera.folder_path = "/export/foscam/front_door"
    return camera


class TestCameraServiceUpdateStatus:
    """Test update_camera_status method."""

    @pytest.mark.asyncio
    async def test_update_camera_status_calls_repository(self, mock_session, mock_camera):
        """Test that update_camera_status delegates to repository correctly."""
        service = CameraService(mock_session)
        timestamp = datetime.now(UTC)

        # Mock the repository method
        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        updated, camera = await service.update_camera_status("front_door", "online", timestamp)

        assert updated is True
        assert camera == mock_camera
        service.repository.update_status_optimistic.assert_called_once_with(
            camera_id="front_door",
            new_status="online",
            new_last_seen=timestamp,
        )

    @pytest.mark.asyncio
    async def test_update_camera_status_uses_current_time_if_none(self, mock_session, mock_camera):
        """Test that None timestamp defaults to current UTC time."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.update_camera_status("front_door", "online", None)

        # Verify a timestamp was passed (can't check exact value)
        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_last_seen"] is not None
        assert isinstance(call_args.kwargs["new_last_seen"], datetime)

    @pytest.mark.asyncio
    async def test_update_camera_status_returns_false_for_stale_update(
        self, mock_session, mock_camera
    ):
        """Test that stale updates return (False, camera)."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(False, mock_camera))

        updated, camera = await service.update_camera_status(
            "front_door", "offline", datetime.now(UTC)
        )

        assert updated is False
        assert camera == mock_camera

    @pytest.mark.asyncio
    async def test_update_camera_status_returns_none_for_missing_camera(self, mock_session):
        """Test that missing camera returns (False, None)."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(False, None))

        updated, camera = await service.update_camera_status(
            "nonexistent", "online", datetime.now(UTC)
        )

        assert updated is False
        assert camera is None


class TestCameraServiceConvenienceMethods:
    """Test convenience methods for setting camera status."""

    @pytest.mark.asyncio
    async def test_set_camera_online(self, mock_session, mock_camera):
        """Test set_camera_online convenience method."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_online("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "online"

    @pytest.mark.asyncio
    async def test_set_camera_offline(self, mock_session, mock_camera):
        """Test set_camera_offline convenience method."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_offline("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "offline"

    @pytest.mark.asyncio
    async def test_set_camera_error(self, mock_session, mock_camera):
        """Test set_camera_error convenience method."""
        service = CameraService(mock_session)

        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_error("front_door")

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_status"] == "error"

    @pytest.mark.asyncio
    async def test_convenience_methods_accept_timestamp(self, mock_session, mock_camera):
        """Test that convenience methods accept explicit timestamp."""
        service = CameraService(mock_session)
        timestamp = datetime.now(UTC) - timedelta(hours=1)

        service.repository.update_status_optimistic = AsyncMock(return_value=(True, mock_camera))

        await service.set_camera_online("front_door", timestamp)

        call_args = service.repository.update_status_optimistic.call_args
        assert call_args.kwargs["new_last_seen"] == timestamp


class TestCameraServiceGetMethods:
    """Test get methods."""

    @pytest.mark.asyncio
    async def test_get_camera(self, mock_session, mock_camera):
        """Test get_camera delegates to repository."""
        service = CameraService(mock_session)

        service.repository.get_by_id = AsyncMock(return_value=mock_camera)

        result = await service.get_camera("front_door")

        assert result == mock_camera
        service.repository.get_by_id.assert_called_once_with("front_door")

    @pytest.mark.asyncio
    async def test_get_camera_by_folder_path(self, mock_session, mock_camera):
        """Test get_camera_by_folder_path delegates to repository."""
        service = CameraService(mock_session)

        service.repository.get_by_folder_path = AsyncMock(return_value=mock_camera)

        result = await service.get_camera_by_folder_path("/export/foscam/front_door")

        assert result == mock_camera
        service.repository.get_by_folder_path.assert_called_once_with("/export/foscam/front_door")


class TestCameraServiceFactory:
    """Test factory function."""

    def test_get_camera_service_returns_service(self, mock_session):
        """Test that get_camera_service creates a service bound to session."""
        service = get_camera_service(mock_session)

        assert isinstance(service, CameraService)
        assert service.session == mock_session
