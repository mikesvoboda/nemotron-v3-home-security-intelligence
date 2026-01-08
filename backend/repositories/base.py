"""Generic Repository base class for database access abstraction.

This module provides a type-safe, async-first repository pattern implementation
that works with SQLAlchemy 2.0 models. The generic base class provides common
CRUD operations that can be extended by model-specific repositories.

Example:
    from backend.repositories import Repository
    from backend.models import Camera

    class CameraRepository(Repository[Camera]):
        model_class = Camera

        async def get_online_cameras(self) -> list[Camera]:
            # Custom method for camera-specific queries
            ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from sqlalchemy import func, select

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.camera import Base

# Type variable for the model class
# Bound to Base to ensure only SQLAlchemy models can be used
T = TypeVar("T", bound="Base")


class Repository(Generic[T]):  # noqa: UP046
    """Generic repository base class providing common CRUD operations.

    This class provides type-safe, async database operations for SQLAlchemy models.
    It should be subclassed with a specific model type to create model-specific
    repositories.

    Type Parameters:
        T: The SQLAlchemy model class this repository works with.

    Attributes:
        model_class: Class attribute that must be set to the SQLAlchemy model class.
                     This is used for query construction and type inference.
        session: The async database session used for all operations.

    Example:
        class CameraRepository(Repository[Camera]):
            model_class = Camera

        async with get_session() as session:
            repo = CameraRepository(session)
            camera = await repo.get_by_id("front_door")
    """

    # Subclasses must set this to their model class
    model_class: type[T]

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Args:
            session: An async SQLAlchemy session for database operations.
                     The session should be obtained from get_db() or get_session().
        """
        self.session = session

    async def get_by_id(self, entity_id: Any) -> T | None:
        """Retrieve an entity by its primary key.

        Args:
            entity_id: The primary key value of the entity to retrieve.

        Returns:
            The entity if found, None otherwise.
        """
        return await self.session.get(self.model_class, entity_id)

    async def get_all(self) -> Sequence[T]:
        """Retrieve all entities of this type.

        Returns:
            A sequence of all entities. May be empty if no entities exist.

        Note:
            For large tables, consider using list_paginated() instead
            to avoid loading all records into memory.
        """
        result = await self.session.execute(select(self.model_class))
        return result.scalars().all()

    async def list_paginated(self, *, skip: int = 0, limit: int = 100) -> Sequence[T]:
        """Retrieve entities with pagination support.

        Args:
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.

        Returns:
            A sequence of entities within the specified range.

        Example:
            # Get first page of 20 items
            page1 = await repo.list_paginated(skip=0, limit=20)
            # Get second page
            page2 = await repo.list_paginated(skip=20, limit=20)
        """
        stmt = select(self.model_class).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_many(self, entity_ids: Sequence[Any]) -> Sequence[T]:
        """Retrieve multiple entities by their primary keys.

        Args:
            entity_ids: A sequence of primary key values to retrieve.

        Returns:
            A sequence of found entities. May contain fewer items than
            entity_ids if some entities don't exist.
        """
        if not entity_ids:
            return []

        # Get the primary key column(s) from the model
        # For single-column PKs, this is straightforward
        pk = self.model_class.__table__.primary_key
        pk_column_list = list(pk.columns)  # type: ignore[attr-defined]
        if len(pk_column_list) == 1:
            pk_column = pk_column_list[0]
            stmt = select(self.model_class).where(pk_column.in_(entity_ids))
            result = await self.session.execute(stmt)
            return result.scalars().all()
        else:
            # For composite PKs, we need individual lookups
            entities = []
            for entity_id in entity_ids:
                entity = await self.get_by_id(entity_id)
                if entity is not None:
                    entities.append(entity)
            return entities

    async def create(self, entity: T) -> T:
        """Create a new entity in the database.

        Args:
            entity: The entity instance to persist.

        Returns:
            The persisted entity with any database-generated values
            (e.g., auto-increment IDs, default timestamps).

        Note:
            The entity is added to the session but not committed.
            Commit happens when the session context exits or when
            session.commit() is called explicitly.
        """
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def create_many(self, entities: Sequence[T]) -> Sequence[T]:
        """Create multiple entities in a single batch operation.

        Args:
            entities: A sequence of entity instances to persist.

        Returns:
            The persisted entities with any database-generated values.

        Note:
            Uses add_all() for efficient batch insertion.
        """
        if not entities:
            return []

        self.session.add_all(entities)
        await self.session.flush()

        # Refresh each entity to get database-generated values
        for entity in entities:
            await self.session.refresh(entity)

        return entities

    async def update(self, entity: T) -> T:
        """Update an existing entity in the database.

        Args:
            entity: The entity instance with updated values.
                    Must already be attached to the session or have a valid PK.

        Returns:
            The updated entity.

        Note:
            The entity should already be attached to the session
            (e.g., retrieved via get_by_id). Changes are detected
            automatically by SQLAlchemy's unit of work.
            For detached entities, use merge() instead.
        """
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def merge(self, entity: T) -> T:
        """Merge a detached entity into the session.

        This is useful when you have an entity that was loaded in a different
        session or has been detached, and you want to update it.

        Args:
            entity: The entity instance to merge. Can be detached from the session.

        Returns:
            The merged entity, now attached to the current session.

        Note:
            Unlike update(), this works with detached entities by copying
            their state into a new or existing persistent instance.
        """
        merged = await self.session.merge(entity)
        await self.session.flush()
        return merged

    async def save(self, entity: T) -> T:
        """Save an entity, creating or updating as needed (upsert pattern).

        This method checks if the entity exists and performs an update if so,
        otherwise creates a new entity.

        Args:
            entity: The entity to save.

        Returns:
            The saved entity.

        Note:
            This performs an existence check, so for bulk operations
            use create_many() or explicit create()/update() calls instead.
        """
        # Get the primary key value from the entity
        pk = self.model_class.__table__.primary_key
        pk_columns = list(pk.columns)  # type: ignore[attr-defined]

        if len(pk_columns) == 1:
            pk_attr = pk_columns[0].name
            entity_id = getattr(entity, pk_attr, None)
        else:
            # For composite PKs, build a tuple
            entity_id = tuple(getattr(entity, col.name, None) for col in pk_columns)

        if entity_id is not None and await self.exists(entity_id):
            return await self.merge(entity)
        return await self.create(entity)

    async def delete(self, entity: T) -> None:
        """Delete an entity from the database.

        Args:
            entity: The entity instance to delete.
                    Must be attached to the session.

        Note:
            Cascade delete behavior is defined by model relationships.
            See the model's relationship definitions for cascade rules.
        """
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_by_id(self, entity_id: Any) -> bool:
        """Delete an entity by its primary key.

        Args:
            entity_id: The primary key of the entity to delete.

        Returns:
            True if the entity was found and deleted, False if not found.
        """
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self.delete(entity)
        return True

    async def exists(self, entity_id: Any) -> bool:
        """Check if an entity with the given primary key exists.

        Args:
            entity_id: The primary key value to check.

        Returns:
            True if an entity with this ID exists, False otherwise.

        Note:
            More efficient than get_by_id() when you only need to check
            existence, as it doesn't load the full entity.
        """
        pk = self.model_class.__table__.primary_key
        pk_column_list = list(pk.columns)  # type: ignore[attr-defined]
        if len(pk_column_list) == 1:
            pk_column = pk_column_list[0]
            stmt = select(func.count()).select_from(self.model_class).where(pk_column == entity_id)
            result = await self.session.execute(stmt)
            return result.scalar_one() > 0
        else:
            # For composite PKs, try to get the entity
            entity = await self.get_by_id(entity_id)
            return entity is not None

    async def count(self) -> int:
        """Count the total number of entities of this type.

        Returns:
            The total count of entities in the table.
        """
        stmt = select(func.count()).select_from(self.model_class)
        result = await self.session.execute(stmt)
        return result.scalar_one()
