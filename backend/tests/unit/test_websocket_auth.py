"""Unit tests for WebSocket authentication (NEM-5316).

This module tests the hybrid WebSocket authentication system supporting:
1. Cookie-based authentication (web UI - session cookies sent automatically)
2. Query parameter authentication (API/mobile - ?token=<jwt>)
3. First-message authentication (fallback - auth message within timeout)

Tests follow TDD RED phase - they are designed to FAIL initially.

Authentication Priority:
- Cookie authentication is checked first (if present)
- Query parameter is checked second (if no cookie)
- First-message authentication is fallback (if neither cookie nor query param)

Token Refresh:
- Clients can send token_refresh messages to update their JWT
- Connection survives token expiration if refresh is sent in time

Close Codes:
- 4001: Authentication failure (invalid/missing credentials)
- 4002: Token expired (not refreshed in time)
- 1008: Policy violation (other auth issues)

Design Decisions (NEM-5315):
- Hybrid approach supports web browsers (cookies) and API clients (tokens)
- Constant-time comparison prevents timing attacks
- First-message timeout allows graceful fallback
- Token refresh enables long-lived connections
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

# These imports will fail initially (RED phase) - implementations don't exist yet
try:
    from backend.api.middleware.websocket_auth import (
        WebSocketAuthMethod,
        authenticate_websocket_cookie,
        authenticate_websocket_first_message,
        authenticate_websocket_jwt,
        extract_cookie_from_websocket,
        extract_jwt_from_query,
        handle_token_refresh,
        validate_session_cookie,
        validate_websocket_jwt,
        verify_websocket_auth,
    )
except ImportError:
    # Expected to fail in RED phase
    pass


# =============================================================================
# Cookie-Based Authentication Tests (Web UI)
# =============================================================================


class TestWebSocketCookieAuth:
    """Tests for cookie-based WebSocket authentication (web UI clients)."""

    @pytest.mark.asyncio
    async def test_websocket_accepts_valid_session_cookie(self):
        """Test that WebSocket accepts connection with valid session cookie.

        Web UI clients send session cookies automatically via browser.
        This is the primary authentication method for web clients.

        Expected behavior:
        - Extract session cookie from WebSocket headers
        - Validate cookie signature and expiration
        - Accept connection if cookie is valid
        """
        # Mock WebSocket with valid session cookie
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {
            "cookie": "session=valid_session_token_abc123; Path=/; HttpOnly"
        }
        mock_websocket.cookies = {"session": "valid_session_token_abc123"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        # Mock session validation to return valid user
        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_validate:
            mock_validate.return_value = {"user_id": "test_user", "exp": 9999999999}

            result = await authenticate_websocket_cookie(mock_websocket)

            assert result is True
            mock_websocket.accept.assert_not_called()
            mock_websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_session_cookie(self):
        """Test that WebSocket rejects connection with invalid session cookie.

        Invalid cookies include:
        - Malformed cookie strings
        - Invalid signatures
        - Tampered cookie data

        Expected behavior:
        - Extract cookie and attempt validation
        - Close with code 4001 if signature is invalid
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {"cookie": "session=invalid_tampered_token"}
        mock_websocket.cookies = {"session": "invalid_tampered_token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_validate:
            mock_validate.return_value = None  # Invalid cookie

            result = await authenticate_websocket_cookie(mock_websocket)

            assert result is False
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_called_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_websocket_rejects_expired_session_cookie(self):
        """Test that WebSocket rejects connection with expired session cookie.

        Expired cookies should be rejected even if signature is valid.

        Expected behavior:
        - Extract and validate cookie signature
        - Check expiration timestamp
        - Close with code 4002 if expired
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {"cookie": "session=expired_but_valid_signature"}
        mock_websocket.cookies = {"session": "expired_but_valid_signature"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_validate:
            mock_validate.return_value = {"user_id": "test_user", "exp": 0}  # Expired

            result = await authenticate_websocket_cookie(mock_websocket)

            assert result is False
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_called_once_with(code=4002)


# =============================================================================
# Query Parameter Authentication Tests (API/Mobile)
# =============================================================================


class TestWebSocketQueryParamAuth:
    """Tests for query parameter WebSocket authentication (API/mobile clients)."""

    @pytest.mark.asyncio
    async def test_websocket_accepts_valid_jwt_query_param(self):
        """Test that WebSocket accepts connection with valid JWT in query param.

        API and mobile clients use ?token=<jwt> for authentication.
        This is the primary method for programmatic access.

        Expected behavior:
        - Extract JWT from query parameter
        - Validate JWT signature and expiration
        - Accept connection if JWT is valid
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 9999999999}

            result = await authenticate_websocket_jwt(mock_websocket)

            assert result is True
            mock_websocket.accept.assert_not_called()
            mock_websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_jwt_query_param(self):
        """Test that WebSocket rejects connection with invalid JWT.

        Invalid JWTs include:
        - Malformed token structure
        - Invalid signatures
        - Wrong signing algorithm

        Expected behavior:
        - Extract JWT and attempt validation
        - Close with code 4001 if validation fails
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"token": "invalid.malformed.token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = None  # Invalid JWT

            result = await authenticate_websocket_jwt(mock_websocket)

            assert result is False
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_called_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_websocket_rejects_expired_jwt_query_param(self):
        """Test that WebSocket rejects connection with expired JWT.

        Expired JWTs should be rejected even if signature is valid.

        Expected behavior:
        - Validate JWT signature
        - Check expiration claim (exp)
        - Close with code 4002 if expired
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 0}  # Expired

            result = await authenticate_websocket_jwt(mock_websocket)

            assert result is False
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_called_once_with(code=4002)


