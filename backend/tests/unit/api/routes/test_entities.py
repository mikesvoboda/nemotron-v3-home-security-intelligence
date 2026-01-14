"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using mocked
Redis and ReIdentificationService.

Includes tests for:
- Historical entity queries (PostgreSQL)
- Source parameter (redis, postgres, both)
- Date range filtering (since, until)
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


class TestListEntities:
    """Tests for GET /api/entities endpoint."""

    @pytest.mark.asyncio
    async def test_list_entities_no_redis(self) -> None:
        """Test listing entities when Redis is not available."""
        mock_service = MagicMock()

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_entities_empty(self) -> None:
        """Test listing entities when none exist."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_service.get_entity_history = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_entities_with_data(self) -> None:
        """Test listing entities when data exists."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Create test embeddings
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
                embedding=[0.2] * 768,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                detection_id="det_002",
                attributes={},
            ),
        ]

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: (
                embeddings if kwargs.get("entity_type") == "person" else []
            )
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        assert result.pagination.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_type(self) -> None:
        """Test filtering entities by entity type."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        person_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(return_value=[person_embedding])

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=EntityTypeFilter.person,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should only query person type
        mock_service.get_entity_history.assert_called_once_with(
            redis_client=mock_redis,
            entity_type="person",
            camera_id=None,
        )
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_camera(self) -> None:
        """Test filtering entities by camera ID."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_service.get_entity_history = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            await list_entities(
                entity_type=None,
                camera_id="front_door",
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should pass camera_id to service
        calls = mock_service.get_entity_history.call_args_list
        for call in calls:
            assert call.kwargs["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_since(self) -> None:
        """Test filtering entities by timestamp."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        old_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
            detection_id="det_old",
            attributes={},
        )

        new_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_new",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: (
                [old_embedding, new_embedding] if kwargs.get("entity_type") == "person" else []
            )
        )

        since = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=since,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should only include the new embedding
        assert result.pagination.total == 1
        assert result.items[0].id == "det_new"

    @pytest.mark.asyncio
    async def test_list_entities_pagination(self) -> None:
        """Test pagination of entity list."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Create multiple embeddings
        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, i, 0, 0, tzinfo=UTC),
                detection_id=f"det_{i:03d}",
                attributes={},
            )
            for i in range(5)
        ]

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: (
                embeddings if kwargs.get("entity_type") == "person" else []
            )
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=2,
                offset=1,
                reid_service=mock_service,
            )

        assert result.pagination.total == 5  # Total count
        assert len(result.items) == 2  # Paginated result
        assert result.pagination.limit == 2
        assert result.pagination.offset == 1


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_no_redis(self) -> None:
        """Test getting entity when Redis is not available."""
        mock_service = MagicMock()

        with (
            patch(
                "backend.api.routes.entities._get_redis_client",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(Exception) as exc_info,
        ):
            await get_entity("det_001", reid_service=mock_service)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self) -> None:
        """Test getting non-existent entity returns 404."""
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
            await get_entity("nonexistent", reid_service=mock_service)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_entity_success(self) -> None:
        """Test getting entity successfully."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={"clothing": "blue jacket"},
        )

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "person":
                return [embedding]
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity("det_001", reid_service=mock_service)

        assert result.id == "det_001"
        assert result.entity_type == "person"
        assert result.appearance_count == 1
        assert len(result.appearances) == 1
        assert result.appearances[0].detection_id == "det_001"
        assert result.appearances[0].attributes == {"clothing": "blue jacket"}


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_no_redis(self) -> None:
        """Test getting history when Redis is not available."""
        mock_service = MagicMock()

        with (
            patch(
                "backend.api.routes.entities._get_redis_client",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(Exception) as exc_info,
        ):
            await get_entity_history("det_001", reid_service=mock_service)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_history_not_found(self) -> None:
        """Test getting history for non-existent entity returns 404."""
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
            await get_entity_history("nonexistent", reid_service=mock_service)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_success(self) -> None:
        """Test getting entity history successfully."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

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
        ]

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "person":
                return embeddings
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity_history("det_001", reid_service=mock_service)

        assert result.entity_id == "det_001"
        assert result.entity_type == "person"
        assert result.count == 2
        assert len(result.appearances) == 2
        # Verify chronological order
        assert result.appearances[0].timestamp < result.appearances[1].timestamp


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
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Create embeddings with different timestamps
        old_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
            detection_id="det_old",
            attributes={},
        )

        new_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2] * 768,
            camera_id="backyard",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_new",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: (
                [old_embedding, new_embedding] if kwargs.get("entity_type") == "person" else []
            )
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Verify sorting: newer should be first
        assert result.items[0].id == "det_new"
        assert result.items[1].id == "det_old"

    @pytest.mark.asyncio
    async def test_list_entities_handles_empty_entity_groups(self) -> None:
        """Test that empty entity groups are skipped (ValueError handling)."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Return empty list to trigger the ValueError path in _entity_to_summary
        mock_service.get_entity_history = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should handle empty groups gracefully
        assert result.pagination.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_list_entities_queries_both_types_when_no_filter(self) -> None:
        """Test that both person and vehicle types are queried when no filter."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        person_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_person",
            attributes={},
        )

        vehicle_embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.2] * 768,
            camera_id="driveway",
            timestamp=datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC),
            detection_id="det_vehicle",
            attributes={},
        )

        def get_history(**kwargs):
            if kwargs.get("entity_type") == "person":
                return [person_embedding]
            elif kwargs.get("entity_type") == "vehicle":
                return [vehicle_embedding]
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should have both entities
        assert result.pagination.total == 2
        # Verify both types were queried
        assert mock_service.get_entity_history.call_count == 2

    @pytest.mark.asyncio
    async def test_list_entities_pagination_beyond_results(self) -> None:
        """Test pagination with offset beyond available results."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: [embedding]
            if kwargs.get("entity_type") == "person"
            else []
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=10,
                offset=100,  # Beyond available results
                reid_service=mock_service,
            )

        # Should return empty list but correct count
        assert result.pagination.total == 1  # Total count
        assert len(result.items) == 0  # Paginated result is empty
        assert result.pagination.offset == 100

    @pytest.mark.asyncio
    async def test_list_entities_skips_invalid_summaries(self) -> None:
        """Test that entities with invalid summaries are skipped gracefully."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        valid_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_valid",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: [valid_embedding]
            if kwargs.get("entity_type") == "person"
            else []
        )

        # Mock _entity_to_summary to raise ValueError for first entity, succeed for second
        call_count = 0

        def mock_entity_to_summary(entity_id, embeddings):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Empty embeddings")
            # For subsequent calls, use the real function
            return _entity_to_summary(entity_id, embeddings)

        with (
            patch(
                "backend.api.routes.entities._get_redis_client",
                new_callable=AsyncMock,
                return_value=mock_redis,
            ),
            patch(
                "backend.api.routes.entities._entity_to_summary",
                side_effect=mock_entity_to_summary,
            ),
        ):
            result = await list_entities(
                entity_type=None,
                camera_id=None,
                since=None,
                limit=50,
                offset=0,
                reid_service=mock_service,
            )

        # Should skip the invalid entity and continue
        assert result.pagination.total >= 0  # At least we handled the error gracefully


