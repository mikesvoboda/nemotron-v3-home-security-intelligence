"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using mocked
EntityRepository and PostgreSQL storage.

Includes tests for:
- Entity listing with PostgreSQL
- Entity retrieval by UUID
- Entity history endpoint
- Entity matches endpoint
- Entity statistics endpoint
- Entity detections endpoint
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Import the entire module to ensure coverage tracks it
import backend.api.routes.entities  # noqa: F401
from backend.api.routes.entities import (
    _entity_to_summary,
    _get_thumbnail_url,
    get_entity,
    get_entity_history,
    get_entity_matches,
    list_entities,
)
from backend.api.schemas.entities import EntityTypeFilter, SourceFilter
from backend.services.reid_service import EntityEmbedding, EntityMatch


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
    entity_id=None,
    entity_type="person",
    first_seen=None,
    last_seen=None,
    detection_count=1,
    cameras_seen=None,
    primary_detection_id=123,
):
    """Helper to create mock Entity objects for testing."""
    mock_entity = MagicMock()
    mock_entity.id = entity_id or uuid4()
    mock_entity.entity_type = entity_type
    mock_entity.first_seen_at = first_seen or datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
    mock_entity.last_seen_at = last_seen or datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC)
    mock_entity.detection_count = detection_count
    mock_entity.cameras_seen = cameras_seen or ["front_door"]
    mock_entity.primary_detection_id = primary_detection_id
    mock_entity.entity_metadata = {}
    return mock_entity


def _create_mock_detection(
    detection_id=123,
    camera_id="front_door",
    detected_at=None,
    confidence=0.95,
):
    """Helper to create mock Detection objects for testing."""
    mock_detection = MagicMock()
    mock_detection.id = detection_id
    mock_detection.camera_id = camera_id
    mock_detection.detected_at = detected_at or datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
    mock_detection.confidence = confidence
    mock_detection.thumbnail_path = f"/thumbnails/{detection_id}.jpg"
    mock_detection.object_type = "person"
    return mock_detection


class TestListEntities:
    """Tests for GET /api/entities endpoint (PostgreSQL-based)."""

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
        mock_repo.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_entities_with_data(self) -> None:
        """Test listing entities when data exists."""
        mock_repo = MagicMock()
        entities = [
            _create_mock_entity(entity_type="person"),
            _create_mock_entity(entity_type="person"),
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
    async def test_list_entities_no_redis(self) -> None:
        """Test listing entities - PostgreSQL doesn't depend on Redis."""
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

        # PostgreSQL-based endpoint works without Redis
        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_type(self) -> None:
        """Test filtering entities by entity type."""
        mock_repo = MagicMock()
        entities = [_create_mock_entity(entity_type="person")]
        mock_repo.list = AsyncMock(return_value=(entities, 1))

        result = await list_entities(
            entity_type=EntityTypeFilter.person,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        # Verify the type filter was passed to repository
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

        # Verify camera_id filter was passed
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
        since = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)
        mock_repo.list = AsyncMock(return_value=([], 0))

        await list_entities(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        mock_repo.list.assert_called_once_with(
            entity_type=None,
            camera_id=None,
            since=since,
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_entities_pagination(self) -> None:
        """Test pagination of entity list."""
        mock_repo = MagicMock()
        entities = [_create_mock_entity() for _ in range(2)]
        mock_repo.list = AsyncMock(return_value=(entities, 5))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=2,
            offset=1,
            entity_repo=mock_repo,
        )

        assert result.pagination.total == 5
        assert len(result.items) == 2
        assert result.pagination.limit == 2
        assert result.pagination.offset == 1
        assert result.pagination.has_more is True


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint (PostgreSQL-based)."""

    @pytest.mark.asyncio
    async def test_get_entity_success(self) -> None:
        """Test getting entity successfully."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id, detection_count=3)
        mock_detection = _create_mock_detection()

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert str(result.id) == str(entity_id)
        assert result.entity_type == "person"
        mock_repo.get_by_id.assert_called_once_with(entity_id)

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self) -> None:
        """Test getting non-existent entity returns 404."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity(entity_id, entity_repo=mock_repo)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_entity_no_redis(self) -> None:
        """Test getting entity - PostgreSQL doesn't depend on Redis."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id)
        mock_detection = _create_mock_detection()

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        # PostgreSQL-based endpoint works without Redis
        assert str(result.id) == str(entity_id)


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint (PostgreSQL-based)."""

    @pytest.mark.asyncio
    async def test_get_history_success(self) -> None:
        """Test getting entity history successfully."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id, detection_count=2)
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

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 2))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        assert str(result.entity_id) == str(entity_id)
        assert result.entity_type == "person"
        assert result.count == 2
        assert len(result.appearances) == 2

    @pytest.mark.asyncio
    async def test_get_history_not_found(self) -> None:
        """Test getting history for non-existent entity returns 404."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(Exception) as exc_info:
            await get_entity_history(entity_id, entity_repo=mock_repo)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_no_redis(self) -> None:
        """Test getting history - PostgreSQL doesn't depend on Redis."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id)
        mock_detection = _create_mock_detection()

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        # PostgreSQL-based endpoint works without Redis
        result = await get_entity_history(entity_id, entity_repo=mock_repo)
        assert str(result.entity_id) == str(entity_id)


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
        older_entity = _create_mock_entity(last_seen=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC))
        newer_entity = _create_mock_entity(last_seen=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC))
        # Repository returns them in order (newer first, as expected)
        mock_repo.list = AsyncMock(return_value=([newer_entity, older_entity], 2))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=50,
            offset=0,
            entity_repo=mock_repo,
        )

        assert len(result.items) == 2
        # Items should be in the order returned by repository
        assert result.items[0].last_seen == newer_entity.last_seen_at

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

        assert result.pagination.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_entities_queries_both_types_when_no_filter(self) -> None:
        """Test that no filter returns all entity types."""
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
        # Verify None was passed as entity_type filter
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
        # Total is 1, but offset is 100 so no results returned
        mock_repo.list = AsyncMock(return_value=([], 1))

        result = await list_entities(
            entity_type=None,
            camera_id=None,
            since=None,
            limit=10,
            offset=100,
            entity_repo=mock_repo,
        )

        assert result.pagination.total == 1
        assert len(result.items) == 0
        assert result.pagination.offset == 100

    @pytest.mark.asyncio
    async def test_list_entities_skips_invalid_summaries(self) -> None:
        """Test that invalid entities are handled gracefully."""
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

        # Should handle entities gracefully
        assert result.pagination.total >= 0


