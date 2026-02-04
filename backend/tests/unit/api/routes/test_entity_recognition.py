"""Unit tests for entity recognition summary API routes.

Tests cover:
- GET /api/summaries/entities - Get entity recognition stats for summary time window
- Response format validation
- Error handling

Implements NEM-5395: Entity Recognition Summary - API Endpoint

TDD: Tests written BEFORE implementation
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.entity_recognition import router
from backend.core.database import get_db
from backend.services.entity_recognition_service import (
    EntityRecognitionStats,
    PersonStats,
    VehicleStats,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_cache_service() -> MagicMock:
    """Create a mock cache service."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)  # Cache miss by default
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_cache_service: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    async def override_get_cache():
        yield mock_cache_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_get_cache

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_entity_stats() -> EntityRecognitionStats:
    """Create mock entity recognition stats."""
    return EntityRecognitionStats(
        persons=PersonStats(known=3, unknown=2),
        vehicles=VehicleStats(known=1, unknown=4),
        window_start=datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC),
        window_end=datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC),
    )


# =============================================================================
# GET /api/summaries/entities Tests
# =============================================================================


class TestGetEntityRecognitionStats:
    """Tests for GET /api/summaries/entities endpoint."""

    def test_returns_entity_stats(
        self,
        client: TestClient,
        mock_entity_stats: EntityRecognitionStats,
    ) -> None:
        """Test getting entity recognition stats."""
        with patch("backend.api.routes.entity_recognition.EntityRecognitionService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_hourly_stats = AsyncMock(return_value=mock_entity_stats)
            MockService.return_value = mock_service

            response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        data = response.json()

        # Verify persons stats
        assert data["persons"]["known"] == 3
        assert data["persons"]["unknown"] == 2
        assert data["persons"]["total"] == 5
        assert data["persons"]["breakdown"] == "3 known, 2 unknown"

        # Verify vehicles stats
        assert data["vehicles"]["known"] == 1
        assert data["vehicles"]["unknown"] == 4
        assert data["vehicles"]["total"] == 5
        assert data["vehicles"]["breakdown"] == "1 known, 4 unknown"

        # Verify time window
        assert data["window_start"] == "2026-02-03T10:00:00+00:00"
        assert data["window_end"] == "2026-02-03T11:00:00+00:00"

    def test_returns_empty_stats(
        self,
        client: TestClient,
    ) -> None:
        """Test response when no entities are detected."""
        empty_stats = EntityRecognitionStats(
            persons=PersonStats(known=0, unknown=0),
            vehicles=VehicleStats(known=0, unknown=0),
            window_start=datetime(2026, 2, 3, 10, 0, 0, tzinfo=UTC),
            window_end=datetime(2026, 2, 3, 11, 0, 0, tzinfo=UTC),
        )

        with patch("backend.api.routes.entity_recognition.EntityRecognitionService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_hourly_stats = AsyncMock(return_value=empty_stats)
            MockService.return_value = mock_service

            response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        data = response.json()

        assert data["persons"]["total"] == 0
        assert data["persons"]["breakdown"] == "No persons detected"
        assert data["vehicles"]["total"] == 0
        assert data["vehicles"]["breakdown"] == "No vehicles detected"

    def test_returns_cached_response(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cached response is returned when available."""
        cached_data = {
            "persons": {
                "known": 5,
                "unknown": 3,
                "total": 8,
                "breakdown": "5 known, 3 unknown",
            },
            "vehicles": {
                "known": 2,
                "unknown": 1,
                "total": 3,
                "breakdown": "2 known, 1 unknown",
            },
            "window_start": "2026-02-03T10:00:00+00:00",
            "window_end": "2026-02-03T11:00:00+00:00",
        }
        mock_cache_service.get = AsyncMock(return_value=cached_data)

        response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        data = response.json()
        assert data["persons"]["known"] == 5
        assert data["vehicles"]["known"] == 2

    def test_falls_back_to_db_on_cache_error(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_entity_stats: EntityRecognitionStats,
    ) -> None:
        """Test that database is queried when cache read fails."""
        mock_cache_service.get = AsyncMock(side_effect=Exception("Redis connection error"))

        with patch("backend.api.routes.entity_recognition.EntityRecognitionService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_hourly_stats = AsyncMock(return_value=mock_entity_stats)
            MockService.return_value = mock_service

            response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        data = response.json()
        assert data["persons"]["known"] == 3

    def test_caches_result_on_miss(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_entity_stats: EntityRecognitionStats,
    ) -> None:
        """Test that result is cached after database query."""
        with patch("backend.api.routes.entity_recognition.EntityRecognitionService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_hourly_stats = AsyncMock(return_value=mock_entity_stats)
            MockService.return_value = mock_service

            response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "summaries:entities"
        assert call_args[1]["ttl"] == 300  # 5 minute TTL

    def test_cache_write_failure_does_not_break_response(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_entity_stats: EntityRecognitionStats,
    ) -> None:
        """Test that response is returned even if cache write fails."""
        mock_cache_service.set = AsyncMock(side_effect=Exception("Redis write error"))

        with patch("backend.api.routes.entity_recognition.EntityRecognitionService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_hourly_stats = AsyncMock(return_value=mock_entity_stats)
            MockService.return_value = mock_service

            response = client.get("/api/summaries/entities")

        assert response.status_code == 200
        data = response.json()
        assert data["persons"]["known"] == 3


# =============================================================================
# OpenAPI Documentation Tests
# =============================================================================


class TestEntityRecognitionOpenAPI:
    """Tests for entity recognition routes OpenAPI documentation."""

    def test_routes_have_tags(self, client: TestClient) -> None:
        """Test that routes are tagged for OpenAPI grouping."""
        for route in router.routes:
            if hasattr(route, "tags"):
                assert "summaries" in route.tags

    def test_routes_have_response_models(self, client: TestClient) -> None:
        """Test that routes have response models defined."""
        for route in router.routes:
            if hasattr(route, "response_model"):
                assert route.response_model is not None

    def test_routes_have_correct_prefix(self, client: TestClient) -> None:
        """Test that router has correct prefix."""
        assert router.prefix == "/api/summaries"
