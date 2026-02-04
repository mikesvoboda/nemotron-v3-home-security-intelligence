"""API routes for dashboard summaries.

This module provides endpoints for retrieving LLM-generated summaries of
high/critical security events. Summaries are generated every 5 minutes by
a background job and displayed on the dashboard.

Includes actionable insights generated from event analysis (NEM-5418, NEM-5419,
NEM-5420, NEM-5421).

Includes expandable detail panel with export functionality (NEM-5425, NEM-5426,
NEM-5427).

Endpoints:
    GET /api/summaries/latest - Returns both hourly and daily summaries
    GET /api/summaries/hourly - Returns latest hourly summary only
    GET /api/summaries/daily  - Returns latest daily summary only
    GET /api/summaries/{id}/detail - Returns detailed summary with timeline
    GET /api/summaries/{id}/export - Export summary in JSON, CSV, or PDF format
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_cache_service_dep
from backend.api.schemas.summaries import (
    BulletPointSchema,
    InsightSchema,
    LatestSummariesResponse,
    StructuredSummarySchema,
    SummaryDetailResponse,
    SummaryResponse,
    TimelineEventSchema,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.summary import Summary, SummaryType
from backend.repositories.event_repository import EventRepository
from backend.repositories.summary_repository import SummaryRepository
from backend.services.cache_service import DEFAULT_TTL, CacheService
from backend.services.insight_generator import get_insight_generator
from backend.services.summary_detail_service import get_summary_detail_service
from backend.services.summary_parser import parse_summary_content

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.models.event import Event

logger = get_logger(__name__)
router = APIRouter(prefix="/api/summaries", tags=["summaries"])

# Cache TTL for summaries (5 minutes, same as generation frequency)
SUMMARIES_CACHE_TTL = DEFAULT_TTL  # 300 seconds

# Cache keys for summaries
CACHE_KEY_LATEST = "summaries:latest"
CACHE_KEY_HOURLY = "summaries:hourly"
CACHE_KEY_DAILY = "summaries:daily"


def _build_events_for_parser() -> list[dict[str, Any]]:
    """Build events list for the summary parser.

    Since we don't have access to full event data at query time
    (only the summary content), we return an empty list. The parser
    will extract what it can from the content text itself.

    Returns:
        Empty list (events not available at query time)
    """
    return []


def _generate_insights_from_events(events: Sequence[Event]) -> list[InsightSchema]:
    """Generate actionable insights from events.

    Uses the InsightGenerator service to analyze events and generate
    prioritized insights for display on the dashboard.

    Args:
        events: Sequence of Event objects to analyze

    Returns:
        List of InsightSchema objects sorted by priority (highest first)
    """
    if not events:
        return []

    generator = get_insight_generator()
    insights = generator.generate_insights(events, max_insights=5)

    return [
        InsightSchema(
            type=insight.type.value,  # type: ignore[arg-type]
            priority=insight.priority,
            title=insight.title,
            description=insight.description,
            action_url=insight.action_url,
        )
        for insight in insights
    ]


def _summary_to_response(
    summary: Summary | None,
    events: Sequence[Event] | None = None,
) -> SummaryResponse | None:
    """Convert a Summary model to a SummaryResponse schema.

    Parses the summary content to extract structured data including
    bullet points, focus areas, dominant patterns, and weather conditions.
    Also generates actionable insights from the events if provided.

    Args:
        summary: Summary model instance or None
        events: Optional sequence of Event objects for insight generation

    Returns:
        SummaryResponse with structured data and insights if summary exists, None otherwise
    """
    if summary is None:
        return None

    # Parse the summary content to extract structured data
    parser_events = _build_events_for_parser()
    parsed = parse_summary_content(summary.content, events=parser_events)

    # Convert parsed data to Pydantic schema
    structured = StructuredSummarySchema(
        bullet_points=[
            BulletPointSchema(
                icon=bp.icon,
                text=bp.text,
                severity=bp.severity,
            )
            for bp in parsed.bullet_points
        ],
        focus_areas=parsed.focus_areas,
        dominant_patterns=parsed.dominant_patterns,
        max_risk_score=parsed.max_risk_score,
        weather_conditions=parsed.weather_conditions,
    )

    # Generate actionable insights from events
    insights = _generate_insights_from_events(events or [])

    return SummaryResponse(
        id=summary.id,
        content=summary.content,
        event_count=summary.event_count,
        window_start=summary.window_start,
        window_end=summary.window_end,
        generated_at=summary.generated_at,
        structured=structured,
        insights=insights,
    )


@router.get(
    "/latest",
    response_model=LatestSummariesResponse,
    responses={
        200: {
            "description": "Latest hourly and daily summaries",
            "content": {
                "application/json": {
                    "example": {
                        "hourly": {
                            "id": 1,
                            "content": "Over the past hour...",
                            "event_count": 1,
                            "window_start": "2026-01-18T14:00:00Z",
                            "window_end": "2026-01-18T15:00:00Z",
                            "generated_at": "2026-01-18T14:55:00Z",
                        },
                        "daily": {
                            "id": 2,
                            "content": "Today has seen...",
                            "event_count": 1,
                            "window_start": "2026-01-18T00:00:00Z",
                            "window_end": "2026-01-18T15:00:00Z",
                            "generated_at": "2026-01-18T14:55:00Z",
                        },
                    }
                }
            },
        }
    },
)
async def get_latest_summaries(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> LatestSummariesResponse:
    """Get the latest hourly and daily summaries.

    Returns both the most recent hourly summary (covering the past 60 minutes)
    and the most recent daily summary (covering since midnight today).

    Either `hourly` or `daily` can be null if no summary exists yet for that
    time period. This can happen when:
    - The system was just started
    - No high/critical events have occurred

    Response is cached in Redis with a 5-minute TTL to match the summary
    generation frequency. Cache is invalidated when new summaries are generated.

    Returns:
        LatestSummariesResponse with hourly and daily summaries (or nulls)
    """
    # Try cache first
    try:
        cached_data = await cache.get(CACHE_KEY_LATEST, cache_type="summaries")
        if cached_data is not None:
            logger.debug("Returning cached latest summaries")
            return LatestSummariesResponse(**dict(cached_data))
    except Exception as e:
        logger.warning(f"Cache read failed for summaries, falling back to database: {e}")

    # Cache miss - fetch from database
    repo = SummaryRepository(db)
    summaries = await repo.get_latest_all()

    # Fetch events for insight generation if summaries have event_ids
    hourly_summary = summaries.get("hourly")
    daily_summary = summaries.get("daily")

    hourly_events: list[Event] = []
    daily_events: list[Event] = []

    event_repo = EventRepository(db)

    if hourly_summary and hourly_summary.event_ids:
        hourly_events = await event_repo.get_by_ids(
            hourly_summary.event_ids, eager_load_camera=True
        )

    if daily_summary and daily_summary.event_ids:
        daily_events = await event_repo.get_by_ids(daily_summary.event_ids, eager_load_camera=True)

    hourly = _summary_to_response(hourly_summary, hourly_events)
    daily = _summary_to_response(daily_summary, daily_events)

    response = LatestSummariesResponse(hourly=hourly, daily=daily)

    # Cache the result
    try:
        # Convert to dict for caching (handles nested Pydantic models)
        cache_data = response.model_dump(mode="json")
        await cache.set(CACHE_KEY_LATEST, cache_data, ttl=SUMMARIES_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for summaries: {e}")

    return response


@router.get(
    "/hourly",
    response_model=SummaryResponse | None,
    responses={
        200: {
            "description": "Latest hourly summary or null if none exists",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "content": "Over the past hour, one critical event occurred...",
                        "event_count": 1,
                        "window_start": "2026-01-18T14:00:00Z",
                        "window_end": "2026-01-18T15:00:00Z",
                        "generated_at": "2026-01-18T14:55:00Z",
                    }
                }
            },
        }
    },
)
async def get_hourly_summary(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> SummaryResponse | None:
    """Get the latest hourly summary.

    Returns the most recent hourly summary, which covers high/critical events
    from the past 60 minutes. Returns null if no hourly summary exists.

    This endpoint is useful when you only need the hourly summary without
    the overhead of fetching the daily summary as well.

    Returns:
        SummaryResponse with hourly summary, or null if none exists
    """
    # Try cache first
    try:
        cached_data = await cache.get(CACHE_KEY_HOURLY, cache_type="summaries")
        if cached_data is not None:
            logger.debug("Returning cached hourly summary")
            # Handle null cached value (no summary exists)
            if cached_data == "null":
                return None
            return SummaryResponse(**dict(cached_data))
    except Exception as e:
        logger.warning(f"Cache read failed for hourly summary, falling back to database: {e}")

    # Cache miss - fetch from database
    repo = SummaryRepository(db)
    summary = await repo.get_latest_by_type(SummaryType.HOURLY)

    # Fetch events for insight generation
    events: list[Event] = []
    if summary and summary.event_ids:
        event_repo = EventRepository(db)
        events = await event_repo.get_by_ids(summary.event_ids, eager_load_camera=True)

    response = _summary_to_response(summary, events)

    # Cache the result (cache null as "null" string)
    try:
        if response is not None:
            cache_data = response.model_dump(mode="json")
            await cache.set(CACHE_KEY_HOURLY, cache_data, ttl=SUMMARIES_CACHE_TTL)
        else:
            await cache.set(CACHE_KEY_HOURLY, "null", ttl=SUMMARIES_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for hourly summary: {e}")

    return response


@router.get(
    "/daily",
    response_model=SummaryResponse | None,
    responses={
        200: {
            "description": "Latest daily summary or null if none exists",
            "content": {
                "application/json": {
                    "example": {
                        "id": 2,
                        "content": "Today has seen minimal high-priority activity...",
                        "event_count": 1,
                        "window_start": "2026-01-18T00:00:00Z",
                        "window_end": "2026-01-18T15:00:00Z",
                        "generated_at": "2026-01-18T14:55:00Z",
                    }
                }
            },
        }
    },
)
async def get_daily_summary(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> SummaryResponse | None:
    """Get the latest daily summary.

    Returns the most recent daily summary, which covers high/critical events
    since midnight today. Returns null if no daily summary exists.

    This endpoint is useful when you only need the daily summary without
    the overhead of fetching the hourly summary as well.

    Returns:
        SummaryResponse with daily summary, or null if none exists
    """
    # Try cache first
    try:
        cached_data = await cache.get(CACHE_KEY_DAILY, cache_type="summaries")
        if cached_data is not None:
            logger.debug("Returning cached daily summary")
            # Handle null cached value (no summary exists)
            if cached_data == "null":
                return None
            return SummaryResponse(**dict(cached_data))
    except Exception as e:
        logger.warning(f"Cache read failed for daily summary, falling back to database: {e}")

    # Cache miss - fetch from database
    repo = SummaryRepository(db)
    summary = await repo.get_latest_by_type(SummaryType.DAILY)

    # Fetch events for insight generation
    events: list[Event] = []
    if summary and summary.event_ids:
        event_repo = EventRepository(db)
        events = await event_repo.get_by_ids(summary.event_ids, eager_load_camera=True)

    response = _summary_to_response(summary, events)

    # Cache the result (cache null as "null" string)
    try:
        if response is not None:
            cache_data = response.model_dump(mode="json")
            await cache.set(CACHE_KEY_DAILY, cache_data, ttl=SUMMARIES_CACHE_TTL)
        else:
            await cache.set(CACHE_KEY_DAILY, "null", ttl=SUMMARIES_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for daily summary: {e}")

    return response


# Cache key for detail endpoint
def _get_detail_cache_key(summary_id: int) -> str:
    """Generate cache key for summary detail."""
    return f"summaries:detail:{summary_id}"


@router.get(
    "/{summary_id}/detail",
    response_model=SummaryDetailResponse,
    responses={
        200: {
            "description": "Detailed summary with timeline and export options",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "summary_type": "hourly",
                        "content": "Multiple security events detected...",
                        "event_count": 3,
                        "window_start": "2026-01-21T14:00:00Z",
                        "window_end": "2026-01-21T15:00:00Z",
                        "generated_at": "2026-01-21T14:55:00Z",
                        "timeline": [
                            {
                                "event_id": 101,
                                "timestamp": "2026-01-21T14:10:00Z",
                                "camera_name": "Front Door",
                                "summary": "Person detected",
                                "risk_score": 75,
                                "risk_level": "high",
                                "event_url": "/events/101",
                            }
                        ],
                        "export_formats": ["json", "csv", "pdf"],
                    }
                }
            },
        },
        404: {
            "description": "Summary not found",
        },
    },
)
async def get_summary_detail(
    summary_id: int,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> SummaryDetailResponse:
    """Get detailed summary data for the expandable detail panel.

    Returns full summary content with timeline of events and export options.
    The timeline includes all events that were included in the summary,
    sorted chronologically.

    Args:
        summary_id: ID of the summary to retrieve
        db: Database session
        cache: Cache service

    Returns:
        SummaryDetailResponse with full detail data

    Raises:
        HTTPException: 404 if summary not found
    """
    cache_key = _get_detail_cache_key(summary_id)

    # Try cache first
    try:
        cached_data = await cache.get(cache_key, cache_type="summaries")
        if cached_data is not None:
            logger.debug(f"Returning cached summary detail for {summary_id}")
            return SummaryDetailResponse(**dict(cached_data))
    except Exception as e:
        logger.warning(f"Cache read failed for summary detail {summary_id}: {e}")

    # Cache miss - fetch from database
    repo = SummaryRepository(db)
    summary = await repo.get_by_id(summary_id)

    if summary is None:
        raise HTTPException(status_code=404, detail=f"Summary {summary_id} not found")

    # Fetch related events
    events: list[Event] = []
    if summary.event_ids:
        event_repo = EventRepository(db)
        events = await event_repo.get_by_ids(summary.event_ids, eager_load_camera=True)

    # Parse summary content for structured data
    parser_events = _build_events_for_parser()
    parsed = parse_summary_content(summary.content, events=parser_events)

    # Build detail data
    detail_service = get_summary_detail_service()
    detail_data = detail_service.generate_detail(
        summary,
        events,
        focus_areas=parsed.focus_areas,
        dominant_patterns=parsed.dominant_patterns,
        max_risk_score=parsed.max_risk_score,
    )

    # Build structured data schema
    structured = StructuredSummarySchema(
        bullet_points=[
            BulletPointSchema(
                icon=bp.icon,
                text=bp.text,
                severity=bp.severity,
            )
            for bp in parsed.bullet_points
        ],
        focus_areas=parsed.focus_areas,
        dominant_patterns=parsed.dominant_patterns,
        max_risk_score=parsed.max_risk_score,
        weather_conditions=parsed.weather_conditions,
    )

    # Build response
    response = SummaryDetailResponse(
        id=summary.id,
        summary_type=summary.summary_type,
        content=summary.content,
        event_count=summary.event_count,
        window_start=summary.window_start,
        window_end=summary.window_end,
        generated_at=summary.generated_at,
        structured=structured,
        timeline=[
            TimelineEventSchema(
                event_id=e.event_id,
                timestamp=e.timestamp,
                camera_name=e.camera_name,
                summary=e.summary or "",
                risk_score=e.risk_score,
                risk_level=e.risk_level,
                event_url=e.event_url,
            )
            for e in detail_data.timeline
        ],
        export_formats=detail_data.export_formats,
    )

    # Cache the result
    try:
        cache_data = response.model_dump(mode="json")
        await cache.set(cache_key, cache_data, ttl=SUMMARIES_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for summary detail {summary_id}: {e}")

    return response


@router.get(
    "/{summary_id}/export",
    response_model=None,
    responses={
        200: {
            "description": "Export data in requested format",
            "content": {
                "application/json": {},
                "text/csv": {},
                "application/pdf": {},
            },
        },
        400: {
            "description": "Invalid export format",
        },
        404: {
            "description": "Summary not found",
        },
    },
)
async def export_summary(
    summary_id: int,
    format: Literal["json", "csv", "pdf"] = Query(
        default="json",
        description="Export format: json, csv, or pdf",
        alias="format",
    ),
    db: AsyncSession = Depends(get_db),
    _cache: CacheService = Depends(get_cache_service_dep),
) -> Response:
    """Export summary data in various formats.

    Exports the summary and its related events in JSON, CSV, or PDF format.
    Useful for downloading and sharing summary reports.

    Args:
        summary_id: ID of the summary to export
        format: Export format (json, csv, pdf)
        db: Database session
        cache: Cache service

    Returns:
        Export data in requested format

    Raises:
        HTTPException: 404 if summary not found
        HTTPException: 400 if invalid format
    """
    # Validate format
    valid_formats = ["json", "csv", "pdf"]
    if format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid export format '{format}'. Supported formats: {', '.join(valid_formats)}",
        )

    # Fetch summary from database
    repo = SummaryRepository(db)
    summary = await repo.get_by_id(summary_id)

    if summary is None:
        raise HTTPException(status_code=404, detail=f"Summary {summary_id} not found")

    # Fetch related events
    events: list[Event] = []
    if summary.event_ids:
        event_repo = EventRepository(db)
        events = await event_repo.get_by_ids(summary.event_ids, eager_load_camera=True)

    # Get detail service and export
    detail_service = get_summary_detail_service()

    if format == "json":
        json_data = detail_service.export_json(summary, events)
        # Return as JSONResponse for proper typing
        import json as json_module

        return JSONResponse(
            content=json_module.loads(json_data),
            headers={"Content-Disposition": f"attachment; filename=summary_{summary_id}.json"},
        )

    elif format == "csv":
        csv_data = detail_service.export_csv(summary, events)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=summary_{summary_id}.csv"},
        )

    else:  # pdf
        pdf_data = detail_service.export_pdf(summary, events)
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=summary_{summary_id}.pdf"},
        )
