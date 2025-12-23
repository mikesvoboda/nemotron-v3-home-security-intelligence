"""Redis connection and operations module."""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError, TimeoutError

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


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
        self._retry_delay = 1.0

    async def connect(self) -> None:
        """Establish Redis connection with retry logic."""
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
                    await asyncio.sleep(self._retry_delay * attempt)
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

    async def add_to_queue(self, queue_name: str, data: Any) -> int:
        """Add item to the end of a queue (RPUSH).

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add (will be JSON-serialized if not a string)

        Returns:
            Length of the queue after adding the item
        """
        client = self._ensure_connected()
        serialized = json.dumps(data) if not isinstance(data, str) else data
        return await client.rpush(queue_name, serialized)  # type: ignore

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

    async def peek_queue(self, queue_name: str, start: int = 0, end: int = -1) -> list[Any]:
        """Peek at items in a queue without removing them (LRANGE).

        Args:
            queue_name: Name of the queue (Redis list key)
            start: Start index (0-based)
            end: End index (-1 for all items)

        Returns:
            List of deserialized items
        """
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

    async def listen(self, pubsub: PubSub) -> AsyncGenerator[dict[str, Any], None]:
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


# Global Redis client instance
_redis_client: RedisClient | None = None


async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """FastAPI dependency for Redis client.

    Yields:
        RedisClient instance
    """
    global _redis_client  # noqa: PLW0603

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    yield _redis_client


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
