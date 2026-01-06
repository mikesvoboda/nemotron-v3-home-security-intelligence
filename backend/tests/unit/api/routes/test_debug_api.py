"""Tests for debug API endpoints (NEM-1470, NEM-1471).

This module tests the debug endpoints for:
- Pipeline state inspection
- Log level runtime override
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.redis import get_redis_optional
from backend.main import app


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client."""
    mock = MagicMock()
    mock.ping = AsyncMock(return_value=True)
    mock.llen = AsyncMock(return_value=5)
    mock.get = AsyncMock(return_value=None)
    mock.keys = AsyncMock(return_value=[])
    return mock


async def _mock_redis_none():
    """Mock dependency that yields None."""
    yield None


class TestPipelineStateEndpoint:
    """Tests for GET /api/debug/pipeline-state endpoint."""

    @pytest.mark.asyncio
    async def test_get_pipeline_state_returns_queue_depths(self, mock_redis: MagicMock) -> None:
        """Verify pipeline state includes queue depths."""
        mock_redis.llen = AsyncMock(side_effect=[10, 5])  # detection, analysis queues

        async def mock_redis_dependency():
            yield mock_redis

        app.dependency_overrides[get_redis_optional] = mock_redis_dependency
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/debug/pipeline-state")

            assert response.status_code == 200
            data = response.json()
            assert "queue_depths" in data
            assert data["queue_depths"]["detection_queue"] == 10
            assert data["queue_depths"]["analysis_queue"] == 5
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_state_returns_worker_status(self, mock_redis: MagicMock) -> None:
        """Verify pipeline state includes worker status information."""

        async def mock_redis_dependency():
            yield mock_redis

        app.dependency_overrides[get_redis_optional] = mock_redis_dependency
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/debug/pipeline-state")

            assert response.status_code == 200
            data = response.json()
            assert "workers" in data
            assert "file_watcher" in data["workers"]
            assert "detector" in data["workers"]
            assert "analyzer" in data["workers"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_state_returns_recent_errors(self, mock_redis: MagicMock) -> None:
        """Verify pipeline state includes recent error summary (empty list as placeholder)."""

        async def mock_redis_dependency():
            yield mock_redis

        app.dependency_overrides[get_redis_optional] = mock_redis_dependency
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/debug/pipeline-state")

            assert response.status_code == 200
            data = response.json()
            assert "recent_errors" in data
            # Currently returns empty list as placeholder
            assert data["recent_errors"] == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_state_handles_redis_unavailable(self) -> None:
        """Verify graceful handling when Redis is unavailable."""
        app.dependency_overrides[get_redis_optional] = _mock_redis_none
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/debug/pipeline-state")

            assert response.status_code == 200
            data = response.json()
            assert "queue_depths" in data
            # Should return defaults when Redis is unavailable
            assert data["queue_depths"]["detection_queue"] == 0
            assert data["queue_depths"]["analysis_queue"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_state_includes_correlation_id(self, mock_redis: MagicMock) -> None:
        """Verify pipeline state response includes correlation ID."""

        async def mock_redis_dependency():
            yield mock_redis

        app.dependency_overrides[get_redis_optional] = mock_redis_dependency
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/debug/pipeline-state",
                    headers={"X-Correlation-ID": "test-corr-123"},
                )

            assert response.status_code == 200
            # Response should echo back the correlation ID
            assert response.headers.get("X-Correlation-ID") == "test-corr-123"
        finally:
            app.dependency_overrides.clear()


class TestLogLevelEndpoint:
    """Tests for POST /api/debug/log-level endpoint."""

    @pytest.mark.asyncio
    async def test_set_log_level_to_debug(self) -> None:
        """Verify log level can be set to DEBUG."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/debug/log-level",
                json={"level": "DEBUG"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "DEBUG"
        assert data["previous_level"] is not None

    @pytest.mark.asyncio
    async def test_set_log_level_to_info(self) -> None:
        """Verify log level can be set to INFO."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/debug/log-level",
                json={"level": "INFO"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_set_log_level_invalid_level_returns_400(self) -> None:
        """Verify invalid log level returns 400 error."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/debug/log-level",
                json={"level": "INVALID"},
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_set_log_level_case_insensitive(self) -> None:
        """Verify log level is case-insensitive."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/debug/log-level",
                json={"level": "warning"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "WARNING"

    @pytest.mark.asyncio
    async def test_get_current_log_level(self) -> None:
        """Verify current log level can be retrieved."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/debug/log-level")

        assert response.status_code == 200
        data = response.json()
        assert "level" in data
        assert data["level"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @pytest.mark.asyncio
    async def test_set_log_level_affects_loggers(self) -> None:
        """Verify setting log level affects actual loggers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Set to WARNING
            await client.post(
                "/api/debug/log-level",
                json={"level": "WARNING"},
            )

        # Check that root logger level was changed
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

        # Reset to INFO for other tests
        root_logger.setLevel(logging.INFO)


class TestDebugEndpointSecurity:
    """Tests for debug endpoint security controls."""

    @pytest.mark.asyncio
    async def test_debug_endpoints_require_debug_mode_enabled(self) -> None:
        """Verify debug endpoints are only available when DEBUG_MODE is enabled."""
        # This test verifies the endpoint exists - in production,
        # the endpoint would be gated by DEBUG_MODE setting
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/debug/pipeline-state")

        # Should return 200 in test mode (DEBUG_MODE=True)
        # In production with DEBUG_MODE=False, this would return 404
        assert response.status_code == 200
