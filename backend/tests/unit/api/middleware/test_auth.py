"""Unit tests for API key authentication middleware security logging.

Tests verify that authentication failures are properly logged with
security event metadata for audit and monitoring purposes.

Test coverage:
- Missing API key logs warning with correct fields (HTTP)
- Invalid API key logs warning with correct fields (HTTP)
- Missing API key logs warning for WebSocket
- Invalid API key logs warning for WebSocket
- IP addresses are masked for privacy
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from backend.api.middleware.auth import validate_websocket_api_key
from backend.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear settings cache before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_request():
    """Create a mock HTTP request."""
    request = MagicMock()
    request.url.path = "/api/events"
    request.method = "GET"
    request.headers = {}
    request.query_params = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.100"
    return request


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.url = MagicMock()
    ws.url.path = "/api/events/stream"
    ws.query_params = {}
    ws.headers = {}
    ws.client = MagicMock()
    ws.client.host = "10.0.0.50"
    return ws


@pytest.fixture
def enable_api_key_auth():
    """Enable API key authentication with a test key."""
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = '["test-valid-key-12345"]'  # pragma: allowlist secret
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )
    get_settings.cache_clear()
    yield
    os.environ.pop("API_KEY_ENABLED", None)
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()


class TestAuthMiddlewareMissingKeyLogging:
    """Tests for logging when API key is missing."""

    @pytest.mark.asyncio
    async def test_missing_api_key_logs_warning(self, mock_request, enable_api_key_auth):
        """When API key is missing, a warning should be logged with security fields."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        call_next = AsyncMock()

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            # Verify 401 response
            assert response.status_code == 401

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "Authentication attempt without API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events"
            assert extra["method"] == "GET"
            assert extra["security_event"] is True
            assert extra["event_type"] == "auth_missing_key"

    @pytest.mark.asyncio
    async def test_missing_api_key_masks_client_ip(self, mock_request, enable_api_key_auth):
        """Client IP should be masked for privacy in security logs."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        call_next = AsyncMock()

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            extra = mock_logger.warning.call_args[1]["extra"]
            # IP should be masked (192.xxx.xxx.xxx)
            assert extra["client_ip"] == "192.xxx.xxx.xxx"
            # Original IP should NOT be in the log
            assert "192.168.1.100" not in str(extra)

    @pytest.mark.asyncio
    async def test_missing_api_key_handles_no_client(self, enable_api_key_auth):
        """When request has no client info, should log 'unknown' instead of crashing."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request = MagicMock()
        mock_request.url.path = "/api/events"
        mock_request.method = "POST"
        mock_request.headers = {}
        mock_request.query_params = {}
        mock_request.client = None  # No client info

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        call_next = AsyncMock()

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 401
            extra = mock_logger.warning.call_args[1]["extra"]
            assert extra["client_ip"] == "unknown"


class TestAuthMiddlewareInvalidKeyLogging:
    """Tests for logging when API key is invalid."""

    @pytest.mark.asyncio
    async def test_invalid_api_key_logs_warning(self, mock_request, enable_api_key_auth):
        """When API key is invalid, a warning should be logged with security fields."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request.headers = {"X-API-Key": "wrong-invalid-key"}

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        call_next = AsyncMock()

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            # Verify 401 response
            assert response.status_code == 401

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "Authentication attempt with invalid API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events"
            assert extra["method"] == "GET"
            assert extra["security_event"] is True
            assert extra["event_type"] == "auth_invalid_key"

    @pytest.mark.asyncio
    async def test_invalid_api_key_via_query_param(self, mock_request, enable_api_key_auth):
        """Invalid API key via query parameter should also be logged."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request.query_params = {"api_key": "bad-key-from-query"}  # pragma: allowlist secret

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        call_next = AsyncMock()

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 401
            extra = mock_logger.warning.call_args[1]["extra"]
            assert extra["event_type"] == "auth_invalid_key"


class TestWebSocketAuthLogging:
    """Tests for WebSocket authentication failure logging."""

    @pytest.mark.asyncio
    async def test_websocket_missing_key_logs_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has no API key, a warning should be logged."""
        with patch("backend.api.middleware.auth.logger") as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is False

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "WebSocket authentication attempt without API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events/stream"
            assert extra["security_event"] is True
            assert extra["event_type"] == "ws_auth_missing_key"
            # IP should be masked (10.xxx.xxx.xxx)
            assert extra["client_ip"] == "10.xxx.xxx.xxx"

    @pytest.mark.asyncio
    async def test_websocket_invalid_key_logs_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has invalid API key, a warning should be logged."""
        mock_websocket.query_params = {"api_key": "invalid-ws-key"}  # pragma: allowlist secret

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is False

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args

            # Verify log message
            assert "WebSocket authentication attempt with invalid API key" in call_args[0][0]

            # Verify extra fields
            extra = call_args[1]["extra"]
            assert extra["path"] == "/api/events/stream"
            assert extra["security_event"] is True
            assert extra["event_type"] == "ws_auth_invalid_key"

    @pytest.mark.asyncio
    async def test_websocket_valid_key_no_warning(self, mock_websocket, enable_api_key_auth):
        """When WebSocket has valid API key, no warning should be logged."""
        mock_websocket.query_params = {
            "api_key": "test-valid-key-12345"  # pragma: allowlist secret
        }

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            result = await validate_websocket_api_key(mock_websocket)

            assert result is True
            mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_handles_no_client(self, enable_api_key_auth):
        """When WebSocket has no client info, should log 'unknown'."""
        ws = MagicMock(spec=WebSocket)
        ws.url = MagicMock()
        ws.url.path = "/api/events/stream"
        ws.query_params = {}
        ws.headers = {}
        ws.client = None  # No client info

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            result = await validate_websocket_api_key(ws)

            assert result is False
            extra = mock_logger.warning.call_args[1]["extra"]
            assert extra["client_ip"] == "unknown"


class TestAuthMiddlewareNoLoggingOnSuccess:
    """Tests verifying no logging occurs on successful authentication."""

    @pytest.mark.asyncio
    async def test_valid_api_key_no_warning(self, mock_request, enable_api_key_auth):
        """When API key is valid, no warning should be logged."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request.headers = {"X-API-Key": "test-valid-key-12345"}

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            mock_logger.warning.assert_not_called()


class TestAuthMiddlewareDisabled:
    """Tests when API key authentication is disabled."""

    @pytest.mark.asyncio
    async def test_disabled_auth_no_logging(self, mock_request):
        """When auth is disabled, no security logging should occur."""
        from backend.api.middleware.auth import AuthMiddleware

        os.environ["API_KEY_ENABLED"] = "false"  # pragma: allowlist secret
        get_settings.cache_clear()

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            mock_logger.warning.assert_not_called()

        os.environ.pop("API_KEY_ENABLED", None)


class TestExemptPathsNoLogging:
    """Tests that exempt paths don't trigger auth logging."""

    @pytest.mark.asyncio
    async def test_health_endpoint_no_logging(self, enable_api_key_auth):
        """Health check endpoints should not trigger auth logging."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request = MagicMock()
        mock_request.url.path = "/health"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.query_params = {}

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_logging(self, enable_api_key_auth):
        """Metrics endpoint should not trigger auth logging."""
        from backend.api.middleware.auth import AuthMiddleware

        mock_request = MagicMock()
        mock_request.url.path = "/api/metrics"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.query_params = {}

        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        with patch("backend.api.middleware.auth.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            mock_logger.warning.assert_not_called()
