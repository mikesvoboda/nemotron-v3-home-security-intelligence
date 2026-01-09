"""API routes for events management."""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.api.dependencies import get_cache_service_dep, get_event_or_404
from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier
from backend.api.pagination import CursorData, decode_cursor, encode_cursor, get_deprecation_warning
from backend.api.schemas.bulk import (
    BulkOperationResponse,
    BulkOperationStatus,
    EventBulkCreateRequest,
    EventBulkCreateResponse,
    EventBulkDeleteRequest,
    EventBulkUpdateRequest,
)
from backend.api.schemas.clips import (
    ClipGenerateRequest,
    ClipGenerateResponse,
    ClipInfoResponse,
)
from backend.api.schemas.detections import DetectionListResponse
from backend.api.schemas.enrichment import EventEnrichmentsResponse
from backend.api.schemas.events import (
    DeletedEventsListResponse,
    EventListResponse,
    EventResponse,
    EventStatsResponse,
    EventUpdate,
)
from backend.api.schemas.hateoas import build_event_links
from backend.api.schemas.search import SearchResponse as SearchResponseSchema
from backend.api.utils.field_filter import (
    FieldFilterError,
    filter_fields,
    parse_fields_param,
    validate_fields,
)
from backend.api.validators import validate_date_range
from backend.core.database import escape_ilike_pattern, get_db
from backend.core.logging import get_logger, sanitize_log_value
from backend.core.metrics import record_event_reviewed
from backend.core.sanitization import sanitize_error_for_response
from backend.core.telemetry import get_trace_id
from backend.models.audit import AuditAction
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.audit import AuditService
from backend.services.batch_fetch import batch_fetch_detections, batch_fetch_file_paths
from backend.services.cache_service import SHORT_TTL, CacheKeys, CacheService
from backend.services.event_service import get_event_service
from backend.services.search import SearchFilters, search_events

logger = get_logger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])

# Valid severity values for search filter
VALID_SEVERITY_VALUES = frozenset({"low", "medium", "high", "critical"})

# Valid fields for sparse fieldsets on list_events endpoint (NEM-1434)
VALID_EVENT_LIST_FIELDS = frozenset(
    {
        "id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "reviewed",
        "detection_count",
        "detection_ids",
        "thumbnail_url",
    }
)


def parse_detection_ids(detection_ids_str: str | None) -> list[int]:
    """Parse detection IDs stored as JSON array to list of integers.

    Args:
        detection_ids_str: JSON array string of detection IDs (e.g., "[1, 2, 3]")
                          or None/empty string

    Returns:
        List of integer detection IDs. Empty list if input is None or empty.
    """
    if not detection_ids_str:
        return []
    try:
        ids = json.loads(detection_ids_str)
        if isinstance(ids, list):
            return [int(d) for d in ids]
        return []
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy comma-separated format
        return [int(d.strip()) for d in detection_ids_str.split(",") if d.strip()]


def get_detection_ids_from_event(event: Event) -> list[int]:
    """Get detection IDs using the Event.detections relationship or fallback to legacy column.

    This function provides a migration path from the legacy detection_ids text column
    to the normalized event_detections junction table. It prefers the relationship
    but falls back to parsing the legacy column if the relationship is not populated.

    Args:
        event: Event model instance

    Returns:
        List of detection IDs associated with the event
    """
    # Try the relationship first (normalized data from event_detections table)
    if event.detections:
        return event.detection_id_list

    # Fallback to legacy column for events not yet migrated to junction table
    return parse_detection_ids(event.detection_ids)


def parse_severity_filter(severity_str: str | None) -> list[str]:
    """Parse and validate severity filter parameter.

    Args:
        severity_str: Comma-separated severity values (e.g., "high,critical")
                      or None for no filter

    Returns:
        List of validated severity values

    Raises:
        HTTPException: 400 if any severity value is invalid
    """
    if not severity_str:
        return []

    severity_levels = [s.strip().lower() for s in severity_str.split(",") if s.strip()]

    # Validate all severity values
    invalid_values = [s for s in severity_levels if s not in VALID_SEVERITY_VALUES]
    if invalid_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity value(s): {', '.join(invalid_values)}. "
            f"Valid values are: {', '.join(sorted(VALID_SEVERITY_VALUES))}",
        )

    return severity_levels


# Characters that can trigger formula injection in spreadsheet applications
# These characters at the start of a cell can execute formulas when opened in
# Excel, LibreOffice Calc, Google Sheets, or other spreadsheet applications.
CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_value(value: str | None) -> str:
    """Sanitize a value for safe CSV export to prevent formula injection.

    CSV injection (also known as formula injection) occurs when data
    exported to CSV is opened in spreadsheet applications. Cells starting
    with certain characters (=, +, -, @, tab, carriage return) can be
    interpreted as formulas, potentially executing malicious code.

    This function prefixes dangerous values with a single quote (')
    which tells spreadsheet applications to treat the cell as text.

    Reference:
    - OWASP CSV Injection: https://owasp.org/www-community/attacks/CSV_Injection

    Args:
        value: The string value to sanitize, or None

    Returns:
        The sanitized string value. Returns empty string if value is None.

    Examples:
        >>> sanitize_csv_value("=HYPERLINK(...)")
        "'=HYPERLINK(...)"
        >>> sanitize_csv_value("Normal text")
        "Normal text"
        >>> sanitize_csv_value(None)
        ""
    """
    if value is None:
        return ""

    if not value:
        return value

    # Check if the first character is a dangerous injection prefix
    if value[0] in CSV_INJECTION_PREFIXES:
        return f"'{value}"

    return value


