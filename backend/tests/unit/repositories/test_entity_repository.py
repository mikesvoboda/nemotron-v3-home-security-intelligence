"""Unit tests for EntityRepository.

Tests follow TDD approach - these tests are written BEFORE the implementation.
Run with: uv run pytest backend/tests/unit/repositories/test_entity_repository.py -v

Related to NEM-2450: Create EntityRepository for PostgreSQL CRUD operations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import Entity
from backend.models.enums import EntityType


class TestEntityRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_entity(self, mock_db_session: AsyncMock):
        """Test creating a new entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entity = Entity(
            entity_type=EntityType.PERSON.value,
            detection_count=1,
        )

        # Configure mock to return the entity on refresh
        mock_db_session.refresh = AsyncMock()

        created = await repo.create(entity)

        mock_db_session.add.assert_called_once_with(entity)
        mock_db_session.flush.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(entity)
        assert created == entity

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, mock_db_session: AsyncMock):
        """Test retrieving an existing entity by ID."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        entity_id = uuid.uuid4()
        expected_entity = Entity(id=entity_id, entity_type=EntityType.PERSON.value)

        mock_db_session.get.return_value = expected_entity

        result = await repo.get_by_id(entity_id)

        mock_db_session.get.assert_called_once_with(Entity, entity_id)
        assert result == expected_entity

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db_session: AsyncMock):
        """Test retrieving a non-existent entity returns None."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        mock_db_session.get.return_value = None

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_entity(self, mock_db_session: AsyncMock):
        """Test deleting an entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        entity = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)

        await repo.delete(entity)

        mock_db_session.delete.assert_called_once_with(entity)
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_id(self, mock_db_session: AsyncMock):
        """Test deleting an entity by ID."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        entity_id = uuid.uuid4()
        entity = Entity(id=entity_id, entity_type=EntityType.PERSON.value)

        mock_db_session.get.return_value = entity

        result = await repo.delete_by_id(entity_id)

        assert result is True
        mock_db_session.delete.assert_called_once_with(entity)

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, mock_db_session: AsyncMock):
        """Test delete_by_id returns False for non-existent entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        mock_db_session.get.return_value = None

        result = await repo.delete_by_id(uuid.uuid4())

        assert result is False


class TestEntityRepositorySpecificMethods:
    """Test entity-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_type(self, mock_db_session: AsyncMock):
        """Test getting entities filtered by type."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        person1 = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)
        person2 = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [person1, person2]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_by_type(EntityType.PERSON)

        assert len(result) == 2
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_type_string(self, mock_db_session: AsyncMock):
        """Test getting entities filtered by type using string."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        vehicle = Entity(id=uuid.uuid4(), entity_type=EntityType.VEHICLE.value)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [vehicle]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_by_type("vehicle")

        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent(self, mock_db_session: AsyncMock):
        """Test getting most recent entities with limit."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        entities = [
            Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value, last_seen_at=now),
            Entity(
                id=uuid.uuid4(),
                entity_type=EntityType.PERSON.value,
                last_seen_at=now - timedelta(hours=1),
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_recent(limit=10)

        assert len(result) == 2
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_in_date_range(self, mock_db_session: AsyncMock):
        """Test getting entities seen within a date range."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        entity = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value, last_seen_at=now)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_in_date_range(yesterday, now)

        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_last_seen(self, mock_db_session: AsyncMock):
        """Test updating an entity's last_seen_at timestamp."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        entity_id = uuid.uuid4()
        entity = Entity(
            id=entity_id,
            entity_type=EntityType.PERSON.value,
            detection_count=1,
            last_seen_at=datetime.now(UTC) - timedelta(days=1),
        )

        mock_db_session.get.return_value = entity

        result = await repo.update_last_seen(entity_id)

        assert result is not None
        assert result.detection_count == 2  # Incremented
        mock_db_session.flush.assert_called()
        mock_db_session.refresh.assert_called_with(entity)

    @pytest.mark.asyncio
    async def test_update_last_seen_not_found(self, mock_db_session: AsyncMock):
        """Test update_last_seen returns None for non-existent entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        mock_db_session.get.return_value = None

        result = await repo.update_last_seen(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_primary_detection_id(self, mock_db_session: AsyncMock):
        """Test getting an entity by its primary detection ID."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        detection_id = 12345
        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            primary_detection_id=detection_id,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entity
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_by_primary_detection_id(detection_id)

        assert result == entity
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_primary_detection_id_not_found(self, mock_db_session: AsyncMock):
        """Test get_by_primary_detection_id returns None when not found."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_by_primary_detection_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_type_counts(self, mock_db_session: AsyncMock):
        """Test getting entity counts grouped by type."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("person", 10),
            ("vehicle", 5),
            ("animal", 3),
        ]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_type_counts()

        assert result == {"person": 10, "vehicle": 5, "animal": 3}

    @pytest.mark.asyncio
    async def test_get_total_detection_count(self, mock_db_session: AsyncMock):
        """Test getting the total detection count across all entities."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 150
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_total_detection_count()

        assert result == 150


class TestEntityRepositoryPagination:
    """Test pagination operations from Repository base class."""

    @pytest.mark.asyncio
    async def test_list_paginated_default(self, mock_db_session: AsyncMock):
        """Test list_paginated with default parameters."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(5)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        result = await repo.list_paginated()

        assert len(result) == 5
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_paginated_with_limit(self, mock_db_session: AsyncMock):
        """Test list_paginated respects limit parameter."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(3)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        result = await repo.list_paginated(limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_by_type_paginated(self, mock_db_session: AsyncMock):
        """Test list_by_type_paginated returns entities filtered by type."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        persons = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(3)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = persons
        mock_db_session.execute.return_value = mock_result

        result = await repo.list_by_type_paginated(EntityType.PERSON, skip=0, limit=10)

        assert len(result) == 3


class TestEntityRepositoryFiltering:
    """Test entity filtering operations."""

    @pytest.mark.asyncio
    async def test_search_by_metadata(self, mock_db_session: AsyncMock):
        """Test searching entities by metadata field."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            entity_metadata={"clothing_color": "red"},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity]
        mock_db_session.execute.return_value = mock_result

        result = await repo.search_by_metadata("clothing_color", "red")

        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_high_detection_count(self, mock_db_session: AsyncMock):
        """Test getting entities with detection count above threshold."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        frequent_entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            detection_count=100,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [frequent_entity]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_with_high_detection_count(min_count=50)

        assert len(result) == 1
        assert result[0].detection_count == 100


class TestEntityRepositoryListWithFilters:
    """Test list method with filtering and pagination (NEM-2496)."""

    @pytest.mark.asyncio
    async def test_list_returns_tuple_with_entities_and_count(self, mock_db_session: AsyncMock):
        """Test list returns (entities, total_count) tuple."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [
            Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value),
            Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value),
        ]

        # Mock for entity query
        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = entities

        # Mock for count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 2

        # Set up execute to return different results for different calls
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list()

        assert len(result) == 2
        assert total == 2
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_filters_by_entity_type(self, mock_db_session: AsyncMock):
        """Test list filters by entity_type when provided."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        person = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = [person]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list(entity_type="person")

        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_filters_by_camera_id(self, mock_db_session: AsyncMock):
        """Test list filters by camera_id when provided via metadata."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            entity_metadata={"camera_id": "front_door"},
        )

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = [entity]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list(camera_id="front_door")

        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_filters_by_since_timestamp(self, mock_db_session: AsyncMock):
        """Test list filters by since timestamp."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            last_seen_at=now,
        )

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = [entity]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        since = now - timedelta(hours=1)
        result, total = await repo.list(since=since)

        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_respects_limit_and_offset(self, mock_db_session: AsyncMock):
        """Test list respects limit and offset parameters."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value) for _ in range(3)]

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = entities
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 10  # Total more than returned
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list(limit=3, offset=5)

        assert len(result) == 3
        assert total == 10

    @pytest.mark.asyncio
    async def test_list_with_all_filters(self, mock_db_session: AsyncMock):
        """Test list with multiple filters combined."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.VEHICLE.value,
            entity_metadata={"camera_id": "driveway"},
            last_seen_at=now,
        )

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = [entity]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list(
            entity_type="vehicle",
            camera_id="driveway",
            since=now - timedelta(hours=1),
            limit=10,
            offset=0,
        )

        assert len(result) == 1
        assert total == 1


class TestEntityRepositoryEmbeddingSearch:
    """Test embedding-based similarity search (NEM-2496)."""

    @pytest.mark.asyncio
    async def test_find_by_embedding_returns_sorted_by_similarity(self, mock_db_session: AsyncMock):
        """Test find_by_embedding returns entities sorted by similarity score."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Create entities with different embeddings
        entity1 = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
        )
        entity1.set_embedding([0.9, 0.1, 0.0], model="clip")

        entity2 = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
        )
        entity2.set_embedding([0.8, 0.2, 0.1], model="clip")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity1, entity2]
        mock_db_session.execute.return_value = mock_result

        query_embedding = [1.0, 0.0, 0.0]
        results = await repo.find_by_embedding(
            embedding=query_embedding,
            entity_type="person",
            threshold=0.5,
            limit=10,
        )

        # Should return list of (entity, similarity_score) tuples
        assert len(results) == 2
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        # First result should have higher similarity
        assert results[0][1] >= results[1][1]

    @pytest.mark.asyncio
    async def test_find_by_embedding_filters_by_threshold(self, mock_db_session: AsyncMock):
        """Test find_by_embedding only returns entities above threshold."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Entity with embedding that will have low similarity
        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
        )
        entity.set_embedding([0.0, 0.0, 1.0], model="clip")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity]
        mock_db_session.execute.return_value = mock_result

        # Query embedding orthogonal to entity embedding
        query_embedding = [1.0, 0.0, 0.0]
        results = await repo.find_by_embedding(
            embedding=query_embedding,
            entity_type="person",
            threshold=0.85,  # High threshold
            limit=10,
        )

        # Should filter out low-similarity entities
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_find_by_embedding_filters_by_entity_type(self, mock_db_session: AsyncMock):
        """Test find_by_embedding filters by entity type."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        person = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)
        person.set_embedding([1.0, 0.0, 0.0], model="clip")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [person]
        mock_db_session.execute.return_value = mock_result

        results = await repo.find_by_embedding(
            embedding=[1.0, 0.0, 0.0],
            entity_type="person",
            threshold=0.5,
            limit=10,
        )

        assert len(results) == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_embedding_respects_limit(self, mock_db_session: AsyncMock):
        """Test find_by_embedding respects the limit parameter."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Create multiple entities with high similarity
        entities = []
        for i in range(5):
            entity = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)
            entity.set_embedding([1.0 - i * 0.01, 0.0, 0.0], model="clip")
            entities.append(entity)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_db_session.execute.return_value = mock_result

        results = await repo.find_by_embedding(
            embedding=[1.0, 0.0, 0.0],
            entity_type="person",
            threshold=0.5,
            limit=3,
        )

        # Should return at most 3 results
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_find_by_embedding_handles_missing_embeddings(self, mock_db_session: AsyncMock):
        """Test find_by_embedding gracefully handles entities without embeddings."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Entity without embedding
        entity_no_embed = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)

        # Entity with embedding
        entity_with_embed = Entity(id=uuid.uuid4(), entity_type=EntityType.PERSON.value)
        entity_with_embed.set_embedding([1.0, 0.0, 0.0], model="clip")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entity_no_embed, entity_with_embed]
        mock_db_session.execute.return_value = mock_result

        results = await repo.find_by_embedding(
            embedding=[1.0, 0.0, 0.0],
            entity_type="person",
            threshold=0.5,
            limit=10,
        )

        # Should only include entity with embedding
        assert len(results) == 1
        assert results[0][0].id == entity_with_embed.id


