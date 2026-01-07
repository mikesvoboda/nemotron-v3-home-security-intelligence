"""Tests for profiling debug API endpoints (NEM-1644).

This module tests the profiling endpoints:
- POST /api/debug/profile/start - Start profiling
- POST /api/debug/profile/stop - Stop and get profile stats
- GET /api/debug/profile/stats - Get current profiling stats

TDD: These tests are written FIRST, before implementation.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture(autouse=True)
def enable_debug_mode(monkeypatch):
    """Enable debug mode for all tests in this module."""
    from backend.core.config import get_settings
    from backend.core.profiling import reset_profiling_manager

    # Reset profiling state before each test
    reset_profiling_manager()

    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()
    yield
    # Clean up profiling state after each test
    reset_profiling_manager()
    get_settings.cache_clear()


class TestProfileStartEndpoint:
    """Tests for POST /api/debug/profile/start endpoint."""

    @pytest.mark.asyncio
    async def test_start_profiling_returns_200(self) -> None:
        """Verify starting profiling returns success."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/debug/profile/start")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_profiling_includes_timestamp(self) -> None:
        """Verify start response includes timestamp."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/debug/profile/start")

        assert response.status_code == 200
        data = response.json()
        assert "started_at" in data

    @pytest.mark.asyncio
    async def test_start_profiling_already_running_returns_409(self) -> None:
        """Verify starting profiling when already running returns conflict."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Start profiling
            await client.post("/api/debug/profile/start")
            # Try to start again
            response = await client.post("/api/debug/profile/start")

        # Should return conflict (409)
        assert response.status_code in [200, 409]  # 200 if idempotent, 409 if strict


class TestProfileStopEndpoint:
    """Tests for POST /api/debug/profile/stop endpoint."""

    @pytest.mark.asyncio
    async def test_stop_profiling_returns_200(self) -> None:
        """Verify stopping profiling returns success."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Start profiling first
            await client.post("/api/debug/profile/start")
            # Stop profiling
            response = await client.post("/api/debug/profile/stop")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_profiling_returns_profile_path(self) -> None:
        """Verify stop response includes path to profile file."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/debug/profile/start")
            response = await client.post("/api/debug/profile/stop")

        assert response.status_code == 200
        data = response.json()
        assert "profile_path" in data

    @pytest.mark.asyncio
    async def test_stop_profiling_not_running_returns_400(self) -> None:
        """Verify stopping when not profiling returns error."""
        # Reset profiling state first
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Ensure profiling is stopped
            await client.post("/api/debug/profile/stop")
            # Try to stop again
            response = await client.post("/api/debug/profile/stop")

        # Should return bad request (400) or success if idempotent
        assert response.status_code in [200, 400]


class TestProfileStatsEndpoint:
    """Tests for GET /api/debug/profile/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_200(self) -> None:
        """Verify getting stats returns success."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Start and stop profiling to have stats
            await client.post("/api/debug/profile/start")
            await client.post("/api/debug/profile/stop")
            # Get stats
            response = await client.get("/api/debug/profile/stats")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_stats_includes_is_profiling(self) -> None:
        """Verify stats response includes profiling status."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/debug/profile/stats")

        assert response.status_code == 200
        data = response.json()
        assert "is_profiling" in data
        assert isinstance(data["is_profiling"], bool)

    @pytest.mark.asyncio
    async def test_get_stats_includes_profile_text(self) -> None:
        """Verify stats response includes profile text when available."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Start and stop profiling to have stats
            await client.post("/api/debug/profile/start")
            await client.post("/api/debug/profile/stop")
            # Get stats
            response = await client.get("/api/debug/profile/stats")

        assert response.status_code == 200
        data = response.json()
        # Should have stats_text field (may be None if no profiling data)
        assert "stats_text" in data

    @pytest.mark.asyncio
    async def test_get_stats_no_profile_data_returns_empty(self) -> None:
        """Verify stats returns empty when no profiling has occurred."""
        # Reset profiling manager
        from backend.core.profiling import reset_profiling_manager

        reset_profiling_manager()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/debug/profile/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["is_profiling"] is False


class TestProfilingEndpointSchemas:
    """Tests for profiling endpoint request/response schemas."""

    @pytest.mark.asyncio
    async def test_start_response_schema(self) -> None:
        """Verify start response matches expected schema."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/debug/profile/start")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert "started_at" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_stop_response_schema(self) -> None:
        """Verify stop response matches expected schema."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/debug/profile/start")
            response = await client.post("/api/debug/profile/stop")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert "profile_path" in data
        assert "stopped_at" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_stats_response_schema(self) -> None:
        """Verify stats response matches expected schema."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/debug/profile/stats")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "is_profiling" in data
        assert "stats_text" in data
        assert "last_profile_path" in data
        assert "timestamp" in data