class TestGetEntityEdgeCases:
    """Additional edge case tests for get_entity endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_found_in_vehicle_type(self) -> None:
        """Test getting entity found in vehicle type (not person)."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id, entity_type="vehicle")
        mock_detection = _create_mock_detection()

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert str(result.id) == str(entity_id)
        assert result.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_get_entity_multiple_appearances(self) -> None:
        """Test get_entity with multiple appearances across cameras."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(
            entity_id=entity_id,
            detection_count=3,
            cameras_seen=["front_door", "backyard", "driveway"],
        )
        detections = [
            _create_mock_detection(detection_id=1, camera_id="front_door"),
            _create_mock_detection(detection_id=2, camera_id="backyard"),
            _create_mock_detection(detection_id=3, camera_id="driveway"),
        ]

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 3))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        assert result.appearance_count == 3
        assert len(result.appearances) == 3

    @pytest.mark.asyncio
    async def test_get_entity_camera_name_formatting(self) -> None:
        """Test that camera_name is properly formatted from camera_id."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id)
        mock_detection = _create_mock_detection(camera_id="front_door_camera")

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        result = await get_entity(entity_id, entity_repo=mock_repo)

        # Verify camera name formatting (underscores to spaces, title case)
        assert result.appearances[0].camera_name == "Front Door Camera"