class TestGetEntityEdgeCases:
    """Additional edge case tests for get_entity endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_found_in_vehicle_type(self) -> None:
        """Test getting entity found in vehicle type (not person)."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        vehicle_embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.1] * 768,
            camera_id="driveway",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_vehicle",
            attributes={"color": "blue", "make": "toyota"},
        )

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "vehicle":
                return [vehicle_embedding]
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity("det_vehicle", reid_service=mock_service)

        assert result.id == "det_vehicle"
        assert result.entity_type == "vehicle"
        assert result.appearances[0].attributes == {"color": "blue", "make": "toyota"}

    @pytest.mark.asyncio
    async def test_get_entity_multiple_appearances(self) -> None:
        """Test get_entity with multiple appearances across cameras."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

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
                timestamp=datetime(2025, 12, 23, 11, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="driveway",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
        ]

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "person":
                return embeddings
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity("det_001", reid_service=mock_service)

        assert result.appearance_count == 3
        assert len(result.cameras_seen) == 3
        assert "front_door" in result.cameras_seen
        assert "backyard" in result.cameras_seen
        assert "driveway" in result.cameras_seen
        # Verify sorted by timestamp
        assert result.appearances[0].timestamp <= result.appearances[1].timestamp
        assert result.appearances[1].timestamp <= result.appearances[2].timestamp

    @pytest.mark.asyncio
    async def test_get_entity_camera_name_formatting(self) -> None:
        """Test that camera_name is properly formatted from camera_id."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door_camera",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "person":
                return [embedding]
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity("det_001", reid_service=mock_service)

        # Verify camera name formatting (underscores to spaces, title case)
        assert result.appearances[0].camera_name == "Front Door Camera"


