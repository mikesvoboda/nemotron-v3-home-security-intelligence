"""Unit tests for the base Repository class.

Tests focus on covering the generic repository functionality including:
- Basic CRUD operations
- Composite primary key handling
- Edge cases and boundary conditions
- Error handling for database operations

Run with: uv run pytest backend/tests/unit/repositories/test_base.py -v -n0
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.orm import declarative_base

from backend.repositories.base import Repository
from backend.tests.conftest import unique_id

# Create test models for testing the base repository
TestBase = declarative_base()


class SimpleModel(TestBase):
    """Test model with single-column primary key."""

    __tablename__ = "simple_test_model"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CompositeKeyModel(TestBase):
    """Test model with composite primary key."""

    __tablename__ = "composite_test_model"

    part1 = Column(String, primary_key=True)
    part2 = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class SimpleRepository(Repository[SimpleModel]):
    """Test repository for SimpleModel."""

    model_class = SimpleModel


class CompositeRepository(Repository[CompositeKeyModel]):
    """Test repository for CompositeKeyModel."""

    model_class = CompositeKeyModel


@pytest.fixture
async def simple_repo(test_db):
    """Create a SimpleRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            # Ensure test tables exist
            from backend.core.database import get_engine

            engine = get_engine()
            if engine:
                async with engine.begin() as conn:
                    await conn.run_sync(TestBase.metadata.create_all)

            return SimpleRepository(session), session

    return _get_repo


