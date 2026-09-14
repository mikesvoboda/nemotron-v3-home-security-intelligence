"""Read-through cache service for automatic cache population on misses.

This service implements the read-through caching pattern (NEM-3765) where cache
misses automatically trigger fetching from the underlying data source (database).

Features:
- Automatic cache population on miss
- Configurable TTL per cache type
- Cache stampede protection with distributed locking
- Metrics for cache hit/miss tracking
- Support for async data loaders

Read-Through vs Cache-Aside:
- Cache-Aside: Application checks cache, fetches from DB on miss, updates cache
- Read-Through: Cache layer handles miss by calling configured loader automatically

Usage:
    # Define a loader function
    async def load_camera(camera_id: str) -> dict:
        async with get_session() as session:
            camera = await session.get(Camera, camera_id)
            return camera.to_dict() if camera else None

    # Create read-through cache
    cache = ReadThroughCache(
        cache_prefix="cameras",
        loader=load_camera,
        ttl=300,
    )

    # Get data (automatically populates cache on miss)
    camera = await cache.get("cam_001")
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import record_cache_hit, record_cache_miss
from backend.core.redis import RedisClient, init_redis

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class ReadThroughResult(Generic[T]):
    """Result of a read-through cache operation."""

    value: T | None
    from_cache: bool
    cache_key: str
    ttl_remaining: int | None = None


class ReadThroughCache(Generic[T]):
    """Read-through cache with automatic population on cache miss.

    This cache implementation automatically calls the configured loader function
    when a cache miss occurs, stores the result in Redis, and returns it to the
    caller. This pattern simplifies application code by centralizing cache
    population logic.

    The cache includes stampede protection using a distributed lock to prevent
    multiple concurrent requests from all triggering the loader function
    simultaneously (thundering herd problem).
    """

    def __init__(
        self,
        cache_prefix: str,
        loader: Callable[[str], Awaitable[T | None]],
        ttl: int | None = None,
        stampede_protection: bool = True,
        lock_timeout: int = 30,
        cache_type: str = "other",
    ):
        """Initialize read-through cache.

        Args:
            cache_prefix: Prefix for cache keys (e.g., "cameras", "events")
            loader: Async function that loads data given a key (returns None if not found)
            ttl: Cache TTL in seconds (uses settings.cache_default_ttl if None)
            stampede_protection: Enable distributed locking to prevent thundering herd
            lock_timeout: Lock timeout in seconds for stampede protection
            cache_type: Cache type for metrics tracking
        """
        self._prefix = cache_prefix
        self._loader = loader
        self._ttl = ttl
        self._stampede_protection = stampede_protection
        self._lock_timeout = lock_timeout
        self._cache_type = cache_type
        self._redis: RedisClient | None = None

    def _make_cache_key(self, key: str) -> str:
        """Create full cache key with prefix."""
        settings = get_settings()
        return f"{settings.redis_key_prefix}:cache:{self._prefix}:{key}"

    def _make_lock_key(self, key: str) -> str:
        """Create lock key for stampede protection."""
        return f"{self._make_cache_key(key)}:loading"

    async def _get_redis(self) -> RedisClient:
        """Get or initialize Redis client."""
        if self._redis is None:
            self._redis = await init_redis()
        return self._redis

    async def get(self, key: str) -> ReadThroughResult[T]:
        """Get value from cache, loading from source on miss.

        This method implements the read-through pattern:
        1. Check cache for value
        2. If hit, return cached value
        3. If miss, acquire lock (if stampede protection enabled)
        4. Double-check cache (another request may have populated it)
        5. Call loader to fetch from source
        6. Cache the result
        7. Return the value

        Args:
            key: Key to retrieve (will be prefixed)

        Returns:
            ReadThroughResult with value and metadata
        """
        settings = get_settings()
        ttl = self._ttl or settings.cache_default_ttl
        cache_key = self._make_cache_key(key)

        try:
            redis = await self._get_redis()

            # Step 1: Check cache
            cached_value = await redis.get(cache_key)
            if cached_value is not None:
                record_cache_hit(self._cache_type)
                logger.debug(f"Read-through cache hit: {cache_key}")
                return ReadThroughResult(
                    value=cached_value,
                    from_cache=True,
                    cache_key=cache_key,
                )

            # Cache miss - need to load from source
            record_cache_miss(self._cache_type)
            logger.debug(f"Read-through cache miss: {cache_key}")

            # Step 2: Stampede protection with distributed lock
            if self._stampede_protection:
                return await self._load_with_lock(key, cache_key, ttl, redis)
            else:
                return await self._load_without_lock(key, cache_key, ttl, redis)

        except (RedisConnectionError, RedisTimeoutError, RedisError) as e:
            logger.warning(
                f"Read-through cache error for {cache_key}: {e}, falling back to loader",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            # Fall back to direct load without caching
            value = await self._loader(key)
            return ReadThroughResult(
                value=value,
                from_cache=False,
                cache_key=cache_key,
            )

    async def _load_with_lock(
        self,
        key: str,
        cache_key: str,
        ttl: int,
        redis: RedisClient,
    ) -> ReadThroughResult[T]:
        """Load value with distributed lock for stampede protection."""
        lock_key = self._make_lock_key(key)

        # Try to acquire lock (SET NX with expiration)
        lock_acquired = await redis.set(lock_key, "1", expire=self._lock_timeout, nx=True)

        if not lock_acquired:
            # Another request is loading - wait and check cache
            logger.debug(f"Read-through waiting for lock: {lock_key}")
            return await self._wait_for_cache(key, cache_key, ttl, redis)

        try:
            # Double-check cache after acquiring lock
            cached_value = await redis.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Read-through cache populated while waiting: {cache_key}")
                return ReadThroughResult(
                    value=cached_value,
                    from_cache=True,
                    cache_key=cache_key,
                )

            # Load from source
            value = await self._loader(key)

            if value is not None:
                # Cache the value
                await redis.set(cache_key, value, expire=ttl)
                logger.debug(f"Read-through cached value: {cache_key}")

            return ReadThroughResult(
                value=value,
                from_cache=False,
                cache_key=cache_key,
            )

        finally:
            # Release lock
            await redis.delete(lock_key)

    async def _load_without_lock(
        self,
        key: str,
        cache_key: str,
        ttl: int,
        redis: RedisClient,
    ) -> ReadThroughResult[T]:
        """Load value without stampede protection."""
        value = await self._loader(key)

        if value is not None:
            await redis.set(cache_key, value, expire=ttl)
            logger.debug(f"Read-through cached value: {cache_key}")

        return ReadThroughResult(
            value=value,
            from_cache=False,
            cache_key=cache_key,
        )

    async def _wait_for_cache(
        self,
        key: str,
        cache_key: str,
        ttl: int,
        redis: RedisClient,
        max_wait: float = 5.0,
        poll_interval: float = 0.1,
    ) -> ReadThroughResult[T]:
        """Wait for another request to populate the cache."""
        import time

        start_time = time.monotonic()

        while time.monotonic() - start_time < max_wait:
            # Check if cache was populated
            cached_value = await redis.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Read-through cache populated by another request: {cache_key}")
                return ReadThroughResult(
                    value=cached_value,
                    from_cache=True,
                    cache_key=cache_key,
                )

            await asyncio.sleep(poll_interval)

        # Timeout - load ourselves
        logger.debug(f"Read-through wait timeout, loading: {cache_key}")
        return await self._load_without_lock(key, cache_key, ttl, redis)

    async def invalidate(self, key: str) -> bool:
        """Invalidate a cached value.

        Args:
            key: Key to invalidate

        Returns:
            True if key was deleted, False otherwise
        """
        try:
            redis = await self._get_redis()
            cache_key = self._make_cache_key(key)
            deleted = await redis.delete(cache_key)
            if deleted > 0:
                logger.debug(f"Read-through cache invalidated: {cache_key}")
            return deleted > 0
        except (RedisConnectionError, RedisTimeoutError, RedisError) as e:
            logger.warning(f"Read-through cache invalidation failed: {e}")
            return False

    async def refresh(self, key: str) -> ReadThroughResult[T]:
        """Force refresh a cached value by invalidating and re-loading.

        Args:
            key: Key to refresh

        Returns:
            ReadThroughResult with fresh value
        """
        await self.invalidate(key)
        return await self.get(key)


# =============================================================================
# Pre-configured Read-Through Caches
# =============================================================================


async def _load_camera(camera_id: str) -> dict[str, Any] | None:
    """Load a camera from the database."""
    from sqlalchemy import select

    from backend.core.database import get_session
    from backend.models.camera import Camera

    async with get_session() as session:
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        if camera:
            return {
                "id": camera.id,
                "name": camera.name,
                "folder_path": camera.folder_path,
                "status": camera.status,
                "created_at": camera.created_at.isoformat() if camera.created_at else None,
            }
        return None


async def _load_event(event_id: str) -> dict[str, Any] | None:
    """Load an event from the database."""
    from uuid import UUID

    from sqlalchemy import select

    from backend.core.database import get_session
    from backend.models.event import Event

    async with get_session() as session:
        try:
            event_uuid = UUID(event_id)
        except ValueError:
            return None

        result = await session.execute(select(Event).where(Event.id == event_uuid))
        event = result.scalar_one_or_none()
        if event:
            return {
                "id": str(event.id),
                "camera_id": event.camera_id,
                "risk_score": event.risk_score,
                "risk_level": event.risk_level,
                "summary": event.summary,
                "reviewed": event.reviewed,
                "started_at": event.started_at.isoformat() if event.started_at else None,
            }
        return None


async def _load_alert_rule(alert_id: str) -> dict[str, Any] | None:
    """Load an alert rule from the database."""
    from uuid import UUID

    from sqlalchemy import select

    from backend.core.database import get_session
    from backend.models.alert import AlertRule

    async with get_session() as session:
        try:
            alert_uuid = UUID(alert_id)
        except ValueError:
            return None

        result = await session.execute(select(AlertRule).where(AlertRule.id == alert_uuid))
        alert = result.scalar_one_or_none()
        if alert:
            return {
                "id": str(alert.id),
                "name": alert.name,
                "severity": alert.severity.value if alert.severity else None,
                "enabled": alert.enabled,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }
        return None


# Singleton instances for common read-through caches
_camera_cache: ReadThroughCache[dict[str, Any]] | None = None
_event_cache: ReadThroughCache[dict[str, Any]] | None = None
_alert_cache: ReadThroughCache[dict[str, Any]] | None = None


async def get_camera_read_through_cache() -> ReadThroughCache[dict[str, Any]]:
    """Get the camera read-through cache singleton."""
    global _camera_cache  # noqa: PLW0603
    if _camera_cache is None:
        settings = get_settings()
        _camera_cache = ReadThroughCache(
            cache_prefix="cameras",
            loader=_load_camera,
            ttl=settings.cache_default_ttl,
            cache_type="cameras",
        )
    return _camera_cache


async def get_event_read_through_cache() -> ReadThroughCache[dict[str, Any]]:
    """Get the event read-through cache singleton."""
    global _event_cache  # noqa: PLW0603
    if _event_cache is None:
        settings = get_settings()
        _event_cache = ReadThroughCache(
            cache_prefix="events",
            loader=_load_event,
            ttl=settings.cache_short_ttl,  # Events change more frequently
            cache_type="events",
        )
    return _event_cache


async def get_alert_read_through_cache() -> ReadThroughCache[dict[str, Any]]:
    """Get the alert rule read-through cache singleton."""
    global _alert_cache  # noqa: PLW0603
    if _alert_cache is None:
        settings = get_settings()
        _alert_cache = ReadThroughCache(
            cache_prefix="alerts",
            loader=_load_alert_rule,
            ttl=settings.cache_default_ttl,
            cache_type="alerts",
        )
    return _alert_cache


async def reset_read_through_caches() -> None:
    """Reset all read-through cache singletons (for testing)."""
    global _camera_cache, _event_cache, _alert_cache  # noqa: PLW0603
    _camera_cache = None
    _event_cache = None
    _alert_cache = None