@router.get("", response_model=EventListResponse)
async def list_events(  # noqa: PLR0912
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    risk_level: str | None = Query(
        None, description="Filter by risk level (low, medium, high, critical)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    object_type: str | None = Query(None, description="Filter by detected object type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip (deprecated, use cursor)"),
    cursor: str | None = Query(None, description="Pagination cursor from previous response"),
    fields: str | None = Query(
        None,
        description="Comma-separated list of fields to include in response (sparse fieldsets). "
        "Valid fields: id, camera_id, started_at, ended_at, risk_score, risk_level, summary, "
        "reasoning, reviewed, detection_count, detection_ids, thumbnail_url",
    ),
    db: AsyncSession = Depends(get_db),
) -> EventListResponse:
    """List events with optional filtering and cursor-based pagination.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.

    Sparse Fieldsets (NEM-1434):
    Use the `fields` parameter to request only specific fields in the response,
    reducing payload size. Example: ?fields=id,camera_id,risk_level,summary,reviewed

    Args:
        camera_id: Optional camera ID to filter by
        risk_level: Optional risk level to filter by (low, medium, high, critical)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        reviewed: Optional filter by reviewed status
        object_type: Optional object type to filter by (person, vehicle, animal, etc.)
        limit: Maximum number of results to return (1-100, default 50)
        offset: Number of results to skip (deprecated, use cursor instead)
        cursor: Pagination cursor from previous response's next_cursor field
        fields: Comma-separated list of fields to include (sparse fieldsets)
        db: Database session

    Returns:
        EventListResponse containing filtered events and pagination info

    Raises:
        HTTPException: 400 if start_date is after end_date
        HTTPException: 400 if cursor is invalid
        HTTPException: 400 if invalid fields are requested
    """
    # NEM-1503: Include trace_id in logs for distributed tracing correlation
    trace_id = get_trace_id()
    if trace_id:
        logger.debug(
            "Listing events",
            extra={
                "trace_id": trace_id,
                "camera_id": camera_id,
                "risk_level": risk_level,
                "limit": limit,
            },
        )

    # Validate date range
    validate_date_range(start_date, end_date)

    # Parse and validate fields parameter for sparse fieldsets (NEM-1434)
    requested_fields = parse_fields_param(fields)
    try:
        validated_fields = validate_fields(requested_fields, set(VALID_EVENT_LIST_FIELDS))
    except FieldFilterError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

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

    # Build base query with eager loading for camera relationship (NEM-1619)
    query = select(Event).options(joinedload(Event.camera))

    # Apply filters
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if risk_level:
        query = query.where(Event.risk_level == risk_level)
    if start_date:
        query = query.where(Event.started_at >= start_date)
    if end_date:
        query = query.where(Event.started_at <= end_date)
    if reviewed is not None:
        query = query.where(Event.reviewed == reviewed)

    # Filter by object type - use the cached object_types column on Event
    # This column stores comma-separated object types from related detections
    # We use SQL LIKE for efficient database-side filtering
    if object_type:
        # Escape LIKE wildcard characters to prevent pattern injection
        safe_object_type = escape_ilike_pattern(object_type)
        # Use SQL LIKE to find events with matching object types
        # The object_types column is comma-separated, so we check for:
        # - Exact match at start: "person,..."
        # - Match in middle: "...,person,..."
        # - Exact match at end: "...,person"
        # - Exact single value: "person"
        query = query.where(
            (Event.object_types == object_type)
            | (Event.object_types.like(f"{safe_object_type},%"))
            | (Event.object_types.like(f"%,{safe_object_type},%"))
            | (Event.object_types.like(f"%,{safe_object_type}"))
        )

    # Apply cursor-based pagination filter (takes precedence over offset)
    if cursor_data:
        # For descending order by started_at, we want records where:
        # - started_at < cursor's started_at, OR
        # - started_at == cursor's started_at AND id < cursor's id (tie-breaker)
        query = query.where(
            (Event.started_at < cursor_data.created_at)
            | ((Event.started_at == cursor_data.created_at) & (Event.id < cursor_data.id))
        )

    # Get total count (before pagination) - only when not using cursor
    # With cursor pagination, total count becomes expensive and less meaningful
    total_count: int = 0
    if not cursor_data:
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

    # Sort by started_at descending (newest first), then by id descending for consistency
    query = query.order_by(Event.started_at.desc(), Event.id.desc())

    # Apply pagination - fetch one extra to determine if there are more results
    # Use explicit if/else for readability (clearer than ternary with complex expressions)
    if cursor_data:  # noqa: SIM108
        # Cursor-based: fetch limit + 1 to check for more
        query = query.limit(limit + 1)
    else:
        # Offset-based (deprecated): apply offset
        query = query.limit(limit + 1).offset(offset)

    # Execute query
    result = await db.execute(query)
    events = list(result.scalars().all())

    # Determine if there are more results
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]  # Trim to requested limit

    # Calculate detection count and parse detection_ids for each event
    events_with_counts = []
    for event in events:
        # Parse detection_ids (JSON array string) to list of integers
        parsed_detection_ids = get_detection_ids_from_event(event)
        detection_count = len(parsed_detection_ids)

        # Compute thumbnail_url from first detection ID
        thumbnail_url = (
            f"/api/media/detections/{parsed_detection_ids[0]}" if parsed_detection_ids else None
        )

        # Create response with detection count and detection_ids
        event_dict = {
            "id": event.id,
            "camera_id": event.camera_id,
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "summary": event.summary,
            "reasoning": event.reasoning,
            "reviewed": event.reviewed,
            "detection_count": detection_count,
            "detection_ids": parsed_detection_ids,
            "thumbnail_url": thumbnail_url,
        }
        # Apply sparse fieldsets filter if fields parameter was provided (NEM-1434)
        filtered_event = filter_fields(event_dict, validated_fields)
        events_with_counts.append(filtered_event)

    # Generate next cursor from the last event
    next_cursor: str | None = None
    if has_more and events:
        last_event = events[-1]
        cursor_data_next = CursorData(id=last_event.id, created_at=last_event.started_at)
        next_cursor = encode_cursor(cursor_data_next)

    # Get deprecation warning if using offset without cursor
    deprecation_warning = get_deprecation_warning(cursor, offset)

    return EventListResponse(
        events=events_with_counts,
        count=total_count,
        limit=limit,
        offset=offset,
        next_cursor=next_cursor,
        has_more=has_more,
        deprecation_warning=deprecation_warning,
    )


