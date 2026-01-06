"""API routes for audit log management."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogStats,
)
from backend.api.validators import validate_date_range
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

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    validate_date_range(start_date, end_date)

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

    This endpoint is optimized to use a single aggregation query for counts
    (total, today, by_action, by_resource_type, by_status) plus one query
    for recent actors, reducing database round-trips from 6 to 2.

    Args:
        db: Database session

    Returns:
        AuditLogStats with aggregated statistics
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    # Single aggregation query using UNION ALL to get all stats in one round-trip
    # This combines: total count, today count, by_action, by_resource_type, by_status
    #
    # Query structure:
    # - category='total': total count
    # - category='today': logs today count
    # - category='action': breakdown by action
    # - category='resource_type': breakdown by resource_type
    # - category='status': breakdown by status

    # Total count
    total_subq = select(
        literal("total").label("category"),
        literal("all").label("key"),
        func.count().label("count"),
    ).select_from(AuditLog)

    # Today count
    today_subq = select(
        literal("today").label("category"),
        literal("all").label("key"),
        func.count().label("count"),
    ).where(AuditLog.timestamp >= today_start)

    # By action
    action_subq = select(
        literal("action").label("category"),
        AuditLog.action.label("key"),
        func.count().label("count"),
    ).group_by(AuditLog.action)

    # By resource type
    resource_subq = select(
        literal("resource_type").label("category"),
        AuditLog.resource_type.label("key"),
        func.count().label("count"),
    ).group_by(AuditLog.resource_type)

    # By status
    status_subq = select(
        literal("status").label("category"),
        AuditLog.status.label("key"),
        func.count().label("count"),
    ).group_by(AuditLog.status)

    # Combine all queries with UNION ALL
    combined_query = union_all(
        total_subq,
        today_subq,
        action_subq,
        resource_subq,
        status_subq,
    )

    result = await db.execute(combined_query)
    rows = result.fetchall()

    # Parse the combined results
    total_logs = 0
    logs_today = 0
    by_action: dict[str, int] = {}
    by_resource_type: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for row in rows:
        category: str = row[0]
        key: str = row[1]
        count: int = int(row[2])
        if category == "total":
            total_logs = count
        elif category == "today":
            logs_today = count
        elif category == "action":
            by_action[key] = count
        elif category == "resource_type":
            by_resource_type[key] = count
        elif category == "status":
            by_status[key] = count

    # Recent actors query (separate because it needs different filtering and LIMIT)
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
