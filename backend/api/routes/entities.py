"""API routes for entity re-identification tracking.

This module provides endpoints for tracking entities (persons and vehicles)
across multiple cameras using CLIP embeddings stored in Redis.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from backend.api.schemas.entities import (
    EntityDetail,
    EntityHistoryResponse,
    EntityListResponse,
    EntitySummary,
)
from backend.core.logging import get_logger
from backend.core.redis import get_redis_optional
from backend.services.reid_service import (
    EntityEmbedding,
    ReIdentificationService,
    get_reid_service,
)


class EntityTypeEnum(str, Enum):
    """Valid entity types for filtering."""

    person = "person"
    vehicle = "vehicle"


router = APIRouter(prefix="/api/entities", tags=["entities"])

logger = get_logger(__name__)


def _get_thumbnail_url(detection_id: str) -> str:
    """Generate thumbnail URL for a detection.

    Args:
        detection_id: Detection ID

    Returns:
        URL path to the detection's thumbnail image
    """
    # Try to parse as integer for database detection IDs
    try:
        int_id = int(detection_id)
        return f"/api/detections/{int_id}/image"
    except ValueError:
        # For non-integer IDs, use as-is
        return f"/api/detections/{detection_id}/image"


def _entity_to_summary(
    entity_id: str,
    embeddings: list[EntityEmbedding],
) -> EntitySummary:
    """Convert a list of embeddings for an entity to a summary.

    Args:
        entity_id: Unique identifier for the entity
        embeddings: List of EntityEmbedding objects for this entity

    Returns:
        EntitySummary with aggregated information
    """
    if not embeddings:
        raise ValueError("Cannot create summary from empty embeddings list")

    # Sort by timestamp
    sorted_embeddings = sorted(embeddings, key=lambda e: e.timestamp)

    # Get unique cameras
    cameras_seen = list({e.camera_id for e in sorted_embeddings})

    # Get most recent thumbnail
    latest = sorted_embeddings[-1]
    thumbnail_url = _get_thumbnail_url(latest.detection_id)

    return EntitySummary(
        id=entity_id,
        entity_type=latest.entity_type,
        first_seen=sorted_embeddings[0].timestamp,
        last_seen=latest.timestamp,
        appearance_count=len(embeddings),
        cameras_seen=cameras_seen,
        thumbnail_url=thumbnail_url,
    )


async def _get_redis_client() -> Redis | None:
    """Get raw Redis client from the dependency.

    Returns:
        Raw redis.asyncio.Redis client or None if not available
    """
    async for client in get_redis_optional():
        if client is not None:
            # Get the raw Redis client from our RedisClient wrapper
            return client._ensure_connected()
        return None
    return None


@router.get(
    "",
    response_model=EntityListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_entities(
    entity_type: EntityTypeEnum | None = Query(
        None, description="Filter by entity type: 'person' or 'vehicle'"
    ),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    since: datetime | None = Query(None, description="Filter entities seen since this time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    reid_service: ReIdentificationService = Depends(get_reid_service),
) -> dict[str, Any]:
    """List tracked entities with optional filtering.

    Returns a paginated list of entities that have been tracked via
    re-identification. Entities are grouped by their embedding clusters.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        camera_id: Filter by camera ID
        since: Filter entities seen since this timestamp
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        reid_service: Re-identification service dependency

    Returns:
        EntityListResponse with filtered entities and pagination info
    """
    redis = await _get_redis_client()

    if redis is None:
        logger.warning("Redis not available for entity list")
        return {
            "entities": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
        }

    # Determine which entity types to query
    entity_types = [entity_type.value] if entity_type else ["person", "vehicle"]

    # Collect all embeddings
    all_embeddings: list[EntityEmbedding] = []
    for etype in entity_types:
        embeddings = await reid_service.get_entity_history(
            redis_client=redis,
            entity_type=etype,
            camera_id=camera_id,
        )
        all_embeddings.extend(embeddings)

    # Filter by since timestamp if provided
    if since:
        all_embeddings = [e for e in all_embeddings if e.timestamp >= since]

    # Group embeddings by detection_id (each detection is treated as a unique entity
    # until we implement proper clustering)
    # For now, we use detection_id as entity_id since embeddings are stored per-detection
    entities_by_id: dict[str, list[EntityEmbedding]] = {}
    for emb in all_embeddings:
        entity_id = emb.detection_id
        if entity_id not in entities_by_id:
            entities_by_id[entity_id] = []
        entities_by_id[entity_id].append(emb)

    # Convert to summaries
    summaries: list[EntitySummary] = []
    for entity_id, embeddings in entities_by_id.items():
        try:
            summary = _entity_to_summary(entity_id, embeddings)
            summaries.append(summary)
        except ValueError:
            continue  # Skip empty entity groups

    # Sort by last_seen (newest first)
    summaries.sort(key=lambda s: s.last_seen, reverse=True)

    # Get total count before pagination
    total_count = len(summaries)

    # Apply pagination
    paginated = summaries[offset : offset + limit]

    return {
        "entities": paginated,
        "count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{entity_id}",
    response_model=EntityDetail,
    responses={
        404: {"description": "Entity not found"},
        503: {"description": "Redis service unavailable"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity(
    entity_id: str,
    reid_service: ReIdentificationService = Depends(get_reid_service),
) -> EntityDetail:
    """Get detailed information about a specific entity.

    Returns the entity's summary information along with all recorded appearances.

    Args:
        entity_id: Unique entity identifier (detection_id)
        reid_service: Re-identification service dependency

    Returns:
        EntityDetail with full entity information

    Raises:
        HTTPException: 404 if entity not found, 503 if Redis unavailable
    """
    redis = await _get_redis_client()

    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )

    # Search for entity in both person and vehicle types
    found_embeddings: list[EntityEmbedding] = []
    entity_type_found: str | None = None

    for etype in ["person", "vehicle"]:
        embeddings = await reid_service.get_entity_history(
            redis_client=redis,
            entity_type=etype,
        )
        # Find embeddings matching this entity_id
        matching = [e for e in embeddings if e.detection_id == entity_id]
        if matching:
            found_embeddings.extend(matching)
            entity_type_found = etype
            break

    if not found_embeddings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Sort by timestamp
    sorted_embeddings = sorted(found_embeddings, key=lambda e: e.timestamp)

    # Build appearances list
    from backend.api.schemas.entities import EntityAppearance

    appearances = [
        EntityAppearance(
            detection_id=emb.detection_id,
            camera_id=emb.camera_id,
            camera_name=emb.camera_id.replace("_", " ").title(),  # Simple name formatting
            timestamp=emb.timestamp,
            thumbnail_url=_get_thumbnail_url(emb.detection_id),
            similarity_score=1.0,  # First appearance is always 1.0
            attributes=emb.attributes,
        )
        for emb in sorted_embeddings
    ]

    # Get unique cameras
    cameras_seen = list({e.camera_id for e in sorted_embeddings})

    return EntityDetail(
        id=entity_id,
        entity_type=entity_type_found or "person",
        first_seen=sorted_embeddings[0].timestamp,
        last_seen=sorted_embeddings[-1].timestamp,
        appearance_count=len(sorted_embeddings),
        cameras_seen=cameras_seen,
        thumbnail_url=_get_thumbnail_url(sorted_embeddings[-1].detection_id),
        appearances=appearances,
    )


@router.get(
    "/{entity_id}/history",
    response_model=EntityHistoryResponse,
    responses={
        404: {"description": "Entity not found"},
        503: {"description": "Redis service unavailable"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity_history(
    entity_id: str,
    reid_service: ReIdentificationService = Depends(get_reid_service),
) -> EntityHistoryResponse:
    """Get the appearance timeline for a specific entity.

    Returns a chronological list of all appearances for the entity
    across all cameras.

    Args:
        entity_id: Unique entity identifier (detection_id)
        reid_service: Re-identification service dependency

    Returns:
        EntityHistoryResponse with appearance timeline

    Raises:
        HTTPException: 404 if entity not found, 503 if Redis unavailable
    """
    redis = await _get_redis_client()

    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )

    # Search for entity in both person and vehicle types
    found_embeddings: list[EntityEmbedding] = []
    entity_type_found: str | None = None

    for etype in ["person", "vehicle"]:
        embeddings = await reid_service.get_entity_history(
            redis_client=redis,
            entity_type=etype,
        )
        # Find embeddings matching this entity_id
        matching = [e for e in embeddings if e.detection_id == entity_id]
        if matching:
            found_embeddings.extend(matching)
            entity_type_found = etype
            break

    if not found_embeddings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Sort by timestamp (chronological order)
    sorted_embeddings = sorted(found_embeddings, key=lambda e: e.timestamp)

    # Build appearances list
    from backend.api.schemas.entities import EntityAppearance

    appearances = [
        EntityAppearance(
            detection_id=emb.detection_id,
            camera_id=emb.camera_id,
            camera_name=emb.camera_id.replace("_", " ").title(),
            timestamp=emb.timestamp,
            thumbnail_url=_get_thumbnail_url(emb.detection_id),
            similarity_score=1.0,
            attributes=emb.attributes,
        )
        for emb in sorted_embeddings
    ]

    return EntityHistoryResponse(
        entity_id=entity_id,
        entity_type=entity_type_found or "person",
        appearances=appearances,
        count=len(appearances),
    )
