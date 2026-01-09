"""Camera service with optimistic concurrency control.

This module provides the CameraService class for camera status updates
with timestamp-based optimistic concurrency control to prevent race conditions
when multiple concurrent updates occur.

Example:
    async with get_session() as session:
        service = CameraService(session)
        updated, camera = await service.update_camera_status(
            camera_id="front_door",
            new_status="online",
            timestamp=datetime.now(UTC),
        )
        if updated:
            print(f"Camera {camera.id} updated to {camera.status}")
        else:
            print("Update skipped - newer data exists")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.repositories.camera_repository import CameraRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models import Camera


class CameraService:
    """Service for camera operations with optimistic concurrency control.

    This service provides safe methods for updating camera status that
    prevent race conditions when concurrent updates occur. It uses
    timestamp-based optimistic concurrency control to ensure that
    newer data is never overwritten by stale updates.

    Attributes:
        session: The async database session for operations.
        repository: The camera repository for database access.

    Example:
        async with get_session() as session:
            service = CameraService(session)

            # Two concurrent status updates
            update1_time = datetime.now(UTC)
            update2_time = update1_time + timedelta(seconds=1)

            # If update2 arrives first
            updated, camera = await service.update_camera_status(
                "front_door", "online", update2_time
            )
            assert updated is True

            # Then update1 arrives (stale data)
            updated, camera = await service.update_camera_status(
                "front_door", "offline", update1_time
            )
            assert updated is False  # Skipped - update2 had newer timestamp
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the camera service.

        Args:
            session: An async SQLAlchemy session for database operations.
        """
        self.session = session
        self.repository = CameraRepository(session)

    async def update_camera_status(
        self,
        camera_id: str,
        new_status: str,
        timestamp: datetime | None = None,
    ) -> tuple[bool, Camera | None]:
        """Update camera status with optimistic concurrency control.

        This method safely updates a camera's status and last_seen_at timestamp
        using optimistic concurrency control. The update only succeeds if the
        provided timestamp is newer than the existing last_seen_at value,
        preventing race conditions where stale updates overwrite newer data.

        Args:
            camera_id: The ID of the camera to update.
            new_status: The new status to set (e.g., "online", "offline", "error").
            timestamp: The timestamp of the update. If None, uses current UTC time.
                Update only occurs if this is newer than existing last_seen_at.

        Returns:
            A tuple of (updated: bool, camera: Camera | None):
            - (True, Camera) if the update was applied (timestamp was newer)
            - (False, Camera) if the update was skipped (existing timestamp is newer)
            - (False, None) if the camera doesn't exist

        Example:
            # Update camera status from file watcher event
            async with get_session() as session:
                service = CameraService(session)
                updated, camera = await service.update_camera_status(
                    camera_id="front_door",
                    new_status="online",
                    timestamp=datetime.now(UTC),
                )

                if updated:
                    logger.info(f"Camera {camera.id} status updated to {camera.status}")
                elif camera:
                    logger.debug(f"Skipped stale update for {camera.id}")
                else:
                    logger.warning(f"Camera not found: {camera_id}")
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        return await self.repository.update_status_optimistic(
            camera_id=camera_id,
            new_status=new_status,
            new_last_seen=timestamp,
        )

    async def get_camera(self, camera_id: str) -> Camera | None:
        """Get a camera by ID.

        Args:
            camera_id: The ID of the camera to retrieve.

        Returns:
            The Camera if found, None otherwise.
        """
        return await self.repository.get_by_id(camera_id)

    async def get_camera_by_folder_path(self, folder_path: str) -> Camera | None:
        """Get a camera by its upload folder path.

        Args:
            folder_path: The file system path where the camera uploads images.

        Returns:
            The Camera if found, None otherwise.
        """
        return await self.repository.get_by_folder_path(folder_path)

    async def set_camera_online(
        self,
        camera_id: str,
        timestamp: datetime | None = None,
    ) -> tuple[bool, Camera | None]:
        """Mark a camera as online.

        Convenience method for setting camera status to "online".

        Args:
            camera_id: The ID of the camera to update.
            timestamp: The timestamp of the update. If None, uses current UTC time.

        Returns:
            A tuple of (updated: bool, camera: Camera | None).
        """
        return await self.update_camera_status(camera_id, "online", timestamp)

    async def set_camera_offline(
        self,
        camera_id: str,
        timestamp: datetime | None = None,
    ) -> tuple[bool, Camera | None]:
        """Mark a camera as offline.

        Convenience method for setting camera status to "offline".

        Args:
            camera_id: The ID of the camera to update.
            timestamp: The timestamp of the update. If None, uses current UTC time.

        Returns:
            A tuple of (updated: bool, camera: Camera | None).
        """
        return await self.update_camera_status(camera_id, "offline", timestamp)

    async def set_camera_error(
        self,
        camera_id: str,
        timestamp: datetime | None = None,
    ) -> tuple[bool, Camera | None]:
        """Mark a camera as having an error.

        Convenience method for setting camera status to "error".

        Args:
            camera_id: The ID of the camera to update.
            timestamp: The timestamp of the update. If None, uses current UTC time.

        Returns:
            A tuple of (updated: bool, camera: Camera | None).
        """
        return await self.update_camera_status(camera_id, "error", timestamp)


def get_camera_service(session: AsyncSession) -> CameraService:
    """Get a CameraService instance for the given session.

    This creates a new CameraService bound to the provided session.
    Each request/transaction should use its own session and service.

    Args:
        session: An async SQLAlchemy session for database operations.

    Returns:
        A CameraService instance bound to the session.

    Example:
        async with get_session() as session:
            service = get_camera_service(session)
            updated, camera = await service.update_camera_status(
                "front_door", "online"
            )
    """
    return CameraService(session)
