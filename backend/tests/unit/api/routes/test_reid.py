"""Unit tests for Re-ID similarity search API routes (NEM-4932).

Tests the Re-ID similarity search endpoints for finding similar entities
based on embedding vectors.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.api.routes.reid as reid_routes
import backend.api.schemas.reid as reid_schemas
from backend.api.routes.reid import (
    _get_thumbnail_url,
    find_similar_by_detection,
)
from backend.api.routes.reid import (
    router as reid_router,
)
from backend.services.hybrid_entity_storage import HybridEntityMatch
from backend.services.reid_service import EntityEmbedding


class TestReidSearchRetired:
    """Ruling 236 / B3.1: POST /api/reid/search and SimilaritySearchRequest are retired."""

    def test_post_reid_search_route_is_retired(self) -> None:
        routes = [
            (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()))))
            for route in reid_router.routes
        ]
        assert ("/api/reid/search", ("POST",)) not in routes
        assert not hasattr(reid_routes, "search_similar_entities")
        assert not hasattr(reid_schemas, "SimilaritySearchRequest")


class TestThumbnailUrl:
    """Tests for _get_thumbnail_url helper function."""

    def test_none_detection_id(self) -> None:
        """Test thumbnail URL generation for None detection ID."""
        url = _get_thumbnail_url(None)
        assert url is None

    def test_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for integer detection IDs."""
        url = _get_thumbnail_url("123")
        assert url == "/api/detections/123/image"

    def test_non_integer_detection_id(self) -> None:
        """Test thumbnail URL generation for non-integer detection IDs."""
        url = _get_thumbnail_url("det_abc123")
        assert url == "/api/detections/det_abc123/image"


class TestFindSimilarByDetection:
    """Tests for GET /api/reid/similar/{detection_id} endpoint."""

    @pytest.mark.asyncio
    async def test_find_similar_success(self) -> None:
        """Test finding similar entities for a detection."""
        mock_storage = MagicMock()
        mock_reid = MagicMock()

        # Create test embedding for the detection
        query_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 512,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            detection_id="det_query",
            attributes={},
        )

        # Mock get_entity_history to return the query embedding
        mock_reid.get_entity_history = AsyncMock(return_value=[query_embedding])

        # Create test matches
        matches = [
            HybridEntityMatch(
                entity_id="entity_001",
                entity_type="person",
                embedding=[0.2] * 512,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 8, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={},
                similarity=0.90,
                time_gap_seconds=7200.0,
                source="redis",
            ),
        ]
        mock_storage.find_matches = AsyncMock(return_value=matches)

        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis._ensure_connected.return_value = mock_redis

        with patch(
            "backend.api.routes.reid._get_redis_client",
            return_value=mock_redis,
            autospec=True,
        ):
            result = await find_similar_by_detection(
                detection_id="det_query",
                entity_type="person",
                threshold=0.85,
                limit=10,
                include_historical=True,
                reid_service=mock_reid,
                hybrid_storage=mock_storage,
            )

        assert result.total_matches == 1
        assert len(result.matches) == 1
        assert result.matches[0].entity_id == "entity_001"
        assert result.threshold == 0.85

    @pytest.mark.asyncio
    async def test_find_similar_detection_not_found(self) -> None:
        """Test finding similar entities when detection has no embedding."""
        mock_storage = MagicMock()
        mock_reid = MagicMock()

        # Mock get_entity_history to return empty (no embedding for this detection)
        mock_reid.get_entity_history = AsyncMock(return_value=[])

        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis._ensure_connected.return_value = mock_redis

        with patch(
            "backend.api.routes.reid._get_redis_client",
            return_value=mock_redis,
            autospec=True,
        ):
            with pytest.raises(Exception) as exc_info:
                await find_similar_by_detection(
                    detection_id="det_nonexistent",
                    entity_type="person",
                    threshold=0.85,
                    limit=10,
                    include_historical=True,
                    reid_service=mock_reid,
                    hybrid_storage=mock_storage,
                )

        assert exc_info.value.status_code == 404
        assert "No embedding found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_find_similar_redis_unavailable(self) -> None:
        """Test finding similar entities when Redis is unavailable."""
        mock_storage = MagicMock()
        mock_reid = MagicMock()

        with patch(
            "backend.api.routes.reid._get_redis_client",
            return_value=None,
            autospec=True,
        ):
            with pytest.raises(Exception) as exc_info:
                await find_similar_by_detection(
                    detection_id="det_query",
                    entity_type="person",
                    threshold=0.85,
                    limit=10,
                    include_historical=True,
                    reid_service=mock_reid,
                    hybrid_storage=mock_storage,
                )

        assert exc_info.value.status_code == 503
        assert "Redis service unavailable" in str(exc_info.value.detail)