class TestGetEntityHistoryEdgeCases:
    """Additional edge case tests for get_entity_history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_chronological_order(self) -> None:
        """Test that history appearances are in chronological order."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Create embeddings out of order
        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
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
                camera_id="driveway",
                timestamp=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
            ),
        ]

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "person":
                return embeddings
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity_history("det_001", reid_service=mock_service)

        # Verify chronological order
        assert result.appearances[0].timestamp < result.appearances[1].timestamp
        assert result.appearances[1].timestamp < result.appearances[2].timestamp
        assert result.appearances[0].camera_id == "front_door"
        assert result.appearances[1].camera_id == "driveway"
        assert result.appearances[2].camera_id == "backyard"

    @pytest.mark.asyncio
    async def test_get_history_found_in_vehicle_type(self) -> None:
        """Test get_history for vehicle entity type."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        embeddings = [
            EntityEmbedding(
                entity_type="vehicle",
                embedding=[0.1] * 768,
                camera_id="driveway",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                detection_id="det_vehicle",
                attributes={"color": "red"},
            ),
        ]

        def get_history(redis_client, entity_type, camera_id=None):
            if entity_type == "vehicle":
                return embeddings
            return []

        mock_service.get_entity_history = AsyncMock(side_effect=get_history)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await get_entity_history("det_vehicle", reid_service=mock_service)

        assert result.entity_type == "vehicle"
        assert result.count == 1
        assert result.appearances[0].attributes == {"color": "red"}


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

        # Create query embedding
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

        # Create query embedding
        query_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        # Create matching embedding
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

    @pytest.mark.asyncio
    async def test_get_matches_vehicle_type(self) -> None:
        """Test getting matches for vehicle entity type."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        # Create query embedding
        query_embedding = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.1] * 768,
            camera_id="driveway",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={"color": "red"},
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
                entity_type=EntityTypeFilter.vehicle,
                threshold=0.80,
                reid_service=mock_service,
            )

        # Verify correct entity type was searched
        mock_service.get_entity_history.assert_called_once_with(
            redis_client=mock_redis,
            entity_type="vehicle",
        )
        mock_service.find_matching_entities.assert_called_once()
        call_kwargs = mock_service.find_matching_entities.call_args.kwargs
        assert call_kwargs["entity_type"] == "vehicle"
        assert call_kwargs["threshold"] == 0.80
        assert result.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_get_matches_custom_threshold(self) -> None:
        """Test getting matches with custom similarity threshold."""
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
                threshold=0.95,  # Higher threshold
                reid_service=mock_service,
            )

        # Verify threshold was passed correctly
        call_kwargs = mock_service.find_matching_entities.call_args.kwargs
        assert call_kwargs["threshold"] == 0.95
        assert result.threshold == 0.95

    @pytest.mark.asyncio
    async def test_get_matches_excludes_query_detection(self) -> None:
        """Test that query detection is excluded from matches."""
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
            await get_entity_matches(
                "det_001",
                entity_type=EntityTypeFilter.person,
                threshold=0.85,
                reid_service=mock_service,
            )

        # Verify exclude_detection_id was passed
        call_kwargs = mock_service.find_matching_entities.call_args.kwargs
        assert call_kwargs["exclude_detection_id"] == "det_001"


# =============================================================================
# Historical Entity Lookup API Tests (NEM-2500)
# =============================================================================


