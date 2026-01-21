"""Tests for debug API endpoints (NEM-1470, NEM-1471).

This module tests the debug endpoints for:
- Pipeline state inspection
- Log level runtime override

All debug endpoints require settings.debug == True.
These tests patch get_settings to enable debug mode.
"""

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
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


@pytest.fixture
def debug_settings() -> Settings:
    """Create settings with debug=True."""
    return Settings(
        debug=True,
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )


async def _mock_redis_none():
    """Mock dependency that yields None."""
    yield None


class TestPipelineStateEndpoint:
    """Tests for GET /api/debug/pipeline-state endpoint."""

    @pytest.mark.asyncio
    async def test_get_pipeline_state_returns_queue_depths(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline state includes queue depths."""
        mock_redis.llen = AsyncMock(side_effect=[10, 5])  # detection, analysis queues

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
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
    async def test_get_pipeline_state_returns_worker_status(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline state includes worker status information."""

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
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
    async def test_get_pipeline_state_returns_recent_errors(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline state includes recent errors from Redis."""
        # Mock empty errors list (no errors stored)
        mock_redis.lrange = AsyncMock(return_value=[])

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                assert response.status_code == 200
                data = response.json()
                assert "recent_errors" in data
                # Returns empty list when no errors in Redis
                assert data["recent_errors"] == []
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_state_handles_redis_unavailable(
        self, debug_settings: Settings
    ) -> None:
        """Verify graceful handling when Redis is unavailable."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
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
    async def test_get_pipeline_state_includes_correlation_id(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline state response includes correlation ID."""

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
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
    async def test_set_log_level_to_debug(self, debug_settings: Settings) -> None:
        """Verify log level can be set to DEBUG."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/debug/log-level",
                    json={"level": "DEBUG"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["level"] == "DEBUG"
            assert data["previous_level"] is not None

    @pytest.mark.asyncio
    async def test_set_log_level_to_info(self, debug_settings: Settings) -> None:
        """Verify log level can be set to INFO."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/debug/log-level",
                    json={"level": "INFO"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_set_log_level_invalid_level_returns_400(self, debug_settings: Settings) -> None:
        """Verify invalid log level returns 400 error."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/debug/log-level",
                    json={"level": "INVALID"},
                )

            assert response.status_code == 400
            data = response.json()
            # Exception handlers return RFC 7807 Problem Details format
            assert data["status"] == 400
            assert data["title"] == "Bad Request"
            assert "invalid" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_set_log_level_case_insensitive(self, debug_settings: Settings) -> None:
        """Verify log level is case-insensitive."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/debug/log-level",
                    json={"level": "warning"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["level"] == "WARNING"

    @pytest.mark.asyncio
    async def test_get_current_log_level(self, debug_settings: Settings) -> None:
        """Verify current log level can be retrieved."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/debug/log-level")

            assert response.status_code == 200
            data = response.json()
            assert "level" in data
            assert data["level"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @pytest.mark.asyncio
    async def test_set_log_level_affects_loggers(self, debug_settings: Settings) -> None:
        """Verify setting log level affects actual loggers."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
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
    async def test_debug_endpoints_work_when_debug_mode_enabled(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify debug endpoints work when debug=True."""

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                # Should return 200 when debug mode is enabled
                assert response.status_code == 200
            finally:
                app.dependency_overrides.clear()


class TestPipelineErrorsEndpoint:
    """Tests for GET /api/debug/pipeline-errors endpoint (NEM-2485)."""

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_returns_errors_from_redis(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline errors are retrieved from Redis."""
        import json

        # Mock Redis to return some error records
        error_records = [
            json.dumps(
                {
                    "timestamp": "2024-01-01T10:00:00+00:00",
                    "error_type": "connection_error",
                    "component": "detector",
                    "message": "Connection refused",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2024-01-01T09:00:00+00:00",
                    "error_type": "timeout_error",
                    "component": "analyzer",
                    "message": "Request timed out",
                }
            ),
        ]
        mock_redis.lrange = AsyncMock(return_value=error_records)

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-errors")

                assert response.status_code == 200
                data = response.json()
                assert "errors" in data
                assert len(data["errors"]) == 2
                assert data["errors"][0]["error_type"] == "connection_error"
                assert data["errors"][0]["component"] == "detector"
                assert data["errors"][1]["error_type"] == "timeout_error"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_filters_by_component(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline errors can be filtered by component."""
        import json

        error_records = [
            json.dumps(
                {
                    "timestamp": "2024-01-01T10:00:00+00:00",
                    "error_type": "connection_error",
                    "component": "detector",
                    "message": "Error 1",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2024-01-01T09:00:00+00:00",
                    "error_type": "timeout_error",
                    "component": "analyzer",
                    "message": "Error 2",
                }
            ),
        ]
        mock_redis.lrange = AsyncMock(return_value=error_records)

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-errors?component=detector")

                assert response.status_code == 200
                data = response.json()
                assert len(data["errors"]) == 1
                assert data["errors"][0]["component"] == "detector"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_filters_by_error_type(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline errors can be filtered by error type."""
        import json

        error_records = [
            json.dumps(
                {
                    "timestamp": "2024-01-01T10:00:00+00:00",
                    "error_type": "connection_error",
                    "component": "detector",
                    "message": "Error 1",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2024-01-01T09:00:00+00:00",
                    "error_type": "timeout_error",
                    "component": "analyzer",
                    "message": "Error 2",
                }
            ),
        ]
        mock_redis.lrange = AsyncMock(return_value=error_records)

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/debug/pipeline-errors?error_type=timeout_error"
                    )

                assert response.status_code == 200
                data = response.json()
                assert len(data["errors"]) == 1
                assert data["errors"][0]["error_type"] == "timeout_error"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_respects_limit(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline errors respect limit parameter."""
        import json

        # Create 5 error records
        error_records = [
            json.dumps(
                {
                    "timestamp": f"2024-01-01T{10 - i:02d}:00:00+00:00",
                    "error_type": "error",
                    "component": "detector",
                    "message": f"Error {i}",
                }
            )
            for i in range(5)
        ]
        mock_redis.lrange = AsyncMock(return_value=error_records)

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-errors?limit=3")

                assert response.status_code == 200
                data = response.json()
                assert len(data["errors"]) == 3
                assert data["limit"] == 3
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_returns_empty_when_no_errors(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify empty list when no errors exist."""
        mock_redis.lrange = AsyncMock(return_value=[])

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-errors")

                assert response.status_code == 200
                data = response.json()
                assert data["errors"] == []
                assert data["total"] == 0
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pipeline_errors_handles_redis_unavailable(
        self, debug_settings: Settings
    ) -> None:
        """Verify graceful handling when Redis is unavailable."""
        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = _mock_redis_none
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-errors")

                assert response.status_code == 200
                data = response.json()
                assert data["errors"] == []
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_pipeline_state_includes_recent_errors_from_redis(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify pipeline state endpoint includes errors from Redis."""
        import json

        error_records = [
            json.dumps(
                {
                    "timestamp": "2024-01-01T10:00:00+00:00",
                    "error_type": "connection_error",
                    "component": "detector",
                    "message": "Test error",
                }
            ),
        ]
        mock_redis.llen = AsyncMock(side_effect=[10, 5])
        mock_redis.lrange = AsyncMock(return_value=error_records)

        async def mock_redis_dependency():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_dependency
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                assert response.status_code == 200
                data = response.json()
                assert "recent_errors" in data
                assert len(data["recent_errors"]) == 1
                assert data["recent_errors"][0]["error_type"] == "connection_error"
            finally:
                app.dependency_overrides.clear()


class TestRecordPipelineErrorToRedis:
    """Tests for record_pipeline_error_to_redis helper function (NEM-2485)."""

    @pytest.mark.asyncio
    async def test_record_error_stores_in_redis(self, mock_redis: MagicMock) -> None:
        """Verify errors are stored correctly in Redis."""
        from backend.api.routes.debug import record_pipeline_error_to_redis

        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        result = await record_pipeline_error_to_redis(
            redis=mock_redis,
            error_type="connection_error",
            component="detector",
            message="Test error message",
        )

        assert result is True
        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_error_handles_redis_failure(self, mock_redis: MagicMock) -> None:
        """Verify graceful handling when Redis fails."""
        from backend.api.routes.debug import record_pipeline_error_to_redis

        mock_redis.lpush = AsyncMock(side_effect=Exception("Redis connection error"))

        result = await record_pipeline_error_to_redis(
            redis=mock_redis,
            error_type="timeout_error",
            component="analyzer",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_record_error_without_message(self, mock_redis: MagicMock) -> None:
        """Verify errors can be stored without optional message."""
        import json

        from backend.api.routes.debug import record_pipeline_error_to_redis

        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        result = await record_pipeline_error_to_redis(
            redis=mock_redis,
            error_type="validation_error",
            component="file_watcher",
        )

        assert result is True
        # Verify the stored data structure
        call_args = mock_redis.lpush.call_args
        stored_json = call_args[0][1]
        stored_data = json.loads(stored_json)
        assert stored_data["error_type"] == "validation_error"
        assert stored_data["component"] == "file_watcher"
        assert stored_data["message"] is None
        assert "timestamp" in stored_data
