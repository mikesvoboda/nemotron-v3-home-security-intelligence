"""Unit tests for entities API routes.

Tests the entity re-identification tracking endpoints using mocked
Redis and ReIdentificationService.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.entities import (
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
                entity_type="person",
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