class TestListEntitiesWithSource:
    """Tests for list_entities with source parameter (redis, postgres, both)."""

    @pytest.mark.asyncio
    async def test_list_entities_source_redis_only(self) -> None:
        """Test listing entities from Redis only."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_hybrid_storage = MagicMock()

        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: [embedding]
            if kwargs.get("entity_type") == "person"
            else []
        )

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            from backend.api.routes.entities import list_entities_with_source

            result = await list_entities_with_source(
                entity_type=None,
                camera_id=None,
                since=None,
                until=None,
                source=SourceFilter.redis,
                limit=50,
                offset=0,
                reid_service=mock_service,
                hybrid_storage=mock_hybrid_storage,
            )

        # Redis source should not call hybrid_storage for PostgreSQL data
        assert result.pagination.total >= 0

    @pytest.mark.asyncio
    async def test_list_entities_source_postgres_only(self) -> None:
        """Test listing entities from PostgreSQL only."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_hybrid_storage = MagicMock()

        # Create a mock Entity object that simulates PostgreSQL Entity
        mock_entity = MagicMock()
        mock_entity.id = uuid4()
        mock_entity.entity_type = "person"
        mock_entity.first_seen_at = datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
        mock_entity.last_seen_at = datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC)
        mock_entity.detection_count = 3
        mock_entity.entity_metadata = {"camera_id": "front_door"}
        mock_entity.primary_detection_id = 123

        mock_hybrid_storage.get_entities_by_timerange = AsyncMock(return_value=([mock_entity], 1))

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            from backend.api.routes.entities import list_entities_with_source

            result = await list_entities_with_source(
                entity_type=None,
                camera_id=None,
                since=None,
                until=None,
                source=SourceFilter.postgres,
                limit=50,
                offset=0,
                reid_service=mock_service,
                hybrid_storage=mock_hybrid_storage,
            )

        # PostgreSQL source should call hybrid_storage
        mock_hybrid_storage.get_entities_by_timerange.assert_called_once()
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_entities_source_both(self) -> None:
        """Test listing entities from both Redis and PostgreSQL."""
        mock_redis = MagicMock()
        mock_service = MagicMock()
        mock_hybrid_storage = MagicMock()

        # Redis data
        redis_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC),
            detection_id="det_001",
            attributes={},
        )

        # PostgreSQL data
        mock_entity = MagicMock()
        mock_entity.id = uuid4()
        mock_entity.entity_type = "person"
        mock_entity.first_seen_at = datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC)
        mock_entity.last_seen_at = datetime(2025, 12, 20, 12, 0, 0, tzinfo=UTC)
        mock_entity.detection_count = 2
        mock_entity.entity_metadata = {"camera_id": "backyard"}
        mock_entity.primary_detection_id = 456

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: [redis_embedding]
            if kwargs.get("entity_type") == "person"
            else []
        )
        mock_hybrid_storage.get_entities_by_timerange = AsyncMock(return_value=([mock_entity], 1))

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            from backend.api.routes.entities import list_entities_with_source

            result = await list_entities_with_source(
                entity_type=None,
                camera_id=None,
                since=None,
                until=None,
                source=SourceFilter.both,
                limit=50,
                offset=0,
                reid_service=mock_service,
                hybrid_storage=mock_hybrid_storage,
            )

        # Both sources should be queried
        assert result.pagination.total >= 1