@router.get("/stats", response_model=EventStatsResponse)
async def get_event_stats(
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> EventStatsResponse:
    """Get aggregated event statistics.

    Returns statistics about events including:
    - Total event count
    - Events grouped by risk level (critical, high, medium, low)
    - Events grouped by camera with camera names

    Uses Redis cache with cache-aside pattern to improve performance
    and generate cache hit metrics.

    Args:
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        db: Database session
        cache: Cache service injected via FastAPI DI

    Returns:
        EventStatsResponse with aggregated statistics

    Raises:
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    validate_date_range(start_date, end_date)

    # Generate cache key based on date filters
    # Check isinstance() to handle case when tests pass Query objects directly
    start_str = start_date.isoformat() if isinstance(start_date, datetime) else None
    end_str = end_date.isoformat() if isinstance(end_date, datetime) else None
    cache_key = CacheKeys.event_stats(start_str, end_str)

    # Try cache first
    try:
        cached_data = await cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Returning cached event stats for dates={start_str}:{end_str}")
            # Cast to expected type - cache stores dict[str, Any]
            return EventStatsResponse(**dict(cached_data))
    except Exception as e:
        logger.warning(f"Cache read failed, falling back to database: {e}")

    # Build date filter conditions (reused across queries)
    date_filters = []
    if start_date:
        date_filters.append(Event.started_at >= start_date)
    if end_date:
        date_filters.append(Event.started_at <= end_date)

    # Get total count using database aggregation
    total_count_query = select(func.count()).select_from(Event)
    for condition in date_filters:
        total_count_query = total_count_query.where(condition)
    total_count_result = await db.execute(total_count_query)
    total_events = total_count_result.scalar() or 0

    # Get events by risk level using SQL GROUP BY
    risk_level_query = select(Event.risk_level, func.count().label("count")).group_by(
        Event.risk_level
    )
    for condition in date_filters:
        risk_level_query = risk_level_query.where(condition)
    risk_level_result = await db.execute(risk_level_query)
    risk_level_rows = risk_level_result.all()

    # Initialize with zeros and populate from query results
    risk_level_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    for risk_level, count in risk_level_rows:
        if risk_level and risk_level in risk_level_counts:
            risk_level_counts[risk_level] = count

    # Get events by camera using SQL GROUP BY with JOIN to get camera names
    camera_stats_query = (
        select(Event.camera_id, Camera.name.label("camera_name"), func.count().label("event_count"))
        .join(Camera, Event.camera_id == Camera.id, isouter=True)
        .group_by(Event.camera_id, Camera.name)
        .order_by(func.count().desc())
    )
    for condition in date_filters:
        camera_stats_query = camera_stats_query.where(condition)
    camera_stats_result = await db.execute(camera_stats_query)
    camera_stats_rows = camera_stats_result.all()

    # Build events_by_camera list from query results
    events_by_camera = [
        {
            "camera_id": camera_id,
            "camera_name": camera_name or "Unknown",
            "event_count": event_count,
        }
        for camera_id, camera_name, event_count in camera_stats_rows
    ]

    response = {
        "total_events": total_events,
        "events_by_risk_level": risk_level_counts,
        "events_by_camera": events_by_camera,
    }

    # Cache the result
    try:
        await cache.set(cache_key, response, ttl=SHORT_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    return EventStatsResponse(**response)


@router.get("/search", response_model=SearchResponseSchema)
async def search_events_endpoint(
    q: str = Query(..., min_length=1, description="Search query string"),
    camera_id: str | None = Query(
        None, description="Filter by camera ID (comma-separated for multiple)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    severity: str | None = Query(
        None, description="Filter by risk levels (comma-separated: low,medium,high,critical)"
    ),
    risk_level: str | None = Query(
        None,
        description="Alias for severity - filter by risk levels "
        "(comma-separated: low,medium,high,critical)",
    ),
    object_type: str | None = Query(
        None, description="Filter by object types (comma-separated: person,vehicle,animal)"
    ),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponseSchema:
    """Search events using full-text search.

    This endpoint provides PostgreSQL full-text search across event summaries,
    reasoning, object types, and camera names.

    Search Query Syntax:
    - Basic words: "person vehicle" (implicit AND)
    - Phrase search: '"suspicious person"' (exact phrase)
    - Boolean OR: "person OR animal"
    - Boolean NOT: "person NOT cat"
    - Boolean AND: "person AND vehicle" (explicit)

    Args:
        q: Search query string (required)
        camera_id: Optional comma-separated camera IDs to filter by
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        severity: Optional comma-separated risk levels (low, medium, high, critical)
        risk_level: Alias for severity - accepts same format
        object_type: Optional comma-separated object types (person, vehicle, animal)
        reviewed: Optional filter by reviewed status
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        SearchResponse with ranked results and pagination info

    Raises:
        HTTPException: 400 if any severity value is invalid
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    validate_date_range(start_date, end_date)

    # Parse comma-separated filter values with validation
    camera_ids = [c.strip() for c in camera_id.split(",")] if camera_id else []
    # Support both 'severity' and 'risk_level' parameters for consistency with list_events
    # If both are provided, 'severity' takes precedence (maintains backward compatibility)
    severity_param = severity or risk_level
    severity_levels = parse_severity_filter(severity_param)  # Validates severity values
    object_types = [o.strip() for o in object_type.split(",")] if object_type else []

    # Build filters
    filters = SearchFilters(
        start_date=start_date,
        end_date=end_date,
        camera_ids=camera_ids,
        severity=severity_levels,
        object_types=object_types,
        reviewed=reviewed,
    )

    # Execute search
    search_response = await search_events(
        db=db,
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    # Convert to dict for response
    return SearchResponseSchema(
        results=[
            {
                "id": r.id,
                "camera_id": r.camera_id,
                "camera_name": r.camera_name,
                "started_at": r.started_at,
                "ended_at": r.ended_at,
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
                "summary": r.summary,
                "reasoning": r.reasoning,
                "reviewed": r.reviewed,
                "detection_count": r.detection_count,
                "detection_ids": r.detection_ids,
                "object_types": r.object_types,
                "relevance_score": r.relevance_score,
            }
            for r in search_response.results
        ],
        total_count=search_response.total_count,
        limit=search_response.limit,
        offset=search_response.offset,
    )


@router.get("/export")
async def export_events(
    request: Request,
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    risk_level: str | None = Query(
        None, description="Filter by risk level (low, medium, high, critical)"
    ),
    start_date: datetime | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: datetime | None = Query(None, description="Filter by end date (ISO format)"),
    reviewed: bool | None = Query(None, description="Filter by reviewed status"),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.EXPORT)),
) -> StreamingResponse:
    """Export events as CSV file for external analysis or record-keeping.

    This endpoint is rate-limited to 10 requests per minute per client IP
    to prevent abuse and protect against data exfiltration attacks.

    Exports events with the following fields:
    - Event ID, camera name, timestamps
    - Risk score, risk level, summary
    - Detection count, reviewed status

    Args:
        request: FastAPI request object
        camera_id: Optional camera ID to filter by
        risk_level: Optional risk level to filter by (low, medium, high, critical)
        start_date: Optional start date for date range filter
        end_date: Optional end date for date range filter
        reviewed: Optional filter by reviewed status
        db: Database session
        _rate_limit: Rate limiter dependency (10 req/min, no burst)

    Returns:
        StreamingResponse with CSV file containing exported events

    Raises:
        HTTPException: 429 if rate limit exceeded
        HTTPException: 400 if start_date is after end_date
    """
    # Validate date range
    validate_date_range(start_date, end_date)

    # Build base query
    query = select(Event)

    # Apply filters
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if risk_level:
        query = query.where(Event.risk_level == risk_level)
    if start_date:
        query = query.where(Event.started_at >= start_date)
    if end_date:
        query = query.where(Event.started_at <= end_date)
    if reviewed is not None:
        query = query.where(Event.reviewed == reviewed)

    # Sort by started_at descending (newest first)
    query = query.order_by(Event.started_at.desc())

    # Execute query
    result = await db.execute(query)
    events = result.scalars().all()

    # Get all camera IDs to fetch camera names
    camera_ids = {event.camera_id for event in events}
    camera_query = select(Camera).where(Camera.id.in_(camera_ids))
    camera_result = await db.execute(camera_query)
    cameras = {camera.id: camera.name for camera in camera_result.scalars().all()}

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "event_id",
            "camera_name",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "detection_count",
            "reviewed",
        ]
    )

    # Write event rows
    for event in events:
        camera_name = cameras.get(event.camera_id, "Unknown")
        detection_count = len(get_detection_ids_from_event(event))

        # Format timestamps as ISO strings
        started_at_str = event.started_at.isoformat() if event.started_at else ""
        ended_at_str = event.ended_at.isoformat() if event.ended_at else ""

        # Sanitize string fields to prevent CSV injection attacks
        # Fields that could contain user-influenced data must be sanitized
        safe_camera_name = sanitize_csv_value(camera_name)
        safe_summary = sanitize_csv_value(event.summary)
        safe_risk_level = sanitize_csv_value(event.risk_level)

        writer.writerow(
            [
                event.id,
                safe_camera_name,
                started_at_str,
                ended_at_str,
                event.risk_score if event.risk_score is not None else "",
                safe_risk_level,
                safe_summary,
                detection_count,
                "Yes" if event.reviewed else "No",
            ]
        )

    # Generate filename with timestamp
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"events_export_{timestamp}.csv"

    # Log the export action
    try:
        await AuditService.log_action(
            db=db,
            action=AuditAction.MEDIA_EXPORTED,
            resource_type="event",
            actor="anonymous",
            details={
                "export_type": "csv",
                "filters": {
                    "camera_id": camera_id,
                    "risk_level": risk_level,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "reviewed": reviewed,
                },
                "event_count": len(events),
                "filename": filename,
            },
            request=request,
        )
        await db.commit()
    except Exception:
        logger.error(
            "Failed to commit audit log", exc_info=True, extra={"action": "events_exported"}
        )
        await db.rollback()
        # Don't fail the main operation - audit is non-critical

    # Return as streaming response with CSV content type
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """Get a specific event by ID with HATEOAS links.

    Args:
        event_id: Event ID
        request: FastAPI request object for building HATEOAS links
        db: Database session

    Returns:
        Event object with detection count and HATEOAS links

    Raises:
        HTTPException: 404 if event not found
    """
    event = await get_event_or_404(event_id, db)

    # Parse detection_ids and calculate count
    parsed_detection_ids = get_detection_ids_from_event(event)
    detection_count = len(parsed_detection_ids)

    # Compute thumbnail_url from first detection ID
    thumbnail_url = (
        f"/api/media/detections/{parsed_detection_ids[0]}" if parsed_detection_ids else None
    )

    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        notes=event.notes,
        detection_count=detection_count,
        detection_ids=parsed_detection_ids,
        thumbnail_url=thumbnail_url,
        links=build_event_links(request, event.id, event.camera_id),
    )


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    update_data: EventUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> EventResponse:
    """Update an event (mark as reviewed).

    Args:
        event_id: Event ID
        update_data: Update data (reviewed field)
        request: FastAPI request for audit logging
        db: Database session
        cache: Cache service for cache invalidation (NEM-1938)

    Returns:
        Updated event object

    Raises:
        HTTPException: 404 if event not found
    """
    event = await get_event_or_404(event_id, db)

    # Track changes for audit log
    changes: dict[str, Any] = {}
    old_reviewed = event.reviewed
    old_notes = event.notes

    # Update fields if provided (use exclude_unset to differentiate between None and not provided)
    update_dict = update_data.model_dump(exclude_unset=True)
    if "reviewed" in update_dict and update_data.reviewed is not None:
        event.reviewed = update_data.reviewed
        if old_reviewed != event.reviewed:
            changes["reviewed"] = {"old": old_reviewed, "new": event.reviewed}
    if "notes" in update_dict:
        event.notes = update_data.notes
        if old_notes != event.notes:
            changes["notes"] = {"old": old_notes, "new": event.notes}

    # Determine audit action based on changes
    if changes.get("reviewed", {}).get("new") is True:
        action = AuditAction.EVENT_REVIEWED
        # Record events reviewed metric for Prometheus (NEM-770)
        try:
            record_event_reviewed()
        except Exception as e:
            # Log but don't fail the request - metrics are non-critical
            logger.warning(f"Failed to record event_reviewed metric: {e}")
    elif changes.get("reviewed", {}).get("new") is False:
        action = AuditAction.EVENT_DISMISSED
    else:
        action = AuditAction.EVENT_REVIEWED  # Default for notes-only updates

    # Log the audit entry
    try:
        await AuditService.log_action(
            db=db,
            action=action,
            resource_type="event",
            resource_id=str(event_id),
            actor="anonymous",  # No auth in this system
            details={
                "changes": changes,
                "risk_level": event.risk_level,
                "camera_id": event.camera_id,
            },
            request=request,
        )
        await db.commit()
    except Exception:
        logger.error(
            "Failed to commit audit log",
            exc_info=True,
            extra={"action": "event_updated", "event_id": event_id},
        )
        await db.rollback()
        # Re-apply the event changes since we rolled back
        update_data_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_data_dict.items():
            setattr(event, key, value)
        await db.commit()
    await db.refresh(event)

    # Invalidate event-related caches after successful update (NEM-1950, NEM-1938)
    try:
        await cache.invalidate_events(reason="event_updated")
        await cache.invalidate_event_stats(reason="event_updated")
    except Exception as e:
        # Cache invalidation is non-critical - log but don't fail the request
        logger.warning(f"Cache invalidation failed after event update: {e}")

    # Parse detection_ids and calculate count
    parsed_detection_ids = get_detection_ids_from_event(event)
    detection_count = len(parsed_detection_ids)

    # Compute thumbnail_url from first detection ID
    thumbnail_url = (
        f"/api/media/detections/{parsed_detection_ids[0]}" if parsed_detection_ids else None
    )

    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        started_at=event.started_at,
        ended_at=event.ended_at,
        risk_score=event.risk_score,
        risk_level=event.risk_level,
        summary=event.summary,
        reasoning=event.reasoning,
        reviewed=event.reviewed,
        notes=event.notes,
        detection_count=detection_count,
        detection_ids=parsed_detection_ids,
        thumbnail_url=thumbnail_url,
    )


