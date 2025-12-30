"""Redis connection and operations module."""

import asyncio
import contextlib
import json
import random
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError, TimeoutError

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import (
    record_queue_items_dropped,
    record_queue_items_moved_to_dlq,
    record_queue_items_rejected,
    record_queue_overflow,
)

logger = get_logger(__name__)


class QueueOverflowPolicy(str, Enum):
    """Policy for handling queue overflow."""

    REJECT = "reject"  # Return error when queue is full
    DLQ = "dlq"  # Move oldest items to dead-letter queue before adding
    DROP_OLDEST = "drop_oldest"  # Trim oldest with warning (legacy behavior)


@dataclass
class QueueAddResult:
    """Result of adding an item to a queue with backpressure handling."""

    success: bool
    queue_length: int
    dropped_count: int = 0
    moved_to_dlq_count: int = 0
    error: str | None = None
    warning: str | None = None

    @property
    def had_backpressure(self) -> bool:
        """Return True if backpressure was applied."""
        return self.dropped_count > 0 or self.moved_to_dlq_count > 0 or self.error is not None


@dataclass
class QueuePressureMetrics:
    """Metrics about queue pressure and health."""

    queue_name: str
    current_length: int
    max_size: int
    fill_ratio: float
    is_at_pressure_threshold: bool
    is_full: bool
    overflow_policy: str


