"""Repository for Entity database operations.

This module provides the EntityRepository class which extends the generic
Repository base class with entity-specific query methods for person/object
re-identification tracking.

Related to NEM-2450: Create EntityRepository for PostgreSQL CRUD operations.
Updated for NEM-2494: Added get_repeat_visitors, get_stats, list_filtered methods.

Example:
    async with get_session() as session:
        repo = EntityRepository(session)
        entity = await repo.get_by_primary_detection_id(123)
        recent_persons = await repo.get_by_type(EntityType.PERSON)
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, override
from uuid import UUID

from sqlalchemy import desc, func, select

from backend.models import Entity
from backend.models.enums import EntityType
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.models import Detection

# Type alias to avoid shadowing by the list() method
_list = builtins.list


class EntityRepository(Repository[Entity]):
    """Repository for Entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    entity-specific query methods for filtering, searching, and aggregating
    entity data.

    The Entity model stores information about unique persons, vehicles, animals,
    packages, and other tracked objects across cameras using re-identification
    techniques.

    Attributes:
        model_class: Set to Entity for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = EntityRepository(session)

            # Get entities by type
            persons = await repo.get_by_type(EntityType.PERSON)

            # Get entity by primary detection
            entity = await repo.get_by_primary_detection_id(123)

            # Get most recent entities
            recent = await repo.get_recent(limit=10)
    """

    model_class = Entity

    async def get_by_type(self, entity_type: EntityType | str) -> Sequence[Entity]:
        """Get all entities of a specific type."""
        type_value = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        stmt = select(Entity).where(Entity.entity_type == type_value)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 10) -> Sequence[Entity]:
        """Get the most recently seen entities."""
        stmt = select(Entity).order_by(desc(Entity.last_seen_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_in_date_range(self, start: datetime, end: datetime) -> Sequence[Entity]:
        """Get entities seen within a date range."""
        stmt = select(Entity).where(Entity.last_seen_at >= start, Entity.last_seen_at <= end)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_last_seen(
        self, entity_id: UUID, timestamp: datetime | None = None
    ) -> Entity | None:
        """Update an entity's last_seen_at timestamp and increment detection count."""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return None

        entity.update_seen(timestamp or datetime.now(UTC))
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_by_primary_detection_id(self, detection_id: int) -> Entity | None:
        """Find an entity by its primary detection ID."""
        stmt = select(Entity).where(Entity.primary_detection_id == detection_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_type_counts(self) -> dict[str, int]:
        """Get entity counts grouped by type."""
        stmt = select(Entity.entity_type, func.count(Entity.id)).group_by(Entity.entity_type)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_total_detection_count(self) -> int:
        """Get the total detection count across all entities."""
        stmt = select(func.sum(Entity.detection_count))
        result = await self.session.execute(stmt)
        total = result.scalar_one()
        return total if total is not None else 0

    async def list_by_type_paginated(
        self,
        entity_type: EntityType | str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Entity]:
        """Get entities of a specific type with pagination."""
        type_value = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        stmt = (
            select(Entity)
            .where(Entity.entity_type == type_value)
            .order_by(desc(Entity.last_seen_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_by_metadata(self, key: str, value: str) -> Sequence[Entity]:
        """Search entities by a metadata field value."""
        stmt = select(Entity).where(Entity.entity_metadata.op("@>")({key: value}))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_high_detection_count(self, min_count: int = 10) -> Sequence[Entity]:
        """Get entities that have been detected frequently."""
        stmt = (
            select(Entity)
            .where(Entity.detection_count >= min_count)
            .order_by(desc(Entity.detection_count))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_first_seen_in_range(self, start: datetime, end: datetime) -> Sequence[Entity]:
        """Get entities first seen within a date range."""
        stmt = select(Entity).where(Entity.first_seen_at >= start, Entity.first_seen_at <= end)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_embedding_model(self, model: str) -> Sequence[Entity]:
        """Get entities that have embeddings from a specific model."""
        stmt = select(Entity).where(
            Entity.embedding_vector.isnot(None),
            Entity.embedding_vector["model"].astext == model,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list(
        self,
        entity_type: str | None = None,
        camera_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[_list[Entity], int]:
        """List entities with filtering and pagination.

        Args:
            entity_type: Filter by entity type (person, vehicle, etc.)
            camera_id: Filter by camera_id in entity_metadata
            since: Filter by last_seen_at >= since
            limit: Maximum number of entities to return (default: 50)
            offset: Number of entities to skip (default: 0)

        Returns:
            Tuple of (list of entities, total count matching filters)

        Example:
            entities, total = await repo.list(
                entity_type="person",
                camera_id="front_door",
                since=datetime.now(UTC) - timedelta(hours=24),
                limit=20,
                offset=0,
            )
        """
        from sqlalchemy.orm import selectinload

        # Build base query with filters
        # Eager load primary_detection to allow cameras_seen fallback
        stmt = select(Entity).options(selectinload(Entity.primary_detection))

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        if camera_id:
            # Filter by camera_id in entity_metadata JSONB
            stmt = stmt.where(Entity.entity_metadata.op("@>")({"camera_id": camera_id}))

        if since:
            stmt = stmt.where(Entity.last_seen_at >= since)

        # Order by most recently seen
        stmt = stmt.order_by(desc(Entity.last_seen_at))

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute entity query
        result = await self.session.execute(stmt)
        entities = list(result.scalars().all())

        # Build count query with same filters
        count_stmt = select(func.count(Entity.id))

        if entity_type:
            count_stmt = count_stmt.where(Entity.entity_type == entity_type)

        if camera_id:
            count_stmt = count_stmt.where(Entity.entity_metadata.op("@>")({"camera_id": camera_id}))

        if since:
            count_stmt = count_stmt.where(Entity.last_seen_at >= since)

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return entities, total

    async def find_by_embedding(
        self,
        embedding: Sequence[float],
        entity_type: str,
        threshold: float = 0.85,
        limit: int = 10,
    ) -> Sequence[tuple[Entity, float]]:
        """Find similar entities by embedding vector.

        Uses application-level cosine similarity on JSONB-stored embeddings.
        For high-performance vector search at scale, consider using pgvector extension.

        Args:
            embedding: Query embedding vector as list of floats
            entity_type: Filter by entity type
            threshold: Minimum similarity score (0-1, default: 0.85)
            limit: Maximum number of results (default: 10)

        Returns:
            List of (entity, similarity_score) tuples sorted by similarity descending

        Example:
            matches = await repo.find_by_embedding(
                embedding=[0.1, 0.2, ...],
                entity_type="person",
                threshold=0.85,
                limit=5,
            )
            for entity, score in matches:
                print(f"Entity {entity.id}: {score:.2f}")
        """
        # Query entities of the given type that have embeddings
        stmt = select(Entity).where(
            Entity.entity_type == entity_type,
            Entity.embedding_vector.isnot(None),
        )
        result = await self.session.execute(stmt)
        candidates = result.scalars().all()

        # Compute cosine similarity in application layer
        matches: list[tuple[Entity, float]] = []

        for entity in candidates:
            entity_embedding = entity.get_embedding_vector()
            if entity_embedding is None:
                continue

            similarity = self._cosine_similarity(embedding, entity_embedding)
            if similarity >= threshold:
                matches.append((entity, similarity))

        # Sort by similarity descending and limit results
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    @staticmethod
    def _cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between 0 and 1

        Note:
            Returns 0.0 if vectors have different dimensions or either is zero-length.
        """
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0

        # Compute dot product and magnitudes
        dot_product: float = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1: float = sum(a * a for a in vec1) ** 0.5
        magnitude2: float = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return float(dot_product / (magnitude1 * magnitude2))

    async def increment_detection_count(self, entity_id: UUID) -> Entity | None:
        """Increment detection count and update last_seen_at.

        Args:
            entity_id: UUID of the entity to update

        Returns:
            Updated Entity or None if not found

        Note:
            Does nothing if entity doesn't exist. Uses the Entity.update_seen()
            method which handles both count increment and timestamp update.
        """
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return None

        entity.update_seen()
        await self.session.flush()
        return entity

    async def get_or_create_for_detection(
        self,
        detection_id: int,
        entity_type: str,
        embedding: Sequence[float],
        threshold: float = 0.85,
        attributes: dict[str, Any] | None = None,
    ) -> tuple[Entity, bool]:
        """Get existing matching entity or create new one.

        Uses embedding similarity to find existing entities that match.
        If a match is found above the threshold, updates the existing entity.
        Otherwise, creates a new entity for the detection.

        Args:
            detection_id: ID of the detection to link to
            entity_type: Type of entity (person, vehicle, etc.)
            embedding: Embedding vector for similarity matching
            threshold: Minimum similarity score to consider a match (default: 0.85)
            attributes: Optional metadata to store on new entity (e.g., camera_id)

        Returns:
            Tuple of (entity, is_new) where is_new is True if entity was created

        Example:
            entity, is_new = await repo.get_or_create_for_detection(
                detection_id=123,
                entity_type="person",
                embedding=[0.1, 0.2, ...],
                threshold=0.85,
                attributes={"camera_id": "front_door"},
            )
            if is_new:
                print(f"Created new entity: {entity.id}")
            else:
                print(f"Matched existing entity: {entity.id}")
        """
        # Search for existing entities with similar embeddings
        matches = await self.find_by_embedding(
            embedding=embedding,
            entity_type=entity_type,
            threshold=threshold,
            limit=1,
        )

        if matches:
            # Match found - update existing entity
            matched_entity, _similarity = matches[0]
            matched_entity.update_seen()
            await self.session.flush()
            return matched_entity, False

        # No match - create new entity
        entity = Entity.from_detection(
            entity_type=entity_type,
            detection_id=detection_id,
            embedding=list(embedding),
            model="clip",
            entity_metadata=attributes,
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity, True

    async def get_detections_for_entity(
        self,
        entity_id: UUID,
        limit: int = 50,  # noqa: ARG002  # Reserved for future use
        offset: int = 0,  # noqa: ARG002  # Reserved for future use
    ) -> tuple[_list[Detection], int]:
        """Get all detections linked to an entity.

        Note: Since the Detection table does not have an entity_id foreign key,
        we currently only return the primary detection. In the future, this
        could be extended to use a junction table or entity_id column.

        Args:
            entity_id: UUID of the entity
            limit: Maximum number of detections to return (reserved for future use)
            offset: Number of detections to skip (reserved for future use)

        Returns:
            Tuple of (list of detections, total count)
        """
        from backend.models import Detection

        # Get the entity to find its primary detection
        entity = await self.get_by_id(entity_id)
        if entity is None or entity.primary_detection_id is None:
            return [], 0

        # For now, we only have the primary detection linked
        # Future: Use a junction table or entity_id column on detections
        stmt = select(Detection).where(Detection.id == entity.primary_detection_id)
        result = await self.session.execute(stmt)
        detection = result.scalar_one_or_none()

        if detection is None:
            return [], 0

        return [detection], 1

    async def get_camera_counts(self) -> dict[str, int]:
        """Get entity counts grouped by camera.

        Returns:
            Dictionary mapping camera_id to entity count
        """
        # Query entities and group by camera_id in entity_metadata
        stmt = select(Entity).where(Entity.entity_metadata.isnot(None))
        result = await self.session.execute(stmt)
        entities = result.scalars().all()

        camera_counts: dict[str, int] = {}
        for entity in entities:
            if entity.entity_metadata and "camera_id" in entity.entity_metadata:
                camera_id = entity.entity_metadata["camera_id"]
                camera_counts[camera_id] = camera_counts.get(camera_id, 0) + 1

        return camera_counts

    async def get_repeat_visitor_count(self) -> int:
        """Get count of entities seen more than once.

        Returns:
            Count of entities with detection_count > 1
        """
        stmt = select(func.count(Entity.id)).where(Entity.detection_count > 1)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    @override
    async def count(self) -> int:
        """Get total count of entities.

        Returns:
            Total number of entities in the database
        """
        stmt = select(func.count(Entity.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_repeat_visitors(
        self,
        min_appearances: int = 2,
        entity_type: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> Sequence[Entity]:
        """Get entities that have been detected multiple times.

        Args:
            min_appearances: Minimum detection count to include (default: 2)
            entity_type: Filter by entity type (optional)
            since: Filter by last_seen_at >= since (optional)
            limit: Maximum number of entities to return (default: 50)

        Returns:
            Sequence of entities with detection_count >= min_appearances,
            ordered by detection_count descending

        Example:
            repeat_visitors = await repo.get_repeat_visitors(
                min_appearances=3,
                entity_type="person",
                since=datetime.now(UTC) - timedelta(days=7),
                limit=20,
            )
        """
        stmt = select(Entity).where(Entity.detection_count >= min_appearances)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        if since:
            stmt = stmt.where(Entity.last_seen_at >= since)

        stmt = stmt.order_by(desc(Entity.detection_count)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_stats(self, entity_type: str | None = None) -> dict[str, Any]:
        """Get comprehensive statistics about entities.

        Args:
            entity_type: Filter statistics by entity type (optional)

        Returns:
            Dictionary containing:
            - total_entities: Total count of entities
            - by_type: Dictionary of counts by entity type (only when entity_type is None)
            - total_detections: Sum of all detection counts
            - repeat_visitor_count: Count of entities seen more than once

        Example:
            stats = await repo.get_stats()
            print(f"Total: {stats['total_entities']}")
            print(f"By type: {stats['by_type']}")

            person_stats = await repo.get_stats(entity_type="person")
            print(f"Person entities: {person_stats['total_entities']}")
        """
        result: dict[str, Any] = {}

        if entity_type:
            # Stats for specific entity type
            count_stmt = select(func.count(Entity.id)).where(Entity.entity_type == entity_type)
            count_result = await self.session.execute(count_stmt)
            result["total_entities"] = count_result.scalar_one() or 0

            det_stmt = select(func.sum(Entity.detection_count)).where(
                Entity.entity_type == entity_type
            )
            det_result = await self.session.execute(det_stmt)
            result["total_detections"] = det_result.scalar_one() or 0

            repeat_stmt = select(func.count(Entity.id)).where(
                Entity.entity_type == entity_type, Entity.detection_count > 1
            )
            repeat_result = await self.session.execute(repeat_stmt)
            result["repeat_visitor_count"] = repeat_result.scalar_one() or 0
        else:
            # Stats for all entity types
            count_stmt = select(func.count(Entity.id))
            count_result = await self.session.execute(count_stmt)
            result["total_entities"] = count_result.scalar_one() or 0

            type_stmt = select(Entity.entity_type, func.count(Entity.id)).group_by(
                Entity.entity_type
            )
            type_result = await self.session.execute(type_stmt)
            result["by_type"] = {row[0]: row[1] for row in type_result.all()}

            det_stmt = select(func.sum(Entity.detection_count))
            det_result = await self.session.execute(det_stmt)
            result["total_detections"] = det_result.scalar_one() or 0

            repeat_stmt = select(func.count(Entity.id)).where(Entity.detection_count > 1)
            repeat_result = await self.session.execute(repeat_stmt)
            result["repeat_visitor_count"] = repeat_result.scalar_one() or 0

        return result

    async def list_filtered(
        self,
        entity_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Entity], int]:
        """List entities with time-range filtering and pagination.

        Similar to list() but with an additional 'until' parameter for
        filtering by end timestamp.

        Args:
            entity_type: Filter by entity type (optional)
            since: Filter by last_seen_at >= since (optional)
            until: Filter by last_seen_at <= until (optional)
            limit: Maximum number of entities to return (default: 50)
            offset: Number of entities to skip (default: 0)

        Returns:
            Tuple of (sequence of entities, total count matching filters)

        Example:
            entities, total = await repo.list_filtered(
                entity_type="person",
                since=datetime.now(UTC) - timedelta(days=7),
                until=datetime.now(UTC) - timedelta(days=1),
                limit=20,
                offset=0,
            )
        """
        stmt = select(Entity)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        if since:
            stmt = stmt.where(Entity.last_seen_at >= since)

        if until:
            stmt = stmt.where(Entity.last_seen_at <= until)

        stmt = stmt.order_by(desc(Entity.last_seen_at)).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        entities = result.scalars().all()

        # Build count query with same filters
        count_stmt = select(func.count(Entity.id))

        if entity_type:
            count_stmt = count_stmt.where(Entity.entity_type == entity_type)

        if since:
            count_stmt = count_stmt.where(Entity.last_seen_at >= since)

        if until:
            count_stmt = count_stmt.where(Entity.last_seen_at <= until)

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return entities, total

    # =========================================================================
    # Trust Classification Methods (NEM-2671)
    # =========================================================================

    async def update_trust_status(
        self,
        entity_id: UUID,
        trust_status: str,
        trust_notes: str | None = None,
    ) -> Entity | None:
        """Update an entity's trust classification status.

        Updates the trust_status and trust_notes fields in entity_metadata JSONB.

        Args:
            entity_id: UUID of the entity to update
            trust_status: Trust classification ('trusted', 'untrusted', 'unclassified')
            trust_notes: Optional notes explaining the classification decision

        Returns:
            Updated Entity or None if not found

        Example:
            entity = await repo.update_trust_status(
                entity_id=uuid,
                trust_status="trusted",
                trust_notes="Regular mail carrier",
            )
        """
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return None

        # Initialize entity_metadata if None
        if entity.entity_metadata is None:
            entity.entity_metadata = {}

        # Update trust fields in metadata
        entity.entity_metadata = {
            **entity.entity_metadata,
            "trust_status": trust_status,
            "trust_notes": trust_notes,
            "trust_updated_at": datetime.now(UTC).isoformat(),
        }

        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def list_by_trust_status(
        self,
        trust_status: str,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[_list[Entity], int]:
        """List entities with a specific trust status.

        Args:
            trust_status: Trust classification to filter by ('trusted', 'untrusted')
            entity_type: Optional filter by entity type (person, vehicle, etc.)
            limit: Maximum number of entities to return (default: 50)
            offset: Number of entities to skip (default: 0)

        Returns:
            Tuple of (list of entities, total count matching filters)

        Example:
            trusted_entities, total = await repo.list_by_trust_status(
                trust_status="trusted",
                entity_type="person",
                limit=20,
                offset=0,
            )
        """
        # Build base query filtering by trust_status in entity_metadata
        stmt = select(Entity).where(Entity.entity_metadata.op("@>")({"trust_status": trust_status}))

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        # Order by most recently updated trust status (approximated by last_seen)
        stmt = stmt.order_by(desc(Entity.last_seen_at))

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute entity query
        result = await self.session.execute(stmt)
        entities = list(result.scalars().all())

        # Build count query with same filters
        count_stmt = select(func.count(Entity.id)).where(
            Entity.entity_metadata.op("@>")({"trust_status": trust_status})
        )

        if entity_type:
            count_stmt = count_stmt.where(Entity.entity_type == entity_type)

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return entities, total
