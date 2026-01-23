"""Log management API routes.

This module provides endpoints for:
1. Receiving log entries from the frontend (POST /api/logs/frontend)
2. Querying logs from the database (GET /api/logs)
3. Getting log statistics (GET /api/logs/stats)

The frontend logger.ts service sends logs to these endpoints:
- Individual logs via POST /api/logs/frontend
- Batched logs via POST /api/logs/frontend/batch (preferred)

All frontend logs are tagged with:
- component: "frontend" (or the component name provided in the request)
- source: "frontend" (for Loki label filtering)
- url: The browser URL where the log was generated
- user_agent: The browser user agent string

Usage:
    # Single log entry
    POST /api/logs/frontend
    {
        "level": "ERROR",
        "message": "Failed to load dashboard data",
        "component": "Dashboard",
        "extra": {"error_code": "API_TIMEOUT"}
    }

    # Query logs
    GET /api/logs?level=ERROR&component=backend&limit=50

    # Get statistics
    GET /api/logs/stats
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.pagination import (
    CursorData,
    decode_cursor,
    encode_cursor,
    get_deprecation_warning,
    set_deprecation_headers,
)
from backend.api.schemas.logs import (
    FrontendLogBatchRequest,
    FrontendLogEntry,
    FrontendLogResponse,
    LogEntryResponse,
    LogsListResponse,
    LogStats,
)
from backend.api.schemas.pagination import PaginationMeta
from backend.api.validators import normalize_end_date_to_end_of_day, validate_date_range
from backend.core.database import get_db
from backend.core.logging import get_logger, sanitize_log_value
from backend.models.log import Log

logger = get_logger(__name__)

# Dedicated logger for frontend logs - separate from the route handler logger
# This allows different log levels/routing for frontend logs vs route logs
frontend_logger = get_logger("frontend")

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Map frontend log levels to Python logging levels
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _log_frontend_entry(entry: FrontendLogEntry, request: Request | None = None) -> bool:
    """Write a single frontend log entry to structured logging.

    Args:
        entry: The frontend log entry to write
        request: Optional FastAPI request for additional context (user-agent, etc.)

    Returns:
        True if logging succeeded, False otherwise
    """
    try:
        # Build extra context for the log record
        extra: dict[str, str | None] = {
            "source": "frontend",
            "frontend_component": sanitize_log_value(entry.component)
            if entry.component
            else "unknown",
        }

        # Add URL if provided
        if entry.url:
            extra["frontend_url"] = sanitize_log_value(entry.url)

        # Add user agent from request or entry
        if entry.user_agent:
            extra["frontend_user_agent"] = sanitize_log_value(entry.user_agent)
        elif request:
            user_agent = request.headers.get("user-agent")
            if user_agent:
                extra["frontend_user_agent"] = sanitize_log_value(user_agent)

        # Add timestamp if provided (as ISO string for structured logging)
        if entry.timestamp:
            extra["frontend_timestamp"] = entry.timestamp.isoformat()
        else:
            extra["frontend_timestamp"] = datetime.now(UTC).isoformat()

        # Add any additional context from the entry
        if entry.context:
            # Flatten context into extra with prefix to avoid collisions
            for key, value in entry.context.items():
                # Skip None values and limit key length
                if value is not None and len(key) <= 50:
                    sanitized_key = sanitize_log_value(key)
                    # Prefix context keys to distinguish from system fields
                    extra[f"ctx_{sanitized_key}"] = sanitize_log_value(value)

        # Get the Python log level
        log_level = _LOG_LEVEL_MAP.get(entry.level.value, logging.INFO)

        # Sanitize the message to prevent log injection
        sanitized_message = sanitize_log_value(entry.message)

        # Log with the frontend logger
        frontend_logger.log(
            log_level,
            f"[{entry.component or 'frontend'}] {sanitized_message}",
            extra=extra,
        )

        return True

    except Exception as e:
        # Log the error but don't fail the request
        logger.warning(f"Failed to process frontend log entry: {e}")
        return False


@router.post(
    "/frontend",
    response_model=FrontendLogResponse,
    summary="Ingest single frontend log",
    description="Receive a single log entry from the frontend for structured logging.",
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def ingest_frontend_log(
    entry: FrontendLogEntry,
    request: Request,
) -> FrontendLogResponse:
    """Ingest a single frontend log entry.

    Receives a log entry from the frontend and writes it to the structured
    logging infrastructure (Loki). This endpoint is used as a fallback when
    the batch endpoint is not available.

    Args:
        entry: The frontend log entry to ingest
        request: FastAPI request object for additional context

    Returns:
        FrontendLogResponse with ingestion status
    """
    success = _log_frontend_entry(entry, request)

    return FrontendLogResponse(
        success=success,
        count=1 if success else 0,
        message="Successfully ingested 1 log entry" if success else "Failed to ingest log entry",
    )


@router.post(
    "/frontend/batch",
    response_model=FrontendLogResponse,
    summary="Ingest batch of frontend logs",
    description="Receive a batch of log entries from the frontend for structured logging.",
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def ingest_frontend_logs_batch(
    batch: FrontendLogBatchRequest,
    request: Request,
) -> FrontendLogResponse:
    """Ingest a batch of frontend log entries.

    Receives multiple log entries from the frontend and writes them to the
    structured logging infrastructure (Loki). This is the preferred endpoint
    as it reduces API calls and improves performance.

    Args:
        batch: Batch of frontend log entries to ingest
        request: FastAPI request object for additional context

    Returns:
        FrontendLogResponse with ingestion status and count
    """
    success_count = 0
    total_count = len(batch.entries)

    for entry in batch.entries:
        if _log_frontend_entry(entry, request):
            success_count += 1

    # Log summary at debug level
    if success_count < total_count:
        logger.warning(
            f"Frontend log batch partially processed: {success_count}/{total_count} entries"
        )
    else:
        logger.debug(f"Frontend log batch processed: {success_count} entries")

    return FrontendLogResponse(
        success=success_count > 0,
        count=success_count,
        message=f"Successfully ingested {success_count} log entry(ies)"
        if success_count > 0
        else "No log entries were ingested",
    )


# =============================================================================
# Log Query Endpoints (GET /api/logs, GET /api/logs/stats)
# =============================================================================


@router.get(
    "",
    response_model=LogsListResponse,
    summary="List logs with optional filtering",
    description="Query logs with optional filtering by level, component, source, and date range.",
    responses={
        400: {"description": "Invalid date range or cursor"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_logs(  # noqa: PLR0912
    response: Response,
    level: str | None = Query(
        None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    component: str | None = Query(None, description="Filter by component (partial match)"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    source: str | None = Query(None, description="Filter by source (backend, frontend)"),
    search: str | None = Query(None, description="Full-text search on message content"),
    start_date: datetime | None = Query(None, description="Filter from date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter to date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of results to skip (deprecated, use cursor)"),
    cursor: str | None = Query(None, description="Pagination cursor from previous response"),
    include_total_count: bool = Query(
        False,
        description="Include total count in response. Defaults to False for performance.",
    ),
    db: AsyncSession = Depends(get_db),
) -> LogsListResponse:
    """List logs with optional filtering and cursor-based pagination.

    This endpoint returns logs from the database with optional filtering by level,
    component, camera, source, search text, and date range.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.

    Args:
        level: Optional log level to filter by
        component: Optional component name to filter by (partial match)
        camera_id: Optional camera ID to filter by
        source: Optional source to filter by (backend/frontend)
        search: Optional full-text search on message content
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field
        include_total_count: Whether to calculate total count (default False for performance)
        db: Database session

    Returns:
        LogsListResponse containing filtered logs and pagination info

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
    query = select(Log)

    # Normalize end_date to end of day if it's at midnight (date-only input)
    normalized_end_date = normalize_end_date_to_end_of_day(end_date)

    # Apply filters
    if level:
        query = query.where(Log.level == level.upper())
    if component:
        # Use partial match (contains) for component filtering
        query = query.where(Log.component.ilike(f"%{component}%"))
    if camera_id:
        query = query.where(Log.camera_id == camera_id)
    if source:
        query = query.where(Log.source == source.lower())
    if start_date:
        query = query.where(Log.timestamp >= start_date)
    if normalized_end_date:
        query = query.where(Log.timestamp <= normalized_end_date)
    if search:
        # Use PostgreSQL full-text search on the search_vector column
        # The search_vector includes message, component, and level
        query = query.where(Log.search_vector.match(search))

    # Apply cursor-based pagination filter (takes precedence over offset)
    if cursor_data:
        # For descending order by timestamp, we want records where:
        # - timestamp < cursor's created_at, OR
        # - timestamp == cursor's created_at AND id < cursor's id (tie-breaker)
        query = query.where(
            (Log.timestamp < cursor_data.created_at)
            | ((Log.timestamp == cursor_data.created_at) & (Log.id < cursor_data.id))
        )

    # Get total count only when explicitly requested
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

    # Get deprecation warning if using offset without cursor
    deprecation_warning = get_deprecation_warning(cursor, offset)

    # Set HTTP Deprecation headers per IETF standard
    set_deprecation_headers(response, cursor, offset)

    return LogsListResponse(
        items=[LogEntryResponse.model_validate(log) for log in logs],
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
    response_model=LogStats,
    summary="Get log statistics",
    description="Get aggregated log statistics for the dashboard.",
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_log_stats(
    db: AsyncSession = Depends(get_db),
) -> LogStats:
    """Get log statistics for the dashboard.

    Returns aggregated statistics about logs including:
    - Total logs today
    - Errors today
    - Warnings today
    - Breakdown by component
    - Top component

    This endpoint uses a single aggregation query with UNION ALL for optimal
    performance, similar to the audit stats endpoint.

    Args:
        db: Database session

    Returns:
        LogStats with aggregated statistics
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Single aggregation query using UNION ALL to get all stats in one round-trip
    # Query structure:
    # - category='total': total logs today
    # - category='errors': error count today
    # - category='warnings': warning count today
    # - category='component': breakdown by component

    # Total logs today
    total_subq = select(
        literal("total").label("category"),
        literal("all").label("key"),
        func.count().label("count"),
    ).where(Log.timestamp >= today_start)

    # Errors today
    errors_subq = select(
        literal("errors").label("category"),
        literal("all").label("key"),
        func.count().label("count"),
    ).where(Log.timestamp >= today_start, Log.level == "ERROR")

    # Warnings today
    warnings_subq = select(
        literal("warnings").label("category"),
        literal("all").label("key"),
        func.count().label("count"),
    ).where(Log.timestamp >= today_start, Log.level == "WARNING")

    # By component (today, limit to top 20)
    component_subq = (
        select(
            literal("component").label("category"),
            Log.component.label("key"),
            func.count().label("count"),
        )
        .where(Log.timestamp >= today_start)
        .group_by(Log.component)
    )

    # Combine all queries with UNION ALL
    combined_query = union_all(
        total_subq,
        errors_subq,
        warnings_subq,
        component_subq,
    )

    result = await db.execute(combined_query)
    rows = result.fetchall()

    # Parse the combined results
    total_today = 0
    errors_today = 0
    warnings_today = 0
    by_component: dict[str, int] = {}

    for row in rows:
        category: str = row[0]
        key: str = row[1]
        count: int = int(row[2])
        if category == "total":
            total_today = count
        elif category == "errors":
            errors_today = count
        elif category == "warnings":
            warnings_today = count
        elif category == "component":
            by_component[key] = count

    # Determine top component (by count)
    top_component: str | None = None
    if by_component:
        top_component = max(by_component, key=by_component.get)  # type: ignore[arg-type]

    return LogStats(
        errors_today=errors_today,
        warnings_today=warnings_today,
        total_today=total_today,
        top_component=top_component,
        by_component=by_component,
    )