class RedisClient:
    """Async Redis client with connection pooling and helper methods."""

    def __init__(self, redis_url: str | None = None):
        """Initialize Redis client with connection pool.

        Args:
            redis_url: Redis connection URL. If not provided, uses settings.
        """
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None
        self._pubsub: PubSub | None = None
        self._max_retries = 3
        # Exponential backoff settings
        self._base_delay = 1.0  # Base delay in seconds
        self._max_delay = 30.0  # Maximum delay cap in seconds
        self._jitter_factor = 0.25  # Random jitter 0-25% of delay

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds with exponential backoff and random jitter
        """
        # Exponential backoff: base_delay * 2^(attempt-1), capped at max_delay
        delay: float = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
        # Add random jitter (0-25% of delay) - not cryptographic, just for retry timing
        jitter: float = delay * random.uniform(0, self._jitter_factor)  # noqa: S311
        return delay + jitter

    async def connect(self) -> None:
        """Establish Redis connection with exponential backoff retry logic."""
        for attempt in range(1, self._max_retries + 1):
            try:
                self._pool = ConnectionPool.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                    max_connections=10,
                )
                self._client = Redis(connection_pool=self._pool)
                # Test connection
                await self._client.ping()  # type: ignore
                logger.info("Successfully connected to Redis")
                return
            except (ConnectionError, TimeoutError) as e:
                logger.warning(
                    f"Redis connection attempt {attempt}/{self._max_retries} failed: {e}"
                )
                if attempt < self._max_retries:
                    backoff_delay = self._calculate_backoff_delay(attempt)
                    logger.info(f"Retrying in {backoff_delay:.2f} seconds...")
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error("Failed to connect to Redis after all retries")
                    raise

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        with contextlib.suppress(Exception):
            if self._pubsub:
                await self._pubsub.close()
                self._pubsub = None

            if self._client:
                await self._client.close()
                self._client = None

            if self._pool:
                await self._pool.disconnect()
                self._pool = None

            logger.info("Redis connection closed")

    def _ensure_connected(self) -> Redis:
        """Ensure Redis client is connected.

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If client is not connected
        """
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def health_check(self) -> dict[str, Any]:
        """Check Redis connection health.

        Returns:
            Dictionary with health status information
        """
        try:
            client = self._ensure_connected()
            await client.ping()  # type: ignore
            info = await client.info("server")  # type: ignore
            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    # Queue operations

    async def add_to_queue(self, queue_name: str, data: Any, max_size: int = 10000) -> int:
        """Add item to the end of a queue (RPUSH) with optional size limit.

        DEPRECATED: This method uses legacy behavior that can silently drop items.
        For production use, prefer add_to_queue_safe() which provides proper
        backpressure handling and never silently drops data.

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add (will be JSON-serialized if not a string)
            max_size: Maximum queue size (default 10000). After RPUSH, queue is
                trimmed to keep only the last max_size items (newest). Set to 0
                to disable trimming.

        Returns:
            Length of the queue after adding the item
        """
        client = self._ensure_connected()
        serialized = json.dumps(data) if not isinstance(data, str) else data
        result = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]
        # Trim to max_size (keep newest items)
        if max_size > 0:
            # Calculate and log any dropped items
            if result > max_size:
                dropped_count = result - max_size
                logger.warning(
                    f"Queue '{queue_name}' overflow: trimming {dropped_count} oldest items "
                    f"(queue size {result} exceeds max {max_size}). "
                    "Consider using add_to_queue_safe() for proper backpressure handling.",
                    extra={
                        "queue_name": queue_name,
                        "queue_length": result,
                        "max_size": max_size,
                        "dropped_count": dropped_count,
                    },
                )
            await client.ltrim(queue_name, -max_size, -1)  # type: ignore[misc]
        return result

    async def add_to_queue_safe(  # noqa: PLR0912
        self,
        queue_name: str,
        data: Any,
        max_size: int | None = None,
        overflow_policy: QueueOverflowPolicy | str | None = None,
        dlq_name: str | None = None,
    ) -> QueueAddResult:
        """Add item to queue with proper backpressure handling.

        This method never silently drops data. Based on the overflow policy:
        - REJECT: Returns error if queue is full, item is NOT added
        - DLQ: Moves oldest items to dead-letter queue before adding
        - DROP_OLDEST: Logs warning and trims (legacy behavior with visibility)

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add (will be JSON-serialized if not a string)
            max_size: Maximum queue size. If None, uses settings.queue_max_size
            overflow_policy: Policy for handling overflow. If None, uses settings
            dlq_name: DLQ name for 'dlq' policy. Defaults to f"dlq:overflow:{queue_name}"

        Returns:
            QueueAddResult with success status and metrics
        """
        settings = get_settings()
        client = self._ensure_connected()

        # Apply defaults from settings
        if max_size is None:
            max_size = settings.queue_max_size
        if overflow_policy is None:
            overflow_policy = settings.queue_overflow_policy

        # Normalize policy to enum
        if isinstance(overflow_policy, str):
            try:
                overflow_policy = QueueOverflowPolicy(overflow_policy.lower())
            except ValueError:
                overflow_policy = QueueOverflowPolicy.REJECT

        # Default DLQ name
        if dlq_name is None:
            dlq_name = f"dlq:overflow:{queue_name}"

        serialized = json.dumps(data) if not isinstance(data, str) else data

        # Check current queue length
        current_length = cast("int", await client.llen(queue_name))  # type: ignore[misc]

        # Log warning if approaching threshold
        pressure_threshold = settings.queue_backpressure_threshold
        fill_ratio = current_length / max_size if max_size > 0 else 0
        if fill_ratio >= pressure_threshold:
            logger.warning(
                f"Queue '{queue_name}' pressure warning: {fill_ratio:.1%} full "
                f"({current_length}/{max_size})",
                extra={
                    "queue_name": queue_name,
                    "current_length": current_length,
                    "max_size": max_size,
                    "fill_ratio": fill_ratio,
                    "threshold": pressure_threshold,
                },
            )

        # Handle overflow based on policy
        if current_length >= max_size > 0:
            if overflow_policy == QueueOverflowPolicy.REJECT:
                error_msg = (
                    f"Queue '{queue_name}' is full ({current_length}/{max_size}). "
                    "Item rejected to prevent data loss."
                )
                logger.error(
                    error_msg,
                    extra={
                        "queue_name": queue_name,
                        "current_length": current_length,
                        "max_size": max_size,
                        "policy": overflow_policy.value,
                    },
                )
                # Record metrics for queue overflow
                record_queue_overflow(queue_name, overflow_policy.value)
                record_queue_items_rejected(queue_name)
                return QueueAddResult(
                    success=False,
                    queue_length=current_length,
                    error=error_msg,
                )

            elif overflow_policy == QueueOverflowPolicy.DLQ:
                # Move oldest item to DLQ before adding new one
                moved_count = 0
                items_to_move = (current_length - max_size) + 1  # +1 for the new item

                for _ in range(items_to_move):
                    # Pop from front of queue (oldest item)
                    oldest_item = await client.lpop(queue_name)  # type: ignore[misc]
                    if oldest_item:
                        # Add to DLQ with metadata
                        dlq_entry = {
                            "original_queue": queue_name,
                            "data": oldest_item,
                            "reason": "queue_overflow",
                            "overflow_policy": overflow_policy.value,
                        }
                        await client.rpush(dlq_name, json.dumps(dlq_entry))  # type: ignore[misc]
                        moved_count += 1

                if moved_count > 0:
                    logger.warning(
                        f"Queue '{queue_name}' overflow: moved {moved_count} oldest items "
                        f"to DLQ '{dlq_name}'",
                        extra={
                            "queue_name": queue_name,
                            "dlq_name": dlq_name,
                            "moved_count": moved_count,
                            "policy": overflow_policy.value,
                        },
                    )
                    # Record metrics for queue overflow
                    record_queue_overflow(queue_name, overflow_policy.value)
                    record_queue_items_moved_to_dlq(queue_name, moved_count)

                # Now add the new item
                new_length = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]

                return QueueAddResult(
                    success=True,
                    queue_length=new_length,
                    moved_to_dlq_count=moved_count,
                    warning=f"Moved {moved_count} items to DLQ due to overflow",
                )

            elif overflow_policy == QueueOverflowPolicy.DROP_OLDEST:
                # Add item then trim with explicit warning
                result = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]
                dropped_count = max(0, result - max_size)

                if dropped_count > 0:
                    logger.warning(
                        f"Queue '{queue_name}' overflow: dropping {dropped_count} oldest items "
                        f"(policy: {overflow_policy.value})",
                        extra={
                            "queue_name": queue_name,
                            "queue_length": result,
                            "max_size": max_size,
                            "dropped_count": dropped_count,
                            "policy": overflow_policy.value,
                        },
                    )
                    await client.ltrim(queue_name, -max_size, -1)  # type: ignore[misc]
                    # Record metrics for queue overflow
                    record_queue_overflow(queue_name, overflow_policy.value)
                    record_queue_items_dropped(queue_name, dropped_count)

                return QueueAddResult(
                    success=True,
                    queue_length=min(result, max_size),
                    dropped_count=dropped_count,
                    warning=f"Dropped {dropped_count} oldest items due to overflow"
                    if dropped_count > 0
                    else None,
                )

        # Normal case: queue has space
        new_length = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]

        return QueueAddResult(
            success=True,
            queue_length=new_length,
        )

    async def get_queue_pressure(
        self,
        queue_name: str,
        max_size: int | None = None,
    ) -> QueuePressureMetrics:
        """Get metrics about queue pressure and health.

        Args:
            queue_name: Name of the queue to check
            max_size: Maximum queue size. If None, uses settings.queue_max_size

        Returns:
            QueuePressureMetrics with current queue status
        """
        settings = get_settings()

        if max_size is None:
            max_size = settings.queue_max_size

        current_length = await self.get_queue_length(queue_name)
        fill_ratio = current_length / max_size if max_size > 0 else 0

        return QueuePressureMetrics(
            queue_name=queue_name,
            current_length=current_length,
            max_size=max_size,
            fill_ratio=fill_ratio,
            is_at_pressure_threshold=fill_ratio >= settings.queue_backpressure_threshold,
            is_full=current_length >= max_size,
            overflow_policy=settings.queue_overflow_policy,
        )

    async def get_from_queue(self, queue_name: str, timeout: int = 0) -> Any | None:
        """Get item from the front of a queue (BLPOP).

        Args:
            queue_name: Name of the queue (Redis list key)
            timeout: Timeout in seconds (0 = no timeout, blocks indefinitely)

        Returns:
            Deserialized item from the queue, or None if timeout
        """
        client = self._ensure_connected()
        result = await client.blpop([queue_name], timeout=timeout)  # type: ignore[misc]
        if result:
            _, value = result
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def get_queue_length(self, queue_name: str) -> int:
        """Get the length of a queue (LLEN).

        Args:
            queue_name: Name of the queue (Redis list key)

        Returns:
            Number of items in the queue
        """
        client = self._ensure_connected()
        return cast("int", await client.llen(queue_name))  # type: ignore[misc]

    async def peek_queue(
        self,
        queue_name: str,
        start: int = 0,
        end: int = 100,
        max_items: int = 1000,
    ) -> list[Any]:
        """Peek at items in a queue without removing them (LRANGE).

        Args:
            queue_name: Name of the queue (Redis list key)
            start: Start index (0-based)
            end: End index (default 100, use -1 for all up to max_items)
            max_items: Hard cap on items returned (default 1000)

        Returns:
            List of deserialized items
        """
        end = max_items - 1 if end == -1 else min(end, start + max_items - 1)

        client = self._ensure_connected()
        items = cast("list[str]", await client.lrange(queue_name, start, end))  # type: ignore[misc]
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                result.append(item)
        return result

    async def clear_queue(self, queue_name: str) -> bool:
        """Clear all items from a queue (DELETE).

        Args:
            queue_name: Name of the queue (Redis list key)

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        client = self._ensure_connected()
        result = cast("int", await client.delete(queue_name))
        return result > 0

    # Pub/Sub operations

    def get_pubsub(self) -> PubSub:
        """Get or create a Pub/Sub instance.

        Returns:
            PubSub instance for subscribing to channels
        """
        client = self._ensure_connected()
        if not self._pubsub:
            self._pubsub = client.pubsub()
        return self._pubsub

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a channel.

        Args:
            channel: Channel name
            message: Message to publish (will be JSON-serialized if not a string)

        Returns:
            Number of subscribers that received the message
        """
        client = self._ensure_connected()
        serialized = json.dumps(message) if not isinstance(message, str) else message
        return cast("int", await client.publish(channel, serialized))

    async def subscribe(self, *channels: str) -> PubSub:
        """Subscribe to one or more channels.

        Args:
            *channels: Channel names to subscribe to

        Returns:
            PubSub instance for receiving messages
        """
        pubsub = self.get_pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from one or more channels.

        Args:
            *channels: Channel names to unsubscribe from
        """
        if self._pubsub:
            await self._pubsub.unsubscribe(*channels)

    async def listen(self, pubsub: PubSub) -> AsyncGenerator[dict[str, Any]]:
        """Listen for messages from subscribed channels.

        Args:
            pubsub: PubSub instance to listen on

        Yields:
            Messages from subscribed channels
        """
        async for message in pubsub.listen():
            if message["type"] == "message":
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    message["data"] = json.loads(message["data"])
                yield message

    # Cache operations

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis cache.

        Args:
            key: Cache key

        Returns:
            Deserialized value or None if key doesn't exist
        """
        client = self._ensure_connected()
        value = await client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in Redis cache.

        Args:
            key: Cache key
            value: Value to store (will be JSON-serialized if not a string)
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        return cast("bool", await client.set(key, serialized, ex=expire))

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis.

        Args:
            *keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        client = self._ensure_connected()
        return cast("int", await client.delete(*keys))

    async def exists(self, *keys: str) -> int:
        """Check if one or more keys exist.

        Args:
            *keys: Keys to check

        Returns:
            Number of keys that exist
        """
        client = self._ensure_connected()
        return cast("int", await client.exists(*keys))

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a TTL (time-to-live) on a key.

        Args:
            key: Key to set TTL on
            seconds: TTL in seconds

        Returns:
            True if the timeout was set, False if key doesn't exist
        """
        client = self._ensure_connected()
        return cast("bool", await client.expire(key, seconds))


