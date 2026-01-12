"""Camera status service with WebSocket broadcasting.

This module provides a service for managing camera status changes with
automatic WebSocket broadcasting to notify connected clients in real-time.

Example:
    async with get_session() as session:
        redis = await get_redis()
        service = CameraStatusService(session, redis)
        await service.set_camera_status(
            camera_id="front_door",
            status="offline",
            reason="No activity detected for 5 minutes"
        )
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.api.schemas.websocket import WebSocketCameraEventType
from backend.core.logging import get_logger
from backend.models import Camera
from backend.repositories.camera_repository import CameraRepository
from backend.services.event_broadcaster import get_broadcaster

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient

logger = get_logger(__name__)


def _get_event_type_for_status(status: str) -> WebSocketCameraEventType:
    """Map camera status to the appropriate WebSocket event type.

    Args:
        status: Camera status string (online, offline, error, unknown).

    Returns:
        The corresponding WebSocketCameraEventType.
    """
    status_lower = status.lower()
    if status_lower == "online":
        return WebSocketCameraEventType.CAMERA_ONLINE
    if status_lower == "offline":
        return WebSocketCameraEventType.CAMERA_OFFLINE
    if status_lower == "error":
        return WebSocketCameraEventType.CAMERA_ERROR
    # Default to updated for unknown statuses
    return WebSocketCameraEventType.CAMERA_UPDATED


class CameraStatusService:
    """Service for managing camera status changes with WebSocket broadcasting.

    This service wraps the CameraRepository to provide status change operations
    that automatically broadcast changes to connected WebSocket clients.

    Attributes:
        session: SQLAlchemy async session for database operations.
        redis: Redis client for pub/sub broadcasting.
        repository: Camera repository for database operations.

    Example:
        async with get_session() as session:
            redis = await get_redis()
            service = CameraStatusService(session, redis)

            # Set camera status with broadcast
            camera = await service.set_camera_status(
                camera_id="front_door",
                status="offline",
                reason="No activity detected"
            )
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient,
    ) -> None:
        """Initialize the camera status service.

        Args:
            session: SQLAlchemy async session for database operations.
            redis: Redis client for pub/sub broadcasting.
        """
        self._session = session
        self._redis = redis
        self._repository = CameraRepository(session)

    async def set_camera_status(
        self,
        camera_id: str,
        status: str,
        reason: str | None = None,
    ) -> Camera | None:
        """Set a camera's status and broadcast the change via WebSocket.

        This method updates the camera's status in the database and broadcasts
        a WebSocket message to all connected clients about the status change.

        Args:
            camera_id: The ID of the camera to update.
            status: The new status (online, offline, error, unknown).
            reason: Optional reason for the status change.

        Returns:
            The updated Camera if found, None if the camera doesn't exist.

        Example:
            camera = await service.set_camera_status(
                camera_id="front_door",
                status="offline",
                reason="Connection timeout"
            )
        """
        # Get the camera first to capture previous status
        camera = await self._repository.get_by_id(camera_id)
        if camera is None:
            logger.warning(
                f"Cannot set status for camera {camera_id}: camera not found",
                extra={"camera_id": camera_id, "status": status},
            )
            return None

        previous_status = camera.status

        # Skip update if status hasn't changed
        if previous_status == status:
            logger.debug(
                f"Camera {camera_id} status unchanged: {status}",
                extra={"camera_id": camera_id, "status": status},
            )
            return camera

        # Update the status in the database
        updated_camera = await self._repository.set_status(camera_id, status)
        if updated_camera is None:
            return None

        # Broadcast the status change via WebSocket
        await self._broadcast_status_change(
            camera=updated_camera,
            previous_status=previous_status,
            reason=reason,
        )

        return updated_camera

    async def set_camera_online(
        self,
        camera_id: str,
        reason: str | None = None,
    ) -> Camera | None:
        """Set a camera's status to online and broadcast the change.

        Convenience method for setting a camera to online status.

        Args:
            camera_id: The ID of the camera to update.
            reason: Optional reason for the status change.

        Returns:
            The updated Camera if found, None if the camera doesn't exist.
        """
        return await self.set_camera_status(camera_id, "online", reason)

    async def set_camera_offline(
        self,
        camera_id: str,
        reason: str | None = None,
    ) -> Camera | None:
        """Set a camera's status to offline and broadcast the change.

        Convenience method for setting a camera to offline status.

        Args:
            camera_id: The ID of the camera to update.
            reason: Optional reason for the status change.

        Returns:
            The updated Camera if found, None if the camera doesn't exist.
        """
        return await self.set_camera_status(camera_id, "offline", reason)

    async def set_camera_error(
        self,
        camera_id: str,
        reason: str | None = None,
    ) -> Camera | None:
        """Set a camera's status to error and broadcast the change.

        Convenience method for setting a camera to error status.

        Args:
            camera_id: The ID of the camera to update.
            reason: Optional reason for the error state.

        Returns:
            The updated Camera if found, None if the camera doesn't exist.
        """
        return await self.set_camera_status(camera_id, "error", reason)

    async def _broadcast_status_change(
        self,
        camera: Camera,
        previous_status: str,
        reason: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Broadcast a camera status change to WebSocket clients.

        Args:
            camera: The camera with updated status.
            previous_status: The previous status before the change.
            reason: Optional reason for the status change.
            details: Optional additional details about the status change.
        """
        try:
            broadcaster = await get_broadcaster(self._redis)
            timestamp = datetime.now(UTC).isoformat()

            # Determine event type based on the new status
            event_type = _get_event_type_for_status(camera.status)

            status_data = {
                "event_type": event_type.value,
                "camera_id": camera.id,
                "camera_name": camera.name,
                "status": camera.status,
                "timestamp": timestamp,
                "previous_status": previous_status,
                "reason": reason,
                "details": details,
            }

            subscriber_count = await broadcaster.broadcast_camera_status(status_data)

            logger.info(
                f"Broadcast camera status change: {camera.id} {previous_status} -> {camera.status}",
                extra={
                    "camera_id": camera.id,
                    "event_type": event_type.value,
                    "previous_status": previous_status,
                    "new_status": camera.status,
                    "reason": reason,
                    "subscribers": subscriber_count,
                },
            )
        except Exception as e:
            # Log the error but don't fail the status update
            # Broadcasting is best-effort - the database update succeeded
            logger.error(
                f"Failed to broadcast camera status change for {camera.id}: {e}",
                extra={
                    "camera_id": camera.id,
                    "status": camera.status,
                    "error": str(e),
                },
                exc_info=True,
            )


async def broadcast_camera_status_change(
    redis: RedisClient,
    camera_id: str,
    camera_name: str,
    status: str,
    previous_status: str | None = None,
    reason: str | None = None,
    details: dict[str, object] | None = None,
    event_type: WebSocketCameraEventType | None = None,
) -> int:
    """Standalone function to broadcast a camera status change.

    This function can be used when you've already updated the camera status
    directly and just need to broadcast the change. For a complete solution
    that updates the database and broadcasts, use CameraStatusService instead.

    Args:
        redis: Redis client for pub/sub broadcasting.
        camera_id: The camera ID.
        camera_name: The human-readable camera name.
        status: The new camera status.
        previous_status: The previous status (optional).
        reason: Optional reason for the status change.
        details: Optional additional details about the status change.
        event_type: Optional explicit event type. If not provided, derived from status.

    Returns:
        Number of Redis subscribers that received the message.

    Example:
        await broadcast_camera_status_change(
            redis=redis,
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="offline",
            previous_status="online",
            reason="Connection timeout"
        )
    """
    broadcaster = await get_broadcaster(redis)
    timestamp = datetime.now(UTC).isoformat()

    # Use provided event type or derive from status
    resolved_event_type = event_type or _get_event_type_for_status(status)

    status_data = {
        "event_type": resolved_event_type.value,
        "camera_id": camera_id,
        "camera_name": camera_name,
        "status": status,
        "timestamp": timestamp,
        "previous_status": previous_status,
        "reason": reason,
        "details": details,
    }

    return await broadcaster.broadcast_camera_status(status_data)
