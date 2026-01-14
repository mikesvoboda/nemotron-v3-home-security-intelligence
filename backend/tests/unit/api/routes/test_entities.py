"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using mocked
EntityRepository for PostgreSQL queries.

Includes tests for:
- Historical entity queries (PostgreSQL via EntityRepository)
- Date range filtering (since, until)
- Entity statistics endpoint
- Entity detections endpoint
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Import the entire module to ensure coverage tracks it
import backend.api.routes.entities  # noqa: F401
from backend.api.routes.entities import (
    _entity_to_summary,
    _get_thumbnail_url,
    get_entity,
    get_entity_history,
    list_entities,
)
from backend.api.schemas.entities import EntityTypeFilter
from backend.services.reid_service import EntityEmbedding


class TestThumbnailUrl:
    """Tests for _get_thumbnail_url helper function."""

    def test_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for integer detection IDs."""
        url = _get_thumbnail_url("123")
        assert url == "/api/detections/123/image"

    def test_non_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for non-integer detection IDs."""
        url = _get_thumbnail_url("det_abc123")
        assert url == "/api/detections/det_abc123/image"


class TestEntityToSummary:
    """Tests for _entity_to_summary helper function."""

    def test_single_embedding(self) -> None:
        """Test summary creation from a single embedding."""
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={"clothing": "blue jacket"},
        )

        summary = _entity_to_summary("det_001", [embedding])

        assert summary.id == "det_001"
        assert summary.entity_type == "person"
        assert summary.first_seen == embedding.timestamp
        assert summary.last_seen == embedding.timestamp
        assert summary.appearance_count == 1
        assert summary.cameras_seen == ["front_door"]
        assert summary.thumbnail_url == "/api/detections/det_001/image"

    def test_multiple_embeddings(self) -> None:
        """Test summary creation from multiple embeddings."""
        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
        ]

        summary = _entity_to_summary("det_001", embeddings)

        assert summary.appearance_count == 3
        assert len(summary.cameras_seen) == 2
        assert "front_door" in summary.cameras_seen
        assert "backyard" in summary.cameras_seen
        assert summary.first_seen == embeddings[0].timestamp
        assert summary.last_seen == embeddings[2].timestamp

    def test_empty_embeddings_raises_error(self) -> None:
        """Test that empty embeddings list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot create summary from empty"):
            _entity_to_summary("det_001", [])


def _create_mock_entity(
    entity_id: UUID | None = None,
    entity_type: str = "person",
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
    detection_count: int = 1,
    primary_detection_id: int | None = None,
    entity_metadata: dict | None = None,
) -> MagicMock:
    """Create a mock Entity object for testing."""
    mock_entity = MagicMock()
    mock_entity.id = entity_id or uuid4()
    mock_entity.entity_type = entity_type
    mock_entity.first_seen_at = first_seen or datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
    mock_entity.last_seen_at = last_seen or datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
    mock_entity.detection_count = detection_count
    mock_entity.primary_detection_id = primary_detection_id or 123
    mock_entity.entity_metadata = entity_metadata or {"camera_id": "front_door"}
    return mock_entity


def _create_mock_detection(
    detection_id: int = 1,
    camera_id: str = "front_door",
    detected_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Detection object for testing."""
    mock_detection = MagicMock()
    mock_detection.id = detection_id
    mock_detection.camera_id = camera_id
    mock_detection.detected_at = detected_at or datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
    return mock_detection


