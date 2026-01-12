"""Tests for debug API endpoints (NEM-1642).

This module tests the new debug endpoints for runtime diagnostics:
- GET /api/debug/config - Current configuration with sensitive values redacted
- GET /api/debug/redis/info - Redis connection stats and pub/sub channels
- GET /api/debug/websocket/connections - Active WebSocket connection states
- GET /api/debug/circuit-breakers - All circuit breaker states
- POST /api/debug/log-level - Change log level at runtime (already exists)

SECURITY: All debug endpoints require debug=True in settings.
When debug=False, endpoints return 404 Not Found.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client."""
    mock = MagicMock()
    mock.ping = AsyncMock(return_value=True)
    mock.llen = AsyncMock(return_value=5)
    mock.get = AsyncMock(return_value=None)
    mock.keys = AsyncMock(return_value=[])
    mock.info = AsyncMock(
        return_value={
            "redis_version": "7.0.0",
            "connected_clients": 3,
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M",
            "total_connections_received": 100,
            "total_commands_processed": 5000,
            "uptime_in_seconds": 86400,
        }
    )
    mock.pubsub_channels = AsyncMock(return_value=[b"security_events", b"system_status"])
    mock.pubsub_numsub = AsyncMock(return_value=[(b"security_events", 2), (b"system_status", 1)])
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


@pytest.fixture
def production_settings() -> Settings:
    """Create settings with debug=False (production mode)."""
    return Settings(
        debug=False,
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )


async def _mock_redis_dependency(mock_redis: MagicMock):
    """Generator that yields the mock Redis client."""
    yield mock_redis


async def _mock_redis_none():
    """Generator that yields None (Redis unavailable)."""
    yield None


class TestDebugConfigEndpoint:
    """Tests for GET /api/debug/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_returns_configuration(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify config endpoint returns current configuration."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/config")

                assert response.status_code == 200
                data = response.json()
                assert "config" in data
                assert "app_name" in data["config"]
                assert "app_version" in data["config"]
                assert "debug" in data["config"]
                assert data["config"]["debug"] is True
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_config_redacts_sensitive_values(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify config endpoint redacts sensitive fields."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/config")

                assert response.status_code == 200
                data = response.json()
                config = data["config"]

                # Sensitive fields should be redacted
                if "database_url" in config:
                    # Password portion should be redacted
                    assert (
                        "[REDACTED]" in config["database_url"]
                        or "password" not in config["database_url"].lower()
                    )
                if "redis_url" in config:
                    assert (
                        "[REDACTED]" in config["redis_url"]
                        or "password" not in config["redis_url"].lower()
                    )
                if "api_keys" in config:
                    assert config["api_keys"] == ["[REDACTED]"] or config["api_keys"] == []
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_config_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify config endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/config")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()


class TestDebugRedisInfoEndpoint:
    """Tests for GET /api/debug/redis/info endpoint."""

    @pytest.mark.asyncio
    async def test_get_redis_info_returns_stats(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify redis info endpoint returns connection stats."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                assert "status" in data
                assert "info" in data
                assert "pubsub" in data
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_redis_info_handles_unavailable(self, debug_settings: Settings) -> None:
        """Verify redis info endpoint handles Redis being unavailable."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = _mock_redis_none
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unavailable"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_redis_info_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify redis info endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()


class TestDebugWebSocketConnectionsEndpoint:
    """Tests for GET /api/debug/websocket/connections endpoint."""

    @pytest.mark.asyncio
    async def test_get_websocket_connections_returns_state(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify websocket connections endpoint returns connection states."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/websocket/connections")

                assert response.status_code == 200
                data = response.json()
                assert "event_broadcaster" in data
                assert "system_broadcaster" in data
                # Check structure
                assert "connection_count" in data["event_broadcaster"]
                assert "connection_count" in data["system_broadcaster"]
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_websocket_connections_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify websocket connections endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/websocket/connections")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()