@router.get("/{event_id}/detections", response_model=DetectionListResponse)
async def get_event_detections(
    event_id: int,
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> DetectionListResponse:
    """Get detections for a specific event.

    Args:
        event_id: Event ID
        limit: Maximum number of results to return (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        db: Database session

    Returns:
        DetectionListResponse containing detections for the event

    Raises:
        HTTPException: 404 if event not found
    """
    event = await get_event_or_404(event_id, db)

    # Parse detection_ids using helper function
    detection_ids = get_detection_ids_from_event(event)

    # If no detections, return empty list
    if not detection_ids:
        return DetectionListResponse(
            detections=[],
            count=0,
            limit=limit,
            offset=offset,
        )

    # Build query for detections
    query = select(Detection).where(Detection.id.in_(detection_ids))

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Sort by detected_at ascending (chronological order within event)
    query = query.order_by(Detection.detected_at.asc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    detections = result.scalars().all()

    return DetectionListResponse(
        detections=detections,
        count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}/enrichments", response_model=EventEnrichmentsResponse)
async def get_event_enrichments(
    event_id: int,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of enrichments to return"),
    offset: int = Query(0, ge=0, description="Number of enrichments to skip"),
    db: AsyncSession = Depends(get_db),
) -> EventEnrichmentsResponse:
    """Get enrichment data for detections in an event with pagination.

    Returns structured vision model results from the enrichment pipeline for
    each detection in the event. Results include:
    - License plate detection and OCR
    - Face detection
    - Vehicle classification and damage detection
    - Clothing analysis (FashionCLIP and SegFormer)
    - Violence detection
    - Image quality assessment
    - Pet classification

    Args:
        event_id: Event ID
        limit: Maximum number of enrichments to return (1-200, default 50)
        offset: Number of enrichments to skip (default 0)
        db: Database session

    Returns:
        EventEnrichmentsResponse with enrichment data for each detection and pagination metadata

    Raises:
        HTTPException: 404 if event not found
    """
    # Import transform function from detections route
    from backend.api.routes.detections import _transform_enrichment_data

    event = await get_event_or_404(event_id, db)

    # Parse detection_ids using helper function
    detection_ids = get_detection_ids_from_event(event)
    total = len(detection_ids)

    # If no detections, return empty response with pagination metadata
    if not detection_ids:
        return EventEnrichmentsResponse(
            event_id=event.id,
            enrichments=[],
            count=0,
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
        )

    # Apply pagination to detection_ids before querying
    # This ensures we only fetch the detections we need
    paginated_detection_ids = detection_ids[offset : offset + limit]

    # If offset is beyond available detections, return empty with metadata
    if not paginated_detection_ids:
        return EventEnrichmentsResponse(
            event_id=event.id,
            enrichments=[],
            count=0,
            total=total,
            limit=limit,
            offset=offset,
            has_more=False,
        )

    # Get detections for this page using batch fetching
    # This handles potential PostgreSQL IN clause limits for large detection lists
    detections = await batch_fetch_detections(db, paginated_detection_ids)

    # Transform each detection's enrichment data
    enrichments = [
        _transform_enrichment_data(
            detection_id=det.id,
            enrichment_data=det.enrichment_data,
            detected_at=det.detected_at,
        )
        for det in detections
    ]

    # Calculate has_more based on total and current position
    has_more = offset + len(enrichments) < total

    return EventEnrichmentsResponse(
        event_id=event.id,
        enrichments=enrichments,
        count=len(enrichments),
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get("/{event_id}/clip", response_model=ClipInfoResponse)
async def get_event_clip(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> ClipInfoResponse:
    """Get clip information for a specific event.

    Returns information about whether a video clip is available for the event,
    and if so, provides the URL to access it along with metadata.

    Args:
        event_id: Event ID
        db: Database session

    Returns:
        ClipInfoResponse with clip availability and metadata

    Raises:
        HTTPException: 404 if event not found
    """
    from pathlib import Path

    event = await get_event_or_404(event_id, db)

    # Check if clip exists
    if not event.clip_path:
        return ClipInfoResponse(
            event_id=event.id,
            clip_available=False,
            clip_url=None,
            duration_seconds=None,
            generated_at=None,
            file_size_bytes=None,
        )

    # Check if clip file actually exists on disk
    clip_path = Path(event.clip_path)
    if not clip_path.exists():
        logger.warning(f"Clip path in DB but file missing: {event.clip_path}")
        return ClipInfoResponse(
            event_id=event.id,
            clip_available=False,
            clip_url=None,
            duration_seconds=None,
            generated_at=None,
            file_size_bytes=None,
        )

    # Get file stats
    file_stat = clip_path.stat()
    file_size = file_stat.st_size
    generated_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)

    # Calculate duration from event timestamps
    duration_seconds = None
    if event.started_at and event.ended_at:
        duration_seconds = int((event.ended_at - event.started_at).total_seconds())

    # Build clip URL using the clip filename
    clip_filename = clip_path.name
    clip_url = f"/api/media/clips/{clip_filename}"

    return ClipInfoResponse(
        event_id=event.id,
        clip_available=True,
        clip_url=clip_url,
        duration_seconds=duration_seconds,
        generated_at=generated_at,
        file_size_bytes=file_size,
    )


@router.post(
    "/{event_id}/clip/generate",
    response_model=ClipGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Clip already exists", "model": ClipGenerateResponse},
        201: {"description": "Clip created successfully", "model": ClipGenerateResponse},
        400: {"description": "Cannot generate clip - event has no detections"},
        404: {"description": "Event not found"},
    },
)
async def generate_event_clip(
    event_id: int,
    request: ClipGenerateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ClipGenerateResponse:
    """Trigger video clip generation for an event.

    If a clip already exists and force=False, returns the existing clip info.
    If force=True, regenerates the clip even if one exists.

    Clip generation uses detection images to create a video sequence, or
    extracts from existing video if available.

    Args:
        event_id: Event ID
        request: Clip generation parameters
        db: Database session

    Returns:
        ClipGenerateResponse with generation status and clip info

    Raises:
        HTTPException: 404 if event not found
        HTTPException: 400 if event has no detections to generate clip from
    """
    from pathlib import Path

    from backend.api.schemas.clips import ClipGenerateResponse, ClipStatus
    from backend.services.clip_generator import get_clip_generator

    event = await get_event_or_404(event_id, db)

    # Check if clip already exists and force is False
    if event.clip_path and not request.force:
        clip_path = Path(event.clip_path)
        if clip_path.exists():
            file_stat = clip_path.stat()
            generated_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)
            clip_filename = clip_path.name
            clip_url = f"/api/media/clips/{clip_filename}"

            # Return 200 OK for existing clip (not creating a new resource)
            response.status_code = status.HTTP_200_OK
            return ClipGenerateResponse(
                event_id=event.id,
                status=ClipStatus.COMPLETED,
                clip_url=clip_url,
                generated_at=generated_at,
                message="Clip already exists",
            )

    # Check if event has detections
    detection_ids = get_detection_ids_from_event(event)
    if not detection_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate clip: event has no detections",
        )

    # Get detection file paths using batch fetching to handle large detection lists
    # This avoids N+1 queries and handles potential PostgreSQL IN clause limits
    file_paths = await batch_fetch_file_paths(db, detection_ids)

    if not file_paths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate clip: no detection images available",
        )

    # Delete existing clip if force regeneration
    clip_generator = get_clip_generator()
    if request.force and event.clip_path:
        clip_generator.delete_clip(event.id)

    # Generate clip from detection images
    try:
        generated_clip_path = await clip_generator.generate_clip_from_images(
            event=event,
            image_paths=list(file_paths),  # type: ignore[arg-type]
            fps=2,  # Default 2 FPS for image sequence
            output_format="mp4",
        )

        if generated_clip_path:
            # Update event with clip path
            event.clip_path = str(generated_clip_path)
            await db.commit()
            await db.refresh(event)

            file_stat = generated_clip_path.stat()
            generated_at = datetime.fromtimestamp(file_stat.st_mtime, tz=UTC)
            clip_filename = generated_clip_path.name
            clip_url = f"/api/media/clips/{clip_filename}"

            # Add Location header for the newly created resource (201 Created)
            response.headers["Location"] = clip_url
            return ClipGenerateResponse(
                event_id=event.id,
                status=ClipStatus.COMPLETED,
                clip_url=clip_url,
                generated_at=generated_at,
                message="Clip generated successfully",
            )
        else:
            return ClipGenerateResponse(
                event_id=event.id,
                status=ClipStatus.FAILED,
                clip_url=None,
                generated_at=None,
                message="Clip generation failed - check server logs",
            )

    except Exception as e:
        logger.error(
            f"Clip generation failed for event {sanitize_log_value(event_id)}: {e}", exc_info=True
        )
        # Sanitize exception message to prevent information leakage (NEM-1059)
        # Full error details are logged server-side above
        safe_message = sanitize_error_for_response(e, context="generating clip")
        return ClipGenerateResponse(
            event_id=event.id,
            status=ClipStatus.FAILED,
            clip_url=None,
            generated_at=None,
            message=safe_message,
        )


