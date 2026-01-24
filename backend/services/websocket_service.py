"""WebSocket service with pub/sub channel sharding for scalable broadcasting.

This module provides a sharded pub/sub architecture for WebSocket event broadcasting.
Events are distributed across multiple Redis channels using consistent hashing on
camera_id, enabling horizontal scaling of event distribution.

Key features:
- Consistent hash sharding using MD5 hash of camera_id
- Configurable shard count (default: 16)
- Efficient multi-camera subscription across shards
- Per-shard channel naming: events:shard:{0-N}
- Client-side filtering for specific camera_id within shard

Architecture:
    Publishers use `publish_event()` which:
    1. Computes shard from camera_id using consistent hash
    2. Publishes to `events:shard:{shard_number}`

    Subscribers use `subscribe_camera()` or `subscribe_cameras()` which:
    1. Compute shards for requested camera_id(s)
    2. Subscribe to required shard channels
    3. Filter received messages for specific camera_ids

Example Usage:
    from backend.services.websocket_service import (
        WebSocketShardedService,
        get_websocket_sharded_service,
    )

    # Get the service
    service = await get_websocket_sharded_service(redis_client)

    # Publish an event (automatically routed to correct shard)
    await service.publish_event(
        camera_id="front_door",
        event_type="motion_detected",
        payload={"confidence": 0.95}
    )

    # Subscribe to events from a single camera
    async for event in service.subscribe_camera("front_door"):
        print(f"Event: {event}")

    # Subscribe to events from multiple cameras
    async for event in service.subscribe_cameras(["front_door", "back_yard"]):
        print(f"Event: {event}")

NEM-3415: Implements pub/sub channel sharding for scalable WebSocket broadcasting.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from typing import TYPE_CHECKING, Any

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from redis.asyncio.client import PubSub

    from backend.core.redis import RedisClient

logger = get_logger(__name__)


def _get_shard(camera_id: str, shard_count: int) -> int:
    """Compute the shard number for a given camera_id using consistent hashing.

    Uses MD5 hash to ensure consistent distribution of camera_ids across shards.
    This ensures the same camera_id always maps to the same shard, enabling
    efficient subscription patterns.

    Args:
        camera_id: The camera identifier to hash.
        shard_count: Total number of shards available.

    Returns:
        Shard number (0 to shard_count - 1).

    Example:
        >>> _get_shard("front_door", 16)
        7  # Consistent result for same inputs
    """
    # Use MD5 for consistent hashing - not for security, just distribution
    # nosemgrep: weak-hash-md5  # noqa: ERA001
    hash_digest = hashlib.md5(camera_id.encode(), usedforsecurity=False).hexdigest()
    return int(hash_digest, 16) % shard_count


def _get_shard_channel(shard_number: int, base_channel: str = "events") -> str:
    """Get the Redis channel name for a specific shard.

    Args:
        shard_number: The shard number (0 to shard_count - 1).
        base_channel: Base channel name prefix.

    Returns:
        Channel name in format: "{base_channel}:shard:{shard_number}"

    Example:
        >>> _get_shard_channel(0)
        "events:shard:0"
        >>> _get_shard_channel(7, "security")
        "security:shard:7"
    """
    return f"{base_channel}:shard:{shard_number}"


class WebSocketShardedService:
    """Sharded pub/sub service for scalable WebSocket event distribution.

    This service distributes events across multiple Redis pub/sub channels
    using consistent hashing on camera_id. This enables:
    - Horizontal scaling: Different shards can be processed by different workers
    - Reduced per-channel load: Events are distributed across shards
    - Efficient subscription: Subscribe only to shards containing cameras of interest

    Attributes:
        _redis: Redis client for pub/sub operations.
        _shard_count: Number of shards for event distribution.
        _base_channel: Base channel name for shard naming.
        _subscriptions: Active pub/sub subscriptions by shard.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        shard_count: int | None = None,
        base_channel: str = "events",
    ) -> None:
        """Initialize the sharded WebSocket service.

        Args:
            redis_client: Connected Redis client instance.
            shard_count: Number of shards. Defaults to settings.redis_pubsub_shard_count.
            base_channel: Base channel name for shard naming.
        """
        self._redis = redis_client
        self._shard_count = shard_count or get_settings().redis_pubsub_shard_count
        self._base_channel = base_channel
        self._subscriptions: dict[int, PubSub] = {}
        self._active_subscriptions: set[int] = set()
        self._publish_count = 0
        self._subscribe_count = 0

    @property
    def shard_count(self) -> int:
        """Get the number of shards."""
        return self._shard_count

    @property
    def base_channel(self) -> str:
        """Get the base channel name."""
        return self._base_channel

    @property
    def publish_count(self) -> int:
        """Get total number of events published."""
        return self._publish_count

    @property
    def subscribe_count(self) -> int:
        """Get total number of subscriptions created."""
        return self._subscribe_count

    def get_shard(self, camera_id: str) -> int:
        """Get the shard number for a camera_id.

        Public wrapper for consistent hash computation.

        Args:
            camera_id: The camera identifier.

        Returns:
            Shard number (0 to shard_count - 1).
        """
        return _get_shard(camera_id, self._shard_count)

    def get_shard_channel(self, shard_number: int) -> str:
        """Get the Redis channel name for a shard.

        Args:
            shard_number: The shard number.

        Returns:
            Channel name for the shard.
        """
        return _get_shard_channel(shard_number, self._base_channel)

    def get_camera_channel(self, camera_id: str) -> str:
        """Get the Redis channel name for a camera's shard.

        Args:
            camera_id: The camera identifier.

        Returns:
            Channel name for the camera's shard.
        """
        shard = self.get_shard(camera_id)
        return self.get_shard_channel(shard)

    def get_shards_for_cameras(self, camera_ids: list[str]) -> set[int]:
        """Get the set of shards needed to cover multiple cameras.

        Args:
            camera_ids: List of camera identifiers.

        Returns:
            Set of shard numbers.
        """
        return {self.get_shard(camera_id) for camera_id in camera_ids}

    async def publish_event(
        self,
        camera_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> int:
        """Publish an event to the appropriate shard channel.

        Routes the event to the correct shard based on camera_id's consistent hash.

        Args:
            camera_id: Camera identifier for shard routing.
            event_type: Type of event (e.g., "motion_detected", "alert_created").
            payload: Event payload data.
            correlation_id: Optional correlation ID for request tracing.

        Returns:
            Number of subscribers that received the message.

        Example:
            >>> await service.publish_event(
            ...     camera_id="front_door",
            ...     event_type="motion_detected",
            ...     payload={"confidence": 0.95}
            ... )
            1  # One subscriber received the message
        """
        shard = self.get_shard(camera_id)
        channel = self.get_shard_channel(shard)

        # Build the message with metadata
        message = {
            "camera_id": camera_id,
            "event_type": event_type,
            "payload": payload,
            "shard": shard,
        }
        if correlation_id:
            message["correlation_id"] = correlation_id

        try:
            subscriber_count = await self._redis.publish(channel, message)
            self._publish_count += 1

            logger.debug(
                f"Published event to shard {shard}",
                extra={
                    "camera_id": camera_id,
                    "event_type": event_type,
                    "shard": shard,
                    "channel": channel,
                    "subscribers": subscriber_count,
                },
            )

            return subscriber_count
        except Exception as e:
            logger.error(
                f"Failed to publish event to shard {shard}: {e}",
                extra={
                    "camera_id": camera_id,
                    "event_type": event_type,
                    "shard": shard,
                },
                exc_info=True,
            )
            raise

    async def subscribe_camera(
        self,
        camera_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events for a single camera.

        Creates a subscription to the shard containing the camera and filters
        messages to only yield events for the specified camera.

        Args:
            camera_id: Camera identifier to subscribe to.

        Yields:
            Event dictionaries for the specified camera.

        Example:
            >>> async for event in service.subscribe_camera("front_door"):
            ...     print(f"Event: {event['event_type']}")
        """
        async for event in self.subscribe_cameras([camera_id]):
            yield event

    async def subscribe_cameras(
        self,
        camera_ids: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events for multiple cameras across shards.

        Computes the set of shards needed to cover all cameras, subscribes to
        those shard channels, and filters messages for the specified cameras.

        Args:
            camera_ids: List of camera identifiers to subscribe to.

        Yields:
            Event dictionaries for any of the specified cameras.

        Example:
            >>> async for event in service.subscribe_cameras(["front_door", "back_yard"]):
            ...     print(f"Camera: {event['camera_id']}, Event: {event['event_type']}")
        """
        if not camera_ids:
            return

        # Convert to set for efficient lookup
        camera_set = set(camera_ids)

        # Get required shards
        required_shards = self.get_shards_for_cameras(camera_ids)
        channels = [self.get_shard_channel(shard) for shard in required_shards]

        logger.debug(
            f"Subscribing to {len(required_shards)} shards for {len(camera_ids)} cameras",
            extra={
                "camera_ids": camera_ids,
                "shards": list(required_shards),
                "channels": channels,
            },
        )

        # Create pub/sub subscription
        pubsub = self._redis.create_pubsub()
        try:
            await pubsub.subscribe(*channels)
            self._subscribe_count += 1

            # Track active subscriptions
            for shard in required_shards:
                self._active_subscriptions.add(shard)

            # Listen for messages and filter by camera_id
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                # Parse message data
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                try:
                    if isinstance(data, str):
                        event = json.loads(data)
                    else:
                        event = data
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message as JSON: {data}")
                    continue

                # Filter for requested cameras
                event_camera_id = event.get("camera_id")
                if event_camera_id in camera_set:
                    yield event

        except asyncio.CancelledError:
            logger.debug("Subscription cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in subscription: {e}", exc_info=True)
            raise
        finally:
            # Cleanup subscription
            try:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()
            except Exception as cleanup_error:
                logger.debug(f"Error during subscription cleanup: {cleanup_error}")

            # Remove from active subscriptions
            for shard in required_shards:
                self._active_subscriptions.discard(shard)

    async def subscribe_all_shards(self) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to all shard channels.

        Used for global event monitoring, such as admin dashboards or
        aggregated metrics collection.

        Yields:
            Event dictionaries from all shards.

        Example:
            >>> async for event in service.subscribe_all_shards():
            ...     print(f"Global event: {event}")
        """
        channels = [self.get_shard_channel(shard) for shard in range(self._shard_count)]

        logger.debug(
            f"Subscribing to all {self._shard_count} shards",
            extra={"channels": channels},
        )

        pubsub = self._redis.create_pubsub()
        try:
            await pubsub.subscribe(*channels)
            self._subscribe_count += 1

            # Track all shards as active
            for shard in range(self._shard_count):
                self._active_subscriptions.add(shard)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                try:
                    if isinstance(data, str):
                        event = json.loads(data)
                    else:
                        event = data
                    yield event
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message as JSON: {data}")
                    continue

        except asyncio.CancelledError:
            logger.debug("All-shard subscription cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in all-shard subscription: {e}", exc_info=True)
            raise
        finally:
            try:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()
            except Exception as cleanup_error:
                logger.debug(f"Error during subscription cleanup: {cleanup_error}")

            self._active_subscriptions.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with publish/subscribe counts and configuration.
        """
        return {
            "shard_count": self._shard_count,
            "base_channel": self._base_channel,
            "publish_count": self._publish_count,
            "subscribe_count": self._subscribe_count,
            "active_subscription_shards": len(self._active_subscriptions),
            "active_shards": list(self._active_subscriptions),
        }


# =============================================================================
# Global Singleton Instance
# =============================================================================

_service: WebSocketShardedService | None = None
_service_lock: asyncio.Lock | None = None
_init_lock = threading.Lock()


def _get_service_lock() -> asyncio.Lock:
    """Get the service initialization lock (lazy initialization).

    Thread-safe creation of the asyncio lock for service initialization.

    Returns:
        asyncio.Lock for service initialization
    """
    global _service_lock  # noqa: PLW0603
    if _service_lock is None:
        with _init_lock:
            if _service_lock is None:
                _service_lock = asyncio.Lock()
    return _service_lock


async def get_websocket_sharded_service(
    redis_client: RedisClient,
    shard_count: int | None = None,
    base_channel: str = "events",
) -> WebSocketShardedService:
    """Get or create the global WebSocket sharded service instance.

    This function provides a thread-safe singleton pattern for the
    WebSocketShardedService. On first call, it creates a new instance.
    Subsequent calls return the existing singleton.

    Args:
        redis_client: Redis client instance.
        shard_count: Optional shard count override (only used on first call).
        base_channel: Optional base channel override (only used on first call).

    Returns:
        WebSocketShardedService instance.

    Example:
        # During application startup
        service = await get_websocket_sharded_service(redis_client)

        # Later in application code
        service = await get_websocket_sharded_service(redis_client)
        await service.publish_event("front_door", "motion", {"confidence": 0.95})
    """
    global _service  # noqa: PLW0603

    # Fast path: service already exists
    if _service is not None:
        return _service

    # Slow path: need to initialize with lock
    lock = _get_service_lock()
    async with lock:
        # Double-check after acquiring lock
        if _service is None:
            _service = WebSocketShardedService(
                redis_client=redis_client,
                shard_count=shard_count,
                base_channel=base_channel,
            )
            logger.info(
                f"Global WebSocket sharded service initialized with {_service.shard_count} shards"
            )

    return _service


def get_websocket_sharded_service_sync() -> WebSocketShardedService | None:
    """Get the global WebSocket sharded service instance synchronously.

    Returns the existing singleton if it has been initialized,
    or None if not yet initialized.

    This is useful for checking if the service is available without
    async context.

    Returns:
        WebSocketShardedService instance or None.
    """
    return _service


def reset_service_state() -> None:
    """Reset the global service state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _service, _service_lock  # noqa: PLW0603
    _service = None
    _service_lock = None
