"""API routes for entity re-identification tracking.

This module provides endpoints for tracking entities (persons and vehicles)
across multiple cameras using CLIP embeddings stored in Redis and PostgreSQL.

Features:
- Historical entity queries (PostgreSQL 30-day retention)
- Real-time entity tracking (Redis 24-hour hot cache)
- Source filtering (redis, postgres, both)
- Date range filtering (since, until)
- Entity statistics and aggregations

Related to NEM-2500: Phase 3.1 Historical Entity Lookup API.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from backend.api.schemas.entities import (
    DetectionSummary,
    EntityDetail,
    EntityDetectionsResponse,
    EntityHistoryResponse,
    EntityListResponse,
    EntityMatchItem,
    EntityMatchResponse,
    EntityStatsResponse,
    EntitySummary,
    EntityTrustResponse,
    EntityTrustUpdate,
    EntityTypeFilter,
    SourceFilter,
    TrustedEntityListResponse,
    TrustStatus,
)
from backend.api.schemas.logs import PaginationInfo
from backend.core.dependencies import get_entity_repository, get_hybrid_entity_storage
from backend.core.logging import get_logger
from backend.core.redis import get_redis_optional
from backend.services.reid_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EntityEmbedding,
    ReIdentificationService,
    get_reid_service,
)

if TYPE_CHECKING:
    from backend.models import Entity
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.hybrid_entity_storage import HybridEntityStorage

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
    entity_type: EntityTypeFilter | None = Query(
        None, description="Filter by entity type: 'person' or 'vehicle'"
    ),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    since: datetime | None = Query(None, description="Filter entities seen since this time"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityListResponse:
    """List tracked entities with optional filtering.

    Returns a paginated list of entities from PostgreSQL. Entities are
    tracked via re-identification and stored in the database.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        camera_id: Filter by camera ID
        since: Filter entities seen since this timestamp
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        EntityListResponse with filtered entities and pagination info
    """
    # Convert entity_type filter to string for repository query
    entity_type_str = entity_type.value if entity_type else None

    # Query PostgreSQL via EntityRepository
    entities, total_count = await entity_repo.list(
        entity_type=entity_type_str,
        camera_id=camera_id,
        since=since,
        limit=limit,
        offset=offset,
    )

    # Convert Entity models to EntitySummary
    summaries: list[EntitySummary] = []
    for entity in entities:
        summary = _entity_model_to_summary(entity)
        summaries.append(summary)

    # Determine if there are more results
    has_more = (offset + limit) < total_count

    return EntityListResponse(
        items=summaries,
        pagination=PaginationInfo(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


@router.get(
    "/stats",
    response_model=EntityStatsResponse,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_entity_stats(
    since: datetime | None = Query(None, description="Filter entities seen since this time"),
    until: datetime | None = Query(None, description="Filter entities seen until this time"),
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityStatsResponse:
    """Get aggregated entity statistics.

    Returns statistics about tracked entities including counts by type,
    camera, and repeat visitors.

    Args:
        since: Filter entities seen since this timestamp
        until: Filter entities seen until this timestamp
        entity_repo: Entity repository dependency

    Returns:
        EntityStatsResponse with aggregated statistics
    """
    # Get type counts
    by_type = await entity_repo.get_type_counts()

    # Get total detection count
    total_appearances = await entity_repo.get_total_detection_count()

    # Get camera counts
    by_camera = await entity_repo.get_camera_counts()

    # Get repeat visitor count
    repeat_visitors = await entity_repo.get_repeat_visitor_count()

    # Get total entity count
    total_entities = await entity_repo.count()

    # Build time range if filters provided
    time_range = None
    if since is not None or until is not None:
        time_range = {"since": since, "until": until}

    return EntityStatsResponse(
        total_entities=total_entities,
        total_appearances=total_appearances,
        by_type=by_type,
        by_camera=by_camera,
        repeat_visitors=repeat_visitors,
        time_range=time_range,
    )


# =============================================================================
# Entity Trust Classification API (NEM-2671)
# =============================================================================


def _entity_to_trust_response(entity: Entity) -> EntityTrustResponse:
    """Convert an Entity model to EntityTrustResponse.

    Args:
        entity: Entity model instance from PostgreSQL

    Returns:
        EntityTrustResponse with trust information
    """
    from datetime import datetime as dt

    # Extract trust fields from entity_metadata
    trust_status_str = "unclassified"
    trust_notes = None
    trust_updated_at = None

    if entity.entity_metadata:
        trust_status_str = entity.entity_metadata.get("trust_status", "unclassified")
        trust_notes = entity.entity_metadata.get("trust_notes")
        trust_updated_at_str = entity.entity_metadata.get("trust_updated_at")
        if trust_updated_at_str:
            try:
                trust_updated_at = dt.fromisoformat(trust_updated_at_str)
            except (ValueError, TypeError):
                pass

    # Convert trust status string to enum
    try:
        trust_status = TrustStatus(trust_status_str)
    except ValueError:
        trust_status = TrustStatus.UNCLASSIFIED

    thumbnail_url = None
    if entity.primary_detection_id:
        thumbnail_url = _get_thumbnail_url(str(entity.primary_detection_id))

    return EntityTrustResponse(
        id=str(entity.id),
        entity_type=entity.entity_type,
        trust_status=trust_status,
        trust_notes=trust_notes,
        trust_updated_at=trust_updated_at,
        first_seen=entity.first_seen_at,
        last_seen=entity.last_seen_at,
        appearance_count=entity.detection_count,
        thumbnail_url=thumbnail_url,
    )


@router.get(
    "/trusted",
    response_model=TrustedEntityListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_trusted_entities(
    entity_type: EntityTypeFilter | None = Query(
        None, description="Filter by entity type: 'person' or 'vehicle'"
    ),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> TrustedEntityListResponse:
    """List all trusted entities.

    Returns a paginated list of entities that have been marked as trusted.
    Trusted entities are those that have been classified as known/safe,
    such as family members, regular visitors, or delivery personnel.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        TrustedEntityListResponse with filtered trusted entities and pagination info
    """
    entity_type_str = entity_type.value if entity_type else None

    entities, total_count = await entity_repo.list_by_trust_status(
        trust_status="trusted",
        entity_type=entity_type_str,
        limit=limit,
        offset=offset,
    )

    # Convert Entity models to EntityTrustResponse
    items = [_entity_to_trust_response(entity) for entity in entities]

    has_more = (offset + limit) < total_count

    return TrustedEntityListResponse(
        items=items,
        pagination=PaginationInfo(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


@router.get(
    "/untrusted",
    response_model=TrustedEntityListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_untrusted_entities(
    entity_type: EntityTypeFilter | None = Query(
        None, description="Filter by entity type: 'person' or 'vehicle'"
    ),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> TrustedEntityListResponse:
    """List all untrusted entities.

    Returns a paginated list of entities that have been marked as untrusted.
    Untrusted entities are those that have been classified as unknown or suspicious,
    requiring additional monitoring.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        TrustedEntityListResponse with filtered untrusted entities and pagination info
    """
    entity_type_str = entity_type.value if entity_type else None

    entities, total_count = await entity_repo.list_by_trust_status(
        trust_status="untrusted",
        entity_type=entity_type_str,
        limit=limit,
        offset=offset,
    )

    # Convert Entity models to EntityTrustResponse
    items = [_entity_to_trust_response(entity) for entity in entities]

    has_more = (offset + limit) < total_count

    return TrustedEntityListResponse(
        items=items,
        pagination=PaginationInfo(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


@router.patch(
    "/{entity_id}/trust",
    response_model=EntityTrustResponse,
    responses={
        404: {"description": "Entity not found"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_entity_trust(
    entity_id: UUID,
    trust_update: EntityTrustUpdate,
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityTrustResponse:
    """Update an entity's trust classification status.

    Allows marking entities as trusted (known/safe), untrusted (suspicious),
    or unclassified (default). Includes optional notes for documenting
    the classification decision.

    Args:
        entity_id: UUID of the entity to update
        trust_update: Trust status update request containing trust_status and optional notes
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        EntityTrustResponse with updated trust information

    Raises:
        HTTPException: 404 if entity not found
    """
    entity = await entity_repo.update_trust_status(
        entity_id=entity_id,
        trust_status=trust_update.trust_status.value,
        trust_notes=trust_update.notes,
    )

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    return _entity_to_trust_response(entity)


@router.get(
    "/{entity_id}",
    response_model=EntityDetail,
    responses={
        404: {"description": "Entity not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity(
    entity_id: UUID,
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityDetail:
    """Get detailed information about a specific entity.

    Returns the entity's summary information along with all recorded appearances
    from PostgreSQL.

    Args:
        entity_id: UUID of the entity
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        EntityDetail with full entity information

    Raises:
        HTTPException: 404 if entity not found
    """
    # Query PostgreSQL for the entity
    entity = await entity_repo.get_by_id(entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Get detections for this entity to build appearances list
    detections, _total = await entity_repo.get_detections_for_entity(
        entity_id=entity_id,
        limit=1000,  # Get all detections
        offset=0,
    )

    # Build appearances list from detections
    from backend.api.schemas.entities import EntityAppearance

    appearances = [
        EntityAppearance(
            detection_id=str(det.id),
            camera_id=det.camera_id,
            camera_name=det.camera_id.replace("_", " ").title(),  # Simple name formatting
            timestamp=det.detected_at,
            thumbnail_url=f"/api/detections/{det.id}/image" if det.id else None,
            similarity_score=1.0,  # Similarity to self is always 1.0
            attributes={},  # Detection attributes could be added here
        )
        for det in detections
    ]

    # Extract cameras from entity metadata
    cameras_seen = []
    if entity.entity_metadata and "camera_id" in entity.entity_metadata:
        cameras_seen = [entity.entity_metadata["camera_id"]]

    thumbnail_url = None
    if entity.primary_detection_id:
        thumbnail_url = _get_thumbnail_url(str(entity.primary_detection_id))

    # Extract trust fields from entity_metadata
    trust_status = None
    trust_updated_at = None
    if entity.entity_metadata:
        trust_status = entity.entity_metadata.get("trust_status")
        trust_updated_at_str = entity.entity_metadata.get("trust_updated_at")
        if trust_updated_at_str:
            from datetime import datetime as dt

            try:
                trust_updated_at = dt.fromisoformat(trust_updated_at_str)
            except (ValueError, TypeError):
                pass

    return EntityDetail(
        id=str(entity.id),
        entity_type=entity.entity_type,
        first_seen=entity.first_seen_at,
        last_seen=entity.last_seen_at,
        appearance_count=entity.detection_count,
        cameras_seen=cameras_seen,
        thumbnail_url=thumbnail_url,
        appearances=appearances,
        trust_status=trust_status,
        trust_updated_at=trust_updated_at,
    )


@router.get(
    "/{entity_id}/history",
    response_model=EntityHistoryResponse,
    responses={
        404: {"description": "Entity not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity_history(
    entity_id: UUID,
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityHistoryResponse:
    """Get the appearance timeline for a specific entity.

    Returns a chronological list of all appearances for the entity
    across all cameras from PostgreSQL.

    Args:
        entity_id: UUID of the entity
        entity_repo: Entity repository dependency for PostgreSQL queries

    Returns:
        EntityHistoryResponse with appearance timeline

    Raises:
        HTTPException: 404 if entity not found
    """
    # Query PostgreSQL for the entity
    entity = await entity_repo.get_by_id(entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Get detections for this entity
    detections, total = await entity_repo.get_detections_for_entity(
        entity_id=entity_id,
        limit=1000,  # Get all detections for history
        offset=0,
    )

    # Build appearances list from detections (sorted by timestamp)
    from backend.api.schemas.entities import EntityAppearance

    # Detections should already be sorted by timestamp from the query
    appearances = [
        EntityAppearance(
            detection_id=str(det.id),
            camera_id=det.camera_id,
            camera_name=det.camera_id.replace("_", " ").title(),
            timestamp=det.detected_at,
            thumbnail_url=f"/api/detections/{det.id}/image" if det.id else None,
            similarity_score=1.0,  # Similarity to self is always 1.0
            attributes={},  # Detection attributes could be added here
        )
        for det in detections
    ]

    return EntityHistoryResponse(
        entity_id=str(entity_id),
        entity_type=entity.entity_type,
        appearances=appearances,
        count=total,
    )


@router.get(
    "/matches/{detection_id}",
    response_model=EntityMatchResponse,
    responses={
        404: {"description": "Detection not found or no embedding stored"},
        503: {"description": "Redis service unavailable"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity_matches(
    detection_id: str,
    entity_type: EntityTypeFilter = Query(
        EntityTypeFilter.person, description="Type of entity to search for matches"
    ),
    threshold: float = Query(
        DEFAULT_SIMILARITY_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for matches",
    ),
    reid_service: ReIdentificationService = Depends(get_reid_service),
) -> EntityMatchResponse:
    """Find entities matching a specific detection's embedding.

    Searches for entities similar to the specified detection's embedding
    across all cameras. Used to show re-ID matches in the EventDetailModal.

    NOTE: This endpoint continues to use Redis for real-time similarity matching.

    Args:
        detection_id: Detection ID to find matches for
        entity_type: Type of entity to search ('person' or 'vehicle')
        threshold: Minimum cosine similarity threshold (default 0.85)
        reid_service: Re-identification service dependency

    Returns:
        EntityMatchResponse with matching entities sorted by similarity

    Raises:
        HTTPException: 404 if detection embedding not found, 503 if Redis unavailable
    """
    redis = await _get_redis_client()

    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )

    # First, find the embedding for the requested detection
    all_embeddings = await reid_service.get_entity_history(
        redis_client=redis,
        entity_type=entity_type.value,
    )

    # Find the embedding for the requested detection
    query_embedding: EntityEmbedding | None = None
    for emb in all_embeddings:
        if emb.detection_id == detection_id:
            query_embedding = emb
            break

    if query_embedding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No embedding found for detection '{detection_id}'",
        )

    # Find matching entities
    matches = await reid_service.find_matching_entities(
        redis_client=redis,
        embedding=query_embedding.embedding,
        entity_type=entity_type.value,
        threshold=threshold,
        exclude_detection_id=detection_id,
    )

    # Convert matches to response format
    match_items = [
        EntityMatchItem(
            entity_id=match.entity.detection_id,
            entity_type=match.entity.entity_type,
            camera_id=match.entity.camera_id,
            camera_name=match.entity.camera_id.replace("_", " ").title(),
            timestamp=match.entity.timestamp,
            thumbnail_url=_get_thumbnail_url(match.entity.detection_id),
            similarity_score=match.similarity,
            time_gap_seconds=match.time_gap_seconds,
            attributes=match.entity.attributes,
        )
        for match in matches
    ]

    return EntityMatchResponse(
        query_detection_id=detection_id,
        entity_type=entity_type.value,
        matches=match_items,
        total_matches=len(match_items),
        threshold=threshold,
    )


# =============================================================================
# Historical Entity Lookup API (NEM-2500)
# =============================================================================


def _entity_model_to_summary(entity: Entity) -> EntitySummary:
    """Convert a PostgreSQL Entity model to EntitySummary.

    Args:
        entity: Entity model instance from PostgreSQL

    Returns:
        EntitySummary with entity information
    """
    from datetime import datetime as dt

    # Extract cameras from entity_metadata if available
    cameras_seen = []
    trust_status = None
    trust_updated_at = None

    if entity.entity_metadata:
        if "cameras_seen" in entity.entity_metadata:
            # Use cameras_seen list if available (preferred)
            cameras_seen = entity.entity_metadata["cameras_seen"]
        elif "camera_id" in entity.entity_metadata:
            # Fall back to single camera_id for backward compatibility
            cameras_seen = [entity.entity_metadata["camera_id"]]

        # Extract trust fields
        trust_status = entity.entity_metadata.get("trust_status")
        trust_updated_at_str = entity.entity_metadata.get("trust_updated_at")
        if trust_updated_at_str:
            try:
                trust_updated_at = dt.fromisoformat(trust_updated_at_str)
            except (ValueError, TypeError):
                pass

    thumbnail_url = None
    if entity.primary_detection_id:
        thumbnail_url = _get_thumbnail_url(str(entity.primary_detection_id))

    return EntitySummary(
        id=str(entity.id),
        entity_type=entity.entity_type,
        first_seen=entity.first_seen_at,
        last_seen=entity.last_seen_at,
        appearance_count=entity.detection_count,
        cameras_seen=cameras_seen,
        thumbnail_url=thumbnail_url,
        trust_status=trust_status,
        trust_updated_at=trust_updated_at,
    )


async def _query_redis_entities(
    entity_type: EntityTypeFilter | None,
    camera_id: str | None,
    since: datetime | None,
    until: datetime | None,
    reid_service: ReIdentificationService,
) -> list[EntitySummary]:
    """Query entities from Redis hot cache.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        camera_id: Filter by camera ID
        since: Filter entities seen since this timestamp
        until: Filter entities seen until this timestamp
        reid_service: Re-identification service dependency

    Returns:
        List of EntitySummary from Redis
    """
    summaries: list[EntitySummary] = []
    redis = await _get_redis_client()

    if redis is None:
        return summaries

    # Determine which entity types to query
    entity_types = [entity_type.value] if entity_type else ["person", "vehicle"]

    # Collect all embeddings from Redis
    all_embeddings: list[EntityEmbedding] = []
    for etype in entity_types:
        embeddings = await reid_service.get_entity_history(
            redis_client=redis,
            entity_type=etype,
            camera_id=camera_id,
        )
        all_embeddings.extend(embeddings)

    # Filter by since/until timestamps
    all_embeddings = _filter_embeddings_by_time(all_embeddings, since, until)

    # Group embeddings by detection_id and convert to summaries
    entities_by_id: dict[str, list[EntityEmbedding]] = {}
    for emb in all_embeddings:
        entity_id = emb.detection_id
        if entity_id not in entities_by_id:
            entities_by_id[entity_id] = []
        entities_by_id[entity_id].append(emb)

    for entity_id, embeddings in entities_by_id.items():
        try:
            summary = _entity_to_summary(entity_id, embeddings)
            summaries.append(summary)
        except ValueError:
            continue  # Skip empty entity groups

    return summaries


def _filter_embeddings_by_time(
    embeddings: list[EntityEmbedding],
    since: datetime | None,
    until: datetime | None,
) -> list[EntityEmbedding]:
    """Filter embeddings by timestamp range.

    Args:
        embeddings: List of embeddings to filter
        since: Start timestamp (inclusive)
        until: End timestamp (inclusive)

    Returns:
        Filtered list of embeddings
    """
    if since:
        embeddings = [e for e in embeddings if e.timestamp >= since]
    if until:
        embeddings = [e for e in embeddings if e.timestamp <= until]
    return embeddings


async def list_entities_with_source(
    entity_type: EntityTypeFilter | None,
    camera_id: str | None,
    since: datetime | None,
    until: datetime | None,
    source: SourceFilter,
    limit: int,
    offset: int,
    reid_service: ReIdentificationService,
    hybrid_storage: HybridEntityStorage | None,
) -> EntityListResponse:
    """Internal implementation for listing entities with source filtering.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        camera_id: Filter by camera ID
        since: Filter entities seen since this timestamp
        until: Filter entities seen until this timestamp
        source: Data source filter (redis, postgres, both)
        limit: Maximum number of results
        offset: Number of results to skip
        reid_service: Re-identification service dependency
        hybrid_storage: Hybrid storage service dependency (optional)

    Returns:
        EntityListResponse with filtered entities and pagination info
    """
    summaries: list[EntitySummary] = []

    # Query Redis if source includes Redis
    if source in (SourceFilter.redis, SourceFilter.both):
        redis_summaries = await _query_redis_entities(
            entity_type, camera_id, since, until, reid_service
        )
        summaries.extend(redis_summaries)

    # Query PostgreSQL if source includes PostgreSQL
    if source in (SourceFilter.postgres, SourceFilter.both) and hybrid_storage is not None:
        entity_type_str = entity_type.value if entity_type else None
        pg_entities, _total = await hybrid_storage.get_entities_by_timerange(
            entity_type=entity_type_str,
            since=since,
            until=until,
            limit=1000,  # Fetch more for merging
            offset=0,
        )

        # Convert PostgreSQL entities to summaries
        for entity in pg_entities:
            summary = _entity_model_to_summary(entity)
            summaries.append(summary)

    # Deduplicate by ID (prefer newer entries)
    seen_ids: set[str] = set()
    unique_summaries: list[EntitySummary] = []
    for summary in summaries:
        if summary.id not in seen_ids:
            seen_ids.add(summary.id)
            unique_summaries.append(summary)

    # Sort by last_seen (newest first)
    unique_summaries.sort(key=lambda s: s.last_seen, reverse=True)

    # Get total count before pagination
    total_count = len(unique_summaries)

    # Apply pagination
    paginated = unique_summaries[offset : offset + limit]

    # Determine if there are more results
    has_more = (offset + limit) < total_count

    return EntityListResponse(
        items=paginated,
        pagination=PaginationInfo(
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )


@router.get(
    "/v2",
    response_model=EntityListResponse,
    responses={
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def list_entities_v2(
    entity_type: EntityTypeFilter | None = Query(
        None, description="Filter by entity type: 'person' or 'vehicle'"
    ),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    since: datetime | None = Query(None, description="Filter entities seen since this time"),
    until: datetime | None = Query(None, description="Filter entities seen until this time"),
    source: SourceFilter = Query(
        SourceFilter.both, description="Data source: 'redis', 'postgres', or 'both'"
    ),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    reid_service: ReIdentificationService = Depends(get_reid_service),
    hybrid_storage: HybridEntityStorage = Depends(get_hybrid_entity_storage),
) -> EntityListResponse:
    """List tracked entities with historical query support.

    Returns a paginated list of entities from Redis (hot cache) and/or
    PostgreSQL (historical data). Use the source parameter to control
    which backend to query.

    Args:
        entity_type: Filter by entity type ('person' or 'vehicle')
        camera_id: Filter by camera ID
        since: Filter entities seen since this timestamp
        until: Filter entities seen until this timestamp
        source: Data source ('redis', 'postgres', 'both') - default 'both'
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        reid_service: Re-identification service dependency
        hybrid_storage: Hybrid storage service dependency

    Returns:
        EntityListResponse with filtered entities and pagination info
    """
    return await list_entities_with_source(
        entity_type=entity_type,
        camera_id=camera_id,
        since=since,
        until=until,
        source=source,
        limit=limit,
        offset=offset,
        reid_service=reid_service,
        hybrid_storage=hybrid_storage,
    )


async def get_entity_by_uuid(
    entity_id: UUID,
    hybrid_storage: HybridEntityStorage,
) -> EntityDetail:
    """Get entity by UUID from PostgreSQL.

    Args:
        entity_id: UUID of the entity
        hybrid_storage: Hybrid storage service dependency

    Returns:
        EntityDetail with entity information

    Raises:
        HTTPException: 404 if entity not found
    """
    from datetime import datetime as dt

    entity = await hybrid_storage.get_entity_full_history(entity_id)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Extract cameras and trust fields from metadata
    cameras_seen = []
    trust_status = None
    trust_updated_at = None

    if entity.entity_metadata:
        if "cameras_seen" in entity.entity_metadata:
            # Use cameras_seen list if available (preferred)
            cameras_seen = entity.entity_metadata["cameras_seen"]
        elif "camera_id" in entity.entity_metadata:
            # Fall back to single camera_id for backward compatibility
            cameras_seen = [entity.entity_metadata["camera_id"]]

        # Extract trust fields
        trust_status = entity.entity_metadata.get("trust_status")
        trust_updated_at_str = entity.entity_metadata.get("trust_updated_at")
        if trust_updated_at_str:
            try:
                trust_updated_at = dt.fromisoformat(trust_updated_at_str)
            except (ValueError, TypeError):
                pass

    thumbnail_url = None
    if entity.primary_detection_id:
        thumbnail_url = _get_thumbnail_url(str(entity.primary_detection_id))

    return EntityDetail(
        id=str(entity.id),
        entity_type=entity.entity_type,
        first_seen=entity.first_seen_at,
        last_seen=entity.last_seen_at,
        appearance_count=entity.detection_count,
        cameras_seen=cameras_seen,
        thumbnail_url=thumbnail_url,
        appearances=[],  # Would require joining with detections table
        trust_status=trust_status,
        trust_updated_at=trust_updated_at,
    )


@router.get(
    "/v2/{entity_id}",
    response_model=EntityDetail,
    responses={
        404: {"description": "Entity not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity_v2(
    entity_id: UUID,
    hybrid_storage: HybridEntityStorage = Depends(get_hybrid_entity_storage),
) -> EntityDetail:
    """Get detailed information about a specific entity from PostgreSQL.

    Returns the canonical PostgreSQL entity record with full history.
    For real-time Redis entities, use the original /api/entities/{entity_id} endpoint.

    Args:
        entity_id: UUID of the entity
        hybrid_storage: Hybrid storage service dependency

    Returns:
        EntityDetail with full entity information

    Raises:
        HTTPException: 404 if entity not found
    """
    return await get_entity_by_uuid(entity_id=entity_id, hybrid_storage=hybrid_storage)


@router.get(
    "/v2/{entity_id}/detections",
    response_model=EntityDetectionsResponse,
    responses={
        404: {"description": "Entity not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_entity_detections(
    entity_id: UUID,
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    entity_repo: EntityRepository = Depends(get_entity_repository),
) -> EntityDetectionsResponse:
    """List all detections linked to an entity.

    Returns paginated detections associated with the specified entity.

    Args:
        entity_id: UUID of the entity
        limit: Maximum number of results (1-1000, default 50)
        offset: Number of results to skip for pagination (default 0)
        entity_repo: Entity repository dependency

    Returns:
        EntityDetectionsResponse with linked detections and pagination info

    Raises:
        HTTPException: 404 if entity not found
    """
    # First verify entity exists
    entity = await entity_repo.get_by_id(entity_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with id '{entity_id}' not found",
        )

    # Get detections for this entity
    detections, total = await entity_repo.get_detections_for_entity(
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )

    # Convert to detection summaries
    detection_summaries = [
        DetectionSummary(
            detection_id=det.id,
            camera_id=det.camera_id,
            camera_name=det.camera_id.replace("_", " ").title(),
            timestamp=det.detected_at,
            confidence=det.confidence,
            thumbnail_url=f"/api/detections/{det.id}/image" if det.id else None,
            object_type=det.object_type,
        )
        for det in detections
    ]

    has_more = (offset + limit) < total

    return EntityDetectionsResponse(
        entity_id=str(entity_id),
        entity_type=entity.entity_type,
        detections=detection_summaries,
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
    )