@router.get("/analyze/{batch_id}/stream")
async def analyze_batch_streaming(
    batch_id: str,
    camera_id: str | None = Query(None, description="Camera ID for the batch"),
    detection_ids: str | None = Query(None, description="Comma-separated detection IDs (optional)"),
) -> StreamingResponse:
    """Stream LLM analysis progress for a batch via Server-Sent Events (NEM-1665).

    This endpoint provides progressive LLM response updates during long inference
    times, allowing the frontend to display partial results and show typing
    indicators while the analysis is in progress.

    Event Types:
    - progress: Partial LLM response chunk with accumulated_text
    - complete: Final event with risk assessment and event_id
    - error: Error information with error_code and recoverable flag

    Args:
        batch_id: Batch identifier to analyze
        camera_id: Optional camera ID (uses Redis lookup if not provided)
        detection_ids: Optional comma-separated detection IDs

    Returns:
        StreamingResponse with SSE event stream (text/event-stream)

    Example SSE output:
        data: {"event_type": "progress", "content": "Based on", "accumulated_text": "Based on"}

        data: {"event_type": "progress", "content": " the", "accumulated_text": "Based on the"}

        data: {"event_type": "complete", "event_id": 123, "risk_score": 75, ...}
    """
    from backend.core.redis import get_redis
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    async def event_generator() -> Any:
        """Generate SSE events from streaming analysis."""
        try:
            # Get Redis client from async generator (FastAPI dependency pattern)
            redis_gen = get_redis()
            redis_client = await anext(redis_gen)
            try:
                analyzer = NemotronAnalyzer(redis_client=redis_client)

                # Parse detection_ids if provided
                parsed_detection_ids: list[int | str] | None = None
                if detection_ids:
                    try:
                        parsed_detection_ids = [
                            int(d.strip()) for d in detection_ids.split(",") if d.strip()
                        ]
                    except ValueError:
                        # Return error event for invalid detection_ids
                        error_event = {
                            "event_type": "error",
                            "error_code": "INVALID_DETECTION_IDS",
                            "error_message": "Detection IDs must be numeric",
                            "recoverable": False,
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        return

                # Stream analysis updates
                async for update in analyzer.analyze_batch_streaming(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    detection_ids=parsed_detection_ids,
                ):
                    yield f"data: {json.dumps(update)}\n\n"
            finally:
                # Clean up the generator
                try:
                    await redis_gen.aclose()
                except Exception as cleanup_err:
                    logger.debug(f"Generator cleanup: {cleanup_err}")

        except Exception as e:
            logger.error(f"Streaming analysis error for batch {batch_id}: {e}", exc_info=True)
            error_event = {
                "event_type": "error",
                "error_code": "INTERNAL_ERROR",
                "error_message": "An internal error occurred during analysis",
                "recoverable": False,
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )


# =============================================================================
# Bulk Operations (NEM-1433)
# =============================================================================
# Rate limiting note: Bulk operations should be rate-limited more aggressively
# than single-item operations. Consider implementing:
# - RateLimiter(tier=RateLimitTier.BULK) with lower limits (e.g., 10 req/min)
# - Per-IP rate limiting to prevent abuse
# - Request size limits enforced at the schema level (max 100 items)


@router.post(
    "/bulk",
    response_model=EventBulkCreateResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Bulk create events",
    responses={
        207: {"description": "Multi-status response with per-item results"},
        400: {"description": "Invalid request format"},
        422: {"description": "Validation error"},
    },
)
async def bulk_create_events(
    request: EventBulkCreateRequest,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> EventBulkCreateResponse:
    """Create multiple events in a single request.

    Supports partial success - some events may succeed while others fail.
    Returns HTTP 207 Multi-Status with per-item results.

    Rate limiting: Consider implementing RateLimitTier.BULK for production use.

    Args:
        request: Bulk create request with up to 100 events
        db: Database session

    Returns:
        EventBulkCreateResponse with per-item results
    """
    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    # Validate all camera_ids exist before processing
    camera_ids = {item.camera_id for item in request.events}
    camera_query = select(Camera.id).where(Camera.id.in_(camera_ids))
    camera_result = await db.execute(camera_query)
    valid_camera_ids = {row[0] for row in camera_result.all()}

    for idx, item in enumerate(request.events):
        try:
            # Validate camera exists
            if item.camera_id not in valid_camera_ids:
                results.append(
                    {
                        "index": idx,
                        "status": BulkOperationStatus.FAILED,
                        "id": None,
                        "error": f"Camera not found: {item.camera_id}",
                    }
                )
                failed += 1
                continue

            # Create event
            event = Event(
                camera_id=item.camera_id,
                started_at=item.started_at,
                ended_at=item.ended_at,
                risk_score=item.risk_score,
                risk_level=item.risk_level,
                summary=item.summary,
                reasoning=item.reasoning,
                detection_ids=json.dumps(item.detection_ids) if item.detection_ids else None,
            )
            db.add(event)
            await db.flush()  # Get the ID without committing

            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.SUCCESS,
                    "id": event.id,
                    "error": None,
                }
            )
            succeeded += 1

        except Exception as e:
            logger.error(f"Bulk create event failed at index {idx}: {e}")
            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.FAILED,
                    "id": None,
                    "error": str(e),
                }
            )
            failed += 1

    # Commit all successful operations
    if succeeded > 0:
        try:
            await db.commit()
            # Invalidate event-related caches after successful bulk create (NEM-1950)
            try:
                await cache.invalidate_events(reason="event_created")
                await cache.invalidate_event_stats(reason="event_created")
            except Exception as e:
                # Cache invalidation is non-critical - log but don't fail the request
                logger.warning(f"Cache invalidation failed after bulk create: {e}")
        except Exception as e:
            logger.error(f"Bulk create commit failed: {e}")
            await db.rollback()
            # Mark all as failed on commit error
            for item_result in results:
                if item_result["status"] == BulkOperationStatus.SUCCESS:
                    item_result["status"] = BulkOperationStatus.FAILED
                    item_result["error"] = "Transaction commit failed"
                    succeeded -= 1
                    failed += 1

    return EventBulkCreateResponse(
        total=len(request.events),
        succeeded=succeeded,
        failed=failed,
        skipped=0,
        results=results,
    )


