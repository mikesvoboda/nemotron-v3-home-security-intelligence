"""PostgreSQL LISTEN/NOTIFY listener service for real-time database events.

This service provides database-level event propagation using PostgreSQL's
native LISTEN/NOTIFY mechanism. It complements Redis pub/sub by:
- Providing guaranteed delivery for database events (committed transactions only)
- Bridging database events to WebSocket broadcasts
- Offering lower latency than polling for database changes

Channels:
    - events_new: New events inserted into events table
    - events_update: Events updated (risk score, reviewed status, etc.)
    - detections_new: New detections inserted
    - alerts_new: New alerts created

Usage:
    listener = PgNotifyListener(redis_client, broadcaster)
    await listener.start()
    # ... application runs ...
    await listener.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

import asyncpg

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)


class PgNotifyChannel(str, Enum):
    """PostgreSQL NOTIFY channels for real-time events."""

    EVENTS_NEW = "events_new"
    EVENTS_UPDATE = "events_update"
    DETECTIONS_NEW = "detections_new"
    ALERTS_NEW = "alerts_new"


@dataclass(slots=True)
class PgNotifyPayload:
    """Parsed payload from a PostgreSQL NOTIFY message.

    Attributes:
        channel: The notification channel name
        operation: The database operation (INSERT, UPDATE, DELETE)
        table: The source table name
        data: The row data as a dictionary
    """

    channel: str
    operation: str
    table: str
    data: dict[str, Any]

    @classmethod
    def from_json(cls, channel: str, payload: str) -> PgNotifyPayload:
        """Parse a JSON payload from PostgreSQL NOTIFY.

        Args:
            channel: The notification channel
            payload: JSON string from NOTIFY

        Returns:
            Parsed PgNotifyPayload

        Raises:
            ValueError: If payload is not valid JSON
        """
        try:
            data = json.loads(payload)
            return cls(
                channel=channel,
                operation=data.get("operation", "UNKNOWN"),
                table=data.get("table", "unknown"),
                data=data.get("data", {}),
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON payload: {payload}") from e


class PgNotifyListener:
    """Service that listens to PostgreSQL NOTIFY events and bridges to Redis/WebSocket.

    This service establishes a dedicated database connection for LISTEN operations
    and routes notifications to the appropriate handlers (Redis pub/sub, WebSocket broadcast).

    Features:
    - Automatic reconnection with exponential backoff
    - Graceful shutdown handling
    - Channel-specific message routing
    - Health monitoring and status reporting
    """

    # Maximum reconnection attempts before giving up
    MAX_RECONNECT_ATTEMPTS = 10

    # Base delay for exponential backoff (seconds)
    BASE_RECONNECT_DELAY = 1.0

    # Maximum delay between reconnection attempts (seconds)
    MAX_RECONNECT_DELAY = 60.0

    # Channels to listen on
    DEFAULT_CHANNELS: ClassVar[list[PgNotifyChannel]] = [
        PgNotifyChannel.EVENTS_NEW,
        PgNotifyChannel.EVENTS_UPDATE,
        PgNotifyChannel.DETECTIONS_NEW,
        PgNotifyChannel.ALERTS_NEW,
    ]

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        broadcaster: EventBroadcaster | None = None,
        channels: list[PgNotifyChannel] | None = None,
    ) -> None:
        """Initialize the PostgreSQL NOTIFY listener.

        Args:
            redis_client: Optional Redis client for publishing events
            broadcaster: Optional EventBroadcaster for WebSocket distribution
            channels: List of channels to listen on. Defaults to all channels.
        """
        self._redis = redis_client
        self._broadcaster = broadcaster
        self._channels = channels or self.DEFAULT_CHANNELS
        self._connection: asyncpg.Connection | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._is_running = False
        self._is_healthy = False
        self._reconnect_attempts = 0

        logger.info(
            "PgNotifyListener initialized",
            extra={"channels": [c.value for c in self._channels]},
        )

    async def start(self) -> None:
        """Start listening for PostgreSQL NOTIFY events.

        Establishes a database connection, subscribes to channels, and starts
        the listener task.

        Raises:
            RuntimeError: If already running
            asyncpg.PostgresError: If connection fails after all retries
        """
        if self._is_running:
            logger.warning("PgNotifyListener already running")
            return

        self._is_running = True
        self._reconnect_attempts = 0

        await self._connect()

        # Start listener task
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("PgNotifyListener started")

    async def stop(self) -> None:
        """Stop listening and cleanup resources.

        Gracefully stops the listener task and closes the database connection.
        """
        self._is_running = False
        self._is_healthy = False

        # Cancel listener task
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        # Close database connection
        if self._connection:
            with contextlib.suppress(Exception):
                await self._connection.close()
            self._connection = None

        logger.info("PgNotifyListener stopped")

    async def _connect(self) -> None:
        """Establish database connection and subscribe to channels.

        Uses exponential backoff for reconnection attempts.

        Raises:
            asyncpg.PostgresError: If connection fails after all retries
        """
        settings = get_settings()

        # Parse database URL for asyncpg (convert from SQLAlchemy format)
        dsn = settings.database_url.replace("+asyncpg", "")

        while self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            try:
                # Create dedicated connection for LISTEN
                self._connection = await asyncpg.connect(dsn)

                # Subscribe to all channels
                for channel in self._channels:
                    await self._connection.add_listener(
                        channel.value,
                        self._notification_callback,
                    )

                self._is_healthy = True
                self._reconnect_attempts = 0
                logger.info(
                    "PgNotifyListener connected to database",
                    extra={"channels": [c.value for c in self._channels]},
                )
                return

            except Exception as e:
                self._reconnect_attempts += 1
                self._is_healthy = False

                if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        f"Failed to connect after {self.MAX_RECONNECT_ATTEMPTS} attempts: {e}",
                        exc_info=True,
                    )
                    raise

                # Exponential backoff with cap
                delay = min(
                    self.BASE_RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1)),
                    self.MAX_RECONNECT_DELAY,
                )
                logger.warning(
                    f"Connection attempt {self._reconnect_attempts} failed, "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)

    def _notification_callback(
        self,
        connection: asyncpg.Connection,  # noqa: ARG002 - required by asyncpg callback signature
        pid: int,  # noqa: ARG002 - required by asyncpg callback signature
        channel: str,
        payload: str,
    ) -> None:
        """Callback invoked by asyncpg when a notification arrives.

        This schedules the async handler in the event loop.

        Args:
            connection: The database connection (unused but required by asyncpg)
            pid: Backend process ID that sent the notification (unused but required by asyncpg)
            channel: The notification channel
            payload: The notification payload (JSON string)
        """
        asyncio.create_task(self._handle_notification(channel, payload))

    async def _handle_notification(self, channel: str, payload: str) -> None:
        """Handle a notification from PostgreSQL.

        Parses the payload and routes to appropriate handlers based on channel.

        Args:
            channel: The notification channel
            payload: The notification payload (JSON string)
        """
        try:
            parsed = PgNotifyPayload.from_json(channel, payload)
            logger.debug(
                f"Received notification on {channel}",
                extra={
                    "channel": channel,
                    "operation": parsed.operation,
                    "table": parsed.table,
                },
            )

            # Route to appropriate handler
            if channel == PgNotifyChannel.EVENTS_NEW.value:
                await self._handle_event_new(parsed)
            elif channel == PgNotifyChannel.EVENTS_UPDATE.value:
                await self._handle_event_update(parsed)
            elif channel == PgNotifyChannel.DETECTIONS_NEW.value:
                await self._handle_detection_new(parsed)
            elif channel == PgNotifyChannel.ALERTS_NEW.value:
                await self._handle_alert_new(parsed)
            else:
                logger.warning(f"Unhandled notification channel: {channel}")

        except ValueError as e:
            logger.error(f"Failed to parse notification payload: {e}")
        except Exception as e:
            logger.error(f"Error handling notification: {e}", exc_info=True)

    async def _handle_event_new(self, payload: PgNotifyPayload) -> None:
        """Handle new event notifications.

        Broadcasts to Redis and WebSocket for real-time UI updates.

        Args:
            payload: Parsed notification payload
        """
        event_data = payload.data

        # Build WebSocket message
        message = {
            "type": "event",
            "source": "pg_notify",
            "data": {
                "id": event_data.get("id"),
                "event_id": event_data.get("id"),
                "batch_id": event_data.get("batch_id"),
                "camera_id": event_data.get("camera_id"),
                "risk_score": event_data.get("risk_score"),
                "risk_level": event_data.get("risk_level"),
                "summary": event_data.get("summary"),
                "started_at": event_data.get("started_at"),
            },
        }

        # Publish to Redis for multi-instance support
        if self._redis:
            try:
                settings = get_settings()
                await self._redis.publish(settings.redis_event_channel, message)
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")

        logger.debug(
            "Published new event notification",
            extra={"event_id": event_data.get("id")},
        )

    async def _handle_event_update(self, payload: PgNotifyPayload) -> None:
        """Handle event update notifications.

        Broadcasts updates for risk score changes, review status, etc.

        Args:
            payload: Parsed notification payload
        """
        event_data = payload.data

        message = {
            "type": "event_update",
            "source": "pg_notify",
            "data": {
                "id": event_data.get("id"),
                "event_id": event_data.get("id"),
                "risk_score": event_data.get("risk_score"),
                "risk_level": event_data.get("risk_level"),
                "summary": event_data.get("summary"),
                "reviewed": event_data.get("reviewed"),
            },
        }

        if self._redis:
            try:
                settings = get_settings()
                await self._redis.publish(settings.redis_event_channel, message)
            except Exception as e:
                logger.error(f"Failed to publish event update to Redis: {e}")

        logger.debug(
            "Published event update notification",
            extra={"event_id": event_data.get("id")},
        )

    async def _handle_detection_new(self, payload: PgNotifyPayload) -> None:
        """Handle new detection notifications.

        Args:
            payload: Parsed notification payload
        """
        detection_data = payload.data

        message = {
            "type": "detection.new",
            "source": "pg_notify",
            "data": {
                "detection_id": detection_data.get("id"),
                "camera_id": detection_data.get("camera_id"),
                "label": detection_data.get("object_type"),
                "confidence": detection_data.get("confidence"),
                "timestamp": detection_data.get("detected_at"),
            },
        }

        if self._redis:
            try:
                settings = get_settings()
                await self._redis.publish(settings.redis_event_channel, message)
            except Exception as e:
                logger.error(f"Failed to publish detection to Redis: {e}")

        logger.debug(
            "Published new detection notification",
            extra={"detection_id": detection_data.get("id")},
        )

    async def _handle_alert_new(self, payload: PgNotifyPayload) -> None:
        """Handle new alert notifications.

        Args:
            payload: Parsed notification payload
        """
        alert_data = payload.data

        message = {
            "type": "alert_created",
            "source": "pg_notify",
            "data": {
                "id": alert_data.get("id"),
                "event_id": alert_data.get("event_id"),
                "rule_id": alert_data.get("rule_id"),
                "severity": alert_data.get("severity"),
                "status": alert_data.get("status"),
            },
        }

        if self._redis:
            try:
                settings = get_settings()
                await self._redis.publish(settings.redis_event_channel, message)
            except Exception as e:
                logger.error(f"Failed to publish alert to Redis: {e}")

        logger.debug(
            "Published new alert notification",
            extra={"alert_id": alert_data.get("id")},
        )

    async def _listen_loop(self) -> None:
        """Main listener loop that keeps the connection alive.

        This loop monitors the connection and handles reconnection if needed.
        """
        while self._is_running:
            try:
                # Keep connection alive by checking periodically
                if self._connection is None or self._connection.is_closed():
                    logger.warning("Database connection lost, reconnecting...")
                    self._is_healthy = False
                    await self._connect()

                # Sleep and let asyncpg handle notifications via callback
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                logger.info("Listen loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in listen loop: {e}", exc_info=True)
                self._is_healthy = False

                # Attempt reconnection
                if self._is_running:
                    self._reconnect_attempts += 1
                    if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                        logger.error("Max reconnection attempts exceeded, stopping listener")
                        break

                    delay = min(
                        self.BASE_RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1)),
                        self.MAX_RECONNECT_DELAY,
                    )
                    await asyncio.sleep(delay)

    def is_healthy(self) -> bool:
        """Check if the listener is healthy and connected.

        Returns:
            True if running and connected, False otherwise
        """
        return self._is_running and self._is_healthy

    def get_status(self) -> dict[str, Any]:
        """Get current listener status for health checks.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self._is_running,
            "healthy": self._is_healthy,
            "connected": self._connection is not None and not self._connection.is_closed()
            if self._connection
            else False,
            "reconnect_attempts": self._reconnect_attempts,
            "channels": [c.value for c in self._channels],
        }


# Global listener instance
_listener: PgNotifyListener | None = None


async def get_pg_notify_listener(
    redis_client: RedisClient | None = None,
    broadcaster: EventBroadcaster | None = None,
) -> PgNotifyListener:
    """Get or create the global PgNotifyListener instance.

    Args:
        redis_client: Optional Redis client
        broadcaster: Optional EventBroadcaster

    Returns:
        PgNotifyListener instance
    """
    global _listener  # noqa: PLW0603

    if _listener is None:
        _listener = PgNotifyListener(
            redis_client=redis_client,
            broadcaster=broadcaster,
        )

    return _listener


async def stop_pg_notify_listener() -> None:
    """Stop and cleanup the global PgNotifyListener instance."""
    global _listener  # noqa: PLW0603

    if _listener:
        await _listener.stop()
        _listener = None
