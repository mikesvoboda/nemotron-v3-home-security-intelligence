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
from typing import Any, ParamSpec, TypeVar, cast

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from backend.core.config import get_settings
from backend.core.constants import CacheInvalidationReason
from backend.core.logging import get_logger
from backend.core.metrics import record_cache_hit, record_cache_invalidation, record_cache_miss
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")

# Default TTL values in seconds
# Note: These are now configurable via settings (NEM-2519)
# Use get_settings().cache_default_ttl, cache_short_ttl, cache_long_ttl
# Legacy constants kept for backward compatibility
DEFAULT_TTL = 300  # 5 minutes (default, use settings.cache_default_ttl)
SHORT_TTL = 60  # 1 minute (default, use settings.cache_short_ttl)
LONG_TTL = 3600  # 1 hour (default, use settings.cache_long_ttl)


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
        except RedisConnectionError as e:
            logger.warning(
                f"Cache get failed for key {key}: Redis connection error: {e}",
                extra={"key": key, "error_type": "connection_error"},
            )
            record_cache_miss(metric_type)
            return None
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache get failed for key {key}: Redis timeout: {e}",
                extra={"key": key, "error_type": "timeout_error"},
            )
            record_cache_miss(metric_type)
            return None
        except RedisError as e:
            logger.warning(
                f"Cache get failed for key {key}: Redis error: {e}",
                extra={"key": key, "error_type": "redis_error"},
            )
            record_cache_miss(metric_type)
            return None

    def _infer_cache_type(self, key: str) -> str:  # noqa: PLR0911
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
        elif key.startswith("alerts:"):
            return "alerts"
        elif key.startswith("detections:"):
            return "detections"
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
        except RedisConnectionError as e:
            logger.warning(
                f"Cache set failed for key {key}: Redis connection error: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "connection_error"},
            )
            return False
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache set failed for key {key}: Redis timeout: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "timeout_error"},
            )
            return False
        except RedisError as e:
            logger.warning(
                f"Cache set failed for key {key}: Redis error: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "redis_error"},
            )
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

    # ==========================================================================
    # Stale-While-Revalidate (SWR) Pattern (NEM-3367)
    # ==========================================================================

    async def get_or_set_swr(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int = DEFAULT_TTL,
        stale_ttl: int | None = None,
        cache_type: str | None = None,
    ) -> Any:
        """Get value from cache with Stale-While-Revalidate pattern.

        Implements the SWR pattern for zero-latency cache refresh:
        1. If data is fresh (within TTL), return immediately
        2. If data is stale (beyond TTL but within stale_ttl), return immediately
           AND trigger background refresh
        3. If data is missing or expired, compute and cache synchronously

        This eliminates cache stampede and ensures users never wait for cache refresh.

        Args:
            key: Cache key (will be prefixed with 'cache:')
            factory: Callable that returns the value if not cached.
            ttl: Time to live in seconds (default: 5 minutes).
            stale_ttl: Additional time in seconds after TTL that stale data
                      can be served while refreshing. If None, uses settings.
            cache_type: Optional cache type for metrics.

        Returns:
            Cached or computed value
        """
        import time

        settings = get_settings()
        if stale_ttl is None:
            stale_ttl = settings.cache_swr_stale_ttl

        metric_type = cache_type or self._infer_cache_type(key)
        full_key = f"{CACHE_PREFIX}{key}"
        freshness_key = f"{full_key}:fresh_until"

        try:
            # Try to get cached value and freshness timestamp
            cached_value = await self.get(key, cache_type=cache_type)

            if cached_value is not None:
                # Check if data is still fresh
                fresh_until_str = await self._redis.get(freshness_key)
                now = time.time()

                if fresh_until_str:
                    fresh_until = float(fresh_until_str)
                    if now < fresh_until:
                        # Data is fresh - return immediately
                        return cached_value
                    else:
                        # Data is stale - return and refresh in background
                        from backend.core.metrics import record_cache_stale_hit

                        record_cache_stale_hit(metric_type)
                        logger.debug(
                            f"SWR: Serving stale data for key: {key}, triggering background refresh"
                        )
                        asyncio.create_task(
                            self._background_refresh(key, factory, ttl, stale_ttl, metric_type)
                        )
                        return cached_value
                else:
                    # No freshness marker but value exists - treat as stale
                    from backend.core.metrics import record_cache_stale_hit

                    record_cache_stale_hit(metric_type)
                    asyncio.create_task(
                        self._background_refresh(key, factory, ttl, stale_ttl, metric_type)
                    )
                    return cached_value

            # Cache miss - compute synchronously
            logger.debug(f"SWR: Cache miss for key: {key}, computing value")
            return await self._fetch_and_cache_swr(key, factory, ttl, stale_ttl)

        except (RedisConnectionError, RedisTimeoutError, RedisError) as e:
            logger.warning(
                f"SWR cache operation failed for key {key}: {e}, "
                "falling back to direct computation",
                extra={"key": key, "error": str(e)},
            )
            # Fall back to direct computation
            result = factory()
            if asyncio.iscoroutine(result):
                result = await result
            return result

    async def _fetch_and_cache_swr(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int,
        stale_ttl: int,
    ) -> Any:
        """Fetch data using factory and cache with SWR metadata."""
        import time

        result = factory()
        if asyncio.iscoroutine(result):
            result = await result

        full_key = f"{CACHE_PREFIX}{key}"
        freshness_key = f"{full_key}:fresh_until"

        # Set the value with total TTL (fresh + stale)
        total_ttl = ttl + stale_ttl
        await self.set(key, result, ttl=total_ttl)

        # Set the freshness marker
        fresh_until = time.time() + ttl
        try:
            await self._redis.set(freshness_key, str(fresh_until), expire=total_ttl)
        except Exception as e:
            logger.warning(f"Failed to set freshness marker for {key}: {e}")

        return result

    async def _background_refresh(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int,
        stale_ttl: int,
        cache_type: str,
    ) -> None:
        """Refresh cache in background (SWR pattern)."""
        from backend.core.metrics import record_cache_background_refresh

        full_key = f"{CACHE_PREFIX}{key}"
        lock_key = f"{full_key}:refreshing"

        try:
            # Use a simple lock to prevent multiple concurrent refreshes
            lock_acquired = await self._redis.set(lock_key, "1", expire=60, nx=True)

            if not lock_acquired:
                record_cache_background_refresh(cache_type, success=False)
                logger.debug(f"SWR: Skipping refresh for {key}, already in progress")
                return

            logger.debug(f"SWR: Starting background refresh for key: {key}")
            await self._fetch_and_cache_swr(key, factory, ttl, stale_ttl)
            record_cache_background_refresh(cache_type, success=True)
            logger.debug(f"SWR: Background refresh completed for key: {key}")

        except Exception as e:
            record_cache_background_refresh(cache_type, success=False)
            logger.error(
                f"SWR: Background refresh failed for key {key}: {e}",
                extra={"key": key, "error": str(e)},
            )
        finally:
            # Release the lock
            try:
                await self._redis.delete(lock_key)
            except Exception:  # noqa: S110
                pass  # Ignore errors during lock cleanup - intentionally silent

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
        except RedisConnectionError as e:
            logger.warning(
                f"Cache invalidation failed for key {key}: Redis connection error: {e}",
                extra={"key": key, "error_type": "connection_error"},
            )
            return False
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache invalidation failed for key {key}: Redis timeout: {e}",
                extra={"key": key, "error_type": "timeout_error"},
            )
            return False
        except RedisError as e:
            logger.warning(
                f"Cache invalidation failed for key {key}: Redis error: {e}",
                extra={"key": key, "error_type": "redis_error"},
            )
            return False

    async def invalidate_pattern(
        self,
        pattern: str,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.MANUAL,
        cache_type: str | None = None,
    ) -> int:
        """Invalidate all cache keys matching a pattern.

        Uses SCAN to find matching keys (non-blocking).
        Records invalidation metrics for monitoring.

        Args:
            pattern: Glob-style pattern (e.g., "cameras:*")
                     Will be prefixed with 'cache:'
            reason: Reason for invalidation for metrics tracking.
                    Use CacheInvalidationReason enum constants
                    (e.g., CacheInvalidationReason.EVENT_CREATED).
            cache_type: Optional cache type for metrics. If not provided,
                       will be inferred from the pattern prefix.

        Returns:
            Number of keys deleted
        """
        full_pattern = f"{CACHE_PREFIX}{pattern}"
        # Infer cache type from pattern if not provided
        metric_type = cache_type or self._infer_cache_type(pattern.rstrip("*"))
        # Convert enum to string for metrics (str(enum) returns value)
        reason_str = str(reason)
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
                record_cache_invalidation(metric_type, reason_str)
                return deleted
            return 0
        except RedisConnectionError as e:
            logger.warning(
                f"Cache pattern invalidation failed for {pattern}: Redis connection error: {e}",
                extra={"pattern": pattern, "reason": reason_str, "error_type": "connection_error"},
            )
            return 0
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache pattern invalidation failed for {pattern}: Redis timeout: {e}",
                extra={"pattern": pattern, "reason": reason_str, "error_type": "timeout_error"},
            )
            return 0
        except RedisError as e:
            logger.warning(
                f"Cache pattern invalidation failed for {pattern}: Redis error: {e}",
                extra={"pattern": pattern, "reason": reason_str, "error_type": "redis_error"},
            )
            return 0

    async def invalidate_event_stats(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.EVENT_CREATED,
    ) -> int:
        """Invalidate all event statistics cache entries.

        Should be called when events are created, updated, or deleted
        to ensure event stats endpoints return fresh data.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.EVENT_CREATED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern(
            "stats:events:*", reason=reason, cache_type="event_stats"
        )

    async def invalidate_events(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.EVENT_CREATED,
    ) -> int:
        """Invalidate all events cache entries.

        Should be called when events are created, updated, or deleted.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.EVENT_CREATED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("events:*", reason=reason, cache_type="events")

    async def invalidate_cameras(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.CAMERA_UPDATED,
    ) -> int:
        """Invalidate all cameras cache entries.

        Should be called when cameras are created, updated, or deleted.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.CAMERA_UPDATED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("cameras:*", reason=reason, cache_type="cameras")

    async def invalidate_system_status(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.STATUS_CHANGED,
    ) -> int:
        """Invalidate system status cache.

        Should be called when system status changes.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.STATUS_CHANGED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("system:*", reason=reason, cache_type="system")

    async def invalidate_alerts(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.ALERT_RULE_CREATED,
    ) -> int:
        """Invalidate all alert rules cache entries.

        Should be called when alert rules are created, updated, or deleted
        to ensure alert rule endpoints return fresh data.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.ALERT_RULE_CREATED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("alerts:*", reason=reason, cache_type="alerts")

    async def invalidate_detections(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.DETECTION_CREATED,
    ) -> int:
        """Invalidate all detections cache entries.

        Should be called when detections are created, updated, or deleted
        to ensure detection endpoints return fresh data.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.DETECTION_CREATED)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("detections:*", reason=reason, cache_type="detections")

    async def invalidate_summaries(
        self,
        reason: str | CacheInvalidationReason = CacheInvalidationReason.MANUAL,
    ) -> int:
        """Invalidate all summaries cache entries.

        Should be called when new summaries are generated to ensure
        dashboard endpoints return fresh data.

        Args:
            reason: Reason for invalidation. Use CacheInvalidationReason enum.
                   (default: CacheInvalidationReason.MANUAL)

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("summaries:*", reason=reason, cache_type="summaries")

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
        except RedisConnectionError as e:
            logger.warning(
                f"Cache exists check failed for key {key}: Redis connection error: {e}",
                extra={"key": key, "error_type": "connection_error"},
            )
            return False
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache exists check failed for key {key}: Redis timeout: {e}",
                extra={"key": key, "error_type": "timeout_error"},
            )
            return False
        except RedisError as e:
            logger.warning(
                f"Cache exists check failed for key {key}: Redis error: {e}",
                extra={"key": key, "error_type": "redis_error"},
            )
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
        except RedisConnectionError as e:
            logger.warning(
                f"Cache refresh failed for key {key}: Redis connection error: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "connection_error"},
            )
            return False
        except RedisTimeoutError as e:
            logger.warning(
                f"Cache refresh failed for key {key}: Redis timeout: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "timeout_error"},
            )
            return False
        except RedisError as e:
            logger.warning(
                f"Cache refresh failed for key {key}: Redis error: {e}",
                extra={"key": key, "ttl": ttl, "error_type": "redis_error"},
            )
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
    def event_stats(
        start_date: str | None = None,
        end_date: str | None = None,
        camera_id: str | None = None,
    ) -> str:
        """Cache key for event statistics.

        Args:
            start_date: Start date for stats range
            end_date: End date for stats range
            camera_id: Optional camera ID filter

        Returns:
            Prefixed cache key: {PREFIX}:cache:event_stats:{start}:{end}:{camera_id}
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:event_stats:{start_date or 'none'}:{end_date or 'none'}:{camera_id or 'all'}"

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

    @staticmethod
    def summaries_latest() -> str:
        """Cache key for latest summaries (both hourly and daily).

        Returns:
            Prefixed cache key: {PREFIX}:cache:summaries:latest
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:summaries:latest"

    @staticmethod
    def summaries_hourly() -> str:
        """Cache key for latest hourly summary.

        Returns:
            Prefixed cache key: {PREFIX}:cache:summaries:hourly
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:summaries:hourly"

    @staticmethod
    def summaries_daily() -> str:
        """Cache key for latest daily summary.

        Returns:
            Prefixed cache key: {PREFIX}:cache:summaries:daily
        """
        prefix = _get_global_prefix()
        return f"{prefix}:cache:summaries:daily"


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
            except RedisConnectionError as e:
                # On Redis connection failure, execute function without caching
                logger.warning(
                    f"Cache operation failed for key {key}: Redis connection error: {e}, "
                    "falling back to uncached",
                    extra={"key": key, "cache_type": cache_type, "error_type": "connection_error"},
                )
                return await func(*args, **kwargs)
            except RedisTimeoutError as e:
                # On Redis timeout, execute function without caching
                logger.warning(
                    f"Cache operation failed for key {key}: Redis timeout: {e}, "
                    "falling back to uncached",
                    extra={"key": key, "cache_type": cache_type, "error_type": "timeout_error"},
                )
                return await func(*args, **kwargs)
            except RedisError as e:
                # On Redis error, execute function without caching
                logger.warning(
                    f"Cache operation failed for key {key}: Redis error: {e}, "
                    "falling back to uncached",
                    extra={"key": key, "cache_type": cache_type, "error_type": "redis_error"},
                )
                return await func(*args, **kwargs)
            except RuntimeError as e:
                # Handle cache service initialization errors (e.g., Redis not connected)
                logger.warning(
                    f"Cache service unavailable for key {key}: {e}, falling back to uncached",
                    extra={"key": key, "cache_type": cache_type, "error_type": "runtime_error"},
                )
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# SWR Caching Decorator (NEM-3367)
# =============================================================================


