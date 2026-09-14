"""Integration tests for EntityRepository.

Tests follow TDD approach - these tests verify EntityRepository works correctly
with a real PostgreSQL database.

Run with: uv run pytest backend/tests/integration/repositories/test_entity_repository.py -v

Related to NEM-2450: Create EntityRepository for PostgreSQL CRUD operations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.models import Entity
from backend.models.enums import EntityType
from backend.repositories.entity_repository import EntityRepository


def unique_entity_id() -> uuid.UUID:
    """Generate a unique entity ID for test isolation."""
    return uuid.uuid4()


class TestEntityRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_entity(self, test_db):
        """Test creating a new entity."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                entity_metadata={"clothing_color": "blue"},
            )

            created = await repo.create(entity)

            assert created.id is not None
            assert created.entity_type == EntityType.PERSON.value
            assert created.detection_count == 1
            assert created.entity_metadata == {"clothing_color": "blue"}
            assert created.first_seen_at is not None
            assert created.last_seen_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing entity by ID."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(
                entity_type=EntityType.VEHICLE.value,
                detection_count=5,
            )
            await repo.create(entity)

            retrieved = await repo.get_by_id(entity.id)

            assert retrieved is not None
            assert retrieved.id == entity.id
            assert retrieved.entity_type == EntityType.VEHICLE.value

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent entity returns None."""
        async with test_db() as session:
            repo = EntityRepository(session)

            result = await repo.get_by_id(unique_entity_id())

            assert result is None

    @pytest.mark.asyncio
    async def test_get_all_entities(self, test_db):
        """Test retrieving all entities."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity1 = Entity(entity_type=EntityType.PERSON.value, detection_count=1)
            entity2 = Entity(entity_type=EntityType.VEHICLE.value, detection_count=2)
            await repo.create(entity1)
            await repo.create(entity2)

            all_entities = await repo.get_all()

            entity_ids = [e.id for e in all_entities]
            assert entity1.id in entity_ids
            assert entity2.id in entity_ids

    @pytest.mark.asyncio
    async def test_update_entity(self, test_db):
        """Test updating an entity's properties."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                entity_metadata={"clothing_color": "red"},
            )
            await repo.create(entity)

            entity.detection_count = 10
            entity.entity_metadata = {"clothing_color": "blue", "has_hat": True}
            updated = await repo.update(entity)

            assert updated.detection_count == 10
            assert updated.entity_metadata == {"clothing_color": "blue", "has_hat": True}

            # Verify persistence
            retrieved = await repo.get_by_id(entity.id)
            assert retrieved.detection_count == 10

    @pytest.mark.asyncio
    async def test_delete_entity(self, test_db):
        """Test deleting an entity."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(entity_type=EntityType.ANIMAL.value, detection_count=1)
            await repo.create(entity)
            entity_id = entity.id

            await repo.delete(entity)

            result = await repo.get_by_id(entity_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_id(self, test_db):
        """Test deleting an entity by ID."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(entity_type=EntityType.PACKAGE.value, detection_count=1)
            await repo.create(entity)

            deleted = await repo.delete_by_id(entity.id)

            assert deleted is True

            result = await repo.get_by_id(entity.id)
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, test_db):
        """Test delete_by_id returns False for non-existent entity."""
        async with test_db() as session:
            repo = EntityRepository(session)

            deleted = await repo.delete_by_id(unique_entity_id())

            assert deleted is False

    @pytest.mark.asyncio
    async def test_exists(self, test_db):
        """Test checking if an entity exists."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(entity_type=EntityType.PERSON.value, detection_count=1)
            await repo.create(entity)

            assert await repo.exists(entity.id) is True
            assert await repo.exists(unique_entity_id()) is False

    @pytest.mark.asyncio
    async def test_count(self, test_db):
        """Test counting entities."""
        async with test_db() as session:
            repo = EntityRepository(session)

            initial_count = await repo.count()

            for i in range(3):
                entity = Entity(entity_type=EntityType.PERSON.value, detection_count=i + 1)
                await repo.create(entity)

            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestEntityRepositorySpecificMethods:
    """Test entity-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_type(self, test_db):
        """Test getting entities filtered by type."""
        async with test_db() as session:
            repo = EntityRepository(session)

            person1 = Entity(entity_type=EntityType.PERSON.value, detection_count=1)
            person2 = Entity(entity_type=EntityType.PERSON.value, detection_count=2)
            vehicle = Entity(entity_type=EntityType.VEHICLE.value, detection_count=1)
            await repo.create(person1)
            await repo.create(person2)
            await repo.create(vehicle)

            persons = await repo.get_by_type(EntityType.PERSON)

            person_ids = [p.id for p in persons]
            assert person1.id in person_ids
            assert person2.id in person_ids
            assert vehicle.id not in person_ids

    @pytest.mark.asyncio
    async def test_get_by_type_string(self, test_db):
        """Test getting entities filtered by type using string."""
        async with test_db() as session:
            repo = EntityRepository(session)

            vehicle = Entity(entity_type=EntityType.VEHICLE.value, detection_count=1)
            person = Entity(entity_type=EntityType.PERSON.value, detection_count=1)
            await repo.create(vehicle)
            await repo.create(person)

            vehicles = await repo.get_by_type("vehicle")

            vehicle_ids = [v.id for v in vehicles]
            assert vehicle.id in vehicle_ids
            assert person.id not in vehicle_ids

    @pytest.mark.asyncio
    async def test_get_recent(self, test_db):
        """Test getting most recent entities with limit."""
        async with test_db() as session:
            repo = EntityRepository(session)

            now = datetime.now(UTC)
            entities = []
            for i in range(5):
                entity = Entity(
                    entity_type=EntityType.PERSON.value,
                    detection_count=1,
                    last_seen_at=now - timedelta(hours=i),
                )
                await repo.create(entity)
                entities.append(entity)

            recent = await repo.get_recent(limit=3)

            assert len(recent) == 3
            # Most recent should be first
            recent_ids = [r.id for r in recent]
            assert entities[0].id in recent_ids
            assert entities[4].id not in recent_ids

    @pytest.mark.asyncio
    async def test_get_in_date_range(self, test_db):
        """Test getting entities seen within a date range."""
        async with test_db() as session:
            repo = EntityRepository(session)

            now = datetime.now(UTC)
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)

            recent = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                last_seen_at=yesterday,
            )
            old = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                last_seen_at=two_weeks_ago,
            )
            await repo.create(recent)
            await repo.create(old)

            entities_in_range = await repo.get_in_date_range(last_week, now)

            entity_ids = [e.id for e in entities_in_range]
            assert recent.id in entity_ids
            assert old.id not in entity_ids

    @pytest.mark.asyncio
    async def test_update_last_seen(self, test_db):
        """Test updating an entity's last_seen_at timestamp."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                last_seen_at=datetime.now(UTC) - timedelta(days=1),
            )
            await repo.create(entity)

            updated = await repo.update_last_seen(entity.id)

            assert updated is not None
            assert updated.detection_count == 2  # Incremented
            # Check last_seen_at is recent (within last minute)
            assert (datetime.now(UTC) - updated.last_seen_at).total_seconds() < 60

    @pytest.mark.asyncio
    async def test_update_last_seen_not_found(self, test_db):
        """Test update_last_seen returns None for non-existent entity."""
        async with test_db() as session:
            repo = EntityRepository(session)

            result = await repo.update_last_seen(unique_entity_id())

            assert result is None

    @pytest.mark.asyncio
    async def test_get_type_counts(self, test_db):
        """Test getting entity counts grouped by type."""
        async with test_db() as session:
            repo = EntityRepository(session)

            # Create entities of different types
            for _ in range(3):
                await repo.create(Entity(entity_type=EntityType.PERSON.value, detection_count=1))
            for _ in range(2):
                await repo.create(Entity(entity_type=EntityType.VEHICLE.value, detection_count=1))
            await repo.create(Entity(entity_type=EntityType.ANIMAL.value, detection_count=1))

            counts = await repo.get_type_counts()

            assert counts.get("person", 0) >= 3
            assert counts.get("vehicle", 0) >= 2
            assert counts.get("animal", 0) >= 1

    @pytest.mark.asyncio
    async def test_get_total_detection_count(self, test_db):
        """Test getting the total detection count across all entities."""
        async with test_db() as session:
            repo = EntityRepository(session)

            # Get initial total
            initial_total = await repo.get_total_detection_count()

            # Create entities with known detection counts
            entity1 = Entity(entity_type=EntityType.PERSON.value, detection_count=10)
            entity2 = Entity(entity_type=EntityType.VEHICLE.value, detection_count=5)
            await repo.create(entity1)
            await repo.create(entity2)

            total = await repo.get_total_detection_count()

            assert total == initial_total + 15

    @pytest.mark.asyncio
    async def test_get_with_high_detection_count(self, test_db):
        """Test getting entities with detection count above threshold."""
        async with test_db() as session:
            repo = EntityRepository(session)

            high_count = Entity(entity_type=EntityType.PERSON.value, detection_count=100)
            medium_count = Entity(entity_type=EntityType.PERSON.value, detection_count=50)
            low_count = Entity(entity_type=EntityType.PERSON.value, detection_count=5)
            await repo.create(high_count)
            await repo.create(medium_count)
            await repo.create(low_count)

            frequent = await repo.get_with_high_detection_count(min_count=50)

            frequent_ids = [f.id for f in frequent]
            assert high_count.id in frequent_ids
            assert medium_count.id in frequent_ids
            assert low_count.id not in frequent_ids


