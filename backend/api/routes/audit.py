"""API routes for audit log management."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogStats,
)
from backend.core.database import get_db
from backend.models.audit import AuditLog
from backend.services.audit import AuditService

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    actor: str | None = Query(None, description="Filter by actor"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (success/failure)"
    ),
    start_date: datetime | None = Query(None, description="Filter from date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter to date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List audit logs with optional filtering and pagination.

    This endpoint is intended for admin use to review security-sensitive operations.

    Args:
        action: Optional action type to filter by
        resource_type: Optional resource type to filter by
        resource_id: Optional specific resource ID to filter by
        actor: Optional actor to filter by
        status_filter: Optional status to filter by (success/failure)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        AuditLogListResponse containing filtered logs and pagination info
    """
    logs, total_count = await AuditService.get_audit_logs(
        db=db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor=actor,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return {
        "logs": logs,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=AuditLogStats)
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get audit log statistics for dashboard.

    Returns aggregated statistics about audit logs including:
    - Total log count
    - Logs today
    - Breakdown by action type
    - Breakdown by resource type
    - Breakdown by status
    - Recently active actors

    Args:
        db: Database session

    Returns:
        AuditLogStats with aggregated statistics
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Total logs
    total_query = select(func.count()).select_from(AuditLog)
    total_result = await db.execute(total_query)
    total_logs = total_result.scalar() or 0

    # Logs today
    today_query = select(func.count()).where(AuditLog.timestamp >= today_start)
    today_result = await db.execute(today_query)
    logs_today = today_result.scalar() or 0

    # By action
    action_query = (
        select(AuditLog.action, func.count().label("count"))
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    )
    action_result = await db.execute(action_query)
    by_action = {row.action: row.count for row in action_result}

    # By resource type
    resource_query = (
        select(AuditLog.resource_type, func.count().label("count"))
        .group_by(AuditLog.resource_type)
        .order_by(func.count().desc())
    )
    resource_result = await db.execute(resource_query)
    by_resource_type = {row.resource_type: row.count for row in resource_result}

    # By status
    status_query = select(AuditLog.status, func.count().label("count")).group_by(AuditLog.status)
    status_result = await db.execute(status_query)
    by_status = {row.status: row.count for row in status_result}

    # Recent actors (last 7 days, top 10)
    seven_days_ago = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = seven_days_ago.replace(day=max(1, seven_days_ago.day - 7))
    actors_query = (
        select(AuditLog.actor)
        .where(AuditLog.timestamp >= seven_days_ago)
        .group_by(AuditLog.actor)
        .order_by(func.count().desc())
        .limit(10)
    )
    actors_result = await db.execute(actors_query)
    recent_actors = [row.actor for row in actors_result]

    return {
        "total_logs": total_logs,
        "logs_today": logs_today,
        "by_action": by_action,
        "by_resource_type": by_resource_type,
        "by_status": by_status,
        "recent_actors": recent_actors,
    }


@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
) -> AuditLog:
    """Get a specific audit log entry by ID.

    Args:
        audit_id: Audit log ID
        db: Database session

    Returns:
        AuditLog record

    Raises:
        HTTPException: 404 if audit log not found
    """
    log = await AuditService.get_audit_log_by_id(db, audit_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log {audit_id} not found",
        )

    return log