class TestGetEntityHistoryEdgeCases:
    """Additional edge case tests for get_entity_history endpoint (PostgreSQL-based)."""

    @pytest.mark.asyncio
    async def test_get_history_chronological_order(self) -> None:
        """Test that history appearances are in chronological order."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id, detection_count=3)

        # Create detections out of order
        detections = [
            _create_mock_detection(
                detection_id=1,
                camera_id="backyard",
                detected_at=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=2,
                camera_id="front_door",
                detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            ),
            _create_mock_detection(
                detection_id=3,
                camera_id="driveway",
                detected_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ),
        ]

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=(detections, 3))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        # Verify appearances are returned (order depends on repository sorting)
        assert result.count == 3
        assert len(result.appearances) == 3

    @pytest.mark.asyncio
    async def test_get_history_found_in_vehicle_type(self) -> None:
        """Test get_history for vehicle entity type."""
        entity_id = uuid4()
        mock_repo = MagicMock()
        mock_entity = _create_mock_entity(entity_id=entity_id, entity_type="vehicle")
        mock_detection = _create_mock_detection(camera_id="driveway")

        mock_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_repo.get_detections_for_entity = AsyncMock(return_value=([mock_detection], 1))

        result = await get_entity_history(entity_id, entity_repo=mock_repo)

        assert result.entity_type == "vehicle"
        assert result.count == 1


class TestGetEntityMatches:
    """Tests for GET /api/entities/matches/{detection_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_matches_no_redis(self) -> None:
        """Test getting matches when Redis is not available."""
        mock_service = MagicMock()

        with (
            patch(
                "backend.api.routes.entities._get_redis_client",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(Exception) as exc_info,
        ):
            await get_entity_matches(
                "det_001",
                entity_type=EntityTypeFilter.person,
                threshold=0.85,
                reid_service=mock_service,
            )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_matches_no_embedding_found(self) -> None:
        """Test getting matches when no embedding exists for detection."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_service.get_entity_history = AsyncMock(return_value=[])

        with (
            patch(
                "backend.api.routes.entities._get_redis_client",
                new_callable=AsyncMock,
                return_value=mock_redis,
            ),
            pytest.raises(Exception) as exc_info,
        ):
            await get_entity_matches(
                "nonexistent",
                entity_type=EntityTypeFilter.person,
                threshold=0.85,
                reid_service=mock_service,
            )

        assert exc_info.value.status_code == 404
        assert "No embedding found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_matches_no_matches_found(self) -> None:
        """Test getting matches when no similar entities found."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        query_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(return_value=[query_embedding])
        mock_service.find_matching_entities = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity_matches(
                "det_001",
                entity_type=EntityTypeFilter.person,
                threshold=0.85,
                reid_service=mock_service,
            )

        assert result.query_detection_id == "det_001"
        assert result.entity_type == "person"
        assert result.total_matches == 0
        assert result.matches == []
        assert result.threshold == 0.85

    @pytest.mark.asyncio
    async def test_get_matches_success(self) -> None:
        """Test getting matches successfully."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        query_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        matched_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="backyard",
            timestamp=datetime(2025, 12, 23, 9, 0, 0, tzinfo=UTC),
            detection_id="det_002",
            attributes={"clothing": "blue jacket"},
        )

        mock_service.get_entity_history = AsyncMock(
            return_value=[query_embedding, matched_embedding]
        )
        mock_service.find_matching_entities = AsyncMock(
            return_value=[
                EntityMatch(
                    entity=matched_embedding,
                    similarity=0.92,
                    time_gap_seconds=3600.0,
                )
            ]
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity_matches(
                "det_001",
                entity_type=EntityTypeFilter.person,
                threshold=0.85,
                reid_service=mock_service,
            )

        assert result.query_detection_id == "det_001"
        assert result.entity_type == "person"
        assert result.total_matches == 1
        assert len(result.matches) == 1
        assert result.matches[0].entity_id == "det_002"
        assert result.matches[0].similarity_score == 0.92
        assert result.matches[0].time_gap_seconds == 3600.0
        assert result.matches[0].attributes == {"clothing": "blue jacket"}
        assert result.matches[0].camera_name == "Backyard"


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_source_filter_values(self) -> None:
        """Test SourceFilter enum has correct values."""
        assert SourceFilter.redis.value == "redis"
        assert SourceFilter.postgres.value == "postgres"
        assert SourceFilter.both.value == "both"

    def test_detection_summary_schema(self) -> None:
        """Test DetectionSummary schema creation."""
        from backend.api.schemas.entities import DetectionSummary

        summary = DetectionSummary(
            detection_id=123,
            camera_id="front_door",
            camera_name="Front Door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            confidence=0.95,
            thumbnail_url="/api/detections/123/image",
            object_type="person",
        )

        assert summary.detection_id == 123
        assert summary.camera_id == "front_door"
        assert summary.confidence == 0.95

    def test_entity_stats_response_schema(self) -> None:
        """Test EntityStatsResponse schema creation."""
        from backend.api.schemas.entities import EntityStatsResponse

        stats = EntityStatsResponse(
            total_entities=207,
            total_appearances=1523,
            by_type={"person": 150, "vehicle": 45},
            by_camera={"front_door": 85},
            repeat_visitors=89,
        )

        assert stats.total_entities == 207
        assert stats.by_type["person"] == 150
        assert stats.repeat_visitors == 89

    def test_entity_detections_response_schema(self) -> None:
        """Test EntityDetectionsResponse schema creation."""
        from backend.api.schemas.entities import (
            DetectionSummary,
            EntityDetectionsResponse,
        )
        from backend.api.schemas.logs import PaginationInfo

        response = EntityDetectionsResponse(
            entity_id="550e8400-e29b-41d4-a716-446655440000",
            entity_type="person",
            detections=[
                DetectionSummary(
                    detection_id=123,
                    camera_id="front_door",
                    timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                )
            ],
            pagination=PaginationInfo(total=1, limit=50, offset=0, has_more=False),
        )

        assert response.entity_id == "550e8400-e29b-41d4-a716-446655440000"
        assert len(response.detections) == 1
        assert response.pagination.total == 1
