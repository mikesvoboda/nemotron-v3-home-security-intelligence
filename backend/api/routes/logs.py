"""API routes for logs management."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.logs import (
    FrontendLogCreate,
    LogEntry,
    LogsResponse,
    LogStats,
)
from backend.core.database import get_db
from backend.models.log import Log

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogsResponse)
async def list_logs(
    level: str | None = Query(None, description="Filter by log level"),
    component: str | None = Query(None, description="Filter by component name"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    source: str | None = Query(None, description="Filter by source (backend, frontend)"),
    search: str | None = Query(None, description="Search in message text"),
    start_date: datetime | None = Query(None, description="Filter from date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter to date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List logs with optional filtering and pagination."""
    query = select(Log)

    # Apply filters
    if level:
        query = query.where(Log.level == level.upper())
    if component:
        query = query.where(Log.component == component)
    if camera_id:
        query = query.where(Log.camera_id == camera_id)
    if source:
        query = query.where(Log.source == source)
    if search:
        query = query.where(Log.message.ilike(f"%{search}%"))
    if start_date:
        query = query.where(Log.timestamp >= start_date)
    if end_date:
        query = query.where(Log.timestamp <= end_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort and paginate
    query = query.order_by(Log.timestamp.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": logs,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=LogStats)
async def get_log_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get log statistics for dashboard."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Total today
    total_query = select(func.count()).where(Log.timestamp >= today_start)
    total_result = await db.execute(total_query)
    total_today = total_result.scalar() or 0

    # Errors today
    errors_query = select(func.count()).where(
        Log.timestamp >= today_start,
        Log.level == "ERROR",
    )
    errors_result = await db.execute(errors_query)
    errors_today = errors_result.scalar() or 0

    # Warnings today
    warnings_query = select(func.count()).where(
        Log.timestamp >= today_start,
        Log.level == "WARNING",
    )
    warnings_result = await db.execute(warnings_query)
    warnings_today = warnings_result.scalar() or 0

    # By component (today)
    component_query = (
        select(Log.component, func.count().label("count"))
        .where(Log.timestamp >= today_start)
        .group_by(Log.component)
        .order_by(func.count().desc())
    )
    component_result = await db.execute(component_query)
    by_component = {row.component: row.count for row in component_result}

    # By level (today)
    level_query = (
        select(Log.level, func.count().label("count"))
        .where(Log.timestamp >= today_start)
        .group_by(Log.level)
    )
    level_result = await db.execute(level_query)
    by_level = {row.level: row.count for row in level_result}

    # Top component
    top_component = next(iter(by_component.keys())) if by_component else None

    return {
        "total_today": total_today,
        "errors_today": errors_today,
        "warnings_today": warnings_today,
        "by_component": by_component,
        "by_level": by_level,
        "top_component": top_component,
    }


@router.get("/{log_id}", response_model=LogEntry)
async def get_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
) -> Log:
    """Get a single log entry by ID."""
    result = await db.execute(select(Log).where(Log.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log {log_id} not found",
        )

    assert isinstance(log, Log)
    return log


@router.post("/frontend", status_code=status.HTTP_201_CREATED)
async def create_frontend_log(
    log_data: FrontendLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive and store a log from the frontend."""
    # Get user agent from request if not provided
    user_agent = log_data.user_agent or request.headers.get("user-agent")

    log = Log(
        timestamp=datetime.now(UTC),
        level=log_data.level.upper(),
        component=log_data.component,
        message=log_data.message,
        extra=log_data.extra,
        source="frontend",
        user_agent=user_agent,
    )

    db.add(log)
    await db.commit()

    return {"status": "created"}
