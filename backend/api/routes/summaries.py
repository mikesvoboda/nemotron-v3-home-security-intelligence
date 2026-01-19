"""API routes for dashboard summaries.

This module provides endpoints for retrieving LLM-generated summaries of
high/critical security events. Summaries are generated every 5 minutes by
a background job and displayed on the dashboard.

Endpoints:
    GET /api/summaries/latest - Returns both hourly and daily summaries
    GET /api/summaries/hourly - Returns latest hourly summary only
    GET /api/summaries/daily  - Returns latest daily summary only
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_cache_service_dep
from backend.api.schemas.summaries import (
    BulletPointSchema,
    LatestSummariesResponse,
    StructuredSummarySchema,
    SummaryResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.summary import Summary, SummaryType
from backend.repositories.summary_repository import SummaryRepository
from backend.services.cache_service import DEFAULT_TTL, CacheService
from backend.services.summary_parser import parse_summary_content

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


def _summary_to_response(summary: Summary | None) -> SummaryResponse | None:
    """Convert a Summary model to a SummaryResponse schema.

    Parses the summary content to extract structured data including
    bullet points, focus areas, dominant patterns, and weather conditions.

    Args:
        summary: Summary model instance or None

    Returns:
        SummaryResponse with structured data if summary exists, None otherwise
    """
    if summary is None:
        return None

    # Parse the summary content to extract structured data
    events = _build_events_for_parser()
    parsed = parse_summary_content(summary.content, events=events)

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

    return SummaryResponse(
        id=summary.id,
        content=summary.content,
        event_count=summary.event_count,
        window_start=summary.window_start,
        window_end=summary.window_end,
        generated_at=summary.generated_at,
        structured=structured,
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

    hourly = _summary_to_response(summaries.get("hourly"))
    daily = _summary_to_response(summaries.get("daily"))

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

    response = _summary_to_response(summary)

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

    response = _summary_to_response(summary)

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
