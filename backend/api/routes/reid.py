"""API routes for Re-ID similarity search (NEM-4932).

This module provides endpoints for searching similar entities using
embedding-based similarity matching across Redis (hot cache) and
PostgreSQL (historical data).

Endpoints:
- POST /api/reid/search: Search for similar entities by embedding
- GET /api/reid/similar/{detection_id}: Find similar entities for a detection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from backend.api.schemas.reid import (
    SimilarityMatch,
    SimilaritySearchRequest,
    SimilaritySearchResponse,
)
from backend.core.dependencies import get_hybrid_entity_storage
from backend.core.logging import get_logger
from backend.core.redis import get_redis_optional
from backend.services.reid_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    get_reid_service,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from backend.services.hybrid_entity_storage import HybridEntityStorage
    from backend.services.reid_service import ReIdentificationService

router = APIRouter(
    prefix="/api/reid",
    tags=["reid"],
    default_response_class=ORJSONResponse,
)

logger = get_logger(__name__)


def _get_thumbnail_url(detection_id: str | None) -> str | None:
    """Generate thumbnail URL for a detection.

    Args:
        detection_id: Detection ID

    Returns:
        URL path to the detection's thumbnail image, or None
    """
    if not detection_id:
        return None
    try:
        int_id = int(detection_id)
        return f"/api/detections/{int_id}/image"
    except ValueError:
        return f"/api/detections/{detection_id}/image"


async def _get_redis_client() -> Redis | None:
    """Get raw Redis client from the dependency.

    Returns:
        Raw redis.asyncio.Redis client or None if not available
    """
    async for client in get_redis_optional():
        if client is not None:
            return client._ensure_connected()
        return None
    return None


@router.post(
    "/search",
    response_model=SimilaritySearchResponse,
    responses={
        400: {"description": "Invalid request parameters"},
        503: {"description": "Service unavailable (Redis/PostgreSQL)"},
        500: {"description": "Internal server error"},
    },
)
async def search_similar_entities(
    request: SimilaritySearchRequest,
    hybrid_storage: HybridEntityStorage = Depends(get_hybrid_entity_storage),
) -> SimilaritySearchResponse:
    """Search for entities similar to the given embedding vector.

    This endpoint allows searching for entities that are similar to a provided
    embedding vector. It can search across both Redis (hot cache, 24h window)
    and PostgreSQL (historical, 30-day retention) depending on the
    `include_historical` parameter.

    Args:
        request: Search request containing embedding vector and parameters
        hybrid_storage: Hybrid storage service for combined Redis/PostgreSQL search

    Returns:
        SimilaritySearchResponse with matching entities sorted by similarity

    Raises:
        HTTPException: 400 for invalid parameters, 503 for service unavailable
    """
    logger.info(
        "Re-ID similarity search: entity_type=%s, threshold=%.2f, include_historical=%s",
        request.entity_type,
        request.threshold,
        request.include_historical,
    )

    try:
        # Use hybrid storage for combined search
        matches = await hybrid_storage.find_matches(
            embedding=request.embedding,
            entity_type=request.entity_type,
            threshold=request.threshold,
            exclude_detection_id=request.exclude_detection_id,
            include_historical=request.include_historical,
        )

        # Apply limit
        limited_matches = matches[: request.limit]

        # Convert to response format
        match_items = [
            SimilarityMatch(
                entity_id=str(match.entity_id),
                entity_type=match.entity_type,
                camera_id=match.camera_id,
                timestamp=match.timestamp,
                detection_id=match.detection_id,
                similarity=match.similarity,
                time_gap_seconds=match.time_gap_seconds,
                source=match.source,
                thumbnail_url=_get_thumbnail_url(match.detection_id),
                attributes=match.attributes,
            )
            for match in limited_matches
        ]

        return SimilaritySearchResponse(
            matches=match_items,
            total_matches=len(matches),
            threshold=request.threshold,
            entity_type=request.entity_type,
            include_historical=request.include_historical,
        )

    except Exception as e:
        logger.error("Re-ID similarity search failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Similarity search failed: {e!s}",
        ) from e


@router.get(
    "/similar/{detection_id}",
    response_model=SimilaritySearchResponse,
    responses={
        404: {"description": "Detection not found or no embedding stored"},
        503: {"description": "Redis service unavailable"},
        500: {"description": "Internal server error"},
    },
)
async def find_similar_by_detection(
    detection_id: str,
    entity_type: str = Query(
        default="person",
        pattern="^(person|vehicle)$",
        description="Type of entity to search for",
    ),
    threshold: float = Query(
        default=DEFAULT_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    include_historical: bool = Query(
        default=True,
        description="Include historical (PostgreSQL) data",
    ),
    reid_service: ReIdentificationService = Depends(get_reid_service),
    hybrid_storage: HybridEntityStorage = Depends(get_hybrid_entity_storage),
) -> SimilaritySearchResponse:
    """Find entities similar to a specific detection.

    This endpoint retrieves the embedding for the specified detection ID
    and searches for similar entities. Useful for finding re-identification
    matches for a known detection.

    Args:
        detection_id: Detection ID to find similar entities for
        entity_type: Type of entity ('person' or 'vehicle')
        threshold: Minimum cosine similarity threshold
        limit: Maximum number of results
        include_historical: Whether to include historical PostgreSQL data
        reid_service: Re-identification service
        hybrid_storage: Hybrid storage service

    Returns:
        SimilaritySearchResponse with matching entities

    Raises:
        HTTPException: 404 if detection/embedding not found, 503 if Redis unavailable
    """
    logger.info(
        "Find similar by detection: detection_id=%s, entity_type=%s, threshold=%.2f",
        detection_id,
        entity_type,
        threshold,
    )

    redis = await _get_redis_client()

    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )

    try:
        # Get all embeddings for the entity type to find the one for this detection
        all_embeddings = await reid_service.get_entity_history(
            redis_client=redis,
            entity_type=entity_type,
        )

        # Find the embedding for the requested detection
        query_embedding = None
        for emb in all_embeddings:
            if emb.detection_id == detection_id:
                query_embedding = emb
                break

        if query_embedding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No embedding found for detection '{detection_id}'",
            )

        # Search for similar entities using hybrid storage
        matches = await hybrid_storage.find_matches(
            embedding=query_embedding.embedding,
            entity_type=entity_type,
            threshold=threshold,
            exclude_detection_id=detection_id,
            include_historical=include_historical,
        )

        # Apply limit
        limited_matches = matches[:limit]

        # Convert to response format
        match_items = [
            SimilarityMatch(
                entity_id=str(match.entity_id),
                entity_type=match.entity_type,
                camera_id=match.camera_id,
                timestamp=match.timestamp,
                detection_id=match.detection_id,
                similarity=match.similarity,
                time_gap_seconds=match.time_gap_seconds,
                source=match.source,
                thumbnail_url=_get_thumbnail_url(match.detection_id),
                attributes=match.attributes,
            )
            for match in limited_matches
        ]

        return SimilaritySearchResponse(
            matches=match_items,
            total_matches=len(matches),
            threshold=threshold,
            entity_type=entity_type,
            include_historical=include_historical,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Find similar by detection failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {e!s}",
        ) from e
