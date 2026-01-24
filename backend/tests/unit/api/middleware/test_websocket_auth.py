"""Unit tests for WebSocket token authentication middleware.

Tests the optional token-based authentication for WebSocket connections
as specified in NEM-1650.

Test coverage:
- No token configured: connections allowed without token
- Token configured + correct token: connection allowed
- Token configured + wrong token: connection rejected
- Token configured + missing token: connection rejected
- Constant-time comparison for token validation

Note: This test file uses hardcoded test tokens which trigger S105/S106 security
warnings. These are intentional test fixtures, not real secrets.
"""

# Test tokens are not real secrets

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import WebSocket, status

from backend.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear settings cache before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket with query params support."""
    ws = MagicMock(spec=WebSocket)
    ws.query_params = {}
    return ws


@pytest.fixture
def mock_websocket_with_token():
    """Create a mock WebSocket with a token query parameter."""
    ws = MagicMock(spec=WebSocket)
    ws.query_params = {"token": "test-secret-token-12345"}
    return ws


class TestValidateWebSocketTokenNoTokenConfigured:
    """Tests when no WEBSOCKET_TOKEN is configured (single-user mode)."""

    @pytest.mark.asyncio
    async def test_allows_connection_without_token(self, mock_websocket):
        """When no token is configured, connections without token are allowed."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        # Ensure no token is configured
        os.environ.pop("WEBSOCKET_TOKEN", None)
        get_settings.cache_clear()

        result = await validate_websocket_token(mock_websocket, token=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_allows_connection_with_any_token(self, mock_websocket_with_token):
        """When no token is configured, connections with any token are allowed."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        # Ensure no token is configured
        os.environ.pop("WEBSOCKET_TOKEN", None)
        get_settings.cache_clear()

        result = await validate_websocket_token(mock_websocket_with_token, token="random-token-xyz")
        assert result is True

    @pytest.mark.asyncio
    async def test_allows_connection_with_empty_string_config(self, mock_websocket):
        """When WEBSOCKET_TOKEN is empty string, treat as disabled."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        os.environ["WEBSOCKET_TOKEN"] = ""
        get_settings.cache_clear()

        result = await validate_websocket_token(mock_websocket, token=None)
        assert result is True

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)


class TestValidateWebSocketTokenWithTokenConfigured:
    """Tests when WEBSOCKET_TOKEN is configured."""

    @pytest.mark.asyncio
    async def test_allows_correct_token(self, mock_websocket):
        """When token matches configured value, connection is allowed."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        secret_token = "my-super-secret-token-abc123"  # pragma: allowlist secret
        os.environ["WEBSOCKET_TOKEN"] = secret_token
        get_settings.cache_clear()

        result = await validate_websocket_token(mock_websocket, token=secret_token)
        assert result is True

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)

    @pytest.mark.asyncio
    async def test_rejects_wrong_token(self, mock_websocket):
        """When token does not match, WebSocketException is raised."""
        from fastapi import WebSocketException

        from backend.api.middleware.websocket_auth import validate_websocket_token

        secret_token = "correct-secret-token"  # pragma: allowlist secret
        os.environ["WEBSOCKET_TOKEN"] = secret_token
        get_settings.cache_clear()

        with pytest.raises(WebSocketException) as exc_info:
            await validate_websocket_token(mock_websocket, token="wrong-token")

        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
        assert "Invalid authentication token" in exc_info.value.reason

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self, mock_websocket):
        """When token is required but not provided, WebSocketException is raised."""
        from fastapi import WebSocketException

        from backend.api.middleware.websocket_auth import validate_websocket_token

        os.environ["WEBSOCKET_TOKEN"] = "required-token"
        get_settings.cache_clear()

        with pytest.raises(WebSocketException) as exc_info:
            await validate_websocket_token(mock_websocket, token=None)

        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
        assert "Authentication token required" in exc_info.value.reason

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)

    @pytest.mark.asyncio
    async def test_rejects_empty_token(self, mock_websocket):
        """When token is required but empty string provided, WebSocketException is raised."""
        from fastapi import WebSocketException

        from backend.api.middleware.websocket_auth import validate_websocket_token

        os.environ["WEBSOCKET_TOKEN"] = "required-token"
        get_settings.cache_clear()

        with pytest.raises(WebSocketException) as exc_info:
            await validate_websocket_token(mock_websocket, token="")

        assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
        assert "Authentication token required" in exc_info.value.reason

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)


class TestTokenComparisonSecurity:
    """Tests for secure token comparison (timing attack resistance)."""

    @pytest.mark.asyncio
    async def test_uses_constant_time_comparison(self, mock_websocket):
        """Verify that hmac.compare_digest is used for token comparison."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        secret_token = "secure-token-for-timing-test"  # pragma: allowlist secret
        os.environ["WEBSOCKET_TOKEN"] = secret_token
        get_settings.cache_clear()

        # Patch hmac.compare_digest to verify it's being called
        with patch("backend.api.middleware.websocket_auth.hmac.compare_digest") as mock_compare:
            mock_compare.return_value = True

            result = await validate_websocket_token(mock_websocket, token=secret_token)

            assert result is True
            mock_compare.assert_called_once_with(secret_token, secret_token)

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)

    @pytest.mark.asyncio
    async def test_case_sensitive_comparison(self, mock_websocket):
        """Token comparison should be case-sensitive."""
        from fastapi import WebSocketException

        from backend.api.middleware.websocket_auth import validate_websocket_token

        os.environ["WEBSOCKET_TOKEN"] = "SecretToken123"
        get_settings.cache_clear()

        # Lowercase version should fail
        with pytest.raises(WebSocketException):
            await validate_websocket_token(mock_websocket, token="secrettoken123")

        # Uppercase version should fail
        with pytest.raises(WebSocketException):
            await validate_websocket_token(mock_websocket, token="SECRETTOKEN123")

        # Correct case should pass
        result = await validate_websocket_token(mock_websocket, token="SecretToken123")
        assert result is True

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)


