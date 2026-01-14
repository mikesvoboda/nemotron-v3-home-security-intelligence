"""API routes for audit log management."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_audit_log_or_404
from backend.api.pagination import (
    CursorData,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
    set_deprecation_headers,
)
from backend.api.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogStats,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.api.validators import validate_date_range
from backend.core.database import get_db
from backend.models.audit import AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    responses={
        400: {"description": "Invalid date range or cursor"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_audit_logs(  # noqa: PLR0912
    response: Response,
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
    offset: int = Query(0, ge=0, description="Number of results to skip (deprecated, use cursor)"),
    cursor: str | None = Query(None, description="Pagination cursor from previous response"),
    include_total_count: bool = Query(
        False,
        description="Include total count in response. Defaults to False for performance. "
        "Total count queries are expensive for large datasets. For cursor-based pagination, "
        "has_more and next_cursor provide sufficient information without the total count.",
    ),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit logs with optional filtering and cursor-based pagination.

    This endpoint is intended for admin use to review security-sensitive operations.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.

    **Performance Note:** Total count queries are expensive for large datasets. By default,
    the total count is not calculated (returns 0). Use `include_total_count=true` only when
    the total count is needed (e.g., for displaying "X of Y results" in UI). For pagination,
    `has_more` and `next_cursor` provide sufficient information.

    Args:
        action: Optional action type to filter by
        resource_type: Optional resource type to filter by
        resource_id: Optional specific resource ID to filter by
        actor: Optional actor to filter by
        status_filter: Optional status to filter by (success/failure)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field
        include_total_count: Whether to calculate total count (default False for performance)
        db: Database session

    Returns:
        AuditLogListResponse containing filtered logs and pagination info

    Raises:
        HTTPException: 400 if start_date is after end_date
        HTTPException: 400 if cursor is invalid
    """
    # Validate date range
    validate_date_range(start_date, end_date)

    # Decode cursor if provided
    cursor_data: CursorData | None = None
    if cursor:
        try:
            cursor_data = decode_cursor(cursor)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cursor: {e}",
            ) from e

    # Build base query
    query = select(AuditLog)

    # Apply filters
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)
    if actor:
        query = query.where(AuditLog.actor == actor)
    if status_filter:
        query = query.where(AuditLog.status == status_filter)
    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.where(AuditLog.timestamp <= end_date)

    # Apply cursor-based pagination filter (takes precedence over offset)
    if cursor_data:
        # For descending order by timestamp, we want records where:
        # - timestamp < cursor's created_at, OR
        # - timestamp == cursor's created_at AND id < cursor's id (tie-breaker)
        query = query.where(
            (AuditLog.timestamp < cursor_data.created_at)
            | ((AuditLog.timestamp == cursor_data.created_at) & (AuditLog.id < cursor_data.id))
        )

    # Get total count only when explicitly requested (NEM-2601 optimization)
    # Total count queries are expensive for large datasets. For cursor-based pagination,
    # has_more and next_cursor provide sufficient information without the total count.
    total_count: int = 0
    if include_total_count:
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

    # Sort by timestamp descending (newest first), then by id descending for consistency
    query = query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())

    # Apply pagination - fetch one extra to determine if there are more results
    if cursor_data:  # noqa: SIM108
        # Cursor-based: fetch limit + 1 to check for more
        query = query.limit(limit + 1)
    else:
        # Offset-based (deprecated): apply offset
        query = query.limit(limit + 1).offset(offset)

    # Execute query
    result = await db.execute(query)
    logs = list(result.scalars().all())

    # Determine if there are more results
    has_more = len(logs) > limit
    if has_more:
        logs = logs[:limit]  # Trim to requested limit

    # Generate next cursor from the last log
    next_cursor: str | None = None
    if has_more and logs:
        last_log = logs[-1]
        cursor_data_next = CursorData(id=last_log.id, created_at=last_log.timestamp)
        next_cursor = encode_cursor(cursor_data_next)

    # Get deprecation warning if using offset without cursor
    deprecation_warning = get_deprecation_warning(cursor, offset)

    # Set HTTP Deprecation headers per IETF standard (NEM-2603)
    set_deprecation_headers(response, cursor, offset)

    return AuditLogListResponse(
        items=logs,
        pagination=PaginationMeta(
            total=total_count,
            limit=limit,
            offset=offset,
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
        deprecation_warning=deprecation_warning,
    )


@router.get(
    "/stats",
    response_model=AuditLogStats,
    responses={
        400: {"description": "Invalid date range"},
        500: {"description": "Internal server error"},
    },
)
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
) -> AuditLogStats:
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

    return AuditLogStats(
        total_logs=total_logs,
        logs_today=logs_today,
        by_action=by_action,
        by_resource_type=by_resource_type,
        by_status=by_status,
        recent_actors=recent_actors,
    )


@router.get(
    "/{audit_id}",
    response_model=AuditLogResponse,
    responses={
        404: {"description": "Audit log not found"},
        500: {"description": "Internal server error"},
    },
)
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
    return await get_audit_log_or_404(audit_id, db)