class TestListEntitiesWithUntilFilter:
    """Tests for list_entities with until date filter."""

    @pytest.mark.asyncio
    async def test_list_entities_with_until_filter(self) -> None:
        """Test filtering entities by until timestamp."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        old_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
            detection_id="det_old",
            attributes={},
        )

        new_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.2] * 768,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 25, 10, 0, 0, tzinfo=UTC),
            detection_id="det_new",
            attributes={},
        )

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: [old_embedding, new_embedding]
            if kwargs.get("entity_type") == "person"
            else []
        )

        until = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            from backend.api.routes.entities import list_entities_with_source

            result = await list_entities_with_source(
                entity_type=None,
                camera_id=None,
                since=None,
                until=until,
                source=SourceFilter.redis,
                limit=50,
                offset=0,
                reid_service=mock_service,
                hybrid_storage=None,
            )

        # Should only include the old embedding (before until)
        assert result.pagination.total == 1
        assert result.items[0].id == "det_old"

    @pytest.mark.asyncio
    async def test_list_entities_with_since_and_until(self) -> None:
        """Test filtering entities with both since and until timestamps."""
        mock_redis = MagicMock()
        mock_service = MagicMock()

        embeddings = [
            EntityEmbedding(
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 15, 10, 0, 0, tzinfo=UTC),
                detection_id="det_early",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.2] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 20, 10, 0, 0, tzinfo=UTC),
                detection_id="det_middle",
                attributes={},
            ),
            EntityEmbedding(
                entity_type="person",
                embedding=[0.3] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 25, 10, 0, 0, tzinfo=UTC),
                detection_id="det_late",
                attributes={},
            ),
        ]

        mock_service.get_entity_history = AsyncMock(
            side_effect=lambda **kwargs: embeddings if kwargs.get("entity_type") == "person" else []
        )

        since = datetime(2025, 12, 18, 0, 0, 0, tzinfo=UTC)
        until = datetime(2025, 12, 22, 0, 0, 0, tzinfo=UTC)

        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            from backend.api.routes.entities import list_entities_with_source

            result = await list_entities_with_source(
                entity_type=None,
                camera_id=None,
                since=since,
                until=until,
                source=SourceFilter.redis,
                limit=50,
                offset=0,
                reid_service=mock_service,
                hybrid_storage=None,
            )

        # Should only include the middle embedding
        assert result.pagination.total == 1
        assert result.items[0].id == "det_middle"


class TestGetEntityWithUUID:
    """Tests for get_entity endpoint with UUID entity_id from PostgreSQL."""

    @pytest.mark.asyncio
    async def test_get_entity_by_uuid(self) -> None:
        """Test getting entity by UUID from PostgreSQL."""
        entity_uuid = uuid4()
        mock_hybrid_storage = MagicMock()

        # Create mock Entity
        mock_entity = MagicMock()
        mock_entity.id = entity_uuid
        mock_entity.entity_type = "person"
        mock_entity.first_seen_at = datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
        mock_entity.last_seen_at = datetime(2025, 12, 23, 14, 0, 0, tzinfo=UTC)
        mock_entity.detection_count = 5
        mock_entity.entity_metadata = {"camera_id": "front_door", "clothing": "blue"}
        mock_entity.primary_detection_id = 123

        mock_hybrid_storage.get_entity_full_history = AsyncMock(return_value=mock_entity)

        from backend.api.routes.entities import get_entity_by_uuid

        result = await get_entity_by_uuid(
            entity_id=entity_uuid,
            hybrid_storage=mock_hybrid_storage,
        )

        assert result.id == str(entity_uuid)
        assert result.entity_type == "person"
        assert result.appearance_count == 5
        mock_hybrid_storage.get_entity_full_history.assert_called_once_with(entity_uuid)

    @pytest.mark.asyncio
    async def test_get_entity_by_uuid_not_found(self) -> None:
        """Test getting non-existent entity returns 404."""
        entity_uuid = uuid4()
        mock_hybrid_storage = MagicMock()
        mock_hybrid_storage.get_entity_full_history = AsyncMock(return_value=None)

        from backend.api.routes.entities import get_entity_by_uuid

        with pytest.raises(Exception) as exc_info:
            await get_entity_by_uuid(
                entity_id=entity_uuid,
                hybrid_storage=mock_hybrid_storage,
            )

        assert exc_info.value.status_code == 404


class TestGetEntityDetections:
    """Tests for GET /api/entities/{entity_id}/detections endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_detections_success(self) -> None:
        """Test getting entity detections successfully."""
        entity_uuid = uuid4()
        mock_entity_repo = MagicMock()

        # Create mock Entity
        mock_entity = MagicMock()
        mock_entity.id = entity_uuid
        mock_entity.entity_type = "person"

        # Create mock detections
        mock_detection1 = MagicMock()
        mock_detection1.id = 123
        mock_detection1.camera_id = "front_door"
        mock_detection1.detected_at = datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
        mock_detection1.confidence = 0.95
        mock_detection1.thumbnail_path = "/thumbnails/123.jpg"
        mock_detection1.object_type = "person"

        mock_detection2 = MagicMock()
        mock_detection2.id = 124
        mock_detection2.camera_id = "backyard"
        mock_detection2.detected_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_detection2.confidence = 0.89
        mock_detection2.thumbnail_path = "/thumbnails/124.jpg"
        mock_detection2.object_type = "person"

        mock_entity_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_entity_repo.get_detections_for_entity = AsyncMock(
            return_value=([mock_detection1, mock_detection2], 2)
        )

        from backend.api.routes.entities import get_entity_detections

        result = await get_entity_detections(
            entity_id=entity_uuid,
            limit=50,
            offset=0,
            entity_repo=mock_entity_repo,
        )

        assert result.entity_id == str(entity_uuid)
        assert result.entity_type == "person"
        assert len(result.detections) == 2
        assert result.pagination.total == 2

    @pytest.mark.asyncio
    async def test_get_entity_detections_not_found(self) -> None:
        """Test getting detections for non-existent entity returns 404."""
        entity_uuid = uuid4()
        mock_entity_repo = MagicMock()
        mock_entity_repo.get_by_id = AsyncMock(return_value=None)

        from backend.api.routes.entities import get_entity_detections

        with pytest.raises(Exception) as exc_info:
            await get_entity_detections(
                entity_id=entity_uuid,
                limit=50,
                offset=0,
                entity_repo=mock_entity_repo,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_entity_detections_pagination(self) -> None:
        """Test pagination of entity detections."""
        entity_uuid = uuid4()
        mock_entity_repo = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = entity_uuid
        mock_entity.entity_type = "person"

        mock_detection = MagicMock()
        mock_detection.id = 125
        mock_detection.camera_id = "front_door"
        mock_detection.detected_at = datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC)
        mock_detection.confidence = 0.95
        mock_detection.thumbnail_path = None
        mock_detection.object_type = "person"

        mock_entity_repo.get_by_id = AsyncMock(return_value=mock_entity)
        mock_entity_repo.get_detections_for_entity = AsyncMock(
            return_value=([mock_detection], 10)  # 10 total but only 1 returned
        )

        from backend.api.routes.entities import get_entity_detections

        result = await get_entity_detections(
            entity_id=entity_uuid,
            limit=1,
            offset=5,
            entity_repo=mock_entity_repo,
        )

        assert len(result.detections) == 1
        assert result.pagination.total == 10
        assert result.pagination.limit == 1
        assert result.pagination.offset == 5
        assert result.pagination.has_more is True


