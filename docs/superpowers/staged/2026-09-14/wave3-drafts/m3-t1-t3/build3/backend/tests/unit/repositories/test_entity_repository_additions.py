"""Additional tests for EntityRepository methods (NEM-2494).

Tests for the new methods and signature changes added as part of
NEM-2494: Reopen EntityRepository for PostgreSQL CRUD.

New methods tested:
- get_repeat_visitors: Get entities detected multiple times
- get_stats: Get comprehensive entity statistics
- list_filtered: List with until parameter for time-range filtering

Updated methods tested:
- increment_detection_count: Now returns Entity | None instead of None
- get_or_create_for_detection: Now accepts attributes parameter
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import Entity
from backend.models.enums import EntityType


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    return session


class TestEntityRepositoryGetRepeatVisitors:
    """Test get_repeat_visitors method (NEM-2494)."""

    @pytest.mark.asyncio
    async def test_get_repeat_visitors_returns_entities_above_threshold(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test get_repeat_visitors returns entities with min_appearances."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        repeat_visitor = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            detection_count=5,
            last_seen_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [repeat_visitor]
        mock_db_session.execute.return_value = mock_result

        result = await repo.get_repeat_visitors(
            min_appearances=3,
            entity_type="person",
        )

        assert len(result) == 1
        assert result[0].detection_count >= 3
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_repeat_visitors_filters_by_since(self, mock_db_session: AsyncMock) -> None:
        """Test get_repeat_visitors filters by since timestamp."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        since = datetime.now(UTC) - timedelta(days=7)
        await repo.get_repeat_visitors(
            min_appearances=2,
            since=since,
        )

        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_repeat_visitors_respects_limit(self, mock_db_session: AsyncMock) -> None:
        """Test get_repeat_visitors respects limit parameter."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await repo.get_repeat_visitors(limit=10)

        mock_db_session.execute.assert_called_once()


class TestEntityRepositoryGetStats:
    """Test get_stats method (NEM-2494)."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_comprehensive_statistics(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test get_stats returns all expected statistics."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Mock results for each query in sequence
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 100

        mock_type_counts_result = MagicMock()
        mock_type_counts_result.all.return_value = [
            ("person", 70),
            ("vehicle", 20),
            ("animal", 10),
        ]

        mock_detections_result = MagicMock()
        mock_detections_result.scalar_one.return_value = 500

        mock_repeat_result = MagicMock()
        mock_repeat_result.scalar_one.return_value = 45

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_type_counts_result,
            mock_detections_result,
            mock_repeat_result,
        ]

        result = await repo.get_stats()

        assert "total_entities" in result
        assert "by_type" in result
        assert "total_detections" in result
        assert "repeat_visitor_count" in result
        assert result["total_entities"] == 100
        assert result["by_type"]["person"] == 70
        assert result["total_detections"] == 500
        assert result["repeat_visitor_count"] == 45

    @pytest.mark.asyncio
    async def test_get_stats_filters_by_entity_type(self, mock_db_session: AsyncMock) -> None:
        """Test get_stats filters by entity_type when provided."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 70

        mock_detections_result = MagicMock()
        mock_detections_result.scalar_one.return_value = 350

        mock_repeat_result = MagicMock()
        mock_repeat_result.scalar_one.return_value = 30

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_detections_result,
            mock_repeat_result,
        ]

        result = await repo.get_stats(entity_type="person")

        # When entity_type is specified, by_type is not included
        assert "total_entities" in result
        assert "by_type" not in result
        assert result["total_entities"] == 70


class TestEntityRepositoryListFiltered:
    """Test list_filtered method with until parameter (NEM-2494)."""

    @pytest.mark.asyncio
    async def test_list_filtered_with_until_parameter(self, mock_db_session: AsyncMock) -> None:
        """Test list_filtered filters by until timestamp."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        now = datetime.now(UTC)
        entity = Entity(
            id=uuid.uuid4(),
            entity_type=EntityType.PERSON.value,
            last_seen_at=now - timedelta(hours=1),
        )

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = [entity]
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        since = now - timedelta(days=1)
        until = now
        result, total = await repo.list_filtered(
            entity_type="person",
            since=since,
            until=until,
            limit=50,
            offset=0,
        )

        assert len(result) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_filtered_without_time_filters(self, mock_db_session: AsyncMock) -> None:
        """Test list_filtered works without since/until."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list_filtered(limit=20, offset=0)

        assert len(result) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_filtered_returns_correct_total(self, mock_db_session: AsyncMock) -> None:
        """Test list_filtered returns accurate total count."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entities = [
            Entity(
                id=uuid.uuid4(),
                entity_type=EntityType.PERSON.value,
                last_seen_at=datetime.now(UTC),
            )
            for _ in range(5)
        ]

        mock_entity_result = MagicMock()
        mock_entity_result.scalars.return_value.all.return_value = entities
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50  # Total is higher than returned
        mock_db_session.execute.side_effect = [mock_entity_result, mock_count_result]

        result, total = await repo.list_filtered(limit=5, offset=0)

        assert len(result) == 5
        assert total == 50  # Total represents all matching records


class TestEntityRepositoryIncrementDetectionCountReturn:
    """Test increment_detection_count returns Entity | None (NEM-2494)."""

    @pytest.mark.asyncio
    async def test_increment_detection_count_returns_updated_entity(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test increment_detection_count returns the updated entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        entity_id = uuid.uuid4()
        entity = Entity(
            id=entity_id,
            entity_type=EntityType.PERSON.value,
            detection_count=5,
        )

        mock_db_session.get.return_value = entity

        result = await repo.increment_detection_count(entity_id)

        assert result is not None
        assert result.id == entity_id
        assert result.detection_count == 6

    @pytest.mark.asyncio
    async def test_increment_detection_count_returns_none_when_not_found(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test increment_detection_count returns None when entity not found."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)
        mock_db_session.get.return_value = None

        result = await repo.increment_detection_count(uuid.uuid4())

        assert result is None


class TestEntityRepositoryGetOrCreateWithAttributes:
    """Test get_or_create_for_detection with attributes parameter (NEM-2494)."""

    @pytest.mark.asyncio
    async def test_get_or_create_with_attributes(self, mock_db_session: AsyncMock) -> None:
        """Test get_or_create passes attributes to new entity."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Mock no existing matches
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        attributes = {"clothing_color": "red", "camera_id": "front_door"}
        _entity, is_new = await repo.get_or_create_for_detection(
            detection_id=456,
            entity_type="person",
            embedding=[0.5, 0.5, 0.0],
            threshold=0.85,
            attributes=attributes,
        )

        assert is_new is True
        mock_db_session.add.assert_called_once()
        added_entity = mock_db_session.add.call_args[0][0]
        assert added_entity.entity_metadata == attributes

    @pytest.mark.asyncio
    async def test_get_or_create_without_attributes(self, mock_db_session: AsyncMock) -> None:
        """Test get_or_create works without attributes (backward compatibility)."""
        from backend.repositories.entity_repository import EntityRepository

        repo = EntityRepository(mock_db_session)

        # Mock no existing matches
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        _entity, is_new = await repo.get_or_create_for_detection(
            detection_id=789,
            entity_type="vehicle",
            embedding=[0.3, 0.3, 0.4],
        )

        assert is_new is True
        mock_db_session.add.assert_called_once()
        added_entity = mock_db_session.add.call_args[0][0]
        # entity_metadata should be None when no attributes provided
        assert added_entity.entity_metadata is None
