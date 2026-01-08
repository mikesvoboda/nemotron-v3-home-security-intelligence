"""Tests for CameraRepository camera-specific operations."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.repositories.camera_repository import CameraRepository


class TestCameraRepository:
    """Test suite for CameraRepository operations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def camera_repository(self, mock_session: AsyncMock) -> CameraRepository:
        """Create a camera repository instance."""
        return CameraRepository(mock_session)

    @pytest.mark.asyncio
    async def test_find_by_status_returns_matching_cameras(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_status returns cameras with matching status."""
        cameras = [
            Camera(id="cam1", name="Camera 1", folder_path="/path1", status="online"),
            Camera(id="cam2", name="Camera 2", folder_path="/path2", status="online"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = cameras
        mock_session.execute.return_value = mock_result

        result = await camera_repository.find_by_status("online")

        assert len(result) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_name_returns_camera(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_name returns camera when found."""
        camera = Camera(id="front_door", name="Front Door", folder_path="/front")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.find_by_name("Front Door")

        assert result == camera

    @pytest.mark.asyncio
    async def test_find_by_name_returns_none_when_not_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_name returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.find_by_name("Nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_folder_path_returns_camera(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_folder_path returns camera when found."""
        camera = Camera(id="front_door", name="Front Door", folder_path="/export/foscam/front")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.find_by_folder_path("/export/foscam/front")

        assert result == camera

    @pytest.mark.asyncio
    async def test_find_by_folder_path_returns_none_when_not_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test find_by_folder_path returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.find_by_folder_path("/nonexistent/path")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_returns_true_when_updated(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test update_status returns True when camera is updated."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        result = await camera_repository.update_status("front_door", "offline")

        assert result is True
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_returns_false_when_not_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test update_status returns False when camera not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        result = await camera_repository.update_status("nonexistent", "offline")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_last_seen_returns_true_when_updated(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test update_last_seen returns True when updated."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        now = datetime.now(UTC)

        result = await camera_repository.update_last_seen("front_door", now)

        assert result is True

    @pytest.mark.asyncio
    async def test_list_online_returns_online_cameras(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test list_online returns only online cameras."""
        cameras = [Camera(id="cam1", name="Camera 1", folder_path="/path1", status="online")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = cameras
        mock_session.execute.return_value = mock_result

        result = await camera_repository.list_online()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_offline_returns_offline_cameras(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test list_offline returns only offline cameras."""
        cameras = [Camera(id="cam2", name="Camera 2", folder_path="/path2", status="offline")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = cameras
        mock_session.execute.return_value = mock_result

        result = await camera_repository.list_offline()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_name_exists_returns_true_when_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test name_exists returns True when camera with name exists."""
        camera = Camera(id="front_door", name="Front Door", folder_path="/path")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.name_exists("Front Door")

        assert result is True

    @pytest.mark.asyncio
    async def test_name_exists_returns_false_when_not_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test name_exists returns False when camera not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.name_exists("Nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_folder_path_exists_returns_true_when_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test folder_path_exists returns True when path exists."""
        camera = Camera(id="front_door", name="Front Door", folder_path="/export/foscam/front")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.folder_path_exists("/export/foscam/front")

        assert result is True

    @pytest.mark.asyncio
    async def test_folder_path_exists_returns_false_when_not_found(
        self, camera_repository: CameraRepository, mock_session: AsyncMock
    ) -> None:
        """Test folder_path_exists returns False when path not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.folder_path_exists("/nonexistent/path")

        assert result is False
