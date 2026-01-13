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
