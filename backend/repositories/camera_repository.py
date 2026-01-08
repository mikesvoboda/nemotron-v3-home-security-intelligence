"""Camera-specific repository operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera, str]):
    """Repository for Camera-specific database operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the camera repository.

        Args:
            db: The async database session
        """
        super().__init__(Camera, db)

    async def find_by_status(self, status: str) -> list[Camera]:
        """Find all cameras with a specific status.

        Args:
            status: The status to filter by (e.g., 'online', 'offline')

        Returns:
            List of cameras with matching status
        """
        stmt = select(Camera).where(Camera.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_name(self, name: str) -> Camera | None:
        """Find a camera by its name.

        Args:
            name: The camera name

        Returns:
            The camera if found, None otherwise
        """
        stmt = select(Camera).where(Camera.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_folder_path(self, folder_path: str) -> Camera | None:
        """Find a camera by its folder path.

        Args:
            folder_path: The folder path to search for

        Returns:
            The camera if found, None otherwise
        """
        stmt = select(Camera).where(Camera.folder_path == folder_path)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, camera_id: str, status: str) -> bool:
        """Update a camera's status.

        Args:
            camera_id: The camera ID
            status: The new status

        Returns:
            True if updated, False if camera not found
        """
        stmt = update(Camera).where(Camera.id == camera_id).values(status=status)
        result: CursorResult = await self.db.execute(stmt)  # type: ignore[assignment]
        await self.db.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def update_last_seen(self, camera_id: str, last_seen: datetime) -> bool:
        """Update a camera's last seen timestamp.

        Args:
            camera_id: The camera ID
            last_seen: The new last seen timestamp

        Returns:
            True if updated, False if camera not found
        """
        stmt = update(Camera).where(Camera.id == camera_id).values(last_seen=last_seen)
        result: CursorResult = await self.db.execute(stmt)  # type: ignore[assignment]
        await self.db.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def list_online(self) -> list[Camera]:
        """List all online cameras.

        Returns:
            List of online cameras
        """
        return await self.find_by_status("online")

    async def list_offline(self) -> list[Camera]:
        """List all offline cameras.

        Returns:
            List of offline cameras
        """
        return await self.find_by_status("offline")

    async def name_exists(self, name: str) -> bool:
        """Check if a camera with the given name exists.

        Args:
            name: The camera name to check

        Returns:
            True if a camera with that name exists
        """
        camera = await self.find_by_name(name)
        return camera is not None

    async def folder_path_exists(self, folder_path: str) -> bool:
        """Check if a camera with the given folder path exists.

        Args:
            folder_path: The folder path to check

        Returns:
            True if a camera with that folder path exists
        """
        camera = await self.find_by_folder_path(folder_path)
        return camera is not None