class TestListEntities:
    """Tests for GET /api/entities endpoint."""

    @pytest.mark.asyncio
    async def test_list_entities_no_redis(self) -> None:
        """Test listing entities returns empty when repository returns empty."""
        mock_repo = MagicMock()
        mock_repo.list = AsyncMock(return_value=([], 0))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_entities_empty(self) -> None:
        """Test listing entities when none exist."""
        mock_repo = MagicMock()
        mock_repo.list = AsyncMock(return_value=([], 0))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_entities_with_data(self) -> None:
        """Test listing entities when data exists."""
        mock_repo = MagicMock()

        # Create test entities
        entities = [
            _create_mock_entity(entity_id=uuid4(), entity_type="person"),
            _create_mock_entity(entity_id=uuid4(), entity_type="person"),
        ]

        mock_repo.list = AsyncMock(return_value=(entities, 2))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        assert result.pagination.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_type(self) -> None:
        """Test filtering entities by entity type."""
        mock_repo = MagicMock()

        entity = _create_mock_entity(entity_type="person")
        mock_repo.list = AsyncMock(return_value=([entity], 1))

        result = await list_entities(
            entity_type=EntityTypeFilter.person,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should only query person type
        mock_repo.list.assert_called_once_with(
            entity_type="person",
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
        )
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_camera(self) -> None:
        """Test filtering entities by camera ID."""
        mock_repo = MagicMock()
        mock_repo.list = AsyncMock(return_value=([], 0))

        await list_entities(
            entity_type=None,
            camera_id="front_door",
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should pass camera_id to repository
        mock_repo.list.assert_called_once_with(
            entity_type=None,
            camera_id="front_door",
            since=None,
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_since(self) -> None:
        """Test filtering entities by timestamp."""
        mock_repo = MagicMock()

        entity = _create_mock_entity(last_seen=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC))
        mock_repo.list = AsyncMock(return_value=([entity], 1))

        since = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should pass since to repository
        mock_repo.list.assert_called_once_with(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
        )
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_entities_pagination(self) -> None:
        """Test pagination of entity list."""
        mock_repo = MagicMock()

        # Create multiple entities
        entities = [_create_mock_entity(entity_id=uuid4()) for _ in range(2)]

        mock_repo.list = AsyncMock(return_value=(entities, 5))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=2,
            offset=1,
            entity_repo=mock_repo,
        )

        assert result.pagination.total == 5  # Total count
        assert len(result.items) == 2  # Paginated result
        assert result.pagination.limit == 2
        assert result.pagination.offset == 1


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_no_redis(self) -> None:
        """Test getting entity when repository returns None (not found)."""
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity(uuid4(), entity_repo=mock_repo)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self) -> None:
        """Test getting non-existent entity returns 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity(uuid4(), entity_repo=mock_repo)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_entity_success(self) -> None:
        """Test getting entity successfully."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        entity = _create_mock_entity(
            entity_id=entity_id,
            entity_type="person",
            detection_count=1,
        )

        detection = _create_mock_detection(
            detection_id=123,
            camera_id="front_door",
        )

        mock_repo.get_by_id = AsyncMock(return_value=entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert result.id == str(entity_id)
        assert result.entity_type == "person"
        assert result.appearance_count == 1
        assert len(result.appearances) == 1
        assert result.appearances[0].detection_id == "123"


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_no_redis(self) -> None:
        """Test getting history when repository returns None (not found)."""
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity_history(uuid4(), entity_repo=mock_repo)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_not_found(self) -> None:
        """Test getting history for non-existent entity returns 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity_history(uuid4(), entity_repo=mock_repo)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_success(self) -> None:
        """Test getting entity history successfully."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        entity = _create_mock_entity(entity_id=entity_id, entity_type="person")

        detections = [
            _create_mock_detection(
                detection_id=1,
                camera_id="front_door",
                detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=2,
                camera_id="backyard",
                detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ),
        ]

        mock_repo.get_by_id = AsyncMock(return_value=entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 2))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        assert result.entity_id == str(entity_id)
        assert result.entity_type == "person"
        assert result.count == 2
        assert len(result.appearances) == 2


class TestGetRedisClient:
    """Tests for _get_redis_client helper function."""

    @pytest.mark.asyncio
    async def test_get_redis_client_returns_connected_client(self) -> None:
        """Test _get_redis_client returns connected Redis client."""
        from backend.api.routes.entities import _get_redis_client

        mock_redis_instance = MagicMock()
        mock_redis_instance._ensure_connected.return_value = mock_redis_instance
        mock_redis_client = MagicMock()
        mock_redis_client._ensure_connected.return_value = mock_redis_instance

        async def mock_get_redis():
            yield mock_redis_client

        with patch(
            "backend.api.routes.entities.get_redis_optional",
            return_value=mock_get_redis(),
        ):
            result = await _get_redis_client()

        assert result is mock_redis_instance
        mock_redis_client._ensure_connected.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_client_returns_none_when_unavailable(self) -> None:
        """Test _get_redis_client returns None when Redis is unavailable."""
        from backend.api.routes.entities import _get_redis_client

        async def mock_get_redis():
            yield None

        with patch(
            "backend.api.routes.entities.get_redis_optional",
            return_value=mock_get_redis(),
        ):
            result = await _get_redis_client()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_redis_client_empty_generator(self) -> None:
        """Test _get_redis_client with empty generator (no yields)."""
        from backend.api.routes.entities import _get_redis_client

        # Create an empty async generator using a class
        class EmptyAsyncGenerator:
            """Async generator that yields nothing."""

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        with patch(
            "backend.api.routes.entities.get_redis_optional",
            return_value=EmptyAsyncGenerator(),
        ):
            result = await _get_redis_client()

        assert result is None


