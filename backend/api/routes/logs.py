"""API routes for logs management."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.pagination import (
    CursorData,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
    set_deprecation_headers,
)
from backend.api.schemas.logs import (
    FrontendLogBatchCreate,
    FrontendLogCreate,
    LogEntry,
    LogsResponse,
    LogStats,
    PaginationInfo,
)
from backend.api.validators import normalize_end_date_to_end_of_day, validate_date_range
from backend.core.database import escape_ilike_pattern, get_db
from backend.models.log import Log

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get(
    "",
    response_model=LogsResponse,
    responses={
        400: {"description": "Invalid date range or cursor"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_logs(  # noqa: PLR0912
    response: Response,
    level: str | None = Query(None, description="Filter by log level"),
    component: str | None = Query(None, description="Filter by component name"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    source: str | None = Query(None, description="Filter by source (backend, frontend)"),
    search: str | None = Query(None, description="Search in message text"),
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
) -> LogsResponse:
    """List logs with optional filtering and cursor-based pagination.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.

    **Performance Note:** Total count queries are expensive for large datasets. By default,
    the total count is not calculated (returns 0). Use `include_total_count=true` only when
    the total count is needed (e.g., for displaying "X of Y results" in UI). For pagination,
    `has_more` and `next_cursor` provide sufficient information.

    Args:
        level: Optional log level to filter by (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        component: Optional component name to filter by
        camera_id: Optional camera ID to filter by
        source: Optional source to filter by (backend, frontend)
        search: Optional search term for message text
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field
        include_total_count: Whether to calculate total count (default False for performance)
        db: Database session

    Returns:
        LogsResponse containing filtered logs and pagination info

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

    query = select(Log)

    # Normalize end_date to end of day if it's at midnight (date-only input)
    # This ensures date-only filters like "2026-01-15" include all logs from that day
    normalized_end_date = normalize_end_date_to_end_of_day(end_date)

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
        # Escape ILIKE special characters to prevent pattern injection
        query = query.where(Log.message.ilike(f"%{escape_ilike_pattern(search)}%"))
    if start_date:
        query = query.where(Log.timestamp >= start_date)
    if normalized_end_date:
        query = query.where(Log.timestamp <= normalized_end_date)

    # Apply cursor-based pagination filter (takes precedence over offset)
    if cursor_data:
        # For descending order by timestamp, we want records where:
        # - timestamp < cursor's created_at, OR
        # - timestamp == cursor's created_at AND id < cursor's id (tie-breaker)
        query = query.where(
            (Log.timestamp < cursor_data.created_at)
            | ((Log.timestamp == cursor_data.created_at) & (Log.id < cursor_data.id))
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
    query = query.order_by(Log.timestamp.desc(), Log.id.desc())

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

    # Get deprecation warning if using offset without cursor (logged but not returned in new format)
    deprecation_warning = get_deprecation_warning(cursor, offset)
    if deprecation_warning:
        import logging

        logging.getLogger(__name__).warning(deprecation_warning)

    # Set HTTP Deprecation headers per IETF standard (NEM-2603)
    set_deprecation_headers(response, cursor, offset)

    return LogsResponse(
        items=logs,
        pagination=PaginationInfo(
            total=total_count,
            limit=limit,
            offset=offset if offset else None,
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
    )


@router.get(
    "/stats",
    response_model=LogStats,
    responses={
        400: {"description": "Invalid date range"},
        500: {"description": "Internal server error"},
    },
)
async def get_log_stats(
    db: AsyncSession = Depends(get_db),
) -> LogStats:
    """Get log statistics for dashboard.

    Optimized to use a single aggregation query with conditional counting
    instead of 5 separate queries. This reduces database round-trips and
    improves performance for high-volume log tables.
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Single optimized query using conditional aggregation
    # This replaces 5 separate queries with one that computes:
    # - Total count, error count, warning count (via conditional SUM)
    # - Counts by level and component (via GROUP BY with GROUPING SETS simulation)
    #
    # We use two queries that can be combined: one for totals, one for breakdowns
    # The totals query uses FILTER clause (PostgreSQL) or CASE for portability

    # Query 1: Get aggregate totals with conditional counting in a single pass
    totals_query = select(
        func.count().label("total_today"),
        func.sum(case((Log.level == "ERROR", 1), else_=0)).label("errors_today"),
        func.sum(case((Log.level == "WARNING", 1), else_=0)).label("warnings_today"),
    ).where(Log.timestamp >= today_start)

    totals_result = await db.execute(totals_query)
    totals_row = totals_result.one()

    total_today = totals_row.total_today or 0
    errors_today = totals_row.errors_today or 0
    warnings_today = totals_row.warnings_today or 0

    # Query 2: Get breakdown by level and component using UNION ALL
    # This combines two GROUP BY queries efficiently
    # We use a discriminator column to identify which breakdown type each row is
    breakdown_query = (
        select(
            literal("level").label("breakdown_type"),
            Log.level.label("key"),
            func.count().label("count"),
        )
        .where(Log.timestamp >= today_start)
        .group_by(Log.level)
    ).union_all(
        select(
            literal("component").label("breakdown_type"),
            Log.component.label("key"),
            func.count().label("count"),
        )
        .where(Log.timestamp >= today_start)
        .group_by(Log.component)
        .order_by(func.count().desc())
    )

    breakdown_result = await db.execute(breakdown_query)

    by_level: dict[str, int] = {}
    by_component: dict[str, int] = {}

    for row in breakdown_result:
        # mypy confuses the 'count' column with Row.count() method - ignore the type error
        count_value: int = row.count  # type: ignore[assignment]
        if row.breakdown_type == "level":
            by_level[row.key] = count_value
        else:  # component
            by_component[row.key] = count_value

    # Sort by_component by count descending to get top_component
    by_component = dict(sorted(by_component.items(), key=lambda x: x[1], reverse=True))

    # Top component is the first key after sorting
    top_component = next(iter(by_component.keys())) if by_component else None

    return LogStats(
        total_today=total_today,
        errors_today=errors_today,
        warnings_today=warnings_today,
        by_component=by_component,
        by_level=by_level,
        top_component=top_component,
    )


@router.get(
    "/{log_id}",
    response_model=LogEntry,
    responses={
        404: {"description": "Log entry not found"},
        500: {"description": "Internal server error"},
    },
)
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

    # Type is already narrowed by the None check above
    return log


@router.post(
    "/frontend",
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
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


@router.post(
    "/frontend/batch",
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_frontend_logs_batch(
    batch_data: FrontendLogBatchCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive and store multiple logs from the frontend in a single request.

    This endpoint is optimized for batch log submission to reduce HTTP overhead.
    Maximum 100 log entries per batch.
    """
    # Get default user agent from request
    default_user_agent = request.headers.get("user-agent")

    logs_to_add = []
    for log_data in batch_data.entries:
        user_agent = log_data.user_agent or default_user_agent

        log = Log(
            timestamp=datetime.now(UTC),
            level=log_data.level.upper(),
            component=log_data.component,
            message=log_data.message,
            extra=log_data.extra,
            source="frontend",
            user_agent=user_agent,
        )
        logs_to_add.append(log)

    db.add_all(logs_to_add)
    await db.commit()

    return {"status": "created", "count": len(logs_to_add)}
