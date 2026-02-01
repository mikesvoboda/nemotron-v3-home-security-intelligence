"""API routes for Materialized Views Admin Controls (NEM-4933).

This module provides endpoints for administering materialized views,
including listing views, checking status, and triggering refreshes.

Endpoints:
- GET /api/admin/materialized-views: List all managed views with stats
- GET /api/admin/materialized-views/{view_name}: Get status of a specific view
- POST /api/admin/materialized-views/refresh: Trigger refresh of views
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.materialized_views import (
    MaterializedViewInfo,
    MaterializedViewListResponse,
    MaterializedViewRefreshRequest,
    MaterializedViewRefreshResponse,
    MaterializedViewRefreshResult,
    MaterializedViewStatusResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services.materialized_views import MaterializedViewService

router = APIRouter(
    prefix="/api/admin/materialized-views",
    tags=["admin", "materialized-views"],
    default_response_class=ORJSONResponse,
)

logger = get_logger(__name__)


def _format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., '100 KB', '1.5 MB')
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


@router.get(
    "",
    response_model=MaterializedViewListResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def list_materialized_views(
    db: AsyncSession = Depends(get_db),
) -> MaterializedViewListResponse:
    """List all managed materialized views with their statistics.

    Returns information about all materialized views managed by the service,
    including whether they exist, row counts, and sizes.

    Args:
        db: Database session

    Returns:
        MaterializedViewListResponse with view information
    """
    logger.info("Listing all materialized views")

    service = MaterializedViewService(db)

    try:
        stats = await service.get_view_stats()

        total_size = 0
        views = []

        for stat in stats:
            size_bytes = stat.get("size_bytes", 0)
            total_size += size_bytes

            views.append(
                MaterializedViewInfo(
                    view_name=stat["view_name"],
                    exists=stat.get("exists", False),
                    row_count=stat.get("row_count", 0),
                    size_bytes=size_bytes,
                    size_human=_format_bytes(size_bytes),
                    error=stat.get("error"),
                )
            )

        return MaterializedViewListResponse(
            views=views,
            total_views=len(views),
            total_size_bytes=total_size,
            total_size_human=_format_bytes(total_size),
        )

    except Exception as e:
        logger.error("Failed to list materialized views: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list materialized views: {e!s}",
        ) from e


@router.get(
    "/{view_name}",
    response_model=MaterializedViewStatusResponse,
    responses={
        404: {"description": "View not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_materialized_view_status(
    view_name: str,
    db: AsyncSession = Depends(get_db),
) -> MaterializedViewStatusResponse:
    """Get the status of a specific materialized view.

    Returns detailed status information for a single materialized view,
    including whether it exists, row count, size, and population status.

    Args:
        view_name: Name of the materialized view
        db: Database session

    Returns:
        MaterializedViewStatusResponse with view status

    Raises:
        HTTPException: 404 if view is not in the managed list
    """
    logger.info("Getting status for materialized view: %s", view_name)

    service = MaterializedViewService(db)

    # Check if view is in managed list
    if view_name not in service.MANAGED_VIEWS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"View '{view_name}' is not in the managed views list. "
            f"Available views: {', '.join(service.MANAGED_VIEWS)}",
        )

    try:
        # Check if view exists
        exists = await service.check_view_exists(view_name)

        if not exists:
            return MaterializedViewStatusResponse(
                view_name=view_name,
                exists=False,
                row_count=0,
                size_bytes=0,
                size_human="0 B",
                is_populated=False,
                last_refresh=None,
            )

        # Get stats for this specific view
        stats = await service.get_view_stats()
        view_stat = next(
            (s for s in stats if s["view_name"] == view_name),
            {"row_count": 0, "size_bytes": 0},
        )

        row_count = view_stat.get("row_count", 0)
        size_bytes = view_stat.get("size_bytes", 0)

        return MaterializedViewStatusResponse(
            view_name=view_name,
            exists=True,
            row_count=row_count,
            size_bytes=size_bytes,
            size_human=_format_bytes(size_bytes),
            is_populated=row_count > 0,
            last_refresh=None,  # PostgreSQL doesn't track this by default
            error=view_stat.get("error"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get status for view %s: %s", view_name, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get view status: {e!s}",
        ) from e


@router.post(
    "/refresh",
    response_model=MaterializedViewRefreshResponse,
    responses={
        404: {"description": "View not found"},
        500: {"description": "Internal server error"},
    },
)
async def refresh_materialized_views(
    request: MaterializedViewRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> MaterializedViewRefreshResponse:
    """Refresh one or all materialized views.

    Triggers a refresh of either a specific materialized view or all
    managed views. The `concurrently` option allows reads during the
    refresh (requires unique index on the view).

    Args:
        request: Refresh request with optional view name and concurrently flag
        db: Database session

    Returns:
        MaterializedViewRefreshResponse with refresh results

    Raises:
        HTTPException: 404 if specified view not found
    """
    service = MaterializedViewService(db)

    # Validate view name if provided
    if request.view_name and request.view_name not in service.MANAGED_VIEWS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"View '{request.view_name}' is not in the managed views list. "
            f"Available views: {', '.join(service.MANAGED_VIEWS)}",
        )

    logger.info(
        "Refreshing materialized views: view_name=%s, concurrently=%s",
        request.view_name or "all",
        request.concurrently,
    )

    results: list[MaterializedViewRefreshResult] = []
    total_duration_ms = 0.0

    try:
        if request.view_name:
            # Refresh single view
            start_time = time.perf_counter()
            success = await service.refresh_view(
                view_name=request.view_name,
                concurrently=request.concurrently,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            results.append(
                MaterializedViewRefreshResult(
                    view_name=request.view_name,
                    success=success,
                    duration_ms=duration_ms,
                    error=None if success else "Refresh failed",
                )
            )
            total_duration_ms = duration_ms

        else:
            # Refresh all views
            start_time = time.perf_counter()
            refresh_results = await service.refresh_all_views(
                concurrently=request.concurrently,
            )
            total_duration_ms = (time.perf_counter() - start_time) * 1000

            # Calculate per-view duration estimate (total / num_views)
            per_view_duration = total_duration_ms / len(refresh_results) if refresh_results else 0

            for view_name, success in refresh_results.items():
                results.append(
                    MaterializedViewRefreshResult(
                        view_name=view_name,
                        success=success,
                        duration_ms=per_view_duration,  # Estimated
                        error=None if success else "Refresh failed",
                    )
                )

        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count

        return MaterializedViewRefreshResponse(
            results=results,
            total_refreshed=len(results),
            success_count=success_count,
            failure_count=failure_count,
            total_duration_ms=total_duration_ms,
            concurrently=request.concurrently,
            refreshed_at=datetime.now(UTC),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to refresh materialized views: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh views: {e!s}",
        ) from e


@router.get(
    "/list/names",
    response_model=list[str],
    responses={
        500: {"description": "Internal server error"},
    },
)
async def list_view_names() -> list[str]:
    """List the names of all managed materialized views.

    Returns a simple list of view names that are managed by the service.
    This is useful for populating dropdowns or validation.

    Returns:
        List of materialized view names
    """
    return list(MaterializedViewService.MANAGED_VIEWS)
