"""Cache service for Redis-backed caching with cache-aside pattern.

This service implements a cache-aside (lazy loading) pattern for frequently accessed data.
It wraps the RedisClient with higher-level caching operations that generate actual cache
hits in Redis, improving the cache hit ratio metric.

Features (NEM-1682):
- Cache-aside pattern with automatic cache population
- Pattern-based invalidation for efficient cache clearing
- Prometheus metrics for cache hit/miss tracking
- Caching decorator for consistent patterns across endpoints

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

    # Invalidate event stats when events are created
    await cache.invalidate_event_stats()
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import record_cache_hit, record_cache_invalidation, record_cache_miss
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")

# Default TTL values in seconds
DEFAULT_TTL = 300  # 5 minutes
SHORT_TTL = 60  # 1 minute
LONG_TTL = 3600  # 1 hour


def _get_global_prefix() -> str:
    """Get the global Redis key prefix from settings.

    Returns:
        The global Redis key prefix (default: "hsi")
    """
    return get_settings().redis_key_prefix


# Cache key prefixes for different data types
# Now include the global prefix for multi-instance/blue-green deployments (NEM-1621)
def _get_cache_prefix() -> str:
    """Get the full cache prefix including global prefix."""
    return f"{_get_global_prefix()}:cache:"


# Note: CACHE_PREFIX is now a function call result for backward compatibility
# with existing tests. In production, use CacheKeys methods for proper prefixing.
CACHE_PREFIX = "cache:"  # Keep for backward compatibility in CacheService internals
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

    async def get(self, key: str, cache_type: str | None = None) -> Any | None:
        """Get a value from the cache.

        This operation generates a keyspace_hit or keyspace_miss in Redis stats,
        and records Prometheus metrics for cache hit/miss tracking.

        Args:
            key: Cache key (will be prefixed with 'cache:')
            cache_type: Optional cache type for metrics (e.g., "event_stats", "cameras").
                If not provided, will be inferred from the key prefix.

        Returns:
            Cached value if found, None otherwise
        """
        full_key = f"{CACHE_PREFIX}{key}"
        # Infer cache type from key prefix if not provided
        metric_type = cache_type or self._infer_cache_type(key)
        try:
            value = await self._redis.get(full_key)
            if value is not None:
                logger.debug(f"Cache hit for key: {key}")
                record_cache_hit(metric_type)
            else:
                record_cache_miss(metric_type)
            return value
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            record_cache_miss(metric_type)
            return None

    def _infer_cache_type(self, key: str) -> str:
        """Infer cache type from key prefix for metrics.

        Args:
            key: Cache key

        Returns:
            Inferred cache type string
        """
        if key.startswith("stats:events:"):
            return "event_stats"
        elif key.startswith("cameras:"):
            return "cameras"
        elif key.startswith("system:"):
            return "system"
        elif key.startswith("events:"):
            return "events"
        else:
            return "other"

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

    async def invalidate_pattern(
        self, pattern: str, reason: str = "manual", cache_type: str | None = None
    ) -> int:
        """Invalidate all cache keys matching a pattern.

        Uses SCAN to find matching keys (non-blocking).
        Records invalidation metrics for monitoring.

        Args:
            pattern: Glob-style pattern (e.g., "cameras:*")
                     Will be prefixed with 'cache:'
            reason: Reason for invalidation for metrics tracking
                    (e.g., "event_created", "camera_updated", "manual")
            cache_type: Optional cache type for metrics. If not provided,
                       will be inferred from the pattern prefix.

        Returns:
            Number of keys deleted
        """
        full_pattern = f"{CACHE_PREFIX}{pattern}"
        # Infer cache type from pattern if not provided
        metric_type = cache_type or self._infer_cache_type(pattern.rstrip("*"))
        try:
            client = self._redis._ensure_connected()
            keys_to_delete: list[str] = []

            # Use SCAN to find matching keys
            async for key in client.scan_iter(match=full_pattern, count=100):
                keys_to_delete.append(key)

            if keys_to_delete:
                deleted = await self._redis.delete(*keys_to_delete)
                logger.debug(f"Cache invalidated {deleted} keys matching pattern: {pattern}")
                # Record invalidation metric
                record_cache_invalidation(metric_type, reason)
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache pattern invalidation failed for {pattern}: {e}")
            return 0

    async def invalidate_event_stats(self, reason: str = "event_created") -> int:
        """Invalidate all event statistics cache entries.

        Should be called when events are created, updated, or deleted
        to ensure event stats endpoints return fresh data.

        Args:
            reason: Reason for invalidation (default: "event_created")

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern(
            "stats:events:*", reason=reason, cache_type="event_stats"
        )

    async def invalidate_events(self, reason: str = "event_created") -> int:
        """Invalidate all events cache entries.

        Should be called when events are created, updated, or deleted.

        Args:
            reason: Reason for invalidation (default: "event_created")

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("events:*", reason=reason, cache_type="events")

    async def invalidate_cameras(self, reason: str = "camera_updated") -> int:
        """Invalidate all cameras cache entries.

        Should be called when cameras are created, updated, or deleted.

        Args:
            reason: Reason for invalidation (default: "camera_updated")

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("cameras:*", reason=reason, cache_type="cameras")

    async def invalidate_system_status(self, reason: str = "status_changed") -> int:
        """Invalidate system status cache.

        Should be called when system status changes.

        Args:
            reason: Reason for invalidation (default: "status_changed")

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("system:*", reason=reason, cache_type="system")

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


# Create a singleton-like accessor for CacheKeys.PREFIX as a class attribute
# This is needed because the tests expect CacheKeys.PREFIX (not instance.PREFIX)
# NEM-1621: Redis key prefix namespacing for multi-instance/blue-green deployments
class _CacheKeysMeta(type):
    """Metaclass to make CacheKeys.PREFIX work as a class attribute."""

    @property
    def PREFIX(cls) -> str:
        """Get the global prefix from settings."""
        return _get_global_prefix()


# Cache keys for commonly accessed data
class CacheKeys(metaclass=_CacheKeysMeta):
    """Standard cache key generators for commonly cached data.

    All cache keys include a global prefix from settings (default: "hsi")
    to enable key isolation for multi-instance and blue-green deployments
    (NEM-1621).

    Key format: {PREFIX}:cache:{key_type}:{key_details}
    Queue format: {PREFIX}:queue:{queue_name}
    """

    @staticmethod
    def cameras_list() -> str:
        """Cache key for full camera list.

        Returns:
            Prefixed cache key: {PREFIX}:cache:cameras:list
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:cameras:list"

    @staticmethod
    def cameras_list_by_status(status: str | None) -> str:
        """Cache key for camera list filtered by status.

        Args:
            status: Camera status filter or None for all

        Returns:
            Prefixed cache key: {PREFIX}:cache:cameras:list:{status}
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:cameras:list:{status or 'all'}"

    @staticmethod
    def camera(camera_id: str) -> str:
        """Cache key for a single camera.

        Args:
            camera_id: Camera identifier

        Returns:
            Prefixed cache key: {PREFIX}:cache:cameras:{camera_id}
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:cameras:{camera_id}"

    @staticmethod
    def event_stats(start_date: str | None = None, end_date: str | None = None) -> str:
        """Cache key for event statistics.

        Args:
            start_date: Start date for stats range
            end_date: End date for stats range

        Returns:
            Prefixed cache key: {PREFIX}:cache:event_stats:{start}:{end}
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:event_stats:{start_date or 'none'}:{end_date or 'none'}"

    @staticmethod
    def system_status() -> str:
        """Cache key for system status.

        Returns:
            Prefixed cache key: {PREFIX}:cache:system:status
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:system:status"

    @staticmethod
    def queue(queue_name: str) -> str:
        """Cache key for queue operations.

        Args:
            queue_name: Name of the queue (e.g., "detection_queue")

        Returns:
            Prefixed queue key: {PREFIX}:queue:{queue_name}
        """
        prefix = _get_global_prefix()
        return f"{prefix}:queue:{queue_name}"


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


