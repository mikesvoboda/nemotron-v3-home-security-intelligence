"""Scheduler for materialized view refresh operations.

This module provides comprehensive materialized view management including:
1. Configurable refresh strategies (concurrent, full, incremental)
2. Dependency-aware refresh ordering
3. Stale view detection based on configurable intervals
4. Concurrent refresh prevention
5. Performance metrics and monitoring

Related Linear issues:
- NEM-3754: Implement Materialized Views for Analytics Dashboards
- NEM-3389: Create materialized views for dashboard aggregations

Usage:
    async with get_session() as session:
        scheduler = MaterializedViewScheduler(session)

        # Refresh a single view
        result = await scheduler.refresh_view("mv_daily_detection_counts")

        # Refresh all views by priority
        results = await scheduler.refresh_all()

        # Refresh only stale views
        results = await scheduler.refresh_stale_views()
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class RefreshStrategy(Enum):
    """Strategy for refreshing materialized views.

    CONCURRENT: Allows reads during refresh (requires unique index)
    FULL: Blocks reads during refresh (faster for small views)
    INCREMENTAL: Only refreshes changed data (requires custom implementation)
    """

    CONCURRENT = "concurrent"
    FULL = "full"
    INCREMENTAL = "incremental"


class ViewRefreshStatus(Enum):
    """Status of a view refresh operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"


