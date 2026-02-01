"""Unit tests for Re-ID similarity search API routes (NEM-4932).

Tests the Re-ID similarity search endpoints for finding similar entities
based on embedding vectors.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.reid import (
    _get_thumbnail_url,
    find_similar_by_detection,
    search_similar_entities,
)
from backend.api.schemas.reid import SimilaritySearchRequest
from backend.services.hybrid_entity_storage import HybridEntityMatch
from backend.services.reid_service import EntityEmbedding


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


class TestSearchSimilarEntities:
    """Tests for POST /api/reid/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_matches(self) -> None:
        """Test searching for similar entities returns matches."""
        mock_storage = MagicMock()

        # Create test matches
        matches = [
            HybridEntityMatch(
                entity_id="entity_001",
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                detection_id="det_001",
                attributes={"clothing": "blue jacket"},
                similarity=0.92,
                time_gap_seconds=3600.0,
                source="redis",
            ),
            HybridEntityMatch(
                entity_id="entity_002",
                entity_type="person",
                embedding=[0.2] * 768,
                camera_id="backyard",
                timestamp=datetime(2025, 12, 23, 8, 0, 0, tzinfo=UTC),
                detection_id="det_002",
                attributes={},
                similarity=0.88,
                time_gap_seconds=7200.0,
                source="postgresql",
            ),
        ]

        mock_storage.find_matches = AsyncMock(return_value=matches)

        request = SimilaritySearchRequest(
            embedding=[0.1] * 768,
            entity_type="person",
            threshold=0.85,
            limit=10,
            include_historical=True,
        )

        result = await search_similar_entities(
            request=request,
            hybrid_storage=mock_storage,
        )

        assert result.total_matches == 2
        assert len(result.matches) == 2
        assert result.threshold == 0.85
        assert result.entity_type == "person"
        assert result.include_historical is True

        # Check first match
        assert result.matches[0].entity_id == "entity_001"
        assert result.matches[0].similarity == 0.92
        assert result.matches[0].source == "redis"
        assert result.matches[0].thumbnail_url == "/api/detections/det_001/image"

    @pytest.mark.asyncio
    async def test_search_with_limit(self) -> None:
        """Test searching with a limit returns at most that many results."""
        mock_storage = MagicMock()

        # Create 5 matches
        matches = [
            HybridEntityMatch(
                entity_id=f"entity_{i:03d}",
                entity_type="person",
                embedding=[0.1] * 768,
                camera_id="front_door",
                timestamp=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
                detection_id=f"det_{i:03d}",
                attributes={},
                similarity=0.90 - (i * 0.01),
                time_gap_seconds=float(i * 100),
                source="redis",
            )
            for i in range(5)
        ]

        mock_storage.find_matches = AsyncMock(return_value=matches)

        request = SimilaritySearchRequest(
            embedding=[0.1] * 768,
            entity_type="person",
            threshold=0.80,
            limit=3,  # Request only 3
            include_historical=False,
        )

        result = await search_similar_entities(
            request=request,
            hybrid_storage=mock_storage,
        )

        assert result.total_matches == 5  # Total found
        assert len(result.matches) == 3  # Limited to 3

    @pytest.mark.asyncio
    async def test_search_no_matches(self) -> None:
        """Test searching when no matches are found."""
        mock_storage = MagicMock()
        mock_storage.find_matches = AsyncMock(return_value=[])

        request = SimilaritySearchRequest(
            embedding=[0.1] * 768,
            entity_type="vehicle",
            threshold=0.95,
        )

        result = await search_similar_entities(
            request=request,
            hybrid_storage=mock_storage,
        )

        assert result.total_matches == 0
        assert len(result.matches) == 0
        assert result.entity_type == "vehicle"

    @pytest.mark.asyncio
    async def test_search_excludes_detection_id(self) -> None:
        """Test that exclude_detection_id is passed to find_matches."""
        mock_storage = MagicMock()
        mock_storage.find_matches = AsyncMock(return_value=[])

        request = SimilaritySearchRequest(
            embedding=[0.1] * 768,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_exclude",
        )

        await search_similar_entities(
            request=request,
            hybrid_storage=mock_storage,
        )

        mock_storage.find_matches.assert_called_once_with(
            embedding=[0.1] * 768,
            entity_type="person",
            threshold=0.85,
            exclude_detection_id="det_exclude",
            include_historical=True,
        )

    @pytest.mark.asyncio
    async def test_search_handles_error(self) -> None:
        """Test searching handles errors gracefully."""
        mock_storage = MagicMock()
        mock_storage.find_matches = AsyncMock(side_effect=Exception("Database error"))

        request = SimilaritySearchRequest(
            embedding=[0.1] * 768,
            entity_type="person",
        )

        with pytest.raises(Exception) as exc_info:
            await search_similar_entities(
                request=request,
                hybrid_storage=mock_storage,
            )

        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)


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
            embedding=[0.1] * 768,
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
                embedding=[0.2] * 768,
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


class TestSimilaritySearchSchemas:
    """Tests for Re-ID similarity search schemas."""

    def test_search_request_defaults(self) -> None:
        """Test SimilaritySearchRequest has correct defaults."""
        request = SimilaritySearchRequest(embedding=[0.1] * 768)

        assert request.entity_type == "person"
        assert request.threshold == 0.85
        assert request.limit == 10
        assert request.include_historical is True
        assert request.exclude_detection_id is None

    def test_search_request_validation(self) -> None:
        """Test SimilaritySearchRequest validates inputs."""
        # Threshold out of range
        with pytest.raises(ValueError):
            SimilaritySearchRequest(embedding=[0.1], threshold=1.5)

        # Limit out of range
        with pytest.raises(ValueError):
            SimilaritySearchRequest(embedding=[0.1], limit=0)

        # Invalid entity type
        with pytest.raises(ValueError):
            SimilaritySearchRequest(embedding=[0.1], entity_type="invalid")
