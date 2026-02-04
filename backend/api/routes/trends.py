"""API routes for trend comparison sparklines.

This module provides endpoints for retrieving time-bucketed event metrics
with rolling 24-hour baseline comparisons for dashboard sparkline displays.

Endpoints:
    GET /api/summaries/trends?type=hourly - Hourly trend data (12 x 5-min buckets)
    GET /api/summaries/trends?type=daily  - Daily trend data (24 x 1-hour buckets)

Each response includes three metrics:
- event_count: Number of events per bucket
- avg_risk: Average risk score per bucket
- high_risk_count: Number of high-risk events (>= 70) per bucket

Each metric includes:
- values: Array of data points for sparkline visualization
- baseline: Rolling 24-hour average for comparison
- deviation_pct: Percentage above/below baseline
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_cache_service_dep
from backend.api.schemas.trends import TrendMetric, TrendsResponse
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services.cache_service import CacheService
from backend.services.trend_service import TrendService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/summaries", tags=["summaries"])

# Cache TTL for trends (2 minutes for more responsive updates)
TRENDS_CACHE_TTL = 120

# Cache keys for trends
CACHE_KEY_TRENDS_HOURLY = "trends:hourly"
CACHE_KEY_TRENDS_DAILY = "trends:daily"


@router.get(
    "/trends",
    response_model=TrendsResponse,
    responses={
        200: {
            "description": "Trend data for sparkline visualization",
            "content": {
                "application/json": {
                    "example": {
                        "event_count": {
                            "values": [5, 8, 3, 6, 10, 4, 7, 9, 2, 5, 6, 8],
                            "baseline": 6.0,
                            "deviation_pct": 33.3,
                        },
                        "avg_risk": {
                            "values": [45, 52, 38, 60, 72, 40, 55, 65, 35, 48, 50, 58],
                            "baseline": 50.0,
                            "deviation_pct": 16.0,
                        },
                        "high_risk_count": {
                            "values": [1, 2, 0, 1, 3, 1, 2, 2, 0, 1, 1, 2],
                            "baseline": 1.3,
                            "deviation_pct": 53.8,
                        },
                    }
                }
            },
        }
    },
)
async def get_trends(
    trend_type: Literal["hourly", "daily"] = Query(
        "hourly",
        alias="type",
        description="Type of trend: 'hourly' (5-min buckets) or 'daily' (1-hour buckets)",
    ),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> TrendsResponse:
    """Get trend data for sparkline visualization.

    Returns time-bucketed event metrics with rolling 24-hour baseline comparisons.

    **Hourly view** (`type=hourly`, default):
    - 12 x 5-minute buckets (last 60 minutes)
    - Ideal for real-time monitoring

    **Daily view** (`type=daily`):
    - 24 x 1-hour buckets (last 24 hours)
    - Ideal for daily patterns

    **Metrics included:**
    - `event_count`: Number of events per bucket
    - `avg_risk`: Average risk score per bucket
    - `high_risk_count`: Events with risk_score >= 70

    **Deviation indicators:**
    - Positive `deviation_pct`: Above baseline (e.g., "40% above baseline")
    - Negative `deviation_pct`: Below baseline (e.g., "-20% below baseline")

    Response is cached for 2 minutes for performance while maintaining responsiveness.

    Args:
        trend_type: Type of trend ('hourly' or 'daily')
        db: Database session
        cache: Cache service

    Returns:
        TrendsResponse with event_count, avg_risk, and high_risk_count metrics
    """
    # Select cache key based on trend type
    cache_key = CACHE_KEY_TRENDS_DAILY if trend_type == "daily" else CACHE_KEY_TRENDS_HOURLY

    # Try cache first
    try:
        cached_data = await cache.get(cache_key, cache_type="trends")
        if cached_data is not None:
            logger.debug(f"Returning cached {trend_type} trends")
            return TrendsResponse(
                event_count=TrendMetric(**cached_data["event_count"]),
                avg_risk=TrendMetric(**cached_data["avg_risk"]),
                high_risk_count=TrendMetric(**cached_data["high_risk_count"]),
            )
    except Exception as e:
        logger.warning(f"Cache read failed for trends, falling back to database: {e}")

    # Cache miss - calculate trend data
    service = TrendService(db)
    trend_data = await service.get_trend_data(trend_type)

    response = TrendsResponse(
        event_count=TrendMetric(**trend_data["event_count"]),
        avg_risk=TrendMetric(**trend_data["avg_risk"]),
        high_risk_count=TrendMetric(**trend_data["high_risk_count"]),
    )

    # Cache the result
    try:
        cache_data = response.model_dump(mode="json")
        await cache.set(cache_key, cache_data, ttl=TRENDS_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for trends: {e}")

    return response