@dataclass
class ViewRefreshConfig:
    """Configuration for a materialized view refresh.

    Attributes:
        view_name: Name of the materialized view
        strategy: Refresh strategy to use
        refresh_interval_seconds: Minimum seconds between refreshes
        priority: Lower priority refreshes first (for dependency ordering)
        dependencies: List of view names that must be refreshed first
    """

    view_name: str
    strategy: RefreshStrategy = RefreshStrategy.CONCURRENT
    refresh_interval_seconds: int = 300  # 5 minutes default
    priority: int = 1
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ViewRefreshResult:
    """Result of a view refresh operation.

    Attributes:
        view_name: Name of the materialized view
        status: Status of the refresh operation
        refresh_duration_ms: Duration of refresh in milliseconds
        rows_affected: Number of rows in the refreshed view
        error_message: Error message if refresh failed
        refreshed_at: Timestamp when refresh completed
    """

    view_name: str
    status: ViewRefreshStatus
    refresh_duration_ms: float = 0.0
    rows_affected: int | None = None
    error_message: str | None = None
    refreshed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MaterializedViewScheduler:
    """Scheduler for materialized view refresh operations.

    This service manages the lifecycle of materialized views including:
    - Configuring refresh strategies per view
    - Managing dependencies between views
    - Preventing concurrent refresh of the same view
    - Tracking refresh status and performance metrics

    Example:
        async with get_session() as session:
            scheduler = MaterializedViewScheduler(session)

            # Register a custom view
            scheduler.register_view(ViewRefreshConfig(
                view_name="mv_custom",
                strategy=RefreshStrategy.CONCURRENT,
                refresh_interval_seconds=60,
            ))

            # Refresh all views
            results = await scheduler.refresh_all()
    """

    # Default views with their configurations
    DEFAULT_VIEWS: ClassVar[list[ViewRefreshConfig]] = [
        ViewRefreshConfig(
            view_name="mv_daily_detection_counts",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=300,
            priority=1,
        ),
        ViewRefreshConfig(
            view_name="mv_hourly_event_stats",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=300,
            priority=2,
        ),
        ViewRefreshConfig(
            view_name="mv_detection_type_distribution",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=600,
            priority=3,
        ),
        ViewRefreshConfig(
            view_name="mv_entity_tracking_summary",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=600,
            priority=4,
        ),
        ViewRefreshConfig(
            view_name="mv_risk_score_aggregations",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=300,
            priority=2,
            dependencies=["mv_hourly_event_stats"],
        ),
        ViewRefreshConfig(
            view_name="mv_enrichment_summary",
            strategy=RefreshStrategy.CONCURRENT,
            refresh_interval_seconds=900,
            priority=5,
            dependencies=["mv_daily_detection_counts"],
        ),
    ]

    def __init__(self, session: AsyncSession):
        """Initialize the scheduler with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._configs: dict[str, ViewRefreshConfig] = {}
        self._last_refresh: dict[str, datetime] = {}
        self._refresh_locks: dict[str, asyncio.Lock] = {}

        # Initialize with default views
        for config in self.DEFAULT_VIEWS:
            self.register_view(config)

    def register_view(self, config: ViewRefreshConfig) -> None:
        """Register a view configuration.

        Args:
            config: View refresh configuration
        """
        self._configs[config.view_name] = config
        if config.view_name not in self._refresh_locks:
            self._refresh_locks[config.view_name] = asyncio.Lock()

    def unregister_view(self, view_name: str) -> None:
        """Unregister a view configuration.

        Args:
            view_name: Name of the view to unregister
        """
        self._configs.pop(view_name, None)
        self._last_refresh.pop(view_name, None)
        self._refresh_locks.pop(view_name, None)

    def get_view_configs(self) -> dict[str, ViewRefreshConfig]:
        """Get all registered view configurations.

        Returns:
            Dictionary mapping view names to configurations
        """
        return self._configs.copy()

    async def refresh_view(self, view_name: str) -> ViewRefreshResult:
        """Refresh a single materialized view.

        Args:
            view_name: Name of the view to refresh

        Returns:
            ViewRefreshResult with status and metrics
        """
        if view_name not in self._configs:
            return ViewRefreshResult(
                view_name=view_name,
                status=ViewRefreshStatus.FAILED,
                error_message=f"View '{view_name}' is not registered",
            )

        config = self._configs[view_name]

        # Get or create lock for this view
        if view_name not in self._refresh_locks:
            self._refresh_locks[view_name] = asyncio.Lock()

        lock = self._refresh_locks[view_name]

        # Try to acquire lock without blocking
        if lock.locked():
            return ViewRefreshResult(
                view_name=view_name,
                status=ViewRefreshStatus.SKIPPED,
                error_message="Refresh already in progress",
            )

        async with lock:
            start_time = time.perf_counter()

            try:
                # Build refresh SQL based on strategy
                if config.strategy == RefreshStrategy.CONCURRENT:
                    sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"
                elif config.strategy == RefreshStrategy.FULL:
                    sql = f"REFRESH MATERIALIZED VIEW {view_name}"
                else:  # INCREMENTAL
                    # Incremental refresh is view-specific
                    # For now, fall back to concurrent
                    sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"

                # Execute refresh - view_name comes from registered configs, not user input
                await self.session.execute(text(sql))  # nosemgrep: avoid-sqlalchemy-text
                await self.session.commit()

                # Get row count
                rows = await self.get_view_row_count(view_name)

                duration_ms = (time.perf_counter() - start_time) * 1000
                self._last_refresh[view_name] = datetime.now(UTC)

                logger.info(
                    f"Refreshed materialized view: {view_name}",
                    extra={
                        "view_name": view_name,
                        "strategy": config.strategy.value,
                        "duration_ms": round(duration_ms, 2),
                        "rows": rows,
                    },
                )

                return ViewRefreshResult(
                    view_name=view_name,
                    status=ViewRefreshStatus.SUCCESS,
                    refresh_duration_ms=duration_ms,
                    rows_affected=rows,
                )

            except Exception as e:
                await self.session.rollback()
                duration_ms = (time.perf_counter() - start_time) * 1000

                logger.error(
                    f"Failed to refresh materialized view: {view_name}",
                    extra={
                        "view_name": view_name,
                        "error": str(e),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return ViewRefreshResult(
                    view_name=view_name,
                    status=ViewRefreshStatus.FAILED,
                    refresh_duration_ms=duration_ms,
                    error_message=str(e),
                )

    async def refresh_with_dependencies(self, view_name: str) -> list[ViewRefreshResult]:
        """Refresh a view and all its dependencies in order.

        Args:
            view_name: Name of the view to refresh

        Returns:
            List of ViewRefreshResult for all refreshed views
        """
        if view_name not in self._configs:
            return [
                ViewRefreshResult(
                    view_name=view_name,
                    status=ViewRefreshStatus.FAILED,
                    error_message=f"View '{view_name}' is not registered",
                )
            ]

        # Build dependency order
        to_refresh = self._resolve_dependencies(view_name)

        # Sort by priority (lower first)
        to_refresh.sort(key=lambda v: self._configs.get(v, ViewRefreshConfig(view_name=v)).priority)

        results = []
        for vn in to_refresh:
            result = await self.refresh_view(vn)
            results.append(result)

            # Stop if a dependency fails
            if result.status == ViewRefreshStatus.FAILED:
                logger.warning(
                    f"Stopping dependency refresh due to failure: {vn}",
                    extra={"view_name": vn, "error": result.error_message},
                )
                break

        return results

    def _resolve_dependencies(self, view_name: str, visited: set[str] | None = None) -> list[str]:
        """Resolve all dependencies for a view recursively.

        Args:
            view_name: Name of the view
            visited: Set of already visited views (for cycle detection)

        Returns:
            List of view names in dependency order
        """
        if visited is None:
            visited = set()

        if view_name in visited:
            return []  # Cycle detected, skip

        visited.add(view_name)

        config = self._configs.get(view_name)
        if config is None:
            return [view_name]

        result = []
        for dep in config.dependencies:
            result.extend(self._resolve_dependencies(dep, visited))

        result.append(view_name)
        return result

    async def refresh_all(self) -> list[ViewRefreshResult]:
        """Refresh all registered views in priority order.

        Returns:
            List of ViewRefreshResult for all views
        """
        # Sort views by priority
        sorted_views = sorted(
            self._configs.values(),
            key=lambda c: c.priority,
        )

        results = []
        for config in sorted_views:
            result = await self.refresh_view(config.view_name)
            results.append(result)

        return results

    async def refresh_stale_views(self) -> list[ViewRefreshResult]:
        """Refresh only views that are stale (past their interval).

        Returns:
            List of ViewRefreshResult for refreshed views
        """
        now = datetime.now(UTC)
        results = []

        # Sort by priority
        sorted_views = sorted(
            self._configs.values(),
            key=lambda c: c.priority,
        )

        for config in sorted_views:
            last_refresh = self._last_refresh.get(config.view_name)

            if last_refresh is None:
                # Never refreshed - refresh now
                is_stale = True
            else:
                age_seconds = (now - last_refresh).total_seconds()
                is_stale = age_seconds >= config.refresh_interval_seconds

            if is_stale:
                result = await self.refresh_view(config.view_name)
                results.append(result)

        return results

    def get_refresh_status(self) -> dict[str, dict[str, Any]]:
        """Get refresh status for all views.

        Returns:
            Dictionary mapping view names to status info
        """
        now = datetime.now(UTC)
        status = {}

        for view_name, config in self._configs.items():
            last_refresh = self._last_refresh.get(view_name)

            if last_refresh is None:
                is_stale = True
                age_seconds = None
            else:
                age_seconds = (now - last_refresh).total_seconds()
                is_stale = age_seconds >= config.refresh_interval_seconds

            status[view_name] = {
                "last_refreshed": last_refresh.isoformat() if last_refresh else None,
                "age_seconds": age_seconds,
                "refresh_interval_seconds": config.refresh_interval_seconds,
                "is_stale": is_stale,
                "strategy": config.strategy.value,
                "priority": config.priority,
                "dependencies": config.dependencies,
            }

        return status

    async def get_view_row_count(self, view_name: str) -> int:
        """Get the row count for a materialized view.

        Args:
            view_name: Name of the view

        Returns:
            Number of rows in the view
        """
        if view_name not in self._configs:
            return 0

        try:
            # view_name comes from registered configs, not user input
            result = await self.session.execute(
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text, sqlalchemy-raw-text-injection
                text(f"SELECT COUNT(*) FROM {view_name}")  # noqa: S608
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.warning(f"Failed to get row count for {view_name}: {e}")
            return 0

    async def get_view_size_bytes(self, view_name: str) -> int:
        """Get the size in bytes for a materialized view.

        Args:
            view_name: Name of the view

        Returns:
            Size of the view in bytes
        """
        if view_name not in self._configs:
            return 0

        try:
            # view_name comes from registered configs, not user input
            result = await self.session.execute(
                # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text, sqlalchemy-raw-text-injection
                text(f"SELECT pg_relation_size('{view_name}')")
            )
            size = result.scalar()
            return size or 0
        except Exception as e:
            logger.warning(f"Failed to get size for {view_name}: {e}")
            return 0
