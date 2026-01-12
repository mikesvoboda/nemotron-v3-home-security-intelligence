"""WebSocket event emitter service for broadcasting events.

This module provides a centralized service for emitting WebSocket events
throughout the application. It integrates with the existing EventBroadcaster
and SystemBroadcaster services to provide a unified API for event emission.

The WebSocketEmitterService:
- Validates payloads against Pydantic schemas before emission
- Logs all emitted events at debug level
- Supports broadcast, room-based, and user-targeted emission
- Provides automatic timestamp and correlation ID generation

Example Usage:
    from backend.services.websocket_emitter import get_websocket_emitter
    from backend.core.websocket import WebSocketEventType

    # Get the emitter service
    emitter = await get_websocket_emitter()

    # Emit an alert event
    await emitter.emit(
        WebSocketEventType.ALERT_CREATED,
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "front_door:person:rule1",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
    )

    # Broadcast to all connected clients
    await emitter.broadcast(
        WebSocketEventType.SYSTEM_STATUS,
        {"health": "healthy", "gpu": {...}, "cameras": {...}, "queue": {...}}
    )
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from backend.core.logging import get_logger
from backend.core.websocket.event_schemas import (
    BasePayload,
    get_payload_schema,
)
from backend.core.websocket.event_types import (
    WebSocketEventType,
    get_event_channel,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.services.event_broadcaster import EventBroadcaster
    from backend.services.system_broadcaster import SystemBroadcaster

logger = get_logger(__name__)


class WebSocketEmitterService:
    """Centralized service for emitting WebSocket events.

    This service provides a unified API for emitting events to WebSocket
    clients. It integrates with the existing EventBroadcaster and
    SystemBroadcaster services.

    Features:
    - Payload validation against Pydantic schemas
    - Debug-level logging of all emitted events
    - Support for broadcast, room, and user-targeted emission
    - Automatic timestamp and correlation ID generation
    - Thread-safe singleton pattern

    Attributes:
        _event_broadcaster: EventBroadcaster instance for event channel
        _system_broadcaster: SystemBroadcaster instance for system channel
        _redis_client: Redis client for pub/sub
        _validate_payloads: Whether to validate payloads before emission
    """

    def __init__(
        self,
        event_broadcaster: EventBroadcaster | None = None,
        system_broadcaster: SystemBroadcaster | None = None,
        redis_client: RedisClient | None = None,
        *,
        validate_payloads: bool = True,
    ) -> None:
        """Initialize the WebSocket emitter service.

        Args:
            event_broadcaster: Optional EventBroadcaster instance.
            system_broadcaster: Optional SystemBroadcaster instance.
            redis_client: Optional Redis client for pub/sub.
            validate_payloads: Whether to validate payloads against schemas.
                Defaults to True. Set to False for performance in trusted contexts.
        """
        self._event_broadcaster = event_broadcaster
        self._system_broadcaster = system_broadcaster
        self._redis_client = redis_client
        self._validate_payloads = validate_payloads
        self._emit_count = 0
        self._emit_errors = 0

    def set_event_broadcaster(self, broadcaster: EventBroadcaster) -> None:
        """Set the event broadcaster after initialization.

        Args:
            broadcaster: EventBroadcaster instance.
        """
        self._event_broadcaster = broadcaster

    def set_system_broadcaster(self, broadcaster: SystemBroadcaster) -> None:
        """Set the system broadcaster after initialization.

        Args:
            broadcaster: SystemBroadcaster instance.
        """
        self._system_broadcaster = broadcaster

    def set_redis_client(self, redis_client: RedisClient) -> None:
        """Set the Redis client after initialization.

        Args:
            redis_client: Redis client instance.
        """
        self._redis_client = redis_client

    @property
    def emit_count(self) -> int:
        """Get the total number of events emitted."""
        return self._emit_count

    @property
    def emit_errors(self) -> int:
        """Get the total number of emission errors."""
        return self._emit_errors

    def _validate_event_payload(
        self, event_type: WebSocketEventType, payload: dict[str, Any]
    ) -> BasePayload | None:
        """Validate the event payload against its schema.

        Args:
            event_type: The type of event being emitted.
            payload: The payload data to validate.

        Returns:
            Validated Pydantic model if validation succeeds, None if no schema exists.

        Raises:
            ValidationError: If payload validation fails.
        """
        if not self._validate_payloads:
            return None

        schema = get_payload_schema(event_type)
        if schema is None:
            # No schema defined for this event type, skip validation
            logger.debug(f"No payload schema defined for event type: {event_type}")
            return None

        return schema.model_validate(payload)

    def _create_event_message(
        self,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Create a WebSocket event message.

        Args:
            event_type: The type of event.
            payload: Event payload data.
            correlation_id: Optional correlation ID for request tracing.
            channel: Optional channel override.

        Returns:
            Complete event message dict ready for serialization.
        """
        # Get default channel if not specified
        if channel is None:
            channel = get_event_channel(event_type)

        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        return {
            "type": event_type.value,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": correlation_id,
            "channel": channel,
        }

    async def emit(
        self,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
        *,
        room: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """Emit an event to WebSocket clients.

        This is the primary method for emitting events. It validates the payload,
        creates the event message, and dispatches it to the appropriate broadcaster.

        Args:
            event_type: The type of event to emit.
            payload: Event payload data (will be validated against schema).
            room: Optional room/channel to emit to (default: event's default channel).
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            True if the event was successfully emitted, False otherwise.

        Raises:
            ValidationError: If payload validation fails (when validation enabled).
        """
        try:
            # Validate payload if enabled
            if self._validate_payloads:
                try:
                    self._validate_event_payload(event_type, payload)
                except ValidationError as e:
                    logger.error(
                        f"Payload validation failed for {event_type}: {e}",
                        extra={"event_type": event_type.value, "payload": payload},
                    )
                    self._emit_errors += 1
                    raise

            # Create the event message
            message = self._create_event_message(
                event_type, payload, correlation_id=correlation_id, channel=room
            )

            # Log the emission at debug level
            logger.debug(
                f"Emitting WebSocket event: {event_type.value}",
                extra={
                    "event_type": event_type.value,
                    "channel": room or get_event_channel(event_type),
                    "correlation_id": message.get("correlation_id"),
                },
            )

            # Dispatch to appropriate broadcaster based on event type
            await self._dispatch_event(event_type, message, room)

            self._emit_count += 1
            return True

        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(
                f"Failed to emit event {event_type}: {e}",
                extra={"event_type": event_type.value},
                exc_info=True,
            )
            self._emit_errors += 1
            return False

    async def emit_to_user(
        self,
        user_id: str,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> bool:
        """Emit an event to a specific user.

        Note: This is a placeholder for user-targeted emission. In the current
        architecture without authentication, this emits to all clients in a
        user-specific room/channel pattern.

        Args:
            user_id: The user ID to target.
            event_type: The type of event to emit.
            payload: Event payload data.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            True if the event was successfully emitted, False otherwise.
        """
        # Use user-specific room pattern
        room = f"user:{user_id}"
        return await self.emit(event_type, payload, room=room, correlation_id=correlation_id)

    async def broadcast(
        self,
        event_type: WebSocketEventType,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> bool:
        """Broadcast an event to all connected clients.

        This emits the event to all WebSocket clients without any filtering.

        Args:
            event_type: The type of event to broadcast.
            payload: Event payload data.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            True if the event was successfully broadcast, False otherwise.
        """
        return await self.emit(event_type, payload, room=None, correlation_id=correlation_id)

    async def emit_batch(
        self,
        events: list[tuple[WebSocketEventType, dict[str, Any]]],
        *,
        correlation_id: str | None = None,
    ) -> int:
        """Emit multiple events in sequence.

        Args:
            events: List of (event_type, payload) tuples to emit.
            correlation_id: Optional shared correlation ID for all events.

        Returns:
            Number of events successfully emitted.
        """
        success_count = 0
        shared_correlation_id = correlation_id or str(uuid.uuid4())

        for event_type, payload in events:
            try:
                success = await self.emit(event_type, payload, correlation_id=shared_correlation_id)
                if success:
                    success_count += 1
            except ValidationError:
                # Continue with other events even if one fails validation
                logger.warning(f"Skipping event {event_type} due to validation error in batch")
                continue

        return success_count

    async def _dispatch_event(
        self,
        event_type: WebSocketEventType,
        message: dict[str, Any],
        room: str | None,
    ) -> None:
        """Dispatch an event to the appropriate broadcaster.

        Routes events to either EventBroadcaster or SystemBroadcaster
        based on the event type's default channel.

        Args:
            event_type: The type of event.
            message: The complete event message.
            room: Optional room/channel to dispatch to.
        """
        channel = room or get_event_channel(event_type)

        # Route to system broadcaster for system-related events
        if channel == "system" and self._system_broadcaster is not None:
            await self._dispatch_to_system_broadcaster(event_type, message)
        # Route to event broadcaster for all other events
        elif self._event_broadcaster is not None:
            await self._dispatch_to_event_broadcaster(event_type, message)
        # Fallback: publish directly to Redis if no broadcaster available
        elif self._redis_client is not None:
            await self._publish_to_redis(message, channel or "events")
        else:
            logger.warning(
                f"No broadcaster available for event {event_type}",
                extra={"event_type": event_type.value, "channel": channel},
            )

    async def _dispatch_to_event_broadcaster(
        self,
        event_type: WebSocketEventType,
        message: dict[str, Any],
    ) -> None:
        """Dispatch an event via EventBroadcaster.

        Maps event types to appropriate EventBroadcaster methods.

        Args:
            event_type: The type of event.
            message: The complete event message.
        """
        if self._event_broadcaster is None:
            logger.warning("EventBroadcaster not available")
            return

        payload = message.get("payload", {})

        # Map event types to broadcaster methods
        # Alert events
        if event_type in (
            WebSocketEventType.ALERT_CREATED,
            WebSocketEventType.ALERT_UPDATED,
            WebSocketEventType.ALERT_ACKNOWLEDGED,
            WebSocketEventType.ALERT_RESOLVED,
            WebSocketEventType.ALERT_DISMISSED,
        ):
            # Import here to avoid circular import
            from backend.api.schemas.websocket import WebSocketAlertEventType

            alert_type_map = {
                WebSocketEventType.ALERT_CREATED: WebSocketAlertEventType.ALERT_CREATED,
                WebSocketEventType.ALERT_UPDATED: WebSocketAlertEventType.ALERT_UPDATED,
                WebSocketEventType.ALERT_ACKNOWLEDGED: WebSocketAlertEventType.ALERT_ACKNOWLEDGED,
                WebSocketEventType.ALERT_RESOLVED: WebSocketAlertEventType.ALERT_RESOLVED,
                WebSocketEventType.ALERT_DISMISSED: WebSocketAlertEventType.ALERT_DISMISSED,
            }
            await self._event_broadcaster.broadcast_alert(payload, alert_type_map[event_type])

        # Camera events
        elif event_type in (
            WebSocketEventType.CAMERA_ONLINE,
            WebSocketEventType.CAMERA_OFFLINE,
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            WebSocketEventType.CAMERA_ERROR,
        ):
            # Add event_type to payload for camera status messages
            camera_payload = {
                "event_type": event_type.value,
                **payload,
            }
            await self._event_broadcaster.broadcast_camera_status(
                {"type": "camera_status", "data": camera_payload}
            )

        # Scene change events
        elif event_type == WebSocketEventType.SCENE_CHANGE_DETECTED:
            await self._event_broadcaster.broadcast_scene_change(
                {"type": "scene_change", "data": payload}
            )

        # Security events
        elif event_type in (
            WebSocketEventType.EVENT_CREATED,
            WebSocketEventType.EVENT_UPDATED,
        ):
            await self._event_broadcaster.broadcast_event({"type": "event", "data": payload})

        # Service status events
        elif event_type == WebSocketEventType.SERVICE_STATUS_CHANGED:
            await self._event_broadcaster.broadcast_service_status(
                {
                    "type": "service_status",
                    "data": payload,
                    "timestamp": message.get("timestamp"),
                }
            )

        # Default: publish via Redis
        elif self._redis_client is not None:
            channel = get_event_channel(event_type) or "events"
            await self._publish_to_redis(message, channel)

    async def _dispatch_to_system_broadcaster(
        self,
        event_type: WebSocketEventType,
        message: dict[str, Any],
    ) -> None:
        """Dispatch an event via SystemBroadcaster.

        Args:
            event_type: The type of event.
            message: The complete event message.
        """
        if self._system_broadcaster is None:
            logger.warning("SystemBroadcaster not available")
            return

        # System status events use broadcast_status
        status_data = {
            "type": event_type.value,
            "data": message.get("payload", {}),
            "timestamp": message.get("timestamp"),
        }
        await self._system_broadcaster.broadcast_status(status_data)

    async def _publish_to_redis(
        self,
        message: dict[str, Any],
        channel: str,
    ) -> None:
        """Publish an event directly to Redis pub/sub.

        Fallback method when no specific broadcaster is available.

        Args:
            message: The complete event message.
            channel: Redis channel to publish to.
        """
        if self._redis_client is None:
            logger.warning("Redis client not available for direct publish")
            return

        try:
            await self._redis_client.publish(channel, message)
            logger.debug(f"Published event to Redis channel: {channel}")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}", exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Get emitter statistics.

        Returns:
            Dictionary with emit counts, error counts, and broadcaster status.
        """
        return {
            "emit_count": self._emit_count,
            "emit_errors": self._emit_errors,
            "validate_payloads": self._validate_payloads,
            "event_broadcaster_available": self._event_broadcaster is not None,
            "system_broadcaster_available": self._system_broadcaster is not None,
            "redis_client_available": self._redis_client is not None,
        }


# =============================================================================
# Global Singleton Instance
# =============================================================================

_emitter: WebSocketEmitterService | None = None
_emitter_lock: asyncio.Lock | None = None
_init_lock = threading.Lock()


def _get_emitter_lock() -> asyncio.Lock:
    """Get the emitter initialization lock (lazy initialization).

    Thread-safe creation of the asyncio lock for emitter initialization.

    Returns:
        asyncio.Lock for emitter initialization
    """
    global _emitter_lock  # noqa: PLW0603
    if _emitter_lock is None:
        with _init_lock:
            if _emitter_lock is None:
                _emitter_lock = asyncio.Lock()
    return _emitter_lock


async def get_websocket_emitter(
    event_broadcaster: EventBroadcaster | None = None,
    system_broadcaster: SystemBroadcaster | None = None,
    redis_client: RedisClient | None = None,
) -> WebSocketEmitterService:
    """Get or create the global WebSocket emitter instance.

    This function provides a thread-safe singleton pattern for the
    WebSocketEmitterService. On first call, it creates a new instance.
    Subsequent calls return the existing singleton.

    If broadcasters or Redis client are provided, they will be set on
    the existing singleton (useful for lazy initialization).

    Args:
        event_broadcaster: Optional EventBroadcaster instance.
        system_broadcaster: Optional SystemBroadcaster instance.
        redis_client: Optional Redis client instance.

    Returns:
        WebSocketEmitterService instance.

    Example:
        # During application startup
        from backend.services.event_broadcaster import get_broadcaster
        from backend.services.system_broadcaster import get_system_broadcaster

        event_bc = await get_broadcaster(redis)
        system_bc = get_system_broadcaster(redis)
        emitter = await get_websocket_emitter(event_bc, system_bc, redis)

        # Later in application code
        emitter = await get_websocket_emitter()
        await emitter.emit(WebSocketEventType.ALERT_CREATED, {...})
    """
    global _emitter  # noqa: PLW0603

    # Fast path: emitter already exists
    if _emitter is not None:
        # Update broadcasters if provided
        if event_broadcaster is not None:
            _emitter.set_event_broadcaster(event_broadcaster)
        if system_broadcaster is not None:
            _emitter.set_system_broadcaster(system_broadcaster)
        if redis_client is not None:
            _emitter.set_redis_client(redis_client)
        return _emitter

    # Slow path: need to initialize with lock
    lock = _get_emitter_lock()
    async with lock:
        # Double-check after acquiring lock
        if _emitter is None:
            _emitter = WebSocketEmitterService(
                event_broadcaster=event_broadcaster,
                system_broadcaster=system_broadcaster,
                redis_client=redis_client,
            )
            logger.info("Global WebSocket emitter initialized")
        else:
            # Update broadcasters if provided
            if event_broadcaster is not None:
                _emitter.set_event_broadcaster(event_broadcaster)
            if system_broadcaster is not None:
                _emitter.set_system_broadcaster(system_broadcaster)
            if redis_client is not None:
                _emitter.set_redis_client(redis_client)

    return _emitter


def get_websocket_emitter_sync() -> WebSocketEmitterService | None:
    """Get the global WebSocket emitter instance synchronously.

    Returns the existing singleton if it has been initialized,
    or None if not yet initialized.

    This is useful for checking if the emitter is available without
    async context.

    Returns:
        WebSocketEmitterService instance or None.
    """
    return _emitter


def reset_emitter_state() -> None:
    """Reset the global emitter state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _emitter, _emitter_lock  # noqa: PLW0603
    _emitter = None
    _emitter_lock = None