@pytest.fixture
async def composite_repo(test_db):
    """Create a CompositeRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            # Ensure test tables exist
            from backend.core.database import get_engine

            engine = get_engine()
            if engine:
                async with engine.begin() as conn:
                    await conn.run_sync(TestBase.metadata.create_all)

            return CompositeRepository(session), session

    return _get_repo


class TestRepositoryBasicOperations:
    """Test basic repository operations with single-column primary keys."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, simple_repo):
        """Test get_by_id returns entity when it exists."""
        repo, _session = await simple_repo()
        entity_id = unique_id("simple")

        entity = SimpleModel(id=entity_id, name="Test Entity")
        await repo.create(entity)

        retrieved = await repo.get_by_id(entity_id)

        assert retrieved is not None
        assert retrieved.id == entity_id
        assert retrieved.name == "Test Entity"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, simple_repo):
        """Test get_by_id returns None when entity doesn't exist."""
        repo, _session = await simple_repo()

        result = await repo.get_by_id("nonexistent_id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_empty(self, simple_repo):
        """Test get_all returns empty sequence when no entities exist."""
        repo, session = await simple_repo()

        # Clear any existing test data
        stmt = select(SimpleModel)
        result = await session.execute(stmt)
        existing = result.scalars().all()
        for entity in existing:
            await session.delete(entity)
        await session.flush()

        all_entities = await repo.get_all()

        assert len(all_entities) == 0

    @pytest.mark.asyncio
    async def test_get_all_multiple(self, simple_repo):
        """Test get_all returns all entities."""
        repo, _session = await simple_repo()

        entity1 = SimpleModel(id=unique_id("entity1"), name="Entity 1")
        entity2 = SimpleModel(id=unique_id("entity2"), name="Entity 2")
        await repo.create(entity1)
        await repo.create(entity2)

        all_entities = await repo.get_all()

        entity_ids = [e.id for e in all_entities]
        assert entity1.id in entity_ids
        assert entity2.id in entity_ids

    @pytest.mark.asyncio
    async def test_list_paginated_first_page(self, simple_repo):
        """Test list_paginated returns correct first page."""
        repo, _session = await simple_repo()

        # Create 5 entities
        entities = [SimpleModel(id=unique_id(f"page{i}"), name=f"Entity {i}") for i in range(5)]
        for entity in entities:
            await repo.create(entity)

        # Get first 2 items
        page1 = await repo.list_paginated(skip=0, limit=2)

        assert len(page1) >= 2

    @pytest.mark.asyncio
    async def test_list_paginated_offset(self, simple_repo):
        """Test list_paginated with offset returns correct page."""
        repo, _session = await simple_repo()

        # Create 5 entities
        entities = [SimpleModel(id=unique_id(f"offset{i}"), name=f"Entity {i}") for i in range(5)]
        for entity in entities:
            await repo.create(entity)

        # Skip first 2, get next 2
        page2 = await repo.list_paginated(skip=2, limit=2)

        assert len(page2) >= 2

    @pytest.mark.asyncio
    async def test_count_empty(self, simple_repo):
        """Test count returns 0 when no entities exist."""
        repo, session = await simple_repo()

        # Clear any existing test data
        stmt = select(SimpleModel)
        result = await session.execute(stmt)
        existing = result.scalars().all()
        for entity in existing:
            await session.delete(entity)
        await session.flush()

        count = await repo.count()

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_multiple(self, simple_repo):
        """Test count returns correct count of entities."""
        repo, session = await simple_repo()

        # Clear existing data
        stmt = select(SimpleModel)
        result = await session.execute(stmt)
        existing = result.scalars().all()
        for entity in existing:
            await session.delete(entity)
        await session.flush()

        initial_count = await repo.count()

        # Create 3 entities
        for i in range(3):
            entity = SimpleModel(id=unique_id(f"count{i}"), name=f"Entity {i}")
            await repo.create(entity)

        final_count = await repo.count()

        assert final_count == initial_count + 3


class TestRepositoryGetMany:
    """Test get_many method with both single and composite primary keys."""

    @pytest.mark.asyncio
    async def test_get_many_empty_list(self, simple_repo):
        """Test get_many with empty list returns empty sequence."""
        repo, _session = await simple_repo()

        result = await repo.get_many([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_many_single_pk(self, simple_repo):
        """Test get_many with single-column primary keys."""
        repo, _session = await simple_repo()

        entity1 = SimpleModel(id=unique_id("many1"), name="Entity 1")
        entity2 = SimpleModel(id=unique_id("many2"), name="Entity 2")
        entity3 = SimpleModel(id=unique_id("many3"), name="Entity 3")
        await repo.create(entity1)
        await repo.create(entity2)
        await repo.create(entity3)

        # Get multiple entities
        result = await repo.get_many([entity1.id, entity2.id])

        assert len(result) == 2
        result_ids = [e.id for e in result]
        assert entity1.id in result_ids
        assert entity2.id in result_ids
        assert entity3.id not in result_ids

    @pytest.mark.asyncio
    async def test_get_many_some_missing(self, simple_repo):
        """Test get_many returns only found entities when some don't exist."""
        repo, _session = await simple_repo()

        entity1 = SimpleModel(id=unique_id("found"), name="Found Entity")
        await repo.create(entity1)

        # Request one existing and one non-existing
        result = await repo.get_many([entity1.id, "nonexistent_id"])

        assert len(result) == 1
        assert result[0].id == entity1.id

    @pytest.mark.asyncio
    async def test_get_many_composite_pk(self, composite_repo):
        """Test get_many with composite primary keys (lines 141-146)."""
        repo, _session = await composite_repo()

        # Create entities with composite keys
        entity1 = CompositeKeyModel(
            part1=unique_id("part1_a"), part2=unique_id("part2_a"), value="Entity 1"
        )
        entity2 = CompositeKeyModel(
            part1=unique_id("part1_b"), part2=unique_id("part2_b"), value="Entity 2"
        )
        entity3 = CompositeKeyModel(
            part1=unique_id("part1_c"), part2=unique_id("part2_c"), value="Entity 3"
        )
        await repo.create(entity1)
        await repo.create(entity2)
        await repo.create(entity3)

        # Get multiple entities by composite keys
        keys = [(entity1.part1, entity1.part2), (entity2.part1, entity2.part2)]
        result = await repo.get_many(keys)

        assert len(result) == 2
        result_values = [e.value for e in result]
        assert "Entity 1" in result_values
        assert "Entity 2" in result_values
        assert "Entity 3" not in result_values

    @pytest.mark.asyncio
    async def test_get_many_composite_pk_some_missing(self, composite_repo):
        """Test get_many with composite keys when some entities don't exist."""
        repo, _session = await composite_repo()

        entity1 = CompositeKeyModel(
            part1=unique_id("found_p1"), part2=unique_id("found_p2"), value="Found"
        )
        await repo.create(entity1)

        # Request one existing and one non-existing
        keys = [(entity1.part1, entity1.part2), ("nonexistent_p1", "nonexistent_p2")]
        result = await repo.get_many(keys)

        assert len(result) == 1
        assert result[0].value == "Found"


class TestRepositoryCreateMany:
    """Test create_many method including edge cases."""

    @pytest.mark.asyncio
    async def test_create_many_empty_list(self, simple_repo):
        """Test create_many with empty list returns empty sequence (lines 180-181)."""
        repo, _session = await simple_repo()

        result = await repo.create_many([])

        assert result == []

    @pytest.mark.asyncio
    async def test_create_many_single_entity(self, simple_repo):
        """Test create_many with single entity."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("single"), name="Single Entity")
        result = await repo.create_many([entity])

        assert len(result) == 1
        assert result[0].id == entity.id
        assert result[0].name == "Single Entity"
        assert result[0].created_at is not None

    @pytest.mark.asyncio
    async def test_create_many_multiple_entities(self, simple_repo):
        """Test create_many with multiple entities (lines 183-190)."""
        repo, _session = await simple_repo()

        entities = [SimpleModel(id=unique_id(f"bulk{i}"), name=f"Entity {i}") for i in range(3)]

        result = await repo.create_many(entities)

        assert len(result) == 3
        for entity in result:
            # Verify refresh happened - created_at should be populated
            assert entity.created_at is not None
            assert entity.id is not None
            assert entity.name is not None

    @pytest.mark.asyncio
    async def test_create_many_entities_persisted(self, simple_repo):
        """Test create_many persists entities to database."""
        repo, _session = await simple_repo()

        entities = [SimpleModel(id=unique_id(f"persist{i}"), name=f"Entity {i}") for i in range(2)]

        created = await repo.create_many(entities)

        # Verify entities can be retrieved
        for entity in created:
            retrieved = await repo.get_by_id(entity.id)
            assert retrieved is not None
            assert retrieved.name == entity.name


class TestRepositoryUpdate:
    """Test update and merge operations."""

    @pytest.mark.asyncio
    async def test_update_attached_entity(self, simple_repo):
        """Test update with attached entity."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("update"), name="Original Name")
        created = await repo.create(entity)

        # Modify and update
        created.name = "Updated Name"
        updated = await repo.update(created)

        assert updated.name == "Updated Name"

        # Verify persistence
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_merge_detached_entity(self, simple_repo):
        """Test merge with detached entity."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("merge"), name="Original Name")
        created = await repo.create(entity)

        # Simulate detached entity by creating a new instance with same ID
        detached = SimpleModel(id=created.id, name="Merged Name")
        merged = await repo.merge(detached)

        assert merged.name == "Merged Name"

        # Verify persistence
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved.name == "Merged Name"


class TestRepositorySave:
    """Test save method (upsert pattern)."""

    @pytest.mark.asyncio
    async def test_save_new_entity(self, simple_repo):
        """Test save creates new entity when it doesn't exist."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("save_new"), name="New Entity")
        saved = await repo.save(entity)

        assert saved.id == entity.id
        assert saved.name == "New Entity"

        # Verify it was created
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_save_existing_entity(self, simple_repo):
        """Test save updates existing entity."""
        repo, _session = await simple_repo()

        # Create entity first
        entity = SimpleModel(id=unique_id("save_exist"), name="Original")
        await repo.create(entity)

        # Save with same ID but different name
        updated_entity = SimpleModel(id=entity.id, name="Updated")
        saved = await repo.save(updated_entity)

        assert saved.name == "Updated"

        # Verify update
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved.name == "Updated"

    @pytest.mark.asyncio
    async def test_save_composite_pk_new(self, composite_repo):
        """Test save with composite primary key on new entity (line 257)."""
        repo, _session = await composite_repo()

        entity = CompositeKeyModel(
            part1=unique_id("save_comp_p1"), part2=unique_id("save_comp_p2"), value="New"
        )
        saved = await repo.save(entity)

        assert saved.value == "New"

        # Verify creation
        retrieved = await repo.get_by_id((entity.part1, entity.part2))
        assert retrieved is not None
        assert retrieved.value == "New"

    @pytest.mark.asyncio
    async def test_save_composite_pk_existing(self, composite_repo):
        """Test save with composite primary key on existing entity (line 257)."""
        repo, _session = await composite_repo()

        # Create entity first
        entity = CompositeKeyModel(
            part1=unique_id("save_exist_p1"),
            part2=unique_id("save_exist_p2"),
            value="Original",
        )
        await repo.create(entity)

        # Save with same composite key but different value
        updated_entity = CompositeKeyModel(part1=entity.part1, part2=entity.part2, value="Updated")
        saved = await repo.save(updated_entity)

        assert saved.value == "Updated"

        # Verify update
        retrieved = await repo.get_by_id((entity.part1, entity.part2))
        assert retrieved.value == "Updated"


class TestRepositoryDelete:
    """Test delete operations."""

    @pytest.mark.asyncio
    async def test_delete_entity(self, simple_repo):
        """Test delete removes entity from database."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("delete"), name="To Delete")
        created = await repo.create(entity)

        await repo.delete(created)

        # Verify deletion
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_by_id_found(self, simple_repo):
        """Test delete_by_id returns True when entity exists."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("delete_by_id"), name="To Delete")
        await repo.create(entity)

        result = await repo.delete_by_id(entity.id)

        assert result is True

        # Verify deletion
        retrieved = await repo.get_by_id(entity.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, simple_repo):
        """Test delete_by_id returns False when entity doesn't exist."""
        repo, _session = await simple_repo()

        result = await repo.delete_by_id("nonexistent_id")

        assert result is False


class TestRepositoryExists:
    """Test exists method with both single and composite primary keys."""

    @pytest.mark.asyncio
    async def test_exists_single_pk_true(self, simple_repo):
        """Test exists returns True for existing entity with single PK."""
        repo, _session = await simple_repo()

        entity = SimpleModel(id=unique_id("exists"), name="Exists")
        await repo.create(entity)

        result = await repo.exists(entity.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_single_pk_false(self, simple_repo):
        """Test exists returns False for non-existing entity with single PK."""
        repo, _session = await simple_repo()

        result = await repo.exists("nonexistent_id")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_composite_pk_true(self, composite_repo):
        """Test exists returns True for existing entity with composite PK (lines 314-315)."""
        repo, _session = await composite_repo()

        entity = CompositeKeyModel(
            part1=unique_id("exists_p1"), part2=unique_id("exists_p2"), value="Exists"
        )
        await repo.create(entity)

        result = await repo.exists((entity.part1, entity.part2))

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_composite_pk_false(self, composite_repo):
        """Test exists returns False for non-existing entity with composite PK (lines 314-315)."""
        repo, _session = await composite_repo()

        result = await repo.exists(("nonexistent_p1", "nonexistent_p2"))

        assert result is False


class TestRepositoryErrorHandling:
    """Test error handling for database operations."""

    @pytest.mark.asyncio
    async def test_create_with_duplicate_id_raises_error(self, simple_repo):
        """Test creating entity with duplicate ID raises database error."""
        repo, _session = await simple_repo()

        entity_id = unique_id("duplicate")
        entity1 = SimpleModel(id=entity_id, name="First")
        await repo.create(entity1)

        # Attempt to create another with same ID
        entity2 = SimpleModel(id=entity_id, name="Second")

        with pytest.raises(Exception):  # noqa: B017 - SQLAlchemy IntegrityError
            await repo.create(entity2)

    @pytest.mark.asyncio
    async def test_update_with_invalid_session(self, simple_repo):
        """Test operations with closed session handle errors gracefully."""
        repo, session = await simple_repo()

        entity = SimpleModel(id=unique_id("invalid"), name="Test")
        created = await repo.create(entity)

        # Close the session
        await session.close()

        # Attempt operation on closed session should raise error
        with pytest.raises(Exception):  # noqa: B017 - SQLAlchemy session error
            created.name = "Updated"
            await repo.update(created)


class TestRepositoryEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_get_by_id_with_none(self, simple_repo):
        """Test get_by_id with None ID."""
        repo, _session = await simple_repo()

        result = await repo.get_by_id(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_paginated_with_zero_limit(self, simple_repo):
        """Test list_paginated with limit=0."""
        repo, _session = await simple_repo()

        # Create some entities
        entity = SimpleModel(id=unique_id("zero_limit"), name="Entity")
        await repo.create(entity)

        result = await repo.list_paginated(skip=0, limit=0)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_paginated_with_large_offset(self, simple_repo):
        """Test list_paginated with offset larger than total count."""
        repo, _session = await simple_repo()

        # Create a few entities
        entity = SimpleModel(id=unique_id("large_offset"), name="Entity")
        await repo.create(entity)

        # Request page beyond available data
        result = await repo.list_paginated(skip=1000, limit=10)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_create_many_with_mixed_valid_invalid(self, simple_repo):
        """Test create_many with one valid and one invalid entity."""
        repo, _session = await simple_repo()

        entity_id = unique_id("mixed")
        entity1 = SimpleModel(id=entity_id, name="Valid")
        await repo.create(entity1)

        # Attempt to create batch with duplicate ID
        duplicate = SimpleModel(id=entity_id, name="Duplicate")
        entity3 = SimpleModel(id=unique_id("valid"), name="Also Valid")

        with pytest.raises(Exception):  # noqa: B017 - SQLAlchemy raises generic IntegrityError
            await repo.create_many([duplicate, entity3])

    @pytest.mark.asyncio
    async def test_exists_with_none_id(self, simple_repo):
        """Test exists with None ID returns False."""
        repo, _session = await simple_repo()

        result = await repo.exists(None)

        # Should return False rather than raising an error
        assert result is False

    @pytest.mark.asyncio
    async def test_count_after_delete(self, simple_repo):
        """Test count is correct after deleting entities."""
        repo, session = await simple_repo()

        # Clear existing data
        stmt = select(SimpleModel)
        result = await session.execute(stmt)
        existing = result.scalars().all()
        for entity in existing:
            await session.delete(entity)
        await session.flush()

        # Create entities
        entities = [
            SimpleModel(id=unique_id(f"count_del{i}"), name=f"Entity {i}") for i in range(3)
        ]
        for entity in entities:
            await repo.create(entity)

        initial_count = await repo.count()

        # Delete one
        await repo.delete_by_id(entities[0].id)

        final_count = await repo.count()

        assert final_count == initial_count - 1