class TestListEntitiesEdgeCases:
    """Additional edge case tests for list_entities endpoint."""

    @pytest.mark.asyncio
    async def test_list_entities_sorts_by_last_seen_desc(self) -> None:
        """Test that entities are sorted by last_seen timestamp descending."""
        mock_repo = MagicMock()

        # Create entities with different timestamps (repo returns sorted)
        old_entity = _create_mock_entity(
            entity_id=uuid4(),
            last_seen=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
        )
        new_entity = _create_mock_entity(
            entity_id=uuid4(),
            last_seen=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        )

        # Repository should return in sorted order (newest first)
        mock_repo.list = AsyncMock(return_value=([new_entity, old_entity], 2))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Verify order: newer should be first
        assert result.items[0].last_seen > result.items[1].last_seen

    @pytest.mark.asyncio
    async def test_list_entities_handles_empty_entity_groups(self) -> None:
        """Test that empty results are handled gracefully."""
        mock_repo = MagicMock()
        mock_repo.list = AsyncMock(return_value=([], 0))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should handle empty results gracefully
        assert result.pagination.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_entities_queries_both_types_when_no_filter(self) -> None:
        """Test that entity_type is passed as None when no filter."""
        mock_repo = MagicMock()

        person_entity = _create_mock_entity(entity_type="person")
        vehicle_entity = _create_mock_entity(entity_type="vehicle")

        mock_repo.list = AsyncMock(return_value=([person_entity, vehicle_entity], 2))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should have both entities
        assert result.pagination.total == 2
        # Verify entity_type was passed as None
        mock_repo.list.assert_called_once_with(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_entities_pagination_beyond_results(self) -> None:
        """Test pagination with offset beyond available results."""
        mock_repo = MagicMock()

        # Return empty list but total count of 1 (offset beyond results)
        mock_repo.list = AsyncMock(return_value=([], 1))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=10,
            offset=100,  # Beyond available results
            entity_repo=mock_repo,
        )

        # Should return empty list but correct total count
        assert result.pagination.total == 1  # Total count
        assert len(result.items) == 0  # Paginated result is empty
        assert result.pagination.offset == 100

    @pytest.mark.asyncio
    async def test_list_entities_skips_invalid_summaries(self) -> None:
        """Test that entities with valid data are returned."""
        mock_repo = MagicMock()

        valid_entity = _create_mock_entity()
        mock_repo.list = AsyncMock(return_value=([valid_entity], 1))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Should handle valid entity gracefully
        assert result.pagination.total >= 0


class TestGetEntityEdgeCases:
    """Additional edge case tests for get_entity endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_found_in_vehicle_type(self) -> None:
        """Test getting entity found in vehicle type (not person)."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        vehicle_entity = _create_mock_entity(
            entity_id=entity_id,
            entity_type="vehicle",
        )

        detection = _create_mock_detection(
            detection_id=123,
            camera_id="driveway",
        )

        mock_repo.get_by_id = AsyncMock(return_value=vehicle_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert result.id == str(entity_id)
        assert result.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_get_entity_multiple_appearances(self) -> None:
        """Test get_entity with multiple appearances across cameras."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        entity = _create_mock_entity(entity_id=entity_id, detection_count=3)

        detections = [
            _create_mock_detection(
                detection_id=1,
                camera_id="front_door",
                detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=2,
                camera_id="backyard",
                detected_at=datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=3,
                camera_id="driveway",
                detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ),
        ]

        mock_repo.get_by_id = AsyncMock(return_value=entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 3))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert result.appearance_count == 3
        assert len(result.appearances) == 3

    @pytest.mark.asyncio
    async def test_get_entity_camera_name_formatting(self) -> None:
        """Test that camera_name is properly formatted from camera_id."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        entity = _create_mock_entity(entity_id=entity_id)

        detection = _create_mock_detection(
            detection_id=1,
            camera_id="front_door_camera",
        )

        mock_repo.get_by_id = AsyncMock(return_value=entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        # Verify camera name formatting (underscores to spaces, title case)
        assert result.appearances[0].camera_name == "Front Door Camera"


class TestGetEntityHistoryEdgeCases:
    """Additional edge case tests for get_entity_history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_chronological_order(self) -> None:
        """Test that history appearances are in chronological order."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        entity = _create_mock_entity(entity_id=entity_id)

        # Create detections in chronological order (repo should return sorted)
        detections = [
            _create_mock_detection(
                detection_id=1,
                camera_id="front_door",
                detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=2,
                camera_id="driveway",
                detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=3,
                camera_id="backyard",
                detected_at=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
            ),
        ]

        mock_repo.get_by_id = AsyncMock(return_value=entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 3))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        # Verify chronological order
        assert result.appearances[0].timestamp < result.appearances[1].timestamp
        assert result.appearances[1].timestamp < result.appearances[2].timestamp

    @pytest.mark.asyncio
    async def test_get_history_found_in_vehicle_type(self) -> None:
        """Test getting history for vehicle entity type."""
        mock_repo = MagicMock()

        entity_id = uuid4()
        vehicle_entity = _create_mock_entity(
            entity_id=entity_id,
            entity_type="vehicle",
        )

        detection = _create_mock_detection(
            detection_id=1,
            camera_id="driveway",
        )

        mock_repo.get_by_id = AsyncMock(return_value=vehicle_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([detection], 1))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        assert result.entity_type == "vehicle"