def cached_swr(
    cache_key: str | Callable[..., str],
    ttl: int = DEFAULT_TTL,
    stale_ttl: int | None = None,
    cache_type: str = "other",
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for caching with Stale-While-Revalidate pattern.

    Provides zero-latency cache refresh:
    1. Fresh data is returned immediately
    2. Stale data is returned immediately AND triggers background refresh
    3. Missing data is computed synchronously

    Args:
        cache_key: Static cache key string, or a callable returning the cache key.
        ttl: Time to live in seconds (default: 5 minutes).
        stale_ttl: Additional stale time in seconds. If None, uses settings.
        cache_type: Cache type for metrics.

    Returns:
        Decorated function with SWR caching behavior

    Example:
        @cached_swr("dashboard:stats", ttl=60, stale_ttl=30, cache_type="system")
        async def get_dashboard_stats():
            return await compute_heavy_stats()
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = cache_key(*args, **kwargs) if callable(cache_key) else cache_key

            settings = get_settings()
            if not settings.cache_swr_enabled:
                # Fall back to regular caching when SWR disabled
                try:
                    cache = await get_cache_service()
                    cached_value = await cache.get(key, cache_type=cache_type)
                    if cached_value is not None:
                        return cast("T", cached_value)

                    result = await func(*args, **kwargs)
                    await cache.set(key, result, ttl=ttl)
                    return result
                except (RedisConnectionError, RedisTimeoutError, RedisError, RuntimeError):
                    return await func(*args, **kwargs)

            try:
                cache = await get_cache_service()

                async def factory() -> T:
                    return await func(*args, **kwargs)

                return cast(
                    "T",
                    await cache.get_or_set_swr(
                        key=key,
                        factory=factory,
                        ttl=ttl,
                        stale_ttl=stale_ttl,
                        cache_type=cache_type,
                    ),
                )
            except (RedisConnectionError, RedisTimeoutError, RedisError, RuntimeError) as e:
                logger.warning(
                    f"SWR cache failed for key {key}: {e}, falling back to uncached",
                    extra={"key": key, "cache_type": cache_type},
                )
                return await func(*args, **kwargs)

        return wrapper

    return decorator