@router.patch(
    "/bulk",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Bulk update events",
    responses={
        207: {"description": "Multi-status response with per-item results"},
        400: {"description": "Invalid request format"},
        422: {"description": "Validation error"},
    },
)
async def bulk_update_events(
    request: EventBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> BulkOperationResponse:
    """Update multiple events in a single request.

    Supports partial success - some updates may succeed while others fail.
    Returns HTTP 207 Multi-Status with per-item results.

    Rate limiting: Consider implementing RateLimitTier.BULK for production use.

    Args:
        request: Bulk update request with up to 100 event updates
        db: Database session

    Returns:
        BulkOperationResponse with per-item results
    """
    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    # Fetch all events in one query
    event_ids = [item.id for item in request.events]
    query = select(Event).where(Event.id.in_(event_ids))
    result = await db.execute(query)
    events_map = {event.id: event for event in result.scalars().all()}

    for idx, item in enumerate(request.events):
        try:
            event = events_map.get(item.id)
            if not event:
                results.append(
                    {
                        "index": idx,
                        "status": BulkOperationStatus.FAILED,
                        "id": item.id,
                        "error": f"Event not found: {item.id}",
                    }
                )
                failed += 1
                continue

            # Update fields if provided
            if item.reviewed is not None:
                event.reviewed = item.reviewed
            if item.notes is not None:
                event.notes = item.notes

            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.SUCCESS,
                    "id": event.id,
                    "error": None,
                }
            )
            succeeded += 1

        except Exception as e:
            logger.error(f"Bulk update event failed at index {idx}: {e}")
            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.FAILED,
                    "id": item.id,
                    "error": str(e),
                }
            )
            failed += 1

    # Commit all successful operations
    if succeeded > 0:
        try:
            await db.commit()
            # Invalidate event-related caches after successful bulk update (NEM-1950)
            try:
                await cache.invalidate_events(reason="event_updated")
                await cache.invalidate_event_stats(reason="event_updated")
            except Exception as e:
                # Cache invalidation is non-critical - log but don't fail the request
                logger.warning(f"Cache invalidation failed after bulk update: {e}")
        except Exception as e:
            logger.error(f"Bulk update commit failed: {e}")
            await db.rollback()
            # Mark all as failed on commit error
            for item_result in results:
                if item_result["status"] == BulkOperationStatus.SUCCESS:
                    item_result["status"] = BulkOperationStatus.FAILED
                    item_result["error"] = "Transaction commit failed"
                    succeeded -= 1
                    failed += 1

    return BulkOperationResponse(
        total=len(request.events),
        succeeded=succeeded,
        failed=failed,
        skipped=0,
        results=results,
    )


