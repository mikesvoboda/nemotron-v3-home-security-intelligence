"""Repository for Camera entity database operations.

This module provides the CameraRepository class which extends the generic
Repository base class with camera-specific query methods.

Example:
    async with get_session() as session:
        repo = CameraRepository(session)
        camera = await repo.get_by_folder_path("/export/foscam/front_door")
        online_cameras = await repo.get_online_cameras()
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.models import Camera
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class CameraRepository(Repository[Camera]):
    """Repository for Camera entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    camera-specific query methods.

    Attributes:
        model_class: Set to Camera for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = CameraRepository(session)

            # Get camera by ID
            camera = await repo.get_by_id("front_door")

            # Get camera by folder path
            camera = await repo.get_by_folder_path("/export/foscam/front_door")

            # Get all online cameras
            online = await repo.get_online_cameras()
    """

    model_class = Camera

    async def get_by_folder_path(self, folder_path: str) -> Camera | None:
        """Find a camera by its upload folder path.

        Args:
            folder_path: The file system path where the camera uploads images.
                         Should be an absolute path like "/export/foscam/front_door".

        Returns:
            The Camera if found, None otherwise.
        """
        stmt = select(Camera).where(Camera.folder_path == folder_path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Camera | None:
        """Find a camera by its display name.

        Args:
            name: The human-readable camera name (e.g., "Front Door Camera").

        Returns:
            The Camera if found, None otherwise.

        Note:
            Camera names should be unique per the database constraints,
            so this will return at most one camera.
        """
        stmt = select(Camera).where(Camera.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_online_cameras(self) -> Sequence[Camera]:
        """Get all cameras with status='online'.

        Returns:
            A sequence of cameras that are currently online.
        """
        return await self.get_by_status("online")

    async def get_by_status(self, status: str) -> Sequence[Camera]:
        """Get all cameras with a specific status.

        Args:
            status: The status to filter by (e.g., "online", "offline", "error").

        Returns:
            A sequence of cameras with the specified status.
        """
        stmt = select(Camera).where(Camera.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_last_seen(self, camera_id: str) -> Camera | None:
        """Update a camera's last_seen_at timestamp to the current time.

        This method is typically called when new activity is detected
        from a camera to track its last known activity time.

        Args:
            camera_id: The ID of the camera to update.

        Returns:
            The updated Camera if found, None if the camera doesn't exist.
        """
        camera = await self.get_by_id(camera_id)
        if camera is None:
            return None

        camera.last_seen_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(camera)
        return camera

    async def set_status(self, camera_id: str, status: str) -> Camera | None:
        """Set a camera's operational status.

        Args:
            camera_id: The ID of the camera to update.
            status: The new status (e.g., "online", "offline", "error").

        Returns:
            The updated Camera if found, None if the camera doesn't exist.

        Note:
            Valid status values are constrained by the database CHECK constraint:
            'online', 'offline', 'error', 'unknown'.
        """
        camera = await self.get_by_id(camera_id)
        if camera is None:
            return None

        camera.status = status
        await self.session.flush()
        await self.session.refresh(camera)
        return camera
