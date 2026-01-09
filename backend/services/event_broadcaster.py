"""Event broadcaster service for WebSocket real-time event distribution.

This service manages WebSocket connections and broadcasts security events
to all connected clients using Redis pub/sub as the event backbone.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import threading
from collections import deque
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketAlertAcknowledgedMessage,
    WebSocketAlertCreatedMessage,
    WebSocketAlertData,
    WebSocketAlertDismissedMessage,
    WebSocketAlertEventType,
    WebSocketCameraStatusData,
    WebSocketCameraStatusMessage,
    WebSocketEventData,
    WebSocketEventMessage,
    WebSocketSceneChangeData,
    WebSocketSceneChangeMessage,
    WebSocketServiceStatusData,
    WebSocketServiceStatusMessage,
)
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import RedisClient
from backend.core.websocket_circuit_breaker import (
    WebSocketCircuitBreaker,
    WebSocketCircuitState,
)

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

logger = get_logger(__name__)

# Buffer size for message replay on reconnection (NEM-1688)
MESSAGE_BUFFER_SIZE = 100


def requires_ack(message: dict[str, Any]) -> bool:
    """Determine if a message requires client acknowledgment.

    High-priority messages that require acknowledgment:
    - Events with risk_score >= 80
    - Events with risk_level == 'critical'

    Args:
        message: WebSocket message dictionary

    Returns:
        True if the message requires acknowledgment, False otherwise
    """
    if message.get("type") != "event":
        return False

    data = message.get("data")
    if not data:
        return False

    # Check risk_score >= 80
    risk_score = data.get("risk_score", 0)
    if risk_score >= 80:
        return True

    # Check risk_level == 'critical'
    risk_level = data.get("risk_level", "")
    return bool(risk_level == "critical")


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

    Message Delivery Guarantees (NEM-1688):
    - All messages include monotonically increasing sequence numbers
    - Last MESSAGE_BUFFER_SIZE messages are buffered for replay
    - High-priority messages (risk_score >= 80 or critical) require acknowledgment
    - Per-client ACK tracking for delivery confirmation
    """

    # Maximum number of consecutive recovery attempts before giving up
    # Prevents unbounded recursion / stack overflow on repeated failures
    MAX_RECOVERY_ATTEMPTS = 5

    # Interval for supervision checks (seconds)
    SUPERVISION_INTERVAL = 30.0

    # Message buffer size for replay on reconnection
    MESSAGE_BUFFER_SIZE = MESSAGE_BUFFER_SIZE

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

        # Circuit breaker for WebSocket connection resilience
        self._circuit_breaker = WebSocketCircuitBreaker(
            failure_threshold=self.MAX_RECOVERY_ATTEMPTS,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            success_threshold=1,
            name="event_broadcaster",
        )

        # Message sequencing and buffering (NEM-1688)
        self._sequence_counter = 0
        self._message_buffer: deque[dict[str, Any]] = deque(maxlen=self.MESSAGE_BUFFER_SIZE)
        self._client_acks: dict[WebSocket, int] = {}

    @property
    def channel_name(self) -> str:
        """Get the Redis channel name for this broadcaster instance."""
        return self._channel_name

    @property
    def circuit_breaker(self) -> WebSocketCircuitBreaker:
        """Get the circuit breaker instance for this broadcaster."""
        return self._circuit_breaker

    def get_circuit_state(self) -> WebSocketCircuitState:
        """Get current circuit breaker state.

        Returns:
            Current WebSocketCircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        return self._circuit_breaker.get_state()

    @classmethod
    def get_instance(cls) -> EventBroadcaster:
        """Get the global event broadcaster instance.

        This is a convenience method for getting the global broadcaster without
        needing direct access to the module-level _broadcaster variable.

        Returns:
            The global EventBroadcaster instance

        Raises:
            RuntimeError: If the broadcaster has not been initialized
        """
        if _broadcaster is None:
            raise RuntimeError(
                "EventBroadcaster has not been initialized. "
                "Call get_broadcaster() during application startup."
            )
        return _broadcaster

    @property
    def current_sequence(self) -> int:
        """Get the current sequence counter value.

        Returns:
            The current sequence number (0 if no messages have been sent).
        """
        return self._sequence_counter

    def _next_sequence(self) -> int:
        """Get the next sequence number.

        Returns:
            The next sequence number (monotonically increasing).
        """
        self._sequence_counter += 1
        return self._sequence_counter

    def _add_sequence_and_buffer(self, message: dict[str, Any]) -> dict[str, Any]:
        """Add sequence number and buffer the message for replay.

        Creates a copy of the message with sequence and requires_ack fields,
        then adds it to the message buffer.

        Args:
            message: The original message to sequence and buffer.

        Returns:
            A new dict with sequence and requires_ack fields added.
        """
        # Create a copy to avoid modifying the original
        sequenced = dict(message)
        sequenced["sequence"] = self._next_sequence()
        sequenced["requires_ack"] = requires_ack(message)

        # Add to buffer
        self._message_buffer.append(sequenced)

        return sequenced

    def _sequence_event_data(self, event_data: Any) -> Any:
        """Add sequence number to event data (NEM-1688).

        This is a helper method that handles the different types of event data
        that can come from Redis pub/sub.

        Args:
            event_data: The event data from Redis, can be dict, str, or other.

        Returns:
            The sequenced event data if it could be parsed, otherwise original data.
        """
        if isinstance(event_data, dict):
            return self._add_sequence_and_buffer(event_data)
        if isinstance(event_data, str):
            try:
                parsed = json.loads(event_data)
                return self._add_sequence_and_buffer(parsed)
            except json.JSONDecodeError:
                # Can't sequence non-JSON string messages
                return event_data
        return event_data

    def get_messages_since(
        self, last_sequence: int, mark_as_replay: bool = False
    ) -> list[dict[str, Any]]:
        """Get all buffered messages since a given sequence number.

        Used for reconnection replay to catch up clients that missed messages.

        Args:
            last_sequence: The last sequence number the client received.
            mark_as_replay: If True, add replay=True to returned messages.

        Returns:
            List of messages with sequence > last_sequence.
        """
        messages = [msg for msg in self._message_buffer if msg["sequence"] > last_sequence]

        if mark_as_replay:
            # Create copies with replay flag
            return [{**msg, "replay": True} for msg in messages]

        return messages

    def record_ack(self, websocket: WebSocket, sequence: int) -> None:
        """Record a client's acknowledgment of a sequence number.

        Only updates if the new sequence is higher than the current one.

        Args:
            websocket: The client's WebSocket connection.
            sequence: The sequence number being acknowledged.
        """
        current = self._client_acks.get(websocket, 0)
        if sequence > current:
            self._client_acks[websocket] = sequence

    def get_last_ack(self, websocket: WebSocket) -> int:
        """Get the last acknowledged sequence for a client.

        Args:
            websocket: The client's WebSocket connection.

        Returns:
            The last acknowledged sequence number, or 0 if none.
        """
        return self._client_acks.get(websocket, 0)

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
            self._circuit_breaker.reset()  # Reset circuit breaker on successful start
            self._listener_task = asyncio.create_task(self._listen_for_events())
            # Start supervision task to monitor listener health
            self._supervisor_task = asyncio.create_task(self._supervise_listener())
            logger.info(f"Event broadcaster started, listening on channel: {self._channel_name}")
        except Exception as e:
            logger.error(f"Failed to start event broadcaster: {e}")
            self._circuit_breaker.record_failure()
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

    async def __aenter__(self) -> EventBroadcaster:
        """Async context manager entry.

        Starts the event broadcaster and returns self for use in async with statements.

        Returns:
            Self for use in the context manager block.

        Example:
            async with EventBroadcaster(redis_client) as broadcaster:
                # broadcaster is started and listening for events
                await broadcaster.broadcast_event(event_data)
            # broadcaster is automatically stopped when exiting the block
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit.

        Stops the event broadcaster, ensuring cleanup even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.
        """
        await self.stop()

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

        Cleans up ACK tracking for the client.

        Args:
            websocket: WebSocket connection to unregister
        """
        self._connections.discard(websocket)
        # Clean up ACK tracking (NEM-1688)
        self._client_acks.pop(websocket, None)
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

    async def broadcast_service_status(self, status_data: dict[str, Any]) -> int:
        """Broadcast a service status message to all connected WebSocket clients via Redis pub/sub.

        This method validates the status data against the WebSocketServiceStatusMessage schema
        before publishing to Redis. This ensures all messages sent to clients conform
        to the expected format for service status updates.

        Args:
            status_data: Status data dictionary containing service status details

        Returns:
            Number of Redis subscribers that received the message

        Raises:
            ValueError: If the message fails schema validation

        Example status_data:
            {
                "type": "service_status",
                "data": {
                    "service": "nemotron",
                    "status": "healthy",
                    "message": "Service recovered"
                },
                "timestamp": "2025-12-23T12:00:00.000Z"
            }
        """
        try:
            # Validate message format before broadcasting
            # This ensures all outgoing messages conform to the WebSocketServiceStatusMessage schema
            try:
                # Extract the data portion and validate it
                data_dict = status_data.get("data", {})
                validated_data = WebSocketServiceStatusData.model_validate(data_dict)
                validated_message = WebSocketServiceStatusMessage(
                    data=validated_data,
                    timestamp=status_data.get("timestamp", ""),
                )
                # Use the validated message for broadcasting
                broadcast_data = validated_message.model_dump(mode="json")
            except ValidationError as ve:
                logger.error(f"Service status message validation failed: {ve}")
                raise ValueError(f"Invalid service status message format: {ve}") from ve

            # Publish validated message to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, broadcast_data)
            logger.debug(
                f"Service status broadcast to Redis: {broadcast_data.get('type')} "
                f"(subscribers: {subscriber_count})"
            )
            return subscriber_count
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to broadcast service status: {e}")
            raise

    async def broadcast_scene_change(self, scene_change_data: dict[str, Any]) -> int:
        """Broadcast a scene change message to all connected WebSocket clients via Redis pub/sub.

        This method validates the scene change data against the WebSocketSceneChangeMessage schema
        before publishing to Redis. This ensures all messages sent to clients conform
        to the expected format for scene change alerts.

        Args:
            scene_change_data: Scene change data dictionary containing detection details

        Returns:
            Number of Redis subscribers that received the message

        Raises:
            ValueError: If the message fails schema validation

        Example scene_change_data:
            {
                "type": "scene_change",
                "data": {
                    "id": 1,
                    "camera_id": "front_door",
                    "detected_at": "2026-01-03T10:30:00Z",
                    "change_type": "view_blocked",
                    "similarity_score": 0.23
                }
            }
        """
        try:
            # Ensure the message has the correct structure
            if "type" not in scene_change_data:
                scene_change_data = {"type": "scene_change", "data": scene_change_data}

            # Validate message format before broadcasting
            # This ensures all outgoing messages conform to the WebSocketSceneChangeMessage schema
            try:
                # Extract the data portion and validate it
                data_dict = scene_change_data.get("data", {})
                validated_data = WebSocketSceneChangeData.model_validate(data_dict)
                validated_message = WebSocketSceneChangeMessage(data=validated_data)
                # Use the validated message for broadcasting
                broadcast_data = validated_message.model_dump(mode="json")
            except ValidationError as ve:
                logger.error(f"Scene change message validation failed: {ve}")
                raise ValueError(f"Invalid scene change message format: {ve}") from ve

            # Publish validated message to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, broadcast_data)
            logger.debug(
                f"Scene change broadcast to Redis: {broadcast_data.get('type')} "
                f"(subscribers: {subscriber_count})"
            )
            return subscriber_count
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to broadcast scene change: {e}")
            raise

    async def broadcast_camera_status(self, camera_status_data: dict[str, Any]) -> int:
        """Broadcast a camera status change message to all connected WebSocket clients via Redis pub/sub.

        This method validates the camera status data against the WebSocketCameraStatusMessage schema
        before publishing to Redis. This ensures all messages sent to clients conform
        to the expected format for camera status updates.

        Camera status change events are broadcast when:
        - Camera comes online (status = "online")
        - Camera goes offline (status = "offline")
        - Camera enters error state (status = "error")
        - Camera status is updated for any reason

        Args:
            camera_status_data: Camera status data dictionary containing status details

        Returns:
            Number of Redis subscribers that received the message

        Raises:
            ValueError: If the message fails schema validation

        Example camera_status_data:
            {
                "type": "camera_status",
                "data": {
                    "camera_id": "front_door",
                    "camera_name": "Front Door Camera",
                    "status": "offline",
                    "previous_status": "online",
                    "changed_at": "2026-01-09T10:30:00Z",
                    "reason": "No activity detected for 5 minutes"
                }
            }
        """
        try:
            # Ensure the message has the correct structure
            if "type" not in camera_status_data:
                camera_status_data = {"type": "camera_status", "data": camera_status_data}

            # Validate message format before broadcasting
            # This ensures all outgoing messages conform to the WebSocketCameraStatusMessage schema
            try:
                # Extract the data portion and validate it
                data_dict = camera_status_data.get("data", {})
                validated_data = WebSocketCameraStatusData.model_validate(data_dict)
                validated_message = WebSocketCameraStatusMessage(data=validated_data)
                # Use the validated message for broadcasting
                broadcast_data = validated_message.model_dump(mode="json")
            except ValidationError as ve:
                logger.error(f"Camera status message validation failed: {ve}")
                raise ValueError(f"Invalid camera status message format: {ve}") from ve

            # Publish validated message to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, broadcast_data)
            logger.debug(
                f"Camera status broadcast to Redis: {broadcast_data.get('type')} "
                f"(camera_id: {data_dict.get('camera_id')}, status: {data_dict.get('status')}, "
                f"subscribers: {subscriber_count})"
            )
            return subscriber_count
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to broadcast camera status: {e}")
            raise

    async def broadcast_alert(
        self, alert_data: dict[str, Any], event_type: WebSocketAlertEventType
    ) -> int:
        """Broadcast an alert message to all connected WebSocket clients via Redis pub/sub.

        This method validates the alert data against the appropriate WebSocket message schema
        based on the event type before publishing to Redis. This ensures all messages sent
        to clients conform to the expected format for alert events.

        Args:
            alert_data: Alert data dictionary containing alert details
            event_type: Type of alert event (ALERT_CREATED, ALERT_ACKNOWLEDGED, ALERT_DISMISSED)

        Returns:
            Number of Redis subscribers that received the message

        Raises:
            ValueError: If the message fails schema validation or has unknown event type

        Example alert_data:
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "rule_id": "550e8400-e29b-41d4-a716-446655440001",
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-09T12:00:00Z",
                "updated_at": "2026-01-09T12:00:00Z"
            }
        """
        try:
            # Validate the alert data
            validated_data = WebSocketAlertData.model_validate(alert_data)

            # Create the appropriate message type based on event_type
            validated_message: (
                WebSocketAlertCreatedMessage
                | WebSocketAlertAcknowledgedMessage
                | WebSocketAlertDismissedMessage
            )
            if event_type == WebSocketAlertEventType.ALERT_CREATED:
                validated_message = WebSocketAlertCreatedMessage(data=validated_data)
            elif event_type == WebSocketAlertEventType.ALERT_ACKNOWLEDGED:
                validated_message = WebSocketAlertAcknowledgedMessage(data=validated_data)
            elif event_type == WebSocketAlertEventType.ALERT_DISMISSED:
                validated_message = WebSocketAlertDismissedMessage(data=validated_data)
            else:
                raise ValueError(f"Unknown alert event type: {event_type}")

            # Use the validated message for broadcasting
            broadcast_data = validated_message.model_dump(mode="json")

            # Publish validated message to Redis channel
            subscriber_count = await self._redis.publish(self._channel_name, broadcast_data)
            logger.debug(
                f"Alert broadcast to Redis: {broadcast_data.get('type')} "
                f"(subscribers: {subscriber_count})"
            )
            return subscriber_count
        except ValidationError as ve:
            logger.error(f"Alert message validation failed: {ve}")
            raise ValueError(f"Invalid alert message format: {ve}") from ve
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to broadcast alert: {e}")
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

                # Reset recovery attempts and record success on message processing
                self._recovery_attempts = 0
                self._circuit_breaker.record_success()

                # Extract the event data
                event_data = message.get("data")
                if not event_data:
                    continue

                logger.debug(f"Received event from Redis: {event_data}")

                # NEM-1688: Add sequence number and buffer the message
                broadcast_data = self._sequence_event_data(event_data)

                # Broadcast to all connected WebSocket clients
                # Wrapped in try/except to prevent message loss from broadcast failures
                try:
                    await self._send_to_all_clients(broadcast_data)
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
            # Record failure in circuit breaker
            self._circuit_breaker.record_failure()

            # Attempt to restart listener with bounded retry limit
            # Check circuit breaker state before attempting recovery
            if self._is_listening:
                self._recovery_attempts += 1

                # Check if circuit breaker allows recovery attempt
                if not self._circuit_breaker.is_call_permitted():
                    logger.error(
                        "Event listener circuit breaker is OPEN - "
                        "recovery blocked to allow system stabilization"
                    )
                    self._enter_degraded_mode()
                    # Broadcast degraded state to connected clients
                    await self._broadcast_degraded_state()
                    return

                if self._recovery_attempts <= self.MAX_RECOVERY_ATTEMPTS:
                    # Exponential backoff with jitter: 1s, 2s, 4s, 8s, up to 30s max
                    # Jitter prevents thundering herd when multiple instances recover
                    # Using random.uniform is fine here - this is timing jitter, not cryptographic
                    base_delay = min(2 ** (self._recovery_attempts - 1), 30)
                    jitter = base_delay * random.uniform(0.1, 0.3)  # noqa: S311
                    backoff = base_delay + jitter
                    logger.info(
                        f"Restarting event listener after error "
                        f"(attempt {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}) "
                        f"in {backoff:.1f}s"
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
                    # Broadcast degraded state to connected clients
                    await self._broadcast_degraded_state()

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

    async def _broadcast_degraded_state(self) -> None:
        """Broadcast degraded state notification to all connected clients.

        This method is called when the circuit breaker opens or when the broadcaster
        enters degraded mode. It notifies connected clients that real-time events
        may not be delivered reliably.
        """
        if not self._connections:
            return

        degraded_message = {
            "type": "service_status",
            "data": {
                "service": "event_broadcaster",
                "status": "degraded",
                "message": "Real-time event broadcasting is degraded. Events may be delayed or unavailable.",
                "circuit_state": self._circuit_breaker.get_state().value,
            },
        }

        try:
            await self._send_to_all_clients(degraded_message)
            logger.info("Broadcast degraded state notification to connected clients")
        except Exception as e:
            logger.warning(f"Failed to broadcast degraded state: {e}")

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

                if listener_alive:
                    await self._handle_healthy_listener()
                elif self._is_listening:
                    should_break = await self._handle_dead_listener()
                    if should_break:
                        break

        except asyncio.CancelledError:
            logger.info("Listener supervision task cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in supervisor task: {e}", exc_info=True)
        finally:
            logger.info("Listener supervision task stopped")

    async def _handle_healthy_listener(self) -> None:
        """Handle a healthy listener state during supervision.

        Records success and resets recovery counters.
        """
        self._listener_healthy = True
        self._circuit_breaker.record_success()
        if self._recovery_attempts > 0:
            logger.info("Listener recovered successfully, resetting recovery counter")
            self._recovery_attempts = 0

    async def _handle_dead_listener(self) -> bool:
        """Handle a dead listener during supervision.

        Attempts to restart the listener with circuit breaker protection.

        Returns:
            True if supervision loop should break, False to continue.
        """
        # Record failure and log
        self._circuit_breaker.record_failure()
        logger.warning(
            "Listener task died unexpectedly. "
            f"Recovery attempts: {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}"
        )

        # Check circuit breaker before attempting recovery
        if not self._circuit_breaker.is_call_permitted():
            logger.error(
                "Supervisor: circuit breaker is OPEN - "
                "recovery blocked to allow system stabilization"
            )
            self._enter_degraded_mode()
            await self._broadcast_degraded_state()
            return True

        if self._recovery_attempts >= self.MAX_RECOVERY_ATTEMPTS:
            logger.error(
                "Supervisor giving up - max recovery attempts reached. "
                "Manual intervention required."
            )
            self._enter_degraded_mode()
            await self._broadcast_degraded_state()
            return True

        # Attempt recovery
        self._recovery_attempts += 1
        logger.info(f"Supervisor restarting listener (attempt {self._recovery_attempts})")

        # Re-subscribe if needed
        if self._pubsub is None and not await self._resubscribe_for_supervisor():
            return False  # Continue loop to retry

        # Create new listener task
        self._listener_task = asyncio.create_task(self._listen_for_events())
        self._listener_healthy = True
        logger.info("Supervisor successfully restarted listener")
        return False

    async def _resubscribe_for_supervisor(self) -> bool:
        """Attempt to resubscribe to Redis during supervisor recovery.

        Returns:
            True if successful, False if failed.
        """
        try:
            self._pubsub = await self._redis.subscribe(self._channel_name)
            self._circuit_breaker.record_success()
            return True
        except Exception as sub_error:
            logger.error(f"Failed to re-subscribe: {sub_error}")
            self._circuit_breaker.record_failure()
            return False

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
