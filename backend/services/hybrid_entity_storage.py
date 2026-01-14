"""Hybrid Entity Storage Bridge coordinating between Redis and PostgreSQL.

This module provides the HybridEntityStorage service which coordinates entity
storage between Redis (hot cache, 24h TTL) and PostgreSQL (persistence, 30d retention).

The service implements a write-through pattern:
- Write path: Store in both Redis (hot cache) AND PostgreSQL (persistence)
- Read path: Check Redis first (fast), fall back to PostgreSQL (historical)

Architecture:
                    +-----------------------+
                    |  HybridEntityStorage  |
                    |  (this service)       |
                    +----------+------------+
                               |
           +-------------------+-------------------+
           |                   |                   |
           v                   v                   v
    +-------------+     +-------------+     +----------------+
    | Redis       |     | PostgreSQL  |     | Clustering     |
    | (hot cache) |     | (persistence|     | Service        |
    | 24h TTL     |     | 30d retention     |                |
    +-------------+     +-------------+     +----------------+

Related to NEM-2498: Implement Hybrid Storage Bridge (Redis <-> PostgreSQL).
Part of Phase 2.1 of the Hybrid Entity Storage Architecture epic.

Usage:
    from backend.services.hybrid_entity_storage import HybridEntityStorage

    storage = HybridEntityStorage(
        redis_client=redis,
        entity_repository=repo,
        clustering_service=clustering,
        reid_service=reid,
    )

    # Store a detection embedding in both Redis and PostgreSQL
    entity_id, is_new = await storage.store_detection_embedding(
        detection_id=123,
        entity_type="person",
        embedding=[0.1, 0.2, ...],
        camera_id="front_door",
        timestamp=datetime.now(UTC),
    )

    # Find matches (Redis first, then PostgreSQL for historical)
    matches = await storage.find_matches(
        embedding=[0.1, 0.2, ...],
        entity_type="person",
        threshold=0.85,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from backend.core.logging import get_logger
from backend.services.reid_service import EntityEmbedding, EntityMatch

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from backend.models import Entity
    from backend.repositories.entity_repository import EntityRepository
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.services.reid_service import ReIdentificationService

logger = get_logger(__name__)


@dataclass(slots=True)
class HybridEntityMatch:
    """A match result from hybrid storage (Redis or PostgreSQL).

    Attributes:
        entity_id: UUID of the matched entity (from PostgreSQL) or detection_id (from Redis)
        entity_type: Type of entity (person, vehicle, etc.)
        embedding: The embedding vector of the matched entity
        camera_id: Camera that captured the entity
        timestamp: When the entity was detected
        detection_id: Detection ID (for Redis matches) or None
        attributes: Additional attributes from vision extraction
        similarity: Cosine similarity score (0-1)
        time_gap_seconds: Time difference in seconds from query
        source: Where the match was found ("redis" or "postgresql")
        entity: Optional full Entity object (only for PostgreSQL matches)
    """

    entity_id: UUID | str
    entity_type: str
    embedding: list[float]
    camera_id: str
    timestamp: datetime
    detection_id: str | None
    attributes: dict[str, Any]
    similarity: float
    time_gap_seconds: float
    source: Literal["redis", "postgresql"]
    entity: Entity | None = None

    @classmethod
    def from_redis_match(cls, match: EntityMatch) -> HybridEntityMatch:
        """Create HybridEntityMatch from Redis EntityMatch.

        Args:
            match: EntityMatch from ReIdentificationService

        Returns:
            HybridEntityMatch instance
        """
        return cls(
            entity_id=match.entity.detection_id,
            entity_type=match.entity.entity_type,
            embedding=match.entity.embedding,
            camera_id=match.entity.camera_id,
            timestamp=match.entity.timestamp,
            detection_id=match.entity.detection_id,
            attributes=match.entity.attributes,
            similarity=match.similarity,
            time_gap_seconds=match.time_gap_seconds,
            source="redis",
            entity=None,
        )

    @classmethod
    def from_postgresql_match(
        cls,
        entity: Entity,
        similarity: float,
        time_gap_seconds: float = 0.0,
    ) -> HybridEntityMatch:
        """Create HybridEntityMatch from PostgreSQL Entity.

        Args:
            entity: Entity from PostgreSQL
            similarity: Cosine similarity score
            time_gap_seconds: Time difference in seconds

        Returns:
            HybridEntityMatch instance
        """
        return cls(
            entity_id=entity.id,
            entity_type=entity.entity_type,
            embedding=entity.get_embedding_vector() or [],
            camera_id=entity.entity_metadata.get("camera_id", "unknown")
            if entity.entity_metadata
            else "unknown",
            timestamp=entity.last_seen_at,
            detection_id=str(entity.primary_detection_id) if entity.primary_detection_id else None,
            attributes=entity.entity_metadata or {},
            similarity=similarity,
            time_gap_seconds=time_gap_seconds,
            source="postgresql",
            entity=entity,
        )


class HybridEntityStorage:
    """Coordinates entity storage between Redis and PostgreSQL.

    Write path: Store in both Redis (hot cache) AND PostgreSQL (persistence)
    Read path: Check Redis first (fast), fall back to PostgreSQL (historical)

    This service bridges the gap between:
    - Redis (ReIdentificationService): Fast 24h hot cache for recent entities
    - PostgreSQL (EntityRepository): Persistent storage with 30-day retention

    The EntityClusteringService is used for PostgreSQL entity assignment,
    which handles deduplication and entity creation/update logic.

    Attributes:
        redis: Redis client for hot cache operations
        entity_repo: EntityRepository for PostgreSQL operations
        clustering: EntityClusteringService for entity assignment
        reid: ReIdentificationService for Redis embedding operations

    Example:
        storage = HybridEntityStorage(redis, repo, clustering, reid)

        # Store new detection
        entity_id, is_new = await storage.store_detection_embedding(
            detection_id=123,
            entity_type="person",
            embedding=embedding_vector,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
        )

        # Find matches
        matches = await storage.find_matches(
            embedding=embedding_vector,
            entity_type="person",
            threshold=0.85,
        )
    """

    def __init__(
        self,
        redis_client: Redis,
        entity_repository: EntityRepository,
        clustering_service: EntityClusteringService,
        reid_service: ReIdentificationService,
    ) -> None:
        """Initialize the HybridEntityStorage.

        Args:
            redis_client: Redis client for hot cache operations
            entity_repository: EntityRepository for PostgreSQL operations
            clustering_service: EntityClusteringService for entity assignment
            reid_service: ReIdentificationService for Redis embedding operations
        """
        self.redis = redis_client
        self.entity_repo = entity_repository
        self.clustering = clustering_service
        self.reid = reid_service

        logger.debug("HybridEntityStorage initialized")

    async def store_detection_embedding(
        self,
        detection_id: int,
        entity_type: str,
        embedding: list[float],
        camera_id: str,
        timestamp: datetime,
        attributes: dict[str, Any] | None = None,
    ) -> tuple[UUID, bool]:
        """Store embedding in both Redis and PostgreSQL.

        This method implements a write-through pattern:
        1. Assign entity via clustering service (PostgreSQL)
        2. Store embedding in Redis for hot cache access

        Args:
            detection_id: Database ID of the detection record
            entity_type: Type of entity ("person", "vehicle", etc.)
            embedding: Embedding vector (typically 768-dim CLIP embedding)
            camera_id: ID of the camera that captured the detection
            timestamp: When the detection occurred
            attributes: Optional attributes dict (clothing, color, etc.)

        Returns:
            Tuple of (entity_id, is_new_entity):
            - entity_id: UUID of the assigned entity
            - is_new_entity: True if a new entity was created

        Example:
            entity_id, is_new = await storage.store_detection_embedding(
                detection_id=123,
                entity_type="person",
                embedding=[0.1, 0.2, ...],
                camera_id="front_door",
                timestamp=datetime.now(UTC),
                attributes={"clothing": "blue jacket"},
            )
        """
        # Step 1: Store in PostgreSQL via clustering service
        # This handles entity matching and creation/update
        entity, is_new, _similarity = await self.clustering.assign_entity(
            detection_id=detection_id,
            entity_type=entity_type,
            embedding=embedding,
            camera_id=camera_id,
            timestamp=timestamp,
            attributes=attributes,
        )

        logger.debug(
            "Entity %s for detection %d (is_new=%s)",
            "created" if is_new else "matched",
            detection_id,
            is_new,
        )

        # Step 2: Store in Redis for hot cache access
        # Create EntityEmbedding for Reid service
        entity_embedding = EntityEmbedding(
            entity_type=entity_type,
            embedding=embedding,
            camera_id=camera_id,
            timestamp=timestamp,
            detection_id=str(detection_id),
            attributes=attributes or {},
        )

        try:
            await self.reid.store_embedding(self.redis, entity_embedding)
            logger.debug(
                "Stored embedding in Redis for detection %d",
                detection_id,
            )
        except Exception as e:
            # Log error but don't fail - PostgreSQL storage succeeded
            logger.warning(
                "Failed to store embedding in Redis for detection %d: %s",
                detection_id,
                str(e),
            )

        return entity.id, is_new

    async def find_matches(
        self,
        embedding: list[float],
        entity_type: str,
        threshold: float = 0.85,
        exclude_detection_id: str | None = None,
        include_historical: bool = True,
    ) -> list[HybridEntityMatch]:
        """Find matching entities, checking Redis first then PostgreSQL.

        This method implements a tiered lookup:
        1. Check Redis hot cache first (fast, recent entities)
        2. If include_historical=True, also check PostgreSQL (historical)
        3. Deduplicate results and sort by similarity

        Args:
            embedding: Query embedding vector
            entity_type: Type of entity to search ("person", "vehicle", etc.)
            threshold: Minimum cosine similarity threshold (default: 0.85)
            exclude_detection_id: Optional detection ID to exclude from results
            include_historical: If True, also search PostgreSQL (default: True)

        Returns:
            List of HybridEntityMatch objects sorted by similarity (highest first)

        Example:
            matches = await storage.find_matches(
                embedding=[0.1, 0.2, ...],
                entity_type="person",
                threshold=0.85,
                include_historical=True,
            )
            for match in matches:
                print(f"Found {match.source} match: {match.similarity:.2f}")
        """
        matches: list[HybridEntityMatch] = []
        seen_ids: set[str] = set()

        # Step 1: Check Redis hot cache first
        try:
            redis_matches = await self.reid.find_matching_entities(
                redis_client=self.redis,
                embedding=embedding,
                entity_type=entity_type,
                threshold=threshold,
                exclude_detection_id=exclude_detection_id,
            )

            for match in redis_matches:
                hybrid_match = HybridEntityMatch.from_redis_match(match)
                # Track by detection_id for deduplication
                if hybrid_match.detection_id:
                    seen_ids.add(hybrid_match.detection_id)
                matches.append(hybrid_match)

            logger.debug(
                "Found %d Redis matches for %s (threshold=%.2f)",
                len(redis_matches),
                entity_type,
                threshold,
            )

        except Exception as e:
            logger.warning(
                "Redis lookup failed, falling back to PostgreSQL only: %s",
                str(e),
            )

        # Step 2: Check PostgreSQL for historical matches
        if include_historical:
            try:
                pg_matches = await self.entity_repo.find_by_embedding(
                    embedding=embedding,
                    entity_type=entity_type,
                    threshold=threshold,
                    limit=50,  # Reasonable limit for historical search
                )

                for entity, similarity in pg_matches:
                    # Deduplicate: skip if we already have this entity from Redis
                    entity_detection_id = (
                        str(entity.primary_detection_id) if entity.primary_detection_id else None
                    )
                    if entity_detection_id and entity_detection_id in seen_ids:
                        continue

                    hybrid_match = HybridEntityMatch.from_postgresql_match(
                        entity=entity,
                        similarity=similarity,
                    )

                    # Track for deduplication
                    if entity_detection_id:
                        seen_ids.add(entity_detection_id)

                    matches.append(hybrid_match)

                logger.debug(
                    "Found %d PostgreSQL matches for %s (threshold=%.2f)",
                    len(pg_matches),
                    entity_type,
                    threshold,
                )

            except Exception as e:
                logger.warning(
                    "PostgreSQL lookup failed: %s",
                    str(e),
                )

        # Step 3: Sort by similarity (highest first)
        matches.sort(key=lambda m: m.similarity, reverse=True)

        logger.debug(
            "Total matches for %s: %d (Redis + PostgreSQL)",
            entity_type,
            len(matches),
        )

        return matches

    async def get_entity_full_history(
        self,
        entity_id: UUID,
    ) -> Entity | None:
        """Get entity with full history from PostgreSQL.

        Retrieves the complete entity record from PostgreSQL, including
        all metadata and history. This bypasses Redis as it requires
        the full persistent record.

        Args:
            entity_id: UUID of the entity to retrieve

        Returns:
            Entity instance if found, None otherwise

        Example:
            entity = await storage.get_entity_full_history(entity_id)
            if entity:
                print(f"Entity seen {entity.detection_count} times")
        """
        entity = await self.entity_repo.get_by_id(entity_id)

        if entity:
            logger.debug(
                "Retrieved entity %s with %d detections",
                entity_id,
                entity.detection_count,
            )
        else:
            logger.debug("Entity %s not found", entity_id)

        return entity

    async def get_entities_by_timerange(
        self,
        entity_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,  # noqa: ARG002 - Reserved for future repository support
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Entity], int]:
        """Query entities from PostgreSQL with time filtering.

        Retrieves entities from PostgreSQL filtered by type and/or
        time range. This is useful for historical analysis and
        reporting.

        Args:
            entity_type: Optional filter by entity type (person, vehicle, etc.)
            since: Optional start of time range (inclusive)
            until: Optional end of time range (inclusive)
            limit: Maximum number of entities to return (default: 50)
            offset: Number of entities to skip (default: 0)

        Returns:
            Tuple of (list of entities, total count matching filters)

        Example:
            entities, total = await storage.get_entities_by_timerange(
                entity_type="person",
                since=datetime.now(UTC) - timedelta(days=7),
                limit=20,
            )
        """
        entities, total = await self.entity_repo.list(
            entity_type=entity_type,
            since=since,
            limit=limit,
            offset=offset,
        )

        logger.debug(
            "Retrieved %d/%d entities (type=%s, since=%s)",
            len(entities),
            total,
            entity_type,
            since,
        )

        return entities, total


# =============================================================================
# Global Service Instance Management
# =============================================================================

_hybrid_entity_storage: HybridEntityStorage | None = None


def get_hybrid_entity_storage_instance() -> HybridEntityStorage | None:
    """Get the global HybridEntityStorage instance.

    Returns:
        HybridEntityStorage instance if initialized, None otherwise
    """
    return _hybrid_entity_storage


def set_hybrid_entity_storage_instance(storage: HybridEntityStorage) -> None:
    """Set the global HybridEntityStorage instance.

    Args:
        storage: HybridEntityStorage instance to set as global
    """
    global _hybrid_entity_storage  # noqa: PLW0603
    _hybrid_entity_storage = storage


def reset_hybrid_entity_storage() -> None:
    """Reset the global HybridEntityStorage instance (for testing)."""
    global _hybrid_entity_storage  # noqa: PLW0603
    _hybrid_entity_storage = None
