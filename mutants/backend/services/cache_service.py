"""Cache service for Redis-backed caching with cache-aside pattern.

This service implements a cache-aside (lazy loading) pattern for frequently accessed data.
It wraps the RedisClient with higher-level caching operations that generate actual cache
hits in Redis, improving the cache hit ratio metric.

Usage:
    cache = await get_cache_service()

    # Simple get/set
    value = await cache.get("key")
    await cache.set("key", value, ttl=300)

    # Cache-aside pattern
    value = await cache.get_or_set(
        key="cameras:list",
        factory=lambda: db.execute(select(Camera)),
        ttl=60
    )

    # Invalidation
    await cache.invalidate("cameras:list")
    await cache.invalidate_pattern("cameras:*")
"""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from backend.core.logging import get_logger
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)

T = TypeVar("T")

# Default TTL values in seconds
DEFAULT_TTL = 300  # 5 minutes
SHORT_TTL = 60  # 1 minute
LONG_TTL = 3600  # 1 hour

# Cache key prefixes for different data types
CACHE_PREFIX = "cache:"
CAMERAS_PREFIX = f"{CACHE_PREFIX}cameras:"
EVENTS_PREFIX = f"{CACHE_PREFIX}events:"
STATS_PREFIX = f"{CACHE_PREFIX}stats:"


class CacheService:
    """Redis-backed caching service with cache-aside pattern support.

    This service provides:
    - Simple get/set operations with TTL
    - Cache-aside pattern (get_or_set) for automatic cache population
    - Pattern-based invalidation
    - Serialization/deserialization of complex objects

    All cache keys are prefixed with 'cache:' to distinguish them from
    other Redis keys used for queues and pub/sub.
    """

    def __init__(self, redis_client: RedisClient):
        """Initialize cache service with Redis client.

        Args:
            redis_client: Connected RedisClient instance
        """
        self._redis = redis_client

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        This operation generates a keyspace_hit or keyspace_miss in Redis stats.

        Args:
            key: Cache key (will be prefixed with 'cache:')

        Returns:
            Cached value if found, None otherwise
        """
        full_key = f"{CACHE_PREFIX}{key}"
        try:
            value = await self._redis.get(full_key)
            if value is not None:
                logger.debug(f"Cache hit for key: {key}")
            return value
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """Set a value in the cache with TTL.

        Args:
            key: Cache key (will be prefixed with 'cache:')
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        full_key = f"{CACHE_PREFIX}{key}"
        try:
            await self._redis.set(full_key, value, expire=ttl)
            logger.debug(f"Cache set for key: {key} with TTL: {ttl}s")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int = DEFAULT_TTL,
    ) -> Any:
        """Get value from cache or compute and store it.

        Implements the cache-aside pattern:
        1. Try to get value from cache (generates hit/miss metric)
        2. If cache miss, call factory to compute value
        3. Store computed value in cache
        4. Return value

        Args:
            key: Cache key (will be prefixed with 'cache:')
            factory: Callable that returns the value if not cached.
                     Can be sync or async.
            ttl: Time to live in seconds (default: 5 minutes)

        Returns:
            Cached or computed value
        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Cache miss - compute value
        logger.debug(f"Cache miss for key: {key}, computing value")
        try:
            result = factory()
            # Handle async factories
            if asyncio.iscoroutine(result):
                result = await result

            # Store in cache
            await self.set(key, result, ttl)
            return result
        except Exception as e:
            logger.error(f"Factory failed for cache key {key}: {e}")
            raise

    async def invalidate(self, key: str) -> bool:
        """Invalidate a single cache key.

        Args:
            key: Cache key to invalidate (will be prefixed with 'cache:')

        Returns:
            True if key was deleted, False otherwise
        """
        full_key = f"{CACHE_PREFIX}{key}"
        try:
            deleted = await self._redis.delete(full_key)
            if deleted > 0:
                logger.debug(f"Cache invalidated for key: {key}")
            return deleted > 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching a pattern.

        Uses SCAN to find matching keys (non-blocking).

        Args:
            pattern: Glob-style pattern (e.g., "cameras:*")
                     Will be prefixed with 'cache:'

        Returns:
            Number of keys deleted
        """
        full_pattern = f"{CACHE_PREFIX}{pattern}"
        try:
            client = self._redis._ensure_connected()
            keys_to_delete: list[str] = []

            # Use SCAN to find matching keys
            async for key in client.scan_iter(match=full_pattern, count=100):
                keys_to_delete.append(key)

            if keys_to_delete:
                deleted = await self._redis.delete(*keys_to_delete)
                logger.debug(f"Cache invalidated {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache pattern invalidation failed for {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """Check if a cache key exists.

        Note: This does NOT generate a keyspace_hit/miss metric.
        Use get() if you want to contribute to hit ratio.

        Args:
            key: Cache key to check (will be prefixed with 'cache:')

        Returns:
            True if key exists, False otherwise
        """
        full_key = f"{CACHE_PREFIX}{key}"
        try:
            return await self._redis.exists(full_key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return False

    async def refresh(self, key: str, ttl: int = DEFAULT_TTL) -> bool:
        """Refresh the TTL of a cache key without fetching its value.

        Args:
            key: Cache key (will be prefixed with 'cache:')
            ttl: New TTL in seconds

        Returns:
            True if TTL was set, False if key doesn't exist
        """
        full_key = f"{CACHE_PREFIX}{key}"
        try:
            return await self._redis.expire(full_key, ttl)
        except Exception as e:
            logger.warning(f"Cache refresh failed for key {key}: {e}")
            return False


# Cache keys for commonly accessed data
class CacheKeys:
    """Standard cache key generators for commonly cached data."""

    @staticmethod
    def cameras_list() -> str:
        """Cache key for full camera list."""
        return "cameras:list"

    @staticmethod
    def cameras_list_by_status(status: str | None) -> str:
        """Cache key for camera list filtered by status."""
        return f"cameras:list:{status or 'all'}"

    @staticmethod
    def camera(camera_id: str) -> str:
        """Cache key for a single camera."""
        return f"cameras:{camera_id}"

    @staticmethod
    def event_stats(start_date: str | None = None, end_date: str | None = None) -> str:
        """Cache key for event statistics."""
        return f"stats:events:{start_date or 'none'}:{end_date or 'none'}"

    @staticmethod
    def system_status() -> str:
        """Cache key for system status."""
        return "system:status"


# Singleton instance
_cache_service: CacheService | None = None


async def get_cache_service() -> CacheService:
    """Get or create the cache service singleton.

    Returns:
        CacheService instance connected to Redis
    """
    global _cache_service  # noqa: PLW0603
    if _cache_service is None:
        redis_client = await init_redis()
        _cache_service = CacheService(redis_client)
    return _cache_service


async def reset_cache_service() -> None:
    """Reset the cache service singleton (for testing)."""
    global _cache_service  # noqa: PLW0603
    _cache_service = None