class TestEntityRepositoryPagination:
    """Test pagination operations from Repository base class."""

    @pytest.mark.asyncio
    async def test_list_paginated_default(self, test_db):
        """Test list_paginated with default parameters."""
        async with test_db() as session:
            repo = EntityRepository(session)

            for i in range(5):
                entity = Entity(entity_type=EntityType.PERSON.value, detection_count=i + 1)
                await repo.create(entity)

            entities = await repo.list_paginated()

            assert len(entities) >= 5

    @pytest.mark.asyncio
    async def test_list_paginated_with_limit(self, test_db):
        """Test list_paginated respects limit parameter."""
        async with test_db() as session:
            repo = EntityRepository(session)

            for i in range(10):
                entity = Entity(entity_type=EntityType.PERSON.value, detection_count=i + 1)
                await repo.create(entity)

            entities = await repo.list_paginated(limit=3)

            assert len(entities) == 3

    @pytest.mark.asyncio
    async def test_list_paginated_with_skip(self, test_db):
        """Test list_paginated respects skip parameter."""
        async with test_db() as session:
            repo = EntityRepository(session)

            initial_count = await repo.count()

            for i in range(5):
                entity = Entity(entity_type=EntityType.PERSON.value, detection_count=i + 1)
                await repo.create(entity)

            entities = await repo.list_paginated(skip=initial_count + 2, limit=10)

            assert len(entities) <= 3

    @pytest.mark.asyncio
    async def test_list_by_type_paginated(self, test_db):
        """Test list_by_type_paginated returns entities filtered by type."""
        async with test_db() as session:
            repo = EntityRepository(session)

            # Create mixed entities
            for i in range(5):
                await repo.create(
                    Entity(entity_type=EntityType.PERSON.value, detection_count=i + 1)
                )
            for i in range(3):
                await repo.create(
                    Entity(entity_type=EntityType.VEHICLE.value, detection_count=i + 1)
                )

            persons = await repo.list_by_type_paginated(EntityType.PERSON, skip=0, limit=3)

            assert len(persons) == 3
            for p in persons:
                assert p.entity_type == EntityType.PERSON.value


class TestEntityRepositoryMetadataSearch:
    """Test metadata search operations."""

    @pytest.mark.asyncio
    async def test_search_by_metadata(self, test_db):
        """Test searching entities by metadata field."""
        async with test_db() as session:
            repo = EntityRepository(session)

            red_shirt = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                entity_metadata={"clothing_color": "red"},
            )
            blue_shirt = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                entity_metadata={"clothing_color": "blue"},
            )
            await repo.create(red_shirt)
            await repo.create(blue_shirt)

            results = await repo.search_by_metadata("clothing_color", "red")

            result_ids = [r.id for r in results]
            assert red_shirt.id in result_ids
            assert blue_shirt.id not in result_ids

    @pytest.mark.asyncio
    async def test_search_by_metadata_no_results(self, test_db):
        """Test search_by_metadata returns empty when no matches."""
        async with test_db() as session:
            repo = EntityRepository(session)

            entity = Entity(
                entity_type=EntityType.PERSON.value,
                detection_count=1,
                entity_metadata={"clothing_color": "red"},
            )
            await repo.create(entity)

            results = await repo.search_by_metadata("clothing_color", "purple")

            assert len(results) == 0