@router.delete(
    "/bulk",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Bulk delete events",
    responses={
        207: {"description": "Multi-status response with per-item results"},
        400: {"description": "Invalid request format"},
        422: {"description": "Validation error"},
    },
)
async def bulk_delete_events(
    request: EventBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> BulkOperationResponse:
    """Delete multiple events in a single request.

    Supports partial success - some deletions may succeed while others fail.
    Returns HTTP 207 Multi-Status with per-item results.

    By default uses soft delete (sets deleted_at timestamp) with cascade to
    related detections. Use soft_delete=false for permanent deletion.
    Use cascade=false to only delete the event without affecting detections.

    Rate limiting: Consider implementing RateLimitTier.BULK for production use.

    Args:
        request: Bulk delete request with up to 100 event IDs
        db: Database session
        cache: Cache service for invalidation

    Returns:
        BulkOperationResponse with per-item results
    """
    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    event_service = get_event_service()

    for idx, event_id in enumerate(request.event_ids):
        try:
            if request.soft_delete:
                # Soft delete with optional cascade to related detections
                await event_service.soft_delete_event(
                    event_id=event_id,
                    db=db,
                    cascade=request.cascade,
                )
            else:
                # Hard delete - fetch and delete directly
                query = select(Event).where(Event.id == event_id)
                result = await db.execute(query)
                event = result.scalar_one_or_none()
                if event is None:
                    raise ValueError(f"Event not found: {event_id}")
                await db.delete(event)

            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.SUCCESS,
                    "id": event_id,
                    "error": None,
                }
            )
            succeeded += 1

        except ValueError as e:
            # Event not found or already deleted
            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.FAILED,
                    "id": event_id,
                    "error": str(e),
                }
            )
            failed += 1

        except Exception as e:
            logger.error(f"Bulk delete event failed at index {idx}: {e}")
            results.append(
                {
                    "index": idx,
                    "status": BulkOperationStatus.FAILED,
                    "id": event_id,
                    "error": str(e),
                }
            )
            failed += 1

    # Commit all successful operations
    if succeeded > 0:
        try:
            await db.commit()
            # Invalidate event-related caches after successful bulk delete (NEM-1950)
            try:
                await cache.invalidate_events(reason="event_deleted")
                await cache.invalidate_event_stats(reason="event_deleted")
            except Exception as e:
                # Cache invalidation is non-critical - log but don't fail the request
                logger.warning(f"Cache invalidation failed after bulk delete: {e}")
        except Exception as e:
            logger.error(f"Bulk delete commit failed: {e}")
            await db.rollback()
            # Mark all as failed on commit error
            for item_result in results:
                if item_result["status"] == BulkOperationStatus.SUCCESS:
                    item_result["status"] = BulkOperationStatus.FAILED
                    item_result["error"] = "Transaction commit failed"
                    succeeded -= 1
                    failed += 1

    return BulkOperationResponse(
        total=len(request.event_ids),
        succeeded=succeeded,
        failed=failed,
        skipped=0,
        results=results,
    )


