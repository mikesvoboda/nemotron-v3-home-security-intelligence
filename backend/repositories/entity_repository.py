"""Repository for Entity database operations.

This module provides the EntityRepository class which extends the generic
Repository base class with entity-specific query methods for person/object
re-identification tracking.

Related to NEM-2450: Create EntityRepository for PostgreSQL CRUD operations.

Example:
    async with get_session() as session:
        repo = EntityRepository(session)
        entity = await repo.get_by_primary_detection_id(123)
        recent_persons = await repo.get_by_type(EntityType.PERSON)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import desc, func, select

from backend.models import Entity
from backend.models.enums import EntityType
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


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