# =============================================================================
# Caching Decorator (NEM-1682)
# =============================================================================


def cached(
    cache_key: str | Callable[..., str],
    ttl: int = DEFAULT_TTL,
    cache_type: str = "other",
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for caching async function results.

    Provides a consistent caching pattern for async functions:
    1. Check cache for existing value (records hit/miss metrics)
    2. If cache miss, execute function and cache result
    3. Return cached or computed value

    Args:
        cache_key: Either a static cache key string, or a callable that takes
                   the decorated function's arguments and returns the cache key.
        ttl: Time to live in seconds (default: 5 minutes)
        cache_type: Cache type for metrics (e.g., "event_stats", "cameras")

    Returns:
        Decorated function with caching behavior

    Example:
        # Static cache key
        @cached("system:health", ttl=30)
        async def get_system_health():
            return await compute_health()

        # Dynamic cache key from arguments
        @cached(lambda camera_id: f"cameras:{camera_id}", ttl=60)
        async def get_camera(camera_id: str):
            return await db.get_camera(camera_id)

        # With keyword arguments
        @cached(
            lambda start_date=None, end_date=None: f"stats:{start_date}:{end_date}",
            ttl=300,
            cache_type="event_stats"
        )
        async def get_event_stats(start_date=None, end_date=None):
            return await compute_stats(start_date, end_date)
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Compute cache key
            key = cache_key(*args, **kwargs) if callable(cache_key) else cache_key

            try:
                cache = await get_cache_service()
                # Check cache first (this records hit/miss metrics)
                cached_value = await cache.get(key, cache_type=cache_type)
                if cached_value is not None:
                    return cached_value  # type: ignore[no-any-return]

                # Cache miss - execute function
                result = await func(*args, **kwargs)

                # Cache the result
                await cache.set(key, result, ttl=ttl)

                return result
            except Exception as e:
                # On cache failure, just execute function without caching
                logger.warning(
                    f"Cache operation failed for key {key}: {e}, falling back to uncached"
                )
                return await func(*args, **kwargs)

        return wrapper

    return decorator
