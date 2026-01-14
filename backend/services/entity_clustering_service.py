"""Entity clustering service for grouping detections into canonical entities.

This module provides the EntityClusteringService which uses embedding similarity
to determine if a new detection belongs to an existing entity or should create
a new one. This prevents duplicate entity creation for the same person/vehicle.

The service is part of the Hybrid Entity Storage Architecture (Phase 1.2).

Usage:
    from backend.services.entity_clustering_service import EntityClusteringService
    from backend.repositories.entity_repository import EntityRepository

    async with get_session() as session:
        repo = EntityRepository(session)
        service = EntityClusteringService(entity_repository=repo)

        entity, is_new, similarity = await service.assign_entity(
            detection_id=123,
            entity_type="person",
            embedding=[0.1, 0.2, ...],
            camera_id="front_door",
            timestamp=datetime.now(UTC),
        )

Related to NEM-2497: Create Entity Clustering Service.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm.attributes import flag_modified

from backend.core.logging import get_logger
from backend.models import Entity

if TYPE_CHECKING:
    from backend.repositories.entity_repository import EntityRepository

logger = get_logger(__name__)

# Default similarity threshold for entity matching
DEFAULT_SIMILARITY_THRESHOLD = 0.85

# Default embedding model
DEFAULT_EMBEDDING_MODEL = "clip"


class EntityClusteringService:
    """Service for clustering detections into canonical entities.

    Uses embedding similarity to determine if a new detection belongs
    to an existing entity or should create a new one. This prevents
    duplicate entity creation for the same person/vehicle.

    The service queries the EntityRepository to find similar entities
    based on embedding vectors, and either updates the existing entity
    or creates a new one based on the similarity threshold.

    Attributes:
        entity_repository: Repository for entity database operations
        similarity_threshold: Minimum similarity score to consider a match (0-1)
        embedding_model: Name of the embedding model used (e.g., "clip")

    Example:
        service = EntityClusteringService(
            entity_repository=repo,
            similarity_threshold=0.85,
        )

        # Assign detection to entity (new or existing)
        entity, is_new, similarity = await service.assign_entity(
            detection_id=123,
            entity_type="person",
            embedding=embedding_vector,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
        )

        if is_new:
            print(f"Created new entity: {entity.id}")
        else:
            print(f"Matched existing entity: {entity.id} (similarity: {similarity})")
    """

    def __init__(
        self,
        entity_repository: EntityRepository,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        """Initialize the EntityClusteringService.

        Args:
            entity_repository: Repository for entity database operations.
                Must provide find_by_embedding, create, update methods.
            similarity_threshold: Minimum similarity score (0-1) to consider
                a detection as matching an existing entity. Higher values
                require more similar embeddings for a match. Default: 0.85
            embedding_model: Name of the embedding model used for generating
                embeddings. Used for metadata tracking. Default: "clip"
        """
        self.entity_repository = entity_repository
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model

        logger.debug(
            "EntityClusteringService initialized with threshold=%s, model=%s",
            similarity_threshold,
            embedding_model,
        )

    async def assign_entity(
        self,
        detection_id: int,
        entity_type: str,
        embedding: list[float],
        camera_id: str,
        timestamp: datetime,
        attributes: dict[str, Any] | None = None,
    ) -> tuple[Entity, bool, float | None]:
        """Assign a detection to an entity (existing or new).

        This method searches for existing entities with similar embeddings
        using the configured similarity threshold. If a match is found,
        the existing entity is updated with the new detection. Otherwise,
        a new entity is created.

        Args:
            detection_id: Database ID of the detection record
            entity_type: Type of entity ("person", "vehicle", "animal", etc.)
            embedding: Embedding vector (typically 768-dim CLIP embedding)
            camera_id: ID of the camera that captured the detection
            timestamp: When the detection occurred
            attributes: Optional attributes dict (clothing, color, etc.)

        Returns:
            Tuple of (entity, is_new_entity, match_similarity):
            - entity: The assigned Entity (new or existing)
            - is_new_entity: True if a new entity was created
            - match_similarity: Similarity score if matched, None if new

        Example:
            entity, is_new, similarity = await service.assign_entity(
                detection_id=123,
                entity_type="person",
                embedding=[0.1, 0.2, ...],
                camera_id="front_door",
                timestamp=datetime.now(UTC),
                attributes={"clothing": "blue jacket"},
            )
        """
        # Step 1: Search for matching entities using embedding similarity
        matches = await self.entity_repository.find_by_embedding(
            embedding=embedding,
            entity_type=entity_type,
            threshold=self.similarity_threshold,
            limit=1,  # We only need the best match
        )

        # Step 2: If match found above threshold, update existing entity
        if matches:
            matched_entity, similarity = matches[0]
            await self._update_entity_with_detection(
                entity=matched_entity,
                detection_id=detection_id,
                timestamp=timestamp,
                attributes=attributes,
            )
            # Track cameras_seen in entity_metadata (NEM-2453)
            if matched_entity.entity_metadata is None:
                matched_entity.entity_metadata = {}
            cameras_seen = matched_entity.entity_metadata.get("cameras_seen", [])
            if camera_id and camera_id not in cameras_seen:
                cameras_seen.append(camera_id)
                matched_entity.entity_metadata["cameras_seen"] = cameras_seen
                # Flag JSONB column as modified for SQLAlchemy to detect in-place mutation
                flag_modified(matched_entity, "entity_metadata")
                await self.entity_repository.session.flush()
            logger.debug(
                "Detection %d matched entity %s (similarity: %.3f)",
                detection_id,
                matched_entity.id,
                similarity,
            )
            return matched_entity, False, similarity

        # Step 3: No match - create new entity
        new_entity = await self._create_entity(
            detection_id=detection_id,
            entity_type=entity_type,
            embedding=embedding,
            timestamp=timestamp,
            attributes=attributes,
        )
        # Initialize cameras_seen in entity_metadata (NEM-2453)
        if new_entity.entity_metadata is None:
            new_entity.entity_metadata = {}
        if camera_id:
            new_entity.entity_metadata["cameras_seen"] = [camera_id]
            new_entity.entity_metadata["camera_id"] = camera_id
            # Flag JSONB column as modified for SQLAlchemy to detect in-place mutation
            flag_modified(new_entity, "entity_metadata")
            await self.entity_repository.session.flush()
        logger.debug(
            "Detection %d created new entity %s",
            detection_id,
            new_entity.id,
        )
        return new_entity, True, None

    async def _update_entity_with_detection(
        self,
        entity: Entity,
        detection_id: int,  # noqa: ARG002 - Reserved for future detection linking
        timestamp: datetime,
        attributes: dict[str, Any] | None,
    ) -> None:
        """Update entity when a new matching detection is found.

        Updates the entity's last_seen_at timestamp and increments the
        detection count. Optionally merges new attributes with existing ones.

        Args:
            entity: The existing Entity to update
            detection_id: ID of the new matching detection
            timestamp: Timestamp of the new detection
            attributes: Optional new attributes to merge
        """
        # Update seen timestamp and increment detection count
        entity.update_seen(timestamp)

        # Optionally merge attributes if provided
        if attributes:
            if entity.entity_metadata is None:
                entity.entity_metadata = {}
            # Merge new attributes, keeping existing ones
            entity.entity_metadata.update(attributes)
            # Flag JSONB column as modified for SQLAlchemy to detect in-place mutation
            flag_modified(entity, "entity_metadata")

        # Flush changes to database
        await self.entity_repository.session.flush()

    async def _create_entity(
        self,
        detection_id: int,
        entity_type: str,
        embedding: list[float],
        timestamp: datetime,
        attributes: dict[str, Any] | None,
    ) -> Entity:
        """Create a new entity for a detection with no matches.

        Creates a new Entity record linked to the detection, with the
        provided embedding vector and initial attributes.

        Args:
            detection_id: ID of the detection that triggered entity creation
            entity_type: Type of entity (person, vehicle, etc.)
            embedding: Embedding vector for the entity
            timestamp: Timestamp of the initial detection
            attributes: Optional initial attributes

        Returns:
            The newly created Entity instance
        """
        # Create entity using the factory method
        entity = Entity.from_detection(
            entity_type=entity_type,
            detection_id=detection_id,
            embedding=embedding,
            model=self.embedding_model,
            entity_metadata=attributes,
        )

        # Ensure timestamps are set correctly
        entity.first_seen_at = timestamp
        entity.last_seen_at = timestamp

        # Add to session and persist
        self.entity_repository.session.add(entity)
        await self.entity_repository.session.flush()
        await self.entity_repository.session.refresh(entity)

        return entity


# =============================================================================
# Global Service Instance Management
# =============================================================================

_entity_clustering_service: EntityClusteringService | None = None


def get_entity_clustering_service(
    entity_repository: EntityRepository,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> EntityClusteringService:
    """Get or create EntityClusteringService instance.

    This factory function creates a new EntityClusteringService with the
    provided repository. Unlike singleton patterns, this creates a new
    service instance each time because the service depends on a
    request-scoped repository (with its own database session).

    Args:
        entity_repository: Repository for entity database operations
        similarity_threshold: Minimum similarity for matching
        embedding_model: Name of the embedding model

    Returns:
        EntityClusteringService instance
    """
    return EntityClusteringService(
        entity_repository=entity_repository,
        similarity_threshold=similarity_threshold,
        embedding_model=embedding_model,
    )


def reset_entity_clustering_service() -> None:
    """Reset the global EntityClusteringService instance (for testing)."""
    global _entity_clustering_service  # noqa: PLW0603
    _entity_clustering_service = None
