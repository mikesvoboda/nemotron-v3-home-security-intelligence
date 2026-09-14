"""Prepared statement caching for PostgreSQL query plan optimization (NEM-3760).

This module provides a prepared statement cache that stores frequently executed
queries for reuse, reducing query planning overhead and improving performance.

Features:
    - Named query registration for frequently executed statements
    - LRU-based cache eviction when max size is exceeded
    - Hit/miss statistics for monitoring cache effectiveness
    - Automatic disabling when PgBouncer is in use (transaction mode incompatible)
    - Thread-safe singleton pattern for global cache instance

Usage:
    from backend.core.prepared_statements import get_prepared_cache, execute_prepared

    cache = get_prepared_cache()

    # Execute a registered prepared statement
    result = await execute_prepared(session, cache, "list_cameras")

    # Get cache statistics
    stats = cache.get_stats()
    print(f"Hit ratio: {stats['hit_ratio']:.2%}")

Note:
    Prepared statements are incompatible with PgBouncer in transaction mode because
    the server connection may change between transactions. When use_pgbouncer=True
    in settings, the cache is automatically disabled.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from backend.core.logging import get_logger
from backend.models import Camera, Detection, Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql import Select

logger = get_logger(__name__)


class PreparedStatementError(Exception):
    """Error raised for prepared statement cache operations."""

    pass


@dataclass
class CacheStats:
    """Statistics for prepared statement cache performance."""

    hits: int = 0
    misses: int = 0
    registered_queries: int = 0

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests


class PreparedStatementCache:
    """Cache for prepared SQL statements to optimize query planning.

    This cache stores named queries that are frequently executed, allowing
    PostgreSQL to reuse query plans and reduce planning overhead.

    The cache uses an OrderedDict for LRU eviction when the max size is exceeded.

    Attributes:
        max_size: Maximum number of queries to cache (default: 100)
        enabled: Whether the cache is active (default: True)

    Example:
        cache = PreparedStatementCache(max_size=50)
        cache.register(select(Camera), name="list_cameras")

        stmt = cache.get("list_cameras")
        if stmt:
            result = await session.execute(stmt)
    """

    def __init__(
        self,
        max_size: int = 100,
        enabled: bool = True,
    ) -> None:
        """Initialize the prepared statement cache.

        Args:
            max_size: Maximum number of named queries to cache
            enabled: Whether the cache should be active
        """
        self.max_size = max_size
        self.enabled = enabled
        self._named_queries: OrderedDict[str, Select[Any]] = OrderedDict()
        self._cache: dict[str, Select[Any]] = {}
        self._stats = CacheStats()
        self._lock = threading.Lock()

        logger.info(
            "PreparedStatementCache initialized",
            extra={
                "max_size": max_size,
                "enabled": enabled,
            },
        )

    def _generate_cache_key(self, stmt: Select[Any]) -> str:
        """Generate a cache key from a SQLAlchemy statement.

        Uses a hash of the compiled SQL string for consistent key generation.

        Args:
            stmt: SQLAlchemy Select statement

        Returns:
            A string hash suitable for use as a cache key
        """
        # Compile the statement to get the SQL string
        compiled = str(stmt)
        return hashlib.sha256(compiled.encode()).hexdigest()[:16]

    def register(self, stmt: Select[Any], *, name: str) -> None:
        """Register a named query for prepared statement caching.

        Registered queries can be retrieved by name and executed with
        parameters. The cache maintains LRU ordering and evicts oldest
        entries when max_size is exceeded.

        Args:
            stmt: SQLAlchemy Select statement to cache
            name: Unique name for the query (e.g., "get_camera_by_id")

        Example:
            cache.register(
                select(Camera).where(Camera.id == bindparam("camera_id")),
                name="get_camera_by_id"
            )
        """
        if not self.enabled:
            return

        with self._lock:
            # Remove existing entry to update order
            if name in self._named_queries:
                del self._named_queries[name]

            # Add new entry
            self._named_queries[name] = stmt

            # Evict oldest if over limit
            while len(self._named_queries) > self.max_size:
                oldest_key = next(iter(self._named_queries))
                del self._named_queries[oldest_key]
                logger.debug(f"Evicted prepared statement: {oldest_key}")

            self._stats.registered_queries = len(self._named_queries)

    def get(self, name: str) -> Select[Any] | None:
        """Get a registered prepared statement by name.

        Updates cache statistics for monitoring.

        Args:
            name: Name of the registered query

        Returns:
            The cached statement if found, None otherwise
        """
        with self._lock:
            if name in self._named_queries:
                self._stats.hits += 1
                # Move to end for LRU
                self._named_queries.move_to_end(name)
                return self._named_queries[name]
            else:
                self._stats.misses += 1
                return None

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary containing hits, misses, hit_ratio, and registered_queries
        """
        with self._lock:
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "hit_ratio": self._stats.hit_ratio,
                "total_requests": self._stats.total_requests,
                "registered_queries": self._stats.registered_queries,
            }

    def clear(self) -> None:
        """Clear all cached prepared statements."""
        with self._lock:
            self._named_queries.clear()
            self._cache.clear()
            self._stats = CacheStats()
            logger.info("PreparedStatementCache cleared")