# =============================================================================
# First-Message Authentication Tests (Fallback)
# =============================================================================


class TestWebSocketFirstMessageAuth:
    """Tests for first-message WebSocket authentication (fallback method)."""

    @pytest.mark.asyncio
    async def test_websocket_accepts_auth_first_message(self):
        """Test that WebSocket accepts authentication via first message.

        Clients can send authentication credentials in the first message:
        {"type": "auth", "token": "jwt_token_here"}

        Expected behavior:
        - Wait for first message (with timeout)
        - Validate credentials from message
        - Accept connection if valid
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            return_value='{"type": "auth", "token": "valid_jwt_token"}'
        )
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 9999999999}

            result = await authenticate_websocket_first_message(mock_websocket, timeout=5.0)

            assert result is True
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_timeout_without_auth_message(self):
        """Test that WebSocket times out if no auth message received.

        If client doesn't send auth message within timeout, close connection.

        Expected behavior:
        - Wait for first message with timeout (default 5 seconds)
        - Close with code 4001 if timeout exceeded
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_websocket.close = AsyncMock()

        result = await authenticate_websocket_first_message(mock_websocket, timeout=1.0)

        assert result is False
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=4001)

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_auth_message(self):
        """Test that WebSocket rejects invalid authentication message.

        Invalid messages include:
        - Missing "type" field
        - Wrong message type
        - Invalid token in message

        Expected behavior:
        - Receive and parse first message
        - Validate message format and credentials
        - Close with code 4001 if invalid
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            return_value='{"type": "auth", "token": "invalid_token"}'
        )
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = None  # Invalid token

            result = await authenticate_websocket_first_message(mock_websocket, timeout=5.0)

            assert result is False
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_called_once_with(code=4001)


# =============================================================================
# Authentication Priority Tests
# =============================================================================


class TestWebSocketAuthPriority:
    """Tests for WebSocket authentication priority and fallback logic."""

    @pytest.mark.asyncio
    async def test_websocket_prefers_cookie_over_query_param(self):
        """Test that cookie authentication is checked before query parameter.

        When both cookie and query param are present, cookie takes precedence.

        Expected behavior:
        - Check cookie first
        - Skip query param if cookie is valid
        - Use cookie credentials for connection
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.cookies = {"session": "valid_cookie_token"}
        mock_websocket.query_params = {"token": "valid_jwt_token"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_cookie:
            with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_jwt:
                mock_cookie.return_value = {"user_id": "user_from_cookie", "exp": 9999999999}
                mock_jwt.return_value = {"sub": "user_from_jwt", "exp": 9999999999}

                result, method = await verify_websocket_auth(mock_websocket)

                assert result is True
                assert method == WebSocketAuthMethod.COOKIE
                mock_cookie.assert_called_once()
                mock_jwt.assert_not_called()  # Should not check JWT if cookie valid

    @pytest.mark.asyncio
    async def test_websocket_falls_back_to_first_message(self):
        """Test that first-message auth is used when cookie and query param absent.

        Fallback chain: cookie → query param → first message

        Expected behavior:
        - Check cookie (not present)
        - Check query param (not present)
        - Wait for first message with auth credentials
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.cookies = {}
        mock_websocket.query_params = {}
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            return_value='{"type": "auth", "token": "valid_jwt_token"}'
        )
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_cookie:
            with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_jwt:
                mock_cookie.return_value = None  # No cookie
                mock_jwt.return_value = {"sub": "user_from_message", "exp": 9999999999}

                result, method = await verify_websocket_auth(mock_websocket, timeout=5.0)

                assert result is True
                assert method == WebSocketAuthMethod.FIRST_MESSAGE


# =============================================================================
# Token Refresh Tests
# =============================================================================


class TestWebSocketTokenRefresh:
    """Tests for WebSocket token refresh functionality."""

    @pytest.mark.asyncio
    async def test_websocket_token_refresh_message(self):
        """Test that WebSocket accepts token refresh message.

        Long-lived connections need to refresh tokens before expiration.

        Message format:
        {"type": "token_refresh", "token": "new_jwt_token"}

        Expected behavior:
        - Validate new token
        - Update connection credentials
        - Send acknowledgment
        """
        mock_websocket = MagicMock(spec=WebSocket)
        refresh_message = '{"type": "token_refresh", "token": "new_valid_jwt_token"}'

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 9999999999}

            result, new_creds = await handle_token_refresh(mock_websocket, refresh_message)

            assert result is True
            assert new_creds is not None
            assert new_creds["sub"] == "user_123"

    @pytest.mark.asyncio
    async def test_websocket_token_refresh_invalid_token(self):
        """Test that WebSocket rejects token refresh with invalid token.

        If refresh token is invalid, close connection.

        Expected behavior:
        - Validate new token
        - Close with code 4001 if invalid
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.close = AsyncMock()
        refresh_message = '{"type": "token_refresh", "token": "invalid_new_token"}'

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = None  # Invalid token

            result, new_creds = await handle_token_refresh(mock_websocket, refresh_message)

            assert result is False
            assert new_creds is None


# =============================================================================
# Close Code Tests
# =============================================================================


class TestWebSocketAuthCloseCodes:
    """Tests for WebSocket authentication close codes."""

    @pytest.mark.asyncio
    async def test_websocket_closes_with_4001_on_auth_failure(self):
        """Test that WebSocket uses code 4001 for authentication failures.

        Code 4001 indicates:
        - Invalid credentials (cookie/JWT/first-message)
        - Missing required authentication
        - Malformed authentication data

        This is distinct from 1008 (policy violation) used for other issues.
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.cookies = {}
        mock_websocket.query_params = {}
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(
            return_value='{"type": "auth", "token": "invalid"}'
        )
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = None  # Auth failure

            result, method = await verify_websocket_auth(mock_websocket)

            assert result is False
            mock_websocket.close.assert_called_once()
            # Verify close code is 4001
            call_args = mock_websocket.close.call_args
            assert call_args[1]["code"] == 4001 or call_args[0][0] == 4001

    @pytest.mark.asyncio
    async def test_websocket_closes_with_4002_on_token_expired(self):
        """Test that WebSocket uses code 4002 for token expiration.

        Code 4002 indicates:
        - Token was valid but has expired
        - Client should refresh token and reconnect

        This helps clients distinguish between auth failure and expiration.
        """
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"token": "expired_but_valid_signature"}
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 0}  # Expired

            result, method = await verify_websocket_auth(mock_websocket)

            assert result is False
            mock_websocket.close.assert_called_once()
            # Verify close code is 4002
            call_args = mock_websocket.close.call_args
            assert call_args[1]["code"] == 4002 or call_args[0][0] == 4002


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestWebSocketAuthHelpers:
    """Tests for WebSocket authentication helper functions."""

    def test_extract_cookie_from_websocket(self):
        """Test extraction of session cookie from WebSocket headers."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.cookies = {"session": "cookie_value_123"}

        cookie = extract_cookie_from_websocket(mock_websocket)

        assert cookie == "cookie_value_123"

    def test_extract_cookie_from_websocket_missing(self):
        """Test extraction returns None when cookie is missing."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.cookies = {}

        cookie = extract_cookie_from_websocket(mock_websocket)

        assert cookie is None

    def test_extract_jwt_from_query(self):
        """Test extraction of JWT from query parameters."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"token": "jwt_token_abc"}

        jwt = extract_jwt_from_query(mock_websocket)

        assert jwt == "jwt_token_abc"

    def test_extract_jwt_from_query_missing(self):
        """Test extraction returns None when query param is missing."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}

        jwt = extract_jwt_from_query(mock_websocket)

        assert jwt is None

    def test_validate_session_cookie_constant_time_comparison(self):
        """Test that cookie validation uses constant-time comparison.

        Security requirement: prevent timing attacks by using hmac.compare_digest.
        This was already implemented for API keys (NEM-5315).
        """
        valid_cookie = "secure_session_token_123"

        # This test verifies the function uses constant-time comparison
        # Implementation should use hmac.compare_digest()
        with patch("hmac.compare_digest", return_value=True) as mock_compare:
            result = validate_session_cookie(valid_cookie)

            assert result is not None
            mock_compare.assert_called()

    def test_validate_websocket_jwt_constant_time_comparison(self):
        """Test that JWT validation uses constant-time comparison.

        Security requirement: prevent timing attacks by using hmac.compare_digest.
        """
        valid_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid"

        with patch("hmac.compare_digest", return_value=True) as mock_compare:
            result = validate_websocket_jwt(valid_jwt)

            assert result is not None
            mock_compare.assert_called()
