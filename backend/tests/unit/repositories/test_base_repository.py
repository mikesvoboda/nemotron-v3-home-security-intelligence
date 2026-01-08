"""Tests for BaseRepository generic operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.repositories.base import BaseRepository


class TestBaseRepository:
    """Test suite for BaseRepository generic operations."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def camera_repository(self, mock_session: AsyncMock) -> BaseRepository[Camera, str]:
        """Create a base repository instance for Camera model."""
        return BaseRepository(Camera, mock_session)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test get_by_id returns entity when found."""
        camera = Camera(id="test_cam", name="Test Camera", folder_path="/path")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.get_by_id("test_cam")

        assert result == camera

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test get_by_id returns None when entity not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_returns_entities(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test list_all returns all entities."""
        cameras = [
            Camera(id="cam1", name="Camera 1", folder_path="/path1"),
            Camera(id="cam2", name="Camera 2", folder_path="/path2"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = cameras
        mock_session.execute.return_value = mock_result

        result = await camera_repository.list_all()

        assert len(result) == 2
        assert result[0].id == "cam1"

    @pytest.mark.asyncio
    async def test_list_all_with_pagination(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test list_all respects skip and limit."""
        cameras = [Camera(id="cam2", name="Camera 2", folder_path="/path2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = cameras
        mock_session.execute.return_value = mock_result

        result = await camera_repository.list_all(skip=1, limit=1)

        assert len(result) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_returns_total(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test count returns total number of entities."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await camera_repository.count()

        assert result == 5

    @pytest.mark.asyncio
    async def test_create_adds_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test create adds and returns entity."""
        camera = Camera(id="new_cam", name="New Camera", folder_path="/new/path")

        result = await camera_repository.create(camera)

        mock_session.add.assert_called_once_with(camera)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(camera)
        assert result == camera

    @pytest.mark.asyncio
    async def test_update_modifies_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test update modifies and returns entity."""
        camera = Camera(id="cam1", name="Updated Camera", folder_path="/path")

        result = await camera_repository.update(camera)

        mock_session.merge.assert_called_once_with(camera)
        mock_session.flush.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_removes_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test delete removes entity."""
        camera = Camera(id="cam1", name="Camera", folder_path="/path")

        await camera_repository.delete(camera)

        mock_session.delete.assert_called_once_with(camera)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_id_returns_true_when_deleted(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test delete_by_id returns True when entity is deleted."""
        camera = Camera(id="cam1", name="Camera", folder_path="/path")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = camera
        mock_session.execute.return_value = mock_result

        result = await camera_repository.delete_by_id("cam1")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_by_id_returns_false_when_not_found(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test delete_by_id returns False when entity not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await camera_repository.delete_by_id("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_found(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test exists returns True when entity exists."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await camera_repository.exists("cam1")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_found(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test exists returns False when entity doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        result = await camera_repository.exists("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_save_creates_new_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test save creates new entity when it doesn't exist."""
        camera = Camera(id="new_cam", name="New Camera", folder_path="/path")
        mock_exists_result = MagicMock()
        mock_exists_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_exists_result

        result = await camera_repository.save(camera)

        mock_session.add.assert_called_once_with(camera)
        assert result == camera

    @pytest.mark.asyncio
    async def test_save_updates_existing_entity(
        self, camera_repository: BaseRepository[Camera, str], mock_session: AsyncMock
    ) -> None:
        """Test save updates entity when it exists."""
        camera = Camera(id="existing_cam", name="Updated Camera", folder_path="/path")
        mock_exists_result = MagicMock()
        mock_exists_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_exists_result

        result = await camera_repository.save(camera)

        mock_session.merge.assert_called_once_with(camera)
        assert result is not None