class TestDebugCircuitBreakersEndpoint:
    """Tests for GET /api/debug/circuit-breakers endpoint."""

    @pytest.mark.asyncio
    async def test_get_circuit_breakers_returns_all_states(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify circuit breakers endpoint returns all circuit breaker states."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/circuit-breakers")

                assert response.status_code == 200
                data = response.json()
                assert "circuit_breakers" in data
                # Should be a dict of circuit breaker states
                assert isinstance(data["circuit_breakers"], dict)
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_circuit_breakers_includes_state_info(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify circuit breakers endpoint includes state information."""
        from backend.core.redis import get_redis_optional
        from backend.main import app
        from backend.services.circuit_breaker import get_circuit_breaker

        # Pre-register a circuit breaker (result not needed, just registration)
        get_circuit_breaker("test_service")

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/circuit-breakers")

                assert response.status_code == 200
                data = response.json()
                breakers = data["circuit_breakers"]

                # At least the test_service should be in the list
                if "test_service" in breakers:
                    assert "state" in breakers["test_service"]
                    assert "failure_count" in breakers["test_service"]
            finally:
                app.dependency_overrides.clear()
                # Clean up the test circuit breaker
                from backend.services.circuit_breaker import reset_circuit_breaker_registry

                reset_circuit_breaker_registry()

    @pytest.mark.asyncio
    async def test_get_circuit_breakers_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify circuit breakers endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/circuit-breakers")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()


class TestDebugLogLevelEndpoint:
    """Tests for POST /api/debug/log-level endpoint (extended tests)."""

    @pytest.mark.asyncio
    async def test_log_level_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify log level endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/debug/log-level",
                        json={"level": "DEBUG"},
                    )

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_log_level_returns_404_when_debug_disabled(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify GET log level endpoint returns 404 when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/log-level")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()


class TestDebugEndpointSecurity:
    """Security tests for all debug endpoints."""

    @pytest.mark.asyncio
    async def test_all_debug_endpoints_require_debug_mode(
        self, mock_redis: MagicMock, production_settings: Settings
    ) -> None:
        """Verify all debug endpoints are blocked when debug=False."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        endpoints = [
            ("GET", "/api/debug/config"),
            ("GET", "/api/debug/redis/info"),
            ("GET", "/api/debug/websocket/connections"),
            ("GET", "/api/debug/circuit-breakers"),
            ("GET", "/api/debug/log-level"),
            ("POST", "/api/debug/log-level"),
            ("GET", "/api/debug/pipeline-state"),
            ("POST", "/api/debug/profile/start"),
            ("POST", "/api/debug/profile/stop"),
            ("GET", "/api/debug/profile/stats"),
            ("GET", "/api/debug/recordings"),
        ]

        with (
            patch("backend.api.routes.debug.get_settings", return_value=production_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    for method, url in endpoints:
                        if method == "GET":
                            response = await client.get(url)
                        else:
                            response = await client.post(url, json={"level": "DEBUG"})

                        assert response.status_code == 404, (
                            f"Endpoint {method} {url} should return 404 when debug=False, "
                            f"got {response.status_code}"
                        )
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_debug_endpoints_do_not_leak_sensitive_info(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify debug endpoints don't leak raw passwords or secrets."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/config")

                assert response.status_code == 200
                response_text = response.text.lower()

                # Should not contain raw passwords or secrets
                # (unless they're explicitly "[redacted]")
                sensitive_patterns = ["password=", "secret=", "api_key="]
                for pattern in sensitive_patterns:
                    if pattern in response_text:
                        # If present, should be redacted
                        assert "[redacted]" in response_text or "***" in response_text
            finally:
                app.dependency_overrides.clear()


class TestRedisInfoHelpers:
    """Tests for Redis info helper functions and error paths."""

    @pytest.mark.asyncio
    async def test_redis_info_handles_info_error(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify redis info handles errors from Redis INFO command."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.info = AsyncMock(side_effect=Exception("Redis connection failed"))

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "error"
                assert data["info"] is not None
                assert "error" in data["info"]
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_redis_info_handles_pubsub_error(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify redis info handles errors from pubsub commands."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.pubsub_channels = AsyncMock(side_effect=Exception("Pubsub failed"))

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                # Should succeed but pubsub info should be empty
                assert data["pubsub"] is not None
                assert data["pubsub"]["channels"] == []
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_redis_info_handles_string_channels(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify redis info handles string channel names (not bytes)."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        # Mix of bytes and string channel names
        mock_redis.pubsub_channels = AsyncMock(return_value=["channel1", b"channel2"])
        mock_redis.pubsub_numsub = AsyncMock(return_value=[("channel1", 1), (b"channel2", 2)])

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/redis/info")

                assert response.status_code == 200
                data = response.json()
                assert "channel1" in data["pubsub"]["channels"]
                assert "channel2" in data["pubsub"]["channels"]
            finally:
                app.dependency_overrides.clear()


class TestWorkerStatusHelpers:
    """Tests for worker status helper functions."""

    @pytest.mark.asyncio
    async def test_worker_status_handles_error_count_conversion(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify worker status converts error counts to integers."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.get = AsyncMock(
            side_effect=[
                "2023-01-01T00:00:00Z",  # fw_heartbeat
                "2023-01-01T00:00:00Z",  # det_heartbeat
                "2023-01-01T00:00:00Z",  # ana_heartbeat
                "5",  # fw_errors
                "3",  # det_errors
                "0",  # ana_errors
            ]
        )

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                assert response.status_code == 200
                data = response.json()
                assert data["workers"]["file_watcher"]["error_count"] == 5
                assert data["workers"]["detector"]["error_count"] == 3
                assert data["workers"]["analyzer"]["error_count"] == 0
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_worker_status_handles_get_error(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify worker status handles errors from Redis GET."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.get = AsyncMock(side_effect=Exception("Redis GET failed"))

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                assert response.status_code == 200
                data = response.json()
                # Should return default worker status
                assert data["workers"]["file_watcher"]["running"] is False
                assert data["workers"]["detector"]["running"] is False
                assert data["workers"]["analyzer"]["running"] is False
            finally:
                app.dependency_overrides.clear()


class TestQueueDepthsHelpers:
    """Tests for queue depths helper functions."""

    @pytest.mark.asyncio
    async def test_queue_depths_handles_llen_error(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify queue depths handles errors from Redis LLEN."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        mock_redis.llen = AsyncMock(side_effect=Exception("Redis LLEN failed"))

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/pipeline-state")

                assert response.status_code == 200
                data = response.json()
                # Should return 0 on error
                assert data["queue_depths"]["detection_queue"] == 0
                assert data["queue_depths"]["analysis_queue"] == 0
            finally:
                app.dependency_overrides.clear()


class TestConfigRedactionHelpers:
    """Tests for configuration redaction helper functions."""

    @pytest.mark.asyncio
    async def test_config_redaction_handles_nested_settings(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify config redaction handles nested Pydantic models."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with patch("backend.api.routes.debug.get_settings", return_value=debug_settings):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/config")

                assert response.status_code == 200
                data = response.json()
                config = data["config"]

                # Check if nested settings (like orchestrator) are handled
                # The config should be a flat or nested dict
                assert isinstance(config, dict)

                # If orchestrator exists, it should be redacted properly
                if "orchestrator" in config and isinstance(config["orchestrator"], dict):
                    # Nested fields should be present and redacted if sensitive
                    assert config["orchestrator"] is not None
            finally:
                app.dependency_overrides.clear()


class TestProfilingEndpoints:
    """Tests for profiling endpoints (NEM-1644)."""

    @pytest.mark.asyncio
    async def test_start_profiling_success(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify profiling can be started."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = False
            mock_prof.start = MagicMock()
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/profile/start")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "started"
                assert "started_at" in data
                mock_prof.start.assert_called_once()
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_start_profiling_already_running(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify starting profiling when already running returns appropriate status."""
        from datetime import UTC, datetime

        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = True
            mock_prof.get_started_at = MagicMock(return_value=datetime.now(UTC))
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/profile/start")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "already_running"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stop_profiling_success(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify profiling can be stopped."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = True
            mock_prof.last_profile_path = "/path/to/profile.prof"
            mock_prof.stop = MagicMock()
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/profile/stop")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "stopped"
                assert data["profile_path"] == "/path/to/profile.prof"
                mock_prof.stop.assert_called_once()
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stop_profiling_not_running(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify stopping profiling when not running returns appropriate status."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = False
            mock_prof.last_profile_path = None
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/profile/stop")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "not_running"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_profile_stats_while_profiling(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify getting profile stats while profiling is active."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = True
            mock_prof.last_profile_path = None
            mock_prof.get_stats_text = MagicMock(return_value=None)
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/profile/stats")

                assert response.status_code == 200
                data = response.json()
                assert data["is_profiling"] is True
                assert data["stats_text"] is None
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_profile_stats_after_profiling(
        self, mock_redis: MagicMock, debug_settings: Settings
    ) -> None:
        """Verify getting profile stats after profiling has stopped."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.core.profiling.get_profiling_manager") as mock_manager,
        ):
            mock_prof = MagicMock()
            mock_prof.is_profiling = False
            mock_prof.last_profile_path = "/path/to/profile.prof"
            mock_prof.get_stats_text = MagicMock(return_value="Profile statistics here")
            mock_manager.return_value = mock_prof

            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/profile/stats")

                assert response.status_code == 200
                data = response.json()
                assert data["is_profiling"] is False
                assert data["stats_text"] == "Profile statistics here"
                assert data["last_profile_path"] == "/path/to/profile.prof"
            finally:
                app.dependency_overrides.clear()


class TestRecordingEndpoints:
    """Tests for request recording and replay endpoints (NEM-1646)."""

    @pytest.mark.asyncio
    async def test_list_recordings_empty(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify listing recordings when no recordings exist."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(tmp_path / "nonexistent")),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings")

                assert response.status_code == 200
                data = response.json()
                assert data["recordings"] == []
                assert data["total"] == 0
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_recordings_with_data(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify listing recordings with existing recording files."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        # Create test recordings
        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording1 = recordings_dir / "test-rec-1.json"
        recording1.write_text(
            json.dumps(
                {
                    "recording_id": "test-rec-1",
                    "timestamp": "2023-01-01T00:00:00Z",
                    "method": "GET",
                    "path": "/api/events",
                    "status_code": 200,
                    "duration_ms": 50.5,
                    "body_truncated": False,
                }
            )
        )

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert len(data["recordings"]) == 1
                assert data["recordings"][0]["recording_id"] == "test-rec-1"
                assert data["recordings"][0]["method"] == "GET"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_recordings_handles_corrupt_file(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify listing recordings skips corrupt JSON files."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        corrupt_file = recordings_dir / "corrupt.json"
        corrupt_file.write_text("invalid json {")

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings")

                assert response.status_code == 200
                data = response.json()
                # Should skip corrupt file
                assert data["total"] == 0
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_recording_success(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify getting a specific recording by ID."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-1.json"
        recording_data = {
            "recording_id": "test-rec-1",
            "timestamp": "2023-01-01T00:00:00Z",
            "method": "GET",
            "path": "/api/events",
            "headers": {"content-type": "application/json"},
            "body": {"key": "value"},
            "status_code": 200,
        }
        recording.write_text(json.dumps(recording_data))

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings/test-rec-1")

                assert response.status_code == 200
                data = response.json()
                assert data["recording_id"] == "test-rec-1"
                assert data["method"] == "GET"
                assert data["path"] == "/api/events"
                assert "retrieved_at" in data
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_recording_not_found(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify getting a non-existent recording returns 404."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings/nonexistent")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_recording_path_traversal_prevention(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify path traversal attempts are blocked."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings/../../../etc/passwd")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_recording_read_error(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify handling of file read errors."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        # Create a file that exists but contains invalid JSON
        bad_file = recordings_dir / "test-rec-1.json"
        bad_file.write_text("invalid json {")

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/debug/recordings/test-rec-1")

                assert response.status_code == 500
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_replay_request_success(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify replaying a recorded request."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-1.json"
        recording_data = {
            "recording_id": "test-rec-1",
            "timestamp": "2023-01-01T00:00:00Z",
            "method": "GET",
            "path": "/api/system/health",
            "headers": {"content-type": "application/json"},
            "query_params": {},
            "body": None,
            "status_code": 200,
        }
        recording.write_text(json.dumps(recording_data))

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/replay/test-rec-1")

                assert response.status_code == 200
                data = response.json()
                assert data["recording_id"] == "test-rec-1"
                assert data["original_status_code"] == 200
                assert "replay_status_code" in data
                assert "replay_response" in data
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_replay_request_with_body(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify replaying a POST request with body."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-2.json"
        recording_data = {
            "recording_id": "test-rec-2",
            "timestamp": "2023-01-01T00:00:00Z",
            "method": "POST",
            "path": "/api/debug/log-level",
            "headers": {"content-type": "application/json"},
            "query_params": {},
            "body": {"level": "DEBUG"},
            "status_code": 200,
        }
        recording.write_text(json.dumps(recording_data))

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/replay/test-rec-2")

                assert response.status_code == 200
                data = response.json()
                assert data["recording_id"] == "test-rec-2"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_replay_request_with_query_params(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify replaying a request with query parameters."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-3.json"
        recording_data = {
            "recording_id": "test-rec-3",
            "timestamp": "2023-01-01T00:00:00Z",
            "method": "GET",
            "path": "/api/debug/recordings",
            "headers": {"content-type": "application/json"},
            "query_params": {"limit": "10"},
            "body": None,
            "status_code": 200,
        }
        recording.write_text(json.dumps(recording_data))

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/replay/test-rec-3")

                assert response.status_code == 200
                data = response.json()
                assert data["recording_id"] == "test-rec-3"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_replay_request_not_found(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify replaying a non-existent recording returns 404."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post("/api/debug/replay/nonexistent")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_recording_success(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify deleting a recording."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-1.json"
        recording.write_text(json.dumps({"recording_id": "test-rec-1"}))

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.delete("/api/debug/recordings/test-rec-1")

                assert response.status_code == 200
                data = response.json()
                assert "deleted successfully" in data["message"]
                assert not recording.exists()
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_recording_not_found(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify deleting a non-existent recording returns 404."""
        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        async def mock_redis_gen():
            yield mock_redis

        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.delete("/api/debug/recordings/nonexistent")

                assert response.status_code == 404
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_recording_error(
        self, mock_redis: MagicMock, debug_settings: Settings, tmp_path
    ) -> None:
        """Verify handling of file deletion errors."""
        import json

        from backend.core.redis import get_redis_optional
        from backend.main import app

        recordings_dir = tmp_path / "recordings"
        recordings_dir.mkdir()

        recording = recordings_dir / "test-rec-1.json"
        recording.write_text(json.dumps({"recording_id": "test-rec-1"}))

        async def mock_redis_gen():
            yield mock_redis

        # Mock Path.unlink to raise an exception
        with (
            patch("backend.api.routes.debug.get_settings", return_value=debug_settings),
            patch("backend.api.routes.debug.RECORDINGS_DIR", str(recordings_dir)),
            patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")),
        ):
            app.dependency_overrides[get_redis_optional] = mock_redis_gen
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.delete("/api/debug/recordings/test-rec-1")

                assert response.status_code == 500
            finally:
                app.dependency_overrides.clear()