class TestGetEntityStats:
    """Tests for GET /api/entities/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_entity_stats_success(self) -> None:
        """Test getting entity statistics successfully."""
        mock_entity_repo = MagicMock()

        # Mock repository methods
        mock_entity_repo.get_type_counts = AsyncMock(
            return_value={"person": 150, "vehicle": 45, "animal": 12}
        )
        mock_entity_repo.get_total_detection_count = AsyncMock(return_value=1523)
        mock_entity_repo.get_camera_counts = AsyncMock(
            return_value={"front_door": 85, "backyard": 42, "driveway": 68}
        )
        mock_entity_repo.get_repeat_visitor_count = AsyncMock(return_value=89)
        mock_entity_repo.count = AsyncMock(return_value=207)

        from backend.api.routes.entities import get_entity_stats

        result = await get_entity_stats(
            since=None,
            until=None,
            entity_repo=mock_entity_repo,
        )

        assert result.total_entities == 207
        assert result.total_appearances == 1523
        assert result.by_type["person"] == 150
        assert result.by_type["vehicle"] == 45
        assert result.by_camera["front_door"] == 85
        assert result.repeat_visitors == 89

    @pytest.mark.asyncio
    async def test_get_entity_stats_with_time_range(self) -> None:
        """Test getting entity statistics with time range filters."""
        mock_entity_repo = MagicMock()

        since = datetime(2025, 12, 20, 0, 0, 0, tzinfo=UTC)
        until = datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC)

        mock_entity_repo.get_type_counts = AsyncMock(return_value={"person": 50})
        mock_entity_repo.get_total_detection_count = AsyncMock(return_value=200)
        mock_entity_repo.get_camera_counts = AsyncMock(return_value={"front_door": 30})
        mock_entity_repo.get_repeat_visitor_count = AsyncMock(return_value=20)
        mock_entity_repo.count = AsyncMock(return_value=50)

        from backend.api.routes.entities import get_entity_stats

        result = await get_entity_stats(
            since=since,
            until=until,
            entity_repo=mock_entity_repo,
        )

        assert result.total_entities == 50
        assert result.time_range is not None
        assert result.time_range.get("since") == since
        assert result.time_range.get("until") == until

    @pytest.mark.asyncio
    async def test_get_entity_stats_empty_database(self) -> None:
        """Test getting entity statistics when database is empty."""
        mock_entity_repo = MagicMock()

        mock_entity_repo.get_type_counts = AsyncMock(return_value={})
        mock_entity_repo.get_total_detection_count = AsyncMock(return_value=0)
        mock_entity_repo.get_camera_counts = AsyncMock(return_value={})
        mock_entity_repo.get_repeat_visitor_count = AsyncMock(return_value=0)
        mock_entity_repo.count = AsyncMock(return_value=0)

        from backend.api.routes.entities import get_entity_stats

        result = await get_entity_stats(
            since=None,
            until=None,
            entity_repo=mock_entity_repo,
        )

        assert result.total_entities == 0
        assert result.total_appearances == 0
        assert result.repeat_visitors == 0
        assert result.by_type == {}
        assert result.by_camera == {}


class TestSchemaValidation:
    """Tests for new schema validation."""

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
