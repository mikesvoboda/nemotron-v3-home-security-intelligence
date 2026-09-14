"""Cache warming service for pre-populating frequently accessed cache keys on startup.

This service implements cache warming (NEM-3762) to reduce cold-start latency by
pre-populating common cache keys during application startup.

Features:
- Pre-warm camera list cache (most frequently accessed)
- Pre-warm system status cache
- Pre-warm event statistics cache
- Configurable warm-up strategies (eager, lazy, scheduled)
- Graceful failure handling (warming failures don't block startup)

Usage:
    # During application startup
    cache_warmer = CacheWarmer()
    await cache_warmer.warm_all()

    # Selective warming
    await cache_warmer.warm_cameras()
    await cache_warmer.warm_system_status()
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


class WarmingStrategy(str, Enum):
    """Cache warming strategies."""

    EAGER = "eager"  # Warm all caches immediately on startup
    LAZY = "lazy"  # Warm caches on first access (existing behavior)
    PARALLEL = "parallel"  # Warm caches in parallel for faster startup
    SEQUENTIAL = "sequential"  # Warm caches one by one (lower resource usage)


@dataclass
class WarmingResult:
    """Result of a cache warming operation."""

    cache_name: str
    success: bool
    duration_ms: float
    items_cached: int = 0
    error: str | None = None


@dataclass
class WarmingReport:
    """Complete report of cache warming operation."""

    strategy: WarmingStrategy
    total_duration_ms: float
    results: list[WarmingResult] = field(default_factory=list)

    @property
    def successful_count(self) -> int:
        """Count of successfully warmed caches."""
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        """Count of failed cache warmings."""
        return sum(1 for r in self.results if not r.success)

    @property
    def total_items_cached(self) -> int:
        """Total number of items cached across all warmers."""
        return sum(r.items_cached for r in self.results)


class CacheWarmer:
    """Service for warming frequently accessed caches on startup.

    This class provides methods to pre-populate cache keys that are commonly
    accessed, reducing latency for the first requests after application startup.

    The warming process is fail-soft: individual cache warming failures are
    logged but don't block application startup.
    """

    def __init__(
        self,
        strategy: WarmingStrategy | None = None,
        timeout_seconds: float = 30.0,
    ):
        """Initialize cache warmer.

        Args:
            strategy: Warming strategy to use. If None, uses PARALLEL for fast startup.
            timeout_seconds: Maximum time to wait for warming operations.
        """
        self._strategy = strategy or WarmingStrategy.PARALLEL
        self._timeout = timeout_seconds
        self._warmers: list[tuple[str, Callable[[], Awaitable[int]]]] = []

    def register_warmer(
        self,
        name: str,
        warmer_fn: Callable[[], Awaitable[int]],
    ) -> None:
        """Register a cache warming function.

        Args:
            name: Name of the cache being warmed (for logging/metrics)
            warmer_fn: Async function that warms the cache and returns item count
        """
        self._warmers.append((name, warmer_fn))

    async def warm_all(self) -> WarmingReport:
        """Warm all registered caches according to the configured strategy.

        Returns:
            WarmingReport with results of each warming operation
        """
        import time

        settings = get_settings()
        if not settings.cache_warming_enabled:
            logger.info("Cache warming disabled, skipping")
            return WarmingReport(
                strategy=self._strategy,
                total_duration_ms=0,
                results=[],
            )

        start_time = time.perf_counter()
        logger.info(
            f"Starting cache warming with strategy: {self._strategy.value}",
            extra={"strategy": self._strategy.value, "warmer_count": len(self._warmers)},
        )

        # Register default warmers if none registered
        if not self._warmers:
            self._register_default_warmers()

        results: list[WarmingResult] = []

        try:
            if self._strategy == WarmingStrategy.PARALLEL:
                results = await self._warm_parallel()
            elif self._strategy == WarmingStrategy.SEQUENTIAL:
                results = await self._warm_sequential()
            else:
                results = await self._warm_parallel()

        except TimeoutError:
            logger.warning(
                f"Cache warming timed out after {self._timeout}s",
                extra={"timeout_seconds": self._timeout},
            )
        except Exception as e:
            logger.error(
                f"Cache warming failed with unexpected error: {e}",
                extra={"error": str(e)},
            )

        total_duration = (time.perf_counter() - start_time) * 1000

        report = WarmingReport(
            strategy=self._strategy,
            total_duration_ms=total_duration,
            results=results,
        )

        logger.info(
            f"Cache warming completed: {report.successful_count}/{len(results)} caches warmed "
            f"({report.total_items_cached} items) in {total_duration:.2f}ms",
            extra={
                "strategy": self._strategy.value,
                "successful": report.successful_count,
                "failed": report.failed_count,
                "total_items": report.total_items_cached,
                "duration_ms": total_duration,
            },
        )

        return report

    def _register_default_warmers(self) -> None:
        """Register default cache warmers for common data."""
        self.register_warmer("cameras", self._warm_cameras)
        self.register_warmer("system_status", self._warm_system_status)
        self.register_warmer("alert_rules", self._warm_alert_rules)

    async def _warm_parallel(self) -> list[WarmingResult]:
        """Warm caches in parallel for faster startup."""

        async def run_warmer(name: str, fn: Callable[[], Awaitable[int]]) -> WarmingResult:
            import time

            start = time.perf_counter()
            try:
                items = await asyncio.wait_for(fn(), timeout=self._timeout)
                duration = (time.perf_counter() - start) * 1000
                return WarmingResult(
                    cache_name=name,
                    success=True,
                    duration_ms=duration,
                    items_cached=items,
                )
            except TimeoutError:
                duration = (time.perf_counter() - start) * 1000
                return WarmingResult(
                    cache_name=name,
                    success=False,
                    duration_ms=duration,
                    error=f"Timeout after {self._timeout}s",
                )
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.warning(f"Cache warming failed for {name}: {e}")
                return WarmingResult(
                    cache_name=name,
                    success=False,
                    duration_ms=duration,
                    error=str(e),
                )

        tasks = [run_warmer(name, fn) for name, fn in self._warmers]
        return list(await asyncio.gather(*tasks))

    async def _warm_sequential(self) -> list[WarmingResult]:
        """Warm caches sequentially for lower resource usage."""
        import time

        results = []
        for name, fn in self._warmers:
            start = time.perf_counter()
            try:
                items = await asyncio.wait_for(fn(), timeout=self._timeout)
                duration = (time.perf_counter() - start) * 1000
                results.append(
                    WarmingResult(
                        cache_name=name,
                        success=True,
                        duration_ms=duration,
                        items_cached=items,
                    )
                )
            except TimeoutError:
                duration = (time.perf_counter() - start) * 1000
                results.append(
                    WarmingResult(
                        cache_name=name,
                        success=False,
                        duration_ms=duration,
                        error=f"Timeout after {self._timeout}s",
                    )
                )
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.warning(f"Cache warming failed for {name}: {e}")
                results.append(
                    WarmingResult(
                        cache_name=name,
                        success=False,
                        duration_ms=duration,
                        error=str(e),
                    )
                )

        return results

    async def _warm_cameras(self) -> int:
        """Warm the cameras cache."""
        from sqlalchemy import select

        from backend.core.database import get_session
        from backend.models.camera import Camera
        from backend.services.cache_service import get_cache_service

        cache = await get_cache_service()
        settings = get_settings()

        async with get_session() as session:
            result = await session.execute(select(Camera))
            cameras = result.scalars().all()

            # Cache the camera list
            camera_data = [
                {
                    "id": c.id,
                    "name": c.name,
                    "folder_path": c.folder_path,
                    "status": c.status,
                }
                for c in cameras
            ]

            await cache.set("cameras:list", camera_data, ttl=settings.cache_default_ttl)
            logger.debug(f"Warmed cameras cache with {len(cameras)} cameras")

            return len(cameras)

    async def _warm_system_status(self) -> int:
        """Warm the system status cache."""
        from backend.services.cache_service import get_cache_service

        cache = await get_cache_service()
        settings = get_settings()

        # Cache basic system status
        # Note: Full system status includes Redis/DB health checks which are
        # performed during actual requests. We cache a minimal status here.
        status_data = {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.environment,
            "warmed_at": __import__("time").time(),
        }

        await cache.set("system:status:basic", status_data, ttl=settings.cache_default_ttl)
        logger.debug("Warmed system status cache")

        return 1

    async def _warm_alert_rules(self) -> int:
        """Warm the alert rules cache."""
        from sqlalchemy import select

        from backend.core.database import get_session
        from backend.models.alert import AlertRule
        from backend.services.cache_service import get_cache_service

        cache = await get_cache_service()
        settings = get_settings()

        async with get_session() as session:
            result = await session.execute(select(AlertRule).where(AlertRule.enabled == True))  # noqa: E712
            alerts = result.scalars().all()

            # Cache active alert rules
            alert_data = [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "severity": a.severity.value if a.severity else None,
                    "enabled": a.enabled,
                }
                for a in alerts
            ]

            await cache.set("alerts:rules:active", alert_data, ttl=settings.cache_default_ttl)
            logger.debug(f"Warmed alert rules cache with {len(alerts)} rules")

            return len(alerts)


# Global cache warmer instance
_cache_warmer: CacheWarmer | None = None


async def get_cache_warmer() -> CacheWarmer:
    """Get or create the cache warmer singleton.

    Returns:
        CacheWarmer instance
    """
    global _cache_warmer  # noqa: PLW0603
    if _cache_warmer is None:
        settings = get_settings()
        strategy = WarmingStrategy(settings.cache_warming_strategy)
        _cache_warmer = CacheWarmer(
            strategy=strategy,
            timeout_seconds=settings.cache_warming_timeout,
        )
    return _cache_warmer


async def reset_cache_warmer() -> None:
    """Reset the cache warmer singleton (for testing)."""
    global _cache_warmer  # noqa: PLW0603
    _cache_warmer = None


async def warm_caches_on_startup() -> WarmingReport:
    """Convenience function to warm caches during application startup.

    This function should be called in the application lifespan context
    after Redis and database connections are established.

    Returns:
        WarmingReport with results
    """
    warmer = await get_cache_warmer()
    return await warmer.warm_all()
