"""API routes for entity recognition summary.

This module provides endpoints for retrieving entity recognition statistics
for the dashboard summary feature. Shows counts of known vs unknown persons
and vehicles detected in the summary time window.

Endpoints:
    GET /api/summaries/entities - Returns entity recognition stats for past hour

Implements NEM-5395: Entity Recognition Summary - API Endpoint
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_cache_service_dep
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services.cache_service import DEFAULT_TTL, CacheService
from backend.services.entity_recognition_service import EntityRecognitionService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/summaries", tags=["summaries"])

# Cache key and TTL for entity stats
CACHE_KEY_ENTITIES = "summaries:entities"
ENTITIES_CACHE_TTL = DEFAULT_TTL  # 300 seconds (5 minutes)


@router.get(
    "/entities",
    response_model=dict[str, Any],
    responses={
        200: {
            "description": "Entity recognition statistics for the past hour",
            "content": {
                "application/json": {
                    "example": {
                        "persons": {
                            "known": 3,
                            "unknown": 2,
                            "total": 5,
                            "breakdown": "3 known, 2 unknown",
                        },
                        "vehicles": {
                            "known": 1,
                            "unknown": 4,
                            "total": 5,
                            "breakdown": "1 known, 4 unknown",
                        },
                        "window_start": "2026-02-03T10:00:00+00:00",
                        "window_end": "2026-02-03T11:00:00+00:00",
                    }
                }
            },
        }
    },
)
async def get_entity_recognition_stats(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service_dep),
) -> dict[str, Any]:
    """Get entity recognition statistics for the dashboard summary.

    Returns aggregated counts of known vs unknown persons and vehicles
    detected within the past hour. This data is displayed in the
    EntityRecognitionSummary component on the dashboard.

    Persons are classified based on face recognition:
    - **known**: Faces that matched a registered KnownPerson
    - **unknown**: Faces that did not match any known person

    Vehicles are classified based on license plate matching:
    - **known**: Plates that matched a registered household vehicle
    - **unknown**: Plates that did not match any registered vehicle

    Response is cached in Redis with a 5-minute TTL to match the summary
    generation frequency. Cache is automatically invalidated when TTL expires.

    Returns:
        Dictionary with persons stats, vehicles stats, and time window
    """
    # Try cache first
    try:
        cached_data = await cache.get(CACHE_KEY_ENTITIES, cache_type="summaries")
        if cached_data is not None:
            logger.debug("Returning cached entity recognition stats")
            return dict(cached_data)
    except Exception as e:
        logger.warning(f"Cache read failed for entity stats, falling back to database: {e}")

    # Cache miss - fetch from database
    service = EntityRecognitionService()
    stats = await service.get_hourly_stats(db)

    response = stats.to_dict()

    # Cache the result
    try:
        await cache.set(CACHE_KEY_ENTITIES, response, ttl=ENTITIES_CACHE_TTL)
    except Exception as e:
        logger.warning(f"Cache write failed for entity stats: {e}")

    return response
