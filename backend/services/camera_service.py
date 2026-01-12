"""Camera service with optimistic concurrency control and WebSocket events.

This module provides the CameraService class for camera status updates
with timestamp-based optimistic concurrency control to prevent race conditions
when multiple concurrent updates occur.

WebSocket events are emitted when camera status changes, with 30-second
debouncing to prevent rapid online/offline flapping.

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
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.core.websocket.event_schemas import CameraStatus
from backend.core.websocket.event_types import WebSocketEventType
from backend.repositories.camera_repository import CameraRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient
    from backend.models import Camera
    from backend.services.websocket_emitter import WebSocketEmitterService

logger = get_logger(__name__)

# Debounce duration in seconds - status must be stable for this period
CAMERA_STATUS_DEBOUNCE_SECONDS = 30

# Redis key prefix for debounce tracking
CAMERA_DEBOUNCE_KEY_PREFIX = "camera:status:debounce:"


class CameraService:
    """Service for camera operations with optimistic concurrency control.

    This service provides safe methods for updating camera status that
    prevent race conditions when concurrent updates occur. It uses
    timestamp-based optimistic concurrency control to ensure that
    newer data is never overwritten by stale updates.

    WebSocket events are emitted when camera status changes, with debouncing
    to prevent rapid event flapping (default 30 seconds).

    Attributes:
        session: The async database session for operations.
        repository: The camera repository for database access.
        redis: Optional Redis client for debouncing (if None, no debouncing).
        emitter: Optional WebSocket emitter for broadcasting events.

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

    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient | None = None,
        emitter: WebSocketEmitterService | None = None,
    ) -> None:
        """Initialize the camera service.

        Args:
            session: An async SQLAlchemy session for database operations.
            redis: Optional Redis client for debouncing. If None, debouncing is
                disabled and events are emitted immediately on status change.
            emitter: Optional WebSocket emitter for broadcasting events. If None,
                no WebSocket events are emitted.
        """
        self.session = session
        self.repository = CameraRepository(session)
        self._redis = redis
        self._emitter = emitter

    async def update_camera_status(
        self,
        camera_id: str,
        new_status: str,
        timestamp: datetime | None = None,
        *,
        reason: str | None = None,
        emit_event: bool = True,
    ) -> tuple[bool, Camera | None]:
        """Update camera status with optimistic concurrency control.

        This method safely updates a camera's status and last_seen_at timestamp
        using optimistic concurrency control. The update only succeeds if the
        provided timestamp is newer than the existing last_seen_at value,
        preventing race conditions where stale updates overwrite newer data.

        WebSocket events are emitted with 30-second debouncing to prevent rapid
        online/offline flapping notifications.

        Args:
            camera_id: The ID of the camera to update.
            new_status: The new status to set (e.g., "online", "offline", "error").
            timestamp: The timestamp of the update. If None, uses current UTC time.
                Update only occurs if this is newer than existing last_seen_at.
            reason: Optional reason for the status change (e.g., "Connection timeout").
            emit_event: Whether to emit WebSocket events. Defaults to True.

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

        # Get current camera state to capture previous_status
        current_camera = await self.repository.get_by_id(camera_id)
        previous_status = current_camera.status if current_camera else None

        updated, camera = await self.repository.update_status_optimistic(
            camera_id=camera_id,
            new_status=new_status,
            new_last_seen=timestamp,
        )

        # Emit WebSocket event if status actually changed
        if updated and camera and emit_event and previous_status != new_status:
            await self._emit_status_change_event(
                camera=camera,
                previous_status=previous_status,
                reason=reason,
            )

        return updated, camera

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

    # =========================================================================
    # WebSocket Event Emission (Private Methods)
    # =========================================================================

    async def _emit_status_change_event(
        self,
        camera: Camera,
        previous_status: str | None,
        reason: str | None = None,
    ) -> None:
        """Emit WebSocket events for a camera status change with debouncing.

        This method handles debouncing to prevent rapid event flapping when
        cameras go online/offline repeatedly. Events are only emitted after
        the status has been stable for the debounce period (30 seconds).

        Args:
            camera: The camera with updated status.
            previous_status: The previous status before the change.
            reason: Optional reason for the status change.
        """
        if self._emitter is None:
            logger.debug(f"WebSocket emitter not configured, skipping event for {camera.id}")
            return

        # Check if we should debounce this event
        should_emit = await self._should_emit_debounced(
            camera_id=camera.id,
            new_status=camera.status,
        )

        if not should_emit:
            logger.debug(
                f"Camera {camera.id} status change debounced "
                f"({previous_status} -> {camera.status})",
                extra={
                    "camera_id": camera.id,
                    "previous_status": previous_status,
                    "new_status": camera.status,
                    "debounced": True,
                },
            )
            return

        # Emit the appropriate event based on new status
        timestamp = datetime.now(UTC).isoformat()
        try:
            await self._emit_camera_events(
                camera=camera,
                previous_status=previous_status,
                timestamp=timestamp,
                reason=reason,
            )
        except Exception as e:
            # Log error but don't fail the status update
            logger.error(
                f"Failed to emit WebSocket event for camera {camera.id}: {e}",
                extra={
                    "camera_id": camera.id,
                    "status": camera.status,
                    "error": str(e),
                },
                exc_info=True,
            )

    async def _should_emit_debounced(
        self,
        camera_id: str,
        new_status: str,
    ) -> bool:
        """Check if a status change event should be emitted after debouncing.

        Uses Redis to track pending status changes. An event is only emitted
        if the status has been stable for the debounce period.

        The debounce logic:
        1. If no Redis, skip debouncing and always emit
        2. Check if there's a pending status in Redis
        3. If pending status matches new status, emit (stable)
        4. If no pending or different status, set pending and don't emit

        Args:
            camera_id: The camera ID.
            new_status: The new status value.

        Returns:
            True if the event should be emitted, False if debounced.
        """
        if self._redis is None:
            # No Redis configured, skip debouncing
            return True

        debounce_key = f"{CAMERA_DEBOUNCE_KEY_PREFIX}{camera_id}"

        try:
            # Check if there's a pending status change
            pending_status = await self._redis.get(debounce_key)

            if pending_status == new_status:
                # Status matches what was pending - it's been stable long enough
                # Delete the debounce key and emit the event
                await self._redis.delete(debounce_key)
                logger.debug(
                    f"Camera {camera_id} status stable, emitting event",
                    extra={
                        "camera_id": camera_id,
                        "status": new_status,
                    },
                )
                return True
            # Status is new or changed - set/update the pending status
            # Use SETEX to automatically expire after debounce period
            await self._redis.setex(
                debounce_key,
                CAMERA_STATUS_DEBOUNCE_SECONDS,
                new_status,
            )
            logger.debug(
                f"Camera {camera_id} status change pending, will emit in "
                f"{CAMERA_STATUS_DEBOUNCE_SECONDS}s if stable",
                extra={
                    "camera_id": camera_id,
                    "new_status": new_status,
                    "pending_status": pending_status,
                    "debounce_seconds": CAMERA_STATUS_DEBOUNCE_SECONDS,
                },
            )
            return False

        except Exception as e:
            # If Redis fails, emit the event anyway
            logger.warning(
                f"Redis error during debounce check for {camera_id}, emitting: {e}",
                extra={"camera_id": camera_id, "error": str(e)},
            )
            return True

    async def _emit_camera_events(
        self,
        camera: Camera,
        previous_status: str | None,
        timestamp: str,
        reason: str | None = None,
    ) -> None:
        """Emit the appropriate WebSocket events for a status change.

        Emits both:
        1. A specific event (camera.online, camera.offline, camera.error)
        2. A generic camera.status_changed event with full details

        Args:
            camera: The camera with updated status.
            previous_status: The previous status before the change.
            timestamp: ISO 8601 timestamp for the event.
            reason: Optional reason for the status change.
        """
        if self._emitter is None:
            return

        # Map status to event type and emit specific event
        status_lower = camera.status.lower()
        specific_event_type: WebSocketEventType | None = None

        if status_lower == "online":
            specific_event_type = WebSocketEventType.CAMERA_ONLINE
            specific_payload: dict[str, Any] = {
                "camera_id": camera.id,
                "camera_name": camera.name,
                "timestamp": timestamp,
            }
        elif status_lower == "offline":
            specific_event_type = WebSocketEventType.CAMERA_OFFLINE
            specific_payload = {
                "camera_id": camera.id,
                "camera_name": camera.name,
                "timestamp": timestamp,
                "reason": reason,
            }
        elif status_lower == "error":
            specific_event_type = WebSocketEventType.CAMERA_ERROR
            specific_payload = {
                "camera_id": camera.id,
                "camera_name": camera.name,
                "error": reason or "Unknown error",
                "error_code": None,
                "timestamp": timestamp,
            }
        else:
            specific_payload = {}

        # Emit specific event if applicable
        if specific_event_type is not None:
            await self._emitter.emit(specific_event_type, specific_payload)
            logger.info(
                f"Emitted {specific_event_type.value} for camera {camera.id}",
                extra={
                    "camera_id": camera.id,
                    "event_type": specific_event_type.value,
                    "previous_status": previous_status,
                    "new_status": camera.status,
                },
            )

        # Always emit the generic status_changed event with full details
        status_changed_payload: dict[str, Any] = {
            "camera_id": camera.id,
            "camera_name": camera.name,
            "status": _map_status_string_to_enum(camera.status),
            "previous_status": _map_status_string_to_enum(previous_status)
            if previous_status
            else None,
            "timestamp": timestamp,
            "reason": reason,
            "details": None,
        }

        await self._emitter.emit(
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            status_changed_payload,
        )
        logger.info(
            f"Emitted camera.status_changed for camera {camera.id}: "
            f"{previous_status} -> {camera.status}",
            extra={
                "camera_id": camera.id,
                "event_type": WebSocketEventType.CAMERA_STATUS_CHANGED.value,
                "previous_status": previous_status,
                "new_status": camera.status,
            },
        )


def _map_status_string_to_enum(status: str | None) -> str | None:
    """Map a status string to the CameraStatus enum value.

    Args:
        status: Status string (e.g., "online", "offline", "error").

    Returns:
        The enum value string, or None if status is None.
    """
    if status is None:
        return None

    status_lower = status.lower()
    try:
        return CameraStatus(status_lower).value
    except ValueError:
        # If status doesn't match enum, return as-is for forward compatibility
        return status_lower


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