class TestEntityRepositoryIncrementDetectionCount:
    """Test increment_detection_count method (NEM-2496)."""

    @pytest.mark.asyncio
    async def test_increment_detection_count_updates_count_and_timestamp(
        self, mock_db_session: AsyncMock
    ):
        """Test increment_detection_count updates both count and last_seen_at."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entity_id = uuid.uuid4()
        original_time = datetime.now(UTC) - timedelta(hours=1)
        entity = Entity(
            id=entity_id,
            entity_type=EntityType.PERSON.value,
            detection_count=5,
            last_seen_at=original_time,
        )

        mock_db_session.get.return_value = entity

        await repo.increment_detection_count(entity_id)

        assert entity.detection_count == 6
        assert entity.last_seen_at > original_time
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_detection_count_not_found(self, mock_db_session: AsyncMock):
        """Test increment_detection_count raises/handles non-existent entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        mock_db_session.get.return_value = None

        # Should not raise, just do nothing for non-existent entity
        await repo.increment_detection_count(uuid.uuid4())

        mock_db_session.flush.assert_not_called()


class TestEntityRepositoryGetOrCreateForDetection:
    """Test get_or_create_for_detection method (NEM-2496)."""

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing_entity_when_match_found(
        self, mock_db_session: AsyncMock
    ):
        """Test get_or_create returns existing entity when similarity is above threshold."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        existing_entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            detection_count=3,
        )
        existing_entity.set_embedding([1.0, 0.0, 0.0], model="clip")

        # Mock find_by_embedding to return existing entity
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_db_session.execute.return_value = mock_result

        entity, is_new = await repo.get_or_create_for_detection(
            detection_id=123,
            entity_type="person",
            embedding=[1.0, 0.0, 0.0],
            threshold=0.85,
        )

        assert is_new is False
        assert entity.id == existing_entity.id

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_entity_when_no_match(self, mock_db_session: AsyncMock):
        """Test get_or_create creates new entity when no similar entity exists."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Mock find_by_embedding to return no matches
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        _entity, is_new = await repo.get_or_create_for_detection(
            detection_id=456,
            entity_type="person",
            embedding=[0.5, 0.5, 0.0],
            threshold=0.85,
        )

        assert is_new is True
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_when_below_threshold(self, mock_db_session: AsyncMock):
        """Test get_or_create creates new entity when match is below threshold."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Entity with dissimilar embedding
        existing_entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
        )
        existing_entity.set_embedding([0.0, 0.0, 1.0], model="clip")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_db_session.execute.return_value = mock_result

        # Query with orthogonal embedding
        _entity, is_new = await repo.get_or_create_for_detection(
            detection_id=789,
            entity_type="person",
            embedding=[1.0, 0.0, 0.0],
            threshold=0.85,
        )

        assert is_new is True
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_updates_existing_entity_when_matched(
        self, mock_db_session: AsyncMock
    ):
        """Test get_or_create updates detection count on existing entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        existing_entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            detection_count=10,
        )
        existing_entity.set_embedding([1.0, 0.0, 0.0], model="clip")
        original_count = existing_entity.detection_count

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_db_session.execute.return_value = mock_result

        entity, is_new = await repo.get_or_create_for_detection(
            detection_id=101,
            entity_type="person",
            embedding=[1.0, 0.0, 0.0],
            threshold=0.85,
        )

        assert is_new is False
        assert entity.detection_count == original_count + 1