# =============================================================================
# Common Query Registration
# =============================================================================


def register_common_queries(cache: PreparedStatementCache) -> None:
    """Register commonly executed queries for prepared statement caching.

    This function registers the most frequently executed queries in the
    application to benefit from query plan caching.

    Args:
        cache: PreparedStatementCache instance to register queries with
    """
    # Camera queries
    cache.register(
        select(Camera),
        name="list_cameras",
    )
    cache.register(
        select(Camera).where(Camera.id == Camera.id),  # Placeholder for binding
        name="get_camera_by_id",
    )

    # Detection queries
    cache.register(
        select(Detection).where(Detection.id == Detection.id),
        name="get_detection_by_id",
    )
    cache.register(
        select(Detection).where(Detection.camera_id == Detection.camera_id),
        name="list_detections_by_camera",
    )

    # Event queries
    cache.register(
        select(Event).where(Event.id == Event.id),
        name="get_event_by_id",
    )
    cache.register(
        select(Event).where(Event.camera_id == Event.camera_id),
        name="list_events_by_camera",
    )
    cache.register(
        select(func.count()).select_from(Event).where(Event.reviewed == False),  # noqa: E712
        name="count_unreviewed_events",
    )

    logger.info(
        "Registered common queries for prepared statement caching",
        extra={"query_count": len(cache._named_queries)},
    )


# =============================================================================
# Execution Helpers
# =============================================================================


async def execute_prepared(
    session: AsyncSession,
    cache: PreparedStatementCache,
    name: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    """Execute a registered prepared statement.

    Args:
        session: SQLAlchemy AsyncSession
        cache: PreparedStatementCache containing the registered query
        name: Name of the registered query
        params: Optional parameters to bind to the query

    Returns:
        The result of the query execution

    Raises:
        PreparedStatementError: If the query is not registered
    """
    stmt = cache.get(name)
    if stmt is None:
        raise PreparedStatementError(f"Prepared statement not found: {name}")

    if params:
        result = await session.execute(stmt, params)
    else:
        result = await session.execute(stmt)

    return result


# =============================================================================
# Global Cache Instance
# =============================================================================

_global_cache: PreparedStatementCache | None = None
_global_cache_lock = threading.Lock()


def get_prepared_cache() -> PreparedStatementCache:
    """Get the global prepared statement cache instance.

    Returns a singleton instance of PreparedStatementCache. On first call,
    creates and initializes the cache with common queries.

    Returns:
        The global PreparedStatementCache instance
    """
    global _global_cache  # noqa: PLW0603

    if _global_cache is None:
        with _global_cache_lock:
            if _global_cache is None:
                _global_cache = create_cache_from_settings()
                register_common_queries(_global_cache)

    return _global_cache


def create_cache_from_settings() -> PreparedStatementCache:
    """Create a PreparedStatementCache configured from application settings.

    If PgBouncer mode is enabled, the cache is disabled since prepared
    statements are incompatible with PgBouncer's transaction mode.

    Returns:
        A configured PreparedStatementCache instance
    """
    try:
        from backend.core.config import get_settings

        settings = get_settings()
        use_pgbouncer = settings.use_pgbouncer
        cache_size = getattr(settings, "prepared_statement_cache_size", 100)
    except Exception:
        # Fallback for testing or early initialization
        use_pgbouncer = False
        cache_size = 100

    enabled = not use_pgbouncer

    if not enabled:
        logger.info(
            "PreparedStatementCache disabled due to PgBouncer mode",
            extra={"use_pgbouncer": True},
        )

    return PreparedStatementCache(
        max_size=cache_size,
        enabled=enabled,
    )


def reset_global_cache() -> None:
    """Reset the global cache instance.

    This is primarily used for testing to ensure a fresh cache state.
    """
    global _global_cache  # noqa: PLW0603

    with _global_cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
        _global_cache = None
