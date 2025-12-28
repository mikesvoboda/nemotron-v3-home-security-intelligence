"""Event broadcaster service for WebSocket real-time event distribution.

This service manages WebSocket connections and broadcasts security events
to all connected clients using Redis pub/sub as the event backbone.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

from backend.core.config import get_settings
from backend.core.redis import RedisClient

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

logger = logging.getLogger(__name__)


def get_event_channel() -> str:
    """Get the Redis event channel name from settings.

    Returns:
        The configured Redis event channel name.
    """
    return get_settings().redis_event_channel


class EventBroadcaster:
    """Manages WebSocket connections and broadcasts events via Redis pub/sub.

    This class acts as a bridge between Redis pub/sub events and WebSocket
    connections, allowing multiple backend instances to share event notifications.
    """

    # Kept for backward compatibility - fetches from settings dynamically
    # Note: This is a property that returns the current settings value each time
    @property
    def CHANNEL_NAME(self) -> str:
        """Get the Redis channel name from settings (for backward compatibility)."""
        return get_settings().redis_event_channel

    def __init__(self, redis_client: RedisClient, channel_name: str | None = None):
        """Initialize the event broadcaster.

        Args:
            redis_client: Connected Redis client instance
            channel_name: Optional channel name override. Defaults to settings.redis_event_channel.
        """
        self._redis = redis_client
        self._channel_name = channel_name or get_settings().redis_event_channel
        self._connections: set[WebSocket] = set()
        self._pubsub: PubSub | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._is_listening = False

    @property
    def channel_name(self) -> str:
        """Get the Redis channel name for this broadcaster instance."""
        return self._channel_name

    async def start(self) -> None:
        """Start listening for events from Redis pub/sub."""
        if self._is_listening:
            logger.warning("Event broadcaster already started")
            return

        try:
            self._pubsub = await self._redis.subscribe(self._channel_name)
            self._is_listening = True
            self._listener_task = asyncio.create_task(self._listen_for_events())
            logger.info(f"Event broadcaster started, listening on channel: {self._channel_name}")
        except Exception as e:
            logger.error(f"Failed to start event broadcaster: {e}")
            raise

    async def stop(self) -> None:
        """Stop listening for events and cleanup resources."""
        self._is_listening = False

        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub:
            await self._redis.unsubscribe(self._channel_name)
            self._pubsub = None

        # Disconnect all active WebSocket connections
        for ws in list(self._connections):
            await self.disconnect(ws)

        logger.info("Event broadcaster stopped")

    async def connect(self, websocket: WebSocket) -> None:
        """Register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to unregister
        """
        self._connections.discard(websocket)
        with contextlib.suppress(Exception):
            await websocket.close()
        logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def broadcast_event(self, event_data: dict[str, Any]) -> int:
        """Broadcast an event to all connected WebSocket clients via Redis pub/sub.

        This method publishes the event to Redis, which then gets picked up by
        the listener and sent to all connected WebSocket clients. This allows
        multiple backend instances to share events.

        Args:
            event_data: Event data dictionary containing event details

        Returns:
            Number of Redis subscribers that received the message

        Example event_data:
            {
                "type": "event",
                "data": {
                    "id": 1,
                    "camera_id": "cam-123",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person detected near entrance"
                }
            }
        """
        try:
            # Ensure the message has the correct structure
            if "type" not in event_data:
                event_data = {"type": "event", "data": event_data}

            # Publish to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, event_data)
            logger.debug(
                f"Event broadcast to Redis: {event_data.get('type')} "
                f"(subscribers: {subscriber_count})"
            )
            return subscriber_count
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
            raise

    async def _listen_for_events(self) -> None:
        """Listen for events from Redis pub/sub and broadcast to WebSocket clients.

        This method runs in a background task and continuously listens for
        messages from the Redis pub/sub channel, then broadcasts them to all
        connected WebSocket clients.
        """
        if not self._pubsub:
            logger.error("Cannot listen for events: pubsub not initialized")
            return

        logger.info("Starting event listener loop")

        try:
            async for message in self._redis.listen(self._pubsub):
                if not self._is_listening:
                    break

                # Extract the event data
                event_data = message.get("data")
                if not event_data:
                    continue

                logger.debug(f"Received event from Redis: {event_data}")

                # Broadcast to all connected WebSocket clients
                await self._send_to_all_clients(event_data)

        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
        except Exception as e:
            logger.error(f"Error in event listener: {e}")
            # Continue listening even after errors
            if self._is_listening:
                logger.info("Restarting event listener after error")
                await asyncio.sleep(1)
                if self._is_listening:
                    self._listener_task = asyncio.create_task(self._listen_for_events())

    async def _send_to_all_clients(self, event_data: Any) -> None:
        """Send event data to all connected WebSocket clients.

        Args:
            event_data: Event data to send (will be JSON-serialized)
        """
        if not self._connections:
            return

        # Convert to JSON string if not already
        message = event_data if isinstance(event_data, str) else json.dumps(event_data)

        # Send to all clients, removing disconnected ones
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                disconnected.append(ws)

        # Clean up disconnected clients
        for ws in disconnected:
            await self.disconnect(ws)

        if disconnected:
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients")


# Global broadcaster instance
_broadcaster: EventBroadcaster | None = None


async def get_broadcaster(redis_client: RedisClient) -> EventBroadcaster:
    """Get or create the global event broadcaster instance.

    Args:
        redis_client: Redis client instance

    Returns:
        EventBroadcaster instance
    """
    global _broadcaster  # noqa: PLW0603

    if _broadcaster is None:
        _broadcaster = EventBroadcaster(redis_client)
        await _broadcaster.start()

    return _broadcaster


async def stop_broadcaster() -> None:
    """Stop the global event broadcaster instance."""
    global _broadcaster  # noqa: PLW0603

    if _broadcaster:
        await _broadcaster.stop()
        _broadcaster = None