class TestTokenFromQueryParameter:
    """Tests for extracting token from query parameter."""

    @pytest.mark.asyncio
    async def test_extracts_token_from_query_param(self):
        """Token should be extracted from ?token= query parameter."""
        from backend.api.middleware.websocket_auth import validate_websocket_token

        secret_token = "query-param-token"  # pragma: allowlist secret
        os.environ["WEBSOCKET_TOKEN"] = secret_token
        get_settings.cache_clear()

        # Create a mock websocket - the token is passed directly to the function
        # via FastAPI's Query dependency, so we test the function signature
        mock_ws = MagicMock(spec=WebSocket)

        result = await validate_websocket_token(mock_ws, token=secret_token)
        assert result is True

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)


class TestConfigSetting:
    """Tests for the websocket_token configuration setting."""

    def test_websocket_token_default_is_none(self):
        """websocket_token should default to None (disabled)."""
        # Ensure env var is not set
        os.environ.pop("WEBSOCKET_TOKEN", None)
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.websocket_token is None

    def test_websocket_token_reads_from_env(self):
        """websocket_token should read from WEBSOCKET_TOKEN env var."""
        test_token = "env-configured-token-xyz"
        os.environ["WEBSOCKET_TOKEN"] = test_token
        get_settings.cache_clear()

        settings = get_settings()
        # websocket_token is now SecretStr, so we need to get the actual value
        token_value = (
            settings.websocket_token.get_secret_value()
            if settings.websocket_token and hasattr(settings.websocket_token, "get_secret_value")
            else settings.websocket_token
        )
        assert token_value == test_token

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)

    def test_websocket_token_empty_string_treated_as_none(self):
        """Empty WEBSOCKET_TOKEN should be treated as None (disabled)."""
        os.environ["WEBSOCKET_TOKEN"] = ""
        get_settings.cache_clear()

        settings = get_settings()
        # Empty string should be falsy, so validation should be skipped
        assert not settings.websocket_token

        # Cleanup
        os.environ.pop("WEBSOCKET_TOKEN", None)


class TestIntegrationWithWebSocketRoutes:
    """Integration-style tests for WebSocket routes with token auth."""

    @pytest.mark.asyncio
    async def test_dependency_signature(self):
        """Verify validate_websocket_token can be used as a FastAPI dependency."""
        import inspect

        from backend.api.middleware.websocket_auth import validate_websocket_token

        # Check that it's an async function
        assert inspect.iscoroutinefunction(validate_websocket_token)

        # Check function signature includes WebSocket and token parameters
        sig = inspect.signature(validate_websocket_token)
        params = list(sig.parameters.keys())
        assert "websocket" in params
        assert "token" in params
