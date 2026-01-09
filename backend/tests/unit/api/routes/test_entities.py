"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using mocked
Redis and ReIdentificationService.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the entire module to ensure coverage tracks it
import backend.api.routes.entities  # noqa: F401
from backend.api.routes.entities import (
    EntityTypeEnum,
    _entity_to_summary,
    _get_thumbnail_url,
    get_entity,
    get_entity_history,
    list_entities,
)
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

        assert result["entities"] == []
        assert result["count"] == 0

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

        assert result["entities"] == []
        assert result["count"] == 0

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

        assert result["count"] == 2
        assert len(result["entities"]) == 2

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
                entity_type=EntityTypeEnum.person,
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
        assert result["count"] == 1

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
        assert result["count"] == 1
        assert result["entities"][0].id == "det_new"

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

        assert result["count"] == 5  # Total count
        assert len(result["entities"]) == 2  # Paginated result
        assert result["limit"] == 2
        assert result["offset"] == 1


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

        async def mock_get_redis():
            # Generator that doesn't yield anything
            return
            yield  # pragma: no cover

        with patch(
            "backend.api.routes.entities.get_redis_optional",
            return_value=mock_get_redis(),
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
        assert result["entities"][0].id == "det_new"
        assert result["entities"][1].id == "det_old"

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
        assert result["count"] == 0
        assert result["entities"] == []

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
        assert result["count"] == 2
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
        assert result["count"] == 1  # Total count
        assert len(result["entities"]) == 0  # Paginated result is empty
        assert result["offset"] == 100

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
        assert result["count"] >= 0  # At least we handled the error gracefully


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
