"""Event broadcaster service for WebSocket real-time event distribution.

This service manages WebSocket connections and broadcasts security events
to all connected clients using Redis pub/sub as the event backbone.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from pydantic import ValidationError

from backend.api.schemas.websocket import WebSocketEventData, WebSocketEventMessage
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

logger = get_logger(__name__)


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

    Includes a supervision task that monitors listener health and automatically
    restarts dead listeners to ensure reliability.

    When max recovery attempts are exhausted, the broadcaster enters degraded mode
    where it continues to accept connections but cannot broadcast real-time events.
    """

    # Maximum number of consecutive recovery attempts before giving up
    # Prevents unbounded recursion / stack overflow on repeated failures
    MAX_RECOVERY_ATTEMPTS = 5

    # Interval for supervision checks (seconds)
    SUPERVISION_INTERVAL = 30.0

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
        self._supervisor_task: asyncio.Task[None] | None = None
        self._is_listening = False
        self._recovery_attempts = 0
        self._listener_healthy = False
        self._is_degraded = False

    @property
    def channel_name(self) -> str:
        """Get the Redis channel name for this broadcaster instance."""
        return self._channel_name

    async def start(self) -> None:
        """Start listening for events from Redis pub/sub.

        Also starts a supervision task that monitors listener health and
        automatically restarts dead listeners.
        """
        if self._is_listening:
            logger.warning("Event broadcaster already started")
            return

        try:
            self._pubsub = await self._redis.subscribe(self._channel_name)
            self._is_listening = True
            self._listener_healthy = True
            self._is_degraded = False  # Clear degraded mode on successful start
            self._recovery_attempts = 0  # Reset recovery attempts on successful start
            self._listener_task = asyncio.create_task(self._listen_for_events())
            # Start supervision task to monitor listener health
            self._supervisor_task = asyncio.create_task(self._supervise_listener())
            logger.info(f"Event broadcaster started, listening on channel: {self._channel_name}")
        except Exception as e:
            logger.error(f"Failed to start event broadcaster: {e}")
            raise

    async def stop(self) -> None:
        """Stop listening for events and cleanup resources."""
        self._is_listening = False
        self._listener_healthy = False

        # Stop supervisor first
        if self._supervisor_task:
            self._supervisor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._supervisor_task
            self._supervisor_task = None

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

        This method validates the event data against the WebSocketEventMessage schema
        before publishing to Redis. This ensures all messages sent to clients conform
        to the expected format and prevents malformed data from being broadcast.

        Args:
            event_data: Event data dictionary containing event details

        Returns:
            Number of Redis subscribers that received the message

        Raises:
            ValueError: If the message fails schema validation

        Example event_data:
            {
                "type": "event",
                "data": {
                    "id": 1,
                    "event_id": 1,
                    "batch_id": "batch_123",
                    "camera_id": "cam-123",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person detected near entrance",
                    "started_at": "2025-12-23T12:00:00"
                }
            }
        """
        try:
            # Ensure the message has the correct structure
            if "type" not in event_data:
                event_data = {"type": "event", "data": event_data}

            # Validate message format before broadcasting
            # This ensures all outgoing messages conform to the WebSocketEventMessage schema
            try:
                # Extract the data portion and validate it
                data_dict = event_data.get("data", {})
                validated_data = WebSocketEventData.model_validate(data_dict)
                validated_message = WebSocketEventMessage(data=validated_data)
                # Use the validated message for broadcasting
                broadcast_data = validated_message.model_dump(mode="json")
            except ValidationError as ve:
                logger.error(f"Event message validation failed: {ve}")
                raise ValueError(f"Invalid event message format: {ve}") from ve

            # Publish validated message to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, broadcast_data)
            logger.debug(
                f"Event broadcast to Redis: {broadcast_data.get('type')} "
                f"(subscribers: {subscriber_count})"
            )
            return subscriber_count
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
            raise

    def _enter_degraded_mode(self) -> None:
        """Enter degraded mode after exhausting all recovery attempts.

        This method is called when the broadcaster has failed to recover after
        MAX_RECOVERY_ATTEMPTS. In degraded mode:
        - A critical alert is logged for operator attention
        - The degraded flag is set for health checks to detect
        - The broadcaster stops trying to listen but remains available
          for connection management

        This ensures graceful degradation rather than silent failure.
        """
        self._is_degraded = True
        self._is_listening = False
        self._listener_healthy = False

        # Log a CRITICAL alert to ensure operator visibility
        logger.critical(
            "CRITICAL: EventBroadcaster has entered DEGRADED MODE after exhausting "
            f"all {self.MAX_RECOVERY_ATTEMPTS} recovery attempts. "
            "Real-time event broadcasting is UNAVAILABLE. "
            "WebSocket clients will not receive live updates. "
            "Manual intervention required to restore functionality. "
            "Check Redis connectivity and restart the service."
        )

    async def _listen_for_events(self) -> None:
        """Listen for events from Redis pub/sub and broadcast to WebSocket clients.

        This method runs in a background task and continuously listens for
        messages from the Redis pub/sub channel, then broadcasts them to all
        connected WebSocket clients.

        Recovery from errors is bounded to MAX_RECOVERY_ATTEMPTS to prevent
        unbounded recursion and stack overflow. Uses exponential backoff on retries.
        After exhausting all attempts, enters degraded mode for graceful failure.
        """
        if not self._pubsub:
            logger.error("Cannot listen for events: pubsub not initialized")
            return

        logger.info("Starting event listener loop")

        try:
            async for message in self._redis.listen(self._pubsub):
                if not self._is_listening:
                    break

                # Reset recovery attempts on successful message processing
                self._recovery_attempts = 0

                # Extract the event data
                event_data = message.get("data")
                if not event_data:
                    continue

                logger.debug(f"Received event from Redis: {event_data}")

                # Broadcast to all connected WebSocket clients
                # Wrapped in try/except to prevent message loss from broadcast failures
                try:
                    await self._send_to_all_clients(event_data)
                except Exception as broadcast_error:
                    # Log error but continue processing - don't lose future messages
                    logger.error(
                        f"Failed to broadcast event to WebSocket clients: {broadcast_error}",
                        exc_info=True,
                    )

        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
        except Exception as e:
            logger.error(f"Error in event listener: {e}")
            # Attempt to restart listener with bounded retry limit
            if self._is_listening:
                self._recovery_attempts += 1
                if self._recovery_attempts <= self.MAX_RECOVERY_ATTEMPTS:
                    # Exponential backoff: 1s, 2s, 4s, 8s, up to 30s max
                    backoff = min(2 ** (self._recovery_attempts - 1), 30)
                    logger.info(
                        f"Restarting event listener after error "
                        f"(attempt {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}) "
                        f"in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    if self._is_listening:
                        self._listener_task = asyncio.create_task(self._listen_for_events())
                else:
                    logger.error(
                        f"Event listener recovery failed after {self.MAX_RECOVERY_ATTEMPTS} "
                        "attempts. Giving up - manual restart required."
                    )
                    self._enter_degraded_mode()

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

    async def _supervise_listener(self) -> None:
        """Supervision task that monitors listener health and restarts if needed.

        This task runs periodically to check if the listener task is alive and
        functioning. If the listener has died unexpectedly without setting the
        proper flags, the supervisor will attempt to restart it.

        This provides an additional layer of reliability beyond the built-in
        recovery logic in _listen_for_events. After exhausting all recovery
        attempts, enters degraded mode for graceful failure.
        """
        logger.info("Listener supervision task started")

        try:
            while self._is_listening:
                await asyncio.sleep(self.SUPERVISION_INTERVAL)

                if not self._is_listening:
                    break

                # Check if listener task is still alive
                listener_alive = self._listener_task is not None and not self._listener_task.done()

                if not listener_alive and self._is_listening:
                    # Listener died unexpectedly - attempt to restart
                    logger.warning(
                        "Listener task died unexpectedly. "
                        f"Recovery attempts: {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}"
                    )

                    if self._recovery_attempts < self.MAX_RECOVERY_ATTEMPTS:
                        self._recovery_attempts += 1
                        logger.info(
                            f"Supervisor restarting listener (attempt {self._recovery_attempts})"
                        )
                        # Re-subscribe if needed
                        if self._pubsub is None:
                            try:
                                self._pubsub = await self._redis.subscribe(self._channel_name)
                            except Exception as sub_error:
                                logger.error(f"Failed to re-subscribe: {sub_error}")
                                continue
                        # Create new listener task
                        self._listener_task = asyncio.create_task(self._listen_for_events())
                        self._listener_healthy = True
                        logger.info("Supervisor successfully restarted listener")
                    else:
                        logger.error(
                            "Supervisor giving up - max recovery attempts reached. "
                            "Manual intervention required."
                        )
                        self._enter_degraded_mode()
                        break
                elif listener_alive:
                    # Listener is healthy
                    self._listener_healthy = True
                    # Reset recovery attempts on healthy check
                    if self._recovery_attempts > 0:
                        logger.info("Listener recovered successfully, resetting recovery counter")
                        self._recovery_attempts = 0

        except asyncio.CancelledError:
            logger.info("Listener supervision task cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in supervisor task: {e}", exc_info=True)
        finally:
            logger.info("Listener supervision task stopped")

    def is_listener_healthy(self) -> bool:
        """Check if the listener is currently healthy.

        Returns:
            True if listener is running and healthy, False otherwise
        """
        return self._is_listening and self._listener_healthy

    def is_degraded(self) -> bool:
        """Check if the broadcaster is in degraded mode.

        Degraded mode is entered when all recovery attempts have been exhausted.
        In this state, the broadcaster cannot broadcast real-time events but
        may still accept WebSocket connections.

        Returns:
            True if broadcaster is in degraded mode, False otherwise
        """
        return self._is_degraded


# Global broadcaster instance and initialization lock
_broadcaster: EventBroadcaster | None = None
_broadcaster_lock: asyncio.Lock | None = None
# Thread lock to protect initialization of _broadcaster_lock itself
_init_lock = threading.Lock()


def _get_broadcaster_lock() -> asyncio.Lock:
    """Get the broadcaster initialization lock (lazy initialization).

    This ensures the lock is created in a thread-safe manner and in the
    correct event loop context. Uses a threading lock to protect the
    initial creation of the asyncio lock, preventing race conditions
    when multiple coroutines attempt to initialize concurrently.

    Must be called from within an async context.

    Returns:
        asyncio.Lock for broadcaster initialization
    """
    global _broadcaster_lock  # noqa: PLW0603
    if _broadcaster_lock is None:
        with _init_lock:
            # Double-check after acquiring thread lock
            if _broadcaster_lock is None:
                _broadcaster_lock = asyncio.Lock()
    return _broadcaster_lock


async def get_broadcaster(redis_client: RedisClient) -> EventBroadcaster:
    """Get or create the global event broadcaster instance.

    This function is thread-safe and handles concurrent initialization
    attempts using an async lock to prevent race conditions.

    Args:
        redis_client: Redis client instance

    Returns:
        EventBroadcaster instance
    """
    global _broadcaster  # noqa: PLW0603

    # Fast path: broadcaster already exists
    if _broadcaster is not None:
        return _broadcaster

    # Slow path: need to initialize with lock
    lock = _get_broadcaster_lock()
    async with lock:
        # Double-check after acquiring lock (another coroutine may have initialized)
        if _broadcaster is None:
            broadcaster = EventBroadcaster(redis_client)
            await broadcaster.start()
            _broadcaster = broadcaster
            logger.info("Global event broadcaster initialized")

    return _broadcaster


async def stop_broadcaster() -> None:
    """Stop the global event broadcaster instance.

    This function is thread-safe and handles concurrent stop attempts.
    """
    global _broadcaster  # noqa: PLW0603

    lock = _get_broadcaster_lock()
    async with lock:
        if _broadcaster:
            await _broadcaster.stop()
            _broadcaster = None
            logger.info("Global event broadcaster stopped")


def reset_broadcaster_state() -> None:
    """Reset the global broadcaster state for testing purposes.

    This function is NOT thread-safe and should only be used in test
    fixtures to ensure clean state between tests. It resets both the
    broadcaster instance and the asyncio lock.

    Warning: Only use this in test teardown, never in production code.
    """
    global _broadcaster, _broadcaster_lock  # noqa: PLW0603
    _broadcaster = None
    _broadcaster_lock = None
