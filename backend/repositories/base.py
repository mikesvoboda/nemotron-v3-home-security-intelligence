"""Base repository with generic CRUD operations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository[T, ID]:
    """Generic base repository providing common CRUD operations.

    Type Parameters:
        T: The SQLAlchemy model type
        ID: The primary key type (str, int, etc.)
    """

    def __init__(self, model: type[T], db: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            db: The async database session
        """
        self.model = model
        self.db = db

    async def get_by_id(self, entity_id: ID) -> T | None:
        """Get an entity by its primary key.

        Args:
            entity_id: The primary key value

        Returns:
            The entity if found, None otherwise
        """
        stmt = select(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """List all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of entities
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count total number of entities.

        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: T) -> T:
        """Create a new entity.

        Args:
            entity: The entity to create

        Returns:
            The created entity with generated fields populated
        """
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity.

        Args:
            entity: The entity with updated values

        Returns:
            The updated entity
        """
        merged = await self.db.merge(entity)
        await self.db.flush()
        return merged

    async def delete(self, entity: T) -> None:
        """Delete an entity.

        Args:
            entity: The entity to delete
        """
        await self.db.delete(entity)
        await self.db.flush()

    async def delete_by_id(self, entity_id: ID) -> bool:
        """Delete an entity by its primary key.

        Args:
            entity_id: The primary key value

        Returns:
            True if entity was deleted, False if not found
        """
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self.delete(entity)
        return True

    async def exists(self, entity_id: ID) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The primary key value

        Returns:
            True if entity exists, False otherwise
        """
        stmt = (
            select(func.count()).select_from(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def save(self, entity: T) -> T:
        """Save an entity (create or update).

        Args:
            entity: The entity to save

        Returns:
            The saved entity
        """
        entity_id = getattr(entity, "id", None)
        if entity_id is not None and await self.exists(entity_id):
            return await self.update(entity)
        return await self.create(entity)