# Global Redis client instance
_redis_client: RedisClient | None = None


async def get_redis() -> AsyncGenerator[RedisClient]:
    """FastAPI dependency for Redis client.

    Yields:
        RedisClient instance
    """
    global _redis_client  # noqa: PLW0603

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    yield _redis_client


async def get_redis_optional() -> AsyncGenerator[RedisClient | None]:
    """FastAPI dependency for optional Redis client.

    This dependency is fail-soft: it returns None instead of raising an exception
    when Redis is unavailable. Use this for health check endpoints where you want
    to report Redis status rather than fail the request.

    Yields:
        RedisClient instance if connected, None if Redis is unavailable
    """
    global _redis_client  # noqa: PLW0603

    try:
        if _redis_client is None:
            _redis_client = RedisClient()
            await _redis_client.connect()
        yield _redis_client
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis unavailable (will report degraded status): {e}")
        yield None
    except Exception as e:
        # Catch any other Redis connection errors
        logger.warning(f"Redis connection error (will report degraded status): {e}")
        yield None


async def init_redis() -> RedisClient:
    """Initialize Redis client for application startup.

    Returns:
        Connected RedisClient instance
    """
    global _redis_client  # noqa: PLW0603

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    return _redis_client


async def close_redis() -> None:
    """Close Redis client for application shutdown."""
    global _redis_client  # noqa: PLW0603

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