# =============================================================================
# Soft Delete Trash View Endpoint (NEM-1955)
# =============================================================================


@router.get(
    "/deleted",
    response_model=DeletedEventsListResponse,
    summary="List all soft-deleted events",
    responses={
        200: {"description": "List of soft-deleted events"},
    },
)
async def list_deleted_events(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all soft-deleted events for trash view.

    Returns events that have been soft-deleted (deleted_at is not null),
    ordered by deleted_at descending (most recently deleted first).

    This endpoint enables a "trash" view where users can see deleted events
    and optionally restore them.

    Args:
        db: Database session

    Returns:
        DeletedEventsListResponse containing list of deleted events and count
    """
    # Query for events where deleted_at is not null
    query = select(Event).where(Event.deleted_at.isnot(None)).order_by(Event.deleted_at.desc())

    result = await db.execute(query)
    deleted_events = result.scalars().all()

    # Build response with detection info
    events_data = []
    for event in deleted_events:
        detection_ids = get_detection_ids_from_event(event)
        thumbnail_url = f"/api/media/detections/{detection_ids[0]}" if detection_ids else None

        events_data.append(
            {
                "id": event.id,
                "camera_id": event.camera_id,
                "started_at": event.started_at,
                "ended_at": event.ended_at,
                "risk_score": event.risk_score,
                "risk_level": event.risk_level,
                "summary": event.summary,
                "reasoning": event.reasoning,
                "llm_prompt": event.llm_prompt,
                "reviewed": event.reviewed,
                "notes": event.notes,
                "detection_count": len(detection_ids),
                "detection_ids": detection_ids,
                "thumbnail_url": thumbnail_url,
                "enrichment_status": None,
            }
        )

    return {
        "events": events_data,
        "count": len(events_data),
    }


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a single event",
    responses={
        204: {"description": "Event deleted successfully"},
        404: {"description": "Event not found"},
        409: {"description": "Event already deleted"},
    },
)
async def delete_event(
    event_id: int,
    cascade: bool = Query(True, description="Cascade soft delete to related detections"),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> None:
    """Soft delete a single event with optional cascade to related detections.

    By default, cascade=True soft deletes all related detections using the same
    timestamp as the event. This enables cascade restore by matching timestamps.

    Args:
        event_id: ID of the event to delete
        cascade: If True, cascade soft delete to related detections
        db: Database session
        cache: Cache service for invalidation

    Raises:
        HTTPException: 404 if event not found, 409 if already deleted
    """
    event_service = get_event_service()

    try:
        await event_service.soft_delete_event(
            event_id=event_id,
            db=db,
            cascade=cascade,
        )
        await db.commit()

        # Invalidate event-related caches
        try:
            await cache.invalidate_events(reason="event_deleted")
            await cache.invalidate_event_stats(reason="event_deleted")
        except Exception as e:
            logger.warning(f"Cache invalidation failed after delete: {e}")

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg) from e
        if "already deleted" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg) from e
        raise HTTPException(status_code=400, detail=error_msg) from e


@router.post(
    "/{event_id}/restore",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore a soft-deleted event",
    responses={
        200: {"description": "Event restored successfully"},
        404: {"description": "Event not found"},
        409: {"description": "Event is not deleted"},
    },
)
async def restore_event(
    event_id: int,
    cascade: bool = Query(True, description="Cascade restore to related detections"),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> dict[str, Any]:
    """Restore a soft-deleted event with optional cascade to related detections.

    When cascade=True, this restores detections that were deleted at the same
    timestamp as the event, indicating they were cascade-deleted together.

    Args:
        event_id: ID of the event to restore
        cascade: If True, cascade restore to related detections
        db: Database session
        cache: Cache service for invalidation

    Returns:
        The restored event

    Raises:
        HTTPException: 404 if event not found, 409 if not deleted
    """
    event_service = get_event_service()

    try:
        event = await event_service.restore_event(
            event_id=event_id,
            db=db,
            cascade=cascade,
        )
        await db.commit()

        # Invalidate event-related caches
        try:
            await cache.invalidate_events(reason="event_restored")
            await cache.invalidate_event_stats(reason="event_restored")
        except Exception as e:
            logger.warning(f"Cache invalidation failed after restore: {e}")

        return {
            "id": event.id,
            "camera_id": event.camera_id,
            "started_at": event.started_at,
            "ended_at": event.ended_at,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "summary": event.summary,
            "reasoning": event.reasoning,
            "reviewed": event.reviewed,
            "notes": event.notes,
            "clip_path": event.clip_path,
            "deleted_at": event.deleted_at,
        }

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg) from e
        if "not deleted" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg) from e
        raise HTTPException(status_code=400, detail=error_msg) from e
