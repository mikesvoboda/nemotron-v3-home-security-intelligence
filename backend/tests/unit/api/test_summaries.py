"""Unit tests for summaries API routes.

Tests cover:
- GET /api/summaries/latest - Get both hourly and daily summaries
- GET /api/summaries/hourly - Get latest hourly summary only
- GET /api/summaries/daily - Get latest daily summary only
- Cache behavior (cache hits, misses, fallback on errors)
- Null responses when no summaries exist

NEM-2892: Dashboard Summaries API Routes
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_cache_service_dep
from backend.api.routes.summaries import router
from backend.core.database import get_db
from backend.models.summary import SummaryType

# Mark as unit tests - no database required
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
def mock_hourly_summary() -> MagicMock:
    """Create a mock hourly summary."""
    summary = MagicMock()
    summary.id = 1
    summary.summary_type = SummaryType.HOURLY.value
    summary.content = "Over the past hour, one critical event occurred at the front door."
    summary.event_count = 1
    summary.event_ids = [101]
    summary.window_start = datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC)
    summary.window_end = datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
    summary.generated_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)
    summary.created_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)
    return summary


@pytest.fixture
def mock_daily_summary() -> MagicMock:
    """Create a mock daily summary."""
    summary = MagicMock()
    summary.id = 2
    summary.summary_type = SummaryType.DAILY.value
    summary.content = "Today has seen minimal high-priority activity."
    summary.event_count = 1
    summary.event_ids = [101]
    summary.window_start = datetime(2026, 1, 18, 0, 0, 0, tzinfo=UTC)
    summary.window_end = datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
    summary.generated_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)
    summary.created_at = datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)
    return summary


# =============================================================================
# GET /api/summaries/latest Tests
# =============================================================================


class TestGetLatestSummaries:
    """Tests for GET /api/summaries/latest endpoint."""

    def test_returns_both_summaries(
        self,
        client: TestClient,
        mock_hourly_summary: MagicMock,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test getting both hourly and daily summaries."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly_summary,
                    "daily": mock_daily_summary,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()

        # Verify hourly summary
        assert data["hourly"] is not None
        assert data["hourly"]["id"] == 1
        assert "critical event" in data["hourly"]["content"]
        assert data["hourly"]["event_count"] == 1
        assert data["hourly"]["window_start"] == "2026-01-18T14:00:00Z"
        assert data["hourly"]["window_end"] == "2026-01-18T15:00:00Z"
        assert data["hourly"]["generated_at"] == "2026-01-18T14:55:00Z"

        # Verify daily summary
        assert data["daily"] is not None
        assert data["daily"]["id"] == 2
        assert "minimal high-priority" in data["daily"]["content"]
        assert data["daily"]["event_count"] == 1
        assert data["daily"]["window_start"] == "2026-01-18T00:00:00Z"
        assert data["daily"]["window_end"] == "2026-01-18T15:00:00Z"

    def test_returns_null_when_no_summaries_exist(
        self,
        client: TestClient,
    ) -> None:
        """Test that null values are returned when no summaries exist."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": None,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"] is None
        assert data["daily"] is None

    def test_returns_only_hourly_when_daily_missing(
        self,
        client: TestClient,
        mock_hourly_summary: MagicMock,
    ) -> None:
        """Test response when only hourly summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly_summary,
                    "daily": None,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"] is not None
        assert data["daily"] is None

    def test_returns_only_daily_when_hourly_missing(
        self,
        client: TestClient,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test response when only daily summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": None,
                    "daily": mock_daily_summary,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"] is None
        assert data["daily"] is not None

    def test_returns_cached_response(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cached response is returned when available."""
        # Set up cache hit with pre-serialized data
        cached_data = {
            "hourly": {
                "id": 1,
                "content": "Cached hourly summary",
                "event_count": 0,
                "window_start": "2026-01-18T14:00:00Z",
                "window_end": "2026-01-18T15:00:00Z",
                "generated_at": "2026-01-18T14:55:00Z",
            },
            "daily": None,
        }
        mock_cache_service.get = AsyncMock(return_value=cached_data)

        response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"]["content"] == "Cached hourly summary"
        assert data["daily"] is None

    def test_falls_back_to_db_on_cache_error(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_hourly_summary: MagicMock,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test that database is queried when cache read fails."""
        # Cache raises exception
        mock_cache_service.get = AsyncMock(side_effect=Exception("Redis connection error"))

        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly_summary,
                    "daily": mock_daily_summary,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"] is not None
        assert data["daily"] is not None


# =============================================================================
# GET /api/summaries/hourly Tests
# =============================================================================


class TestGetHourlySummary:
    """Tests for GET /api/summaries/hourly endpoint."""

    def test_returns_hourly_summary(
        self,
        client: TestClient,
        mock_hourly_summary: MagicMock,
    ) -> None:
        """Test getting the latest hourly summary."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=mock_hourly_summary)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert "critical event" in data["content"]
        assert data["event_count"] == 1
        assert data["window_start"] == "2026-01-18T14:00:00Z"
        assert data["window_end"] == "2026-01-18T15:00:00Z"

    def test_returns_null_when_no_hourly_summary(
        self,
        client: TestClient,
    ) -> None:
        """Test that null is returned when no hourly summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        assert response.json() is None

    def test_returns_cached_hourly_summary(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cached hourly summary is returned when available."""
        cached_data = {
            "id": 1,
            "content": "Cached hourly summary",
            "event_count": 2,
            "window_start": "2026-01-18T14:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }
        mock_cache_service.get = AsyncMock(return_value=cached_data)

        response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Cached hourly summary"
        assert data["event_count"] == 2

    def test_returns_null_when_cached_null(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that null is returned when cache contains 'null' marker."""
        mock_cache_service.get = AsyncMock(return_value="null")

        response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        assert response.json() is None


# =============================================================================
# GET /api/summaries/daily Tests
# =============================================================================


class TestGetDailySummary:
    """Tests for GET /api/summaries/daily endpoint."""

    def test_returns_daily_summary(
        self,
        client: TestClient,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test getting the latest daily summary."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=mock_daily_summary)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/daily")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert "minimal high-priority" in data["content"]
        assert data["event_count"] == 1
        assert data["window_start"] == "2026-01-18T00:00:00Z"
        assert data["window_end"] == "2026-01-18T15:00:00Z"

    def test_returns_null_when_no_daily_summary(
        self,
        client: TestClient,
    ) -> None:
        """Test that null is returned when no daily summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/daily")

        assert response.status_code == 200
        assert response.json() is None

    def test_returns_cached_daily_summary(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that cached daily summary is returned when available."""
        cached_data = {
            "id": 2,
            "content": "Cached daily summary",
            "event_count": 3,
            "window_start": "2026-01-18T00:00:00Z",
            "window_end": "2026-01-18T15:00:00Z",
            "generated_at": "2026-01-18T14:55:00Z",
        }
        mock_cache_service.get = AsyncMock(return_value=cached_data)

        response = client.get("/api/summaries/daily")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Cached daily summary"
        assert data["event_count"] == 3

    def test_returns_null_when_cached_null(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that null is returned when cache contains 'null' marker."""
        mock_cache_service.get = AsyncMock(return_value="null")

        response = client.get("/api/summaries/daily")

        assert response.status_code == 200
        assert response.json() is None


# =============================================================================
# Cache Behavior Tests
# =============================================================================


class TestCacheBehavior:
    """Tests for cache-related behavior across endpoints."""

    def test_latest_caches_result_on_miss(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_hourly_summary: MagicMock,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test that /latest caches result after database query."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly_summary,
                    "daily": mock_daily_summary,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        # Verify cache.set was called
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "summaries:latest"  # cache key
        assert call_args[1]["ttl"] == 300  # 5 minute TTL

    def test_hourly_caches_result_on_miss(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_hourly_summary: MagicMock,
    ) -> None:
        """Test that /hourly caches result after database query."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=mock_hourly_summary)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "summaries:hourly"

    def test_hourly_caches_null_marker_when_no_summary(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that /hourly caches 'null' marker when no summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/hourly")

        assert response.status_code == 200
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "summaries:hourly"
        assert call_args[0][1] == "null"

    def test_daily_caches_null_marker_when_no_summary(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
    ) -> None:
        """Test that /daily caches 'null' marker when no summary exists."""
        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_by_type = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/daily")

        assert response.status_code == 200
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "summaries:daily"
        assert call_args[0][1] == "null"

    def test_cache_write_failure_does_not_break_response(
        self,
        client: TestClient,
        mock_cache_service: MagicMock,
        mock_hourly_summary: MagicMock,
        mock_daily_summary: MagicMock,
    ) -> None:
        """Test that response is returned even if cache write fails."""
        mock_cache_service.set = AsyncMock(side_effect=Exception("Redis write error"))

        with patch("backend.api.routes.summaries.SummaryRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_latest_all = AsyncMock(
                return_value={
                    "hourly": mock_hourly_summary,
                    "daily": mock_daily_summary,
                }
            )
            MockRepo.return_value = mock_repo

            response = client.get("/api/summaries/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["hourly"] is not None
        assert data["daily"] is not None


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestSummaryToResponse:
    """Tests for _summary_to_response helper function."""

    def test_converts_summary_to_response(
        self,
        mock_hourly_summary: MagicMock,
    ) -> None:
        """Test conversion of Summary model to SummaryResponse."""
        from backend.api.routes.summaries import _summary_to_response

        result = _summary_to_response(mock_hourly_summary)

        assert result is not None
        assert result.id == 1
        assert (
            result.content == "Over the past hour, one critical event occurred at the front door."
        )
        assert result.event_count == 1
        assert result.window_start == datetime(2026, 1, 18, 14, 0, 0, tzinfo=UTC)
        assert result.window_end == datetime(2026, 1, 18, 15, 0, 0, tzinfo=UTC)
        assert result.generated_at == datetime(2026, 1, 18, 14, 55, 0, tzinfo=UTC)

    def test_returns_none_for_none_input(self) -> None:
        """Test that None is returned for None input."""
        from backend.api.routes.summaries import _summary_to_response

        result = _summary_to_response(None)
        assert result is None


# =============================================================================
# OpenAPI Documentation Tests
# =============================================================================


class TestSummariesOpenAPI:
    """Tests for summaries routes OpenAPI documentation."""

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
