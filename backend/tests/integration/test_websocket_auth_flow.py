"""Integration tests for WebSocket authentication flows (NEM-5316).

This module tests end-to-end WebSocket authentication flows:
1. Full connection lifecycle with different auth methods
2. Token refresh during active connections
3. Session invalidation and reconnection
4. Interaction between auth and existing WebSocket features

Tests follow TDD RED phase - they are designed to FAIL initially.

Authentication Methods Tested:
- Session cookies (web UI)
- JWT tokens via query parameter (API/mobile)
- JWT tokens via first message (fallback)
- API keys (existing functionality, tested for compatibility)

Integration Points:
- WebSocket endpoints (/ws/events, /ws/system, /ws/detections)
- Event broadcasting and subscriptions
- Rate limiting interaction with auth
- Idle timeout with token refresh

Design Reference: NEM-5315 (research findings and approved design)
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _get_common_lifespan_mocks():
    """Create common mock objects for all lifespan services.

    Returns a dict with all mock objects needed for fast test startup.
    These mocks prevent real services from initializing during TestClient creation.
    """
    # Mock Redis client
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Mock background services (abbreviated for test performance)
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.connect = AsyncMock()
    mock_event_broadcaster.disconnect = AsyncMock()

    return {
        "redis_client": mock_redis_client,
        "system_broadcaster": mock_system_broadcaster,
        "gpu_monitor": mock_gpu_monitor,
        "cleanup_service": mock_cleanup_service,
        "event_broadcaster": mock_event_broadcaster,
    }


def _apply_common_lifespan_patches(stack, mocks):
    """Apply all common lifespan service patches to an ExitStack."""

    async def mock_init_db():
        pass

    async def mock_close_db():
        pass

    async def mock_seed_cameras():
        return 0

    async def mock_validate_cameras():
        return (0, 0)

    # Core patches
    stack.enter_context(patch("backend.core.redis._redis_client", mocks["redis_client"]))
    stack.enter_context(patch("backend.main.init_db", mock_init_db))
    stack.enter_context(patch("backend.core.database.close_db", mock_close_db))
    stack.enter_context(patch("backend.main.seed_cameras_if_empty", mock_seed_cameras))
    stack.enter_context(
        patch("backend.main.validate_camera_paths_on_startup", mock_validate_cameras)
    )
    stack.enter_context(
        patch("backend.main.get_system_broadcaster", return_value=mocks["system_broadcaster"])
    )
    stack.enter_context(patch("backend.main.GPUMonitor", return_value=mocks["gpu_monitor"]))
    stack.enter_context(patch("backend.main.CleanupService", return_value=mocks["cleanup_service"]))
    stack.enter_context(
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mocks["event_broadcaster"]))
    )


# =============================================================================
# WebSocket Events Endpoint Authentication Tests
# =============================================================================


class TestWebSocketEventsAuthFlow:
    """Integration tests for /ws/events endpoint with various auth methods."""

    @pytest.fixture
    def auth_client(self):
        """Create test client with hybrid auth enabled."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        # Store original environment
        original_api_key = os.environ.get("API_KEY_ENABLED")
        original_jwt_secret = os.environ.get("JWT_SECRET")

        # Enable hybrid auth
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["test_api_key_123"]'
        os.environ["JWT_SECRET"] = "test_jwt_secret_key_for_testing"
        os.environ["SESSION_SECRET"] = "test_session_secret_key"

        get_settings.cache_clear()

        # Get common mocks and apply patches
        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        # Restore environment
        if original_api_key:
            os.environ["API_KEY_ENABLED"] = original_api_key
        else:
            os.environ.pop("API_KEY_ENABLED", None)

        if original_jwt_secret:
            os.environ["JWT_SECRET"] = original_jwt_secret
        else:
            os.environ.pop("JWT_SECRET", None)

        get_settings.cache_clear()

    def test_websocket_events_requires_auth(self, auth_client):
        """Test that /ws/events requires authentication when auth is enabled.

        Expected behavior:
        - Connection without credentials should be rejected
        - Close code should be 4001 (auth failure)
        """
        with auth_client.websocket_connect("/ws/events") as websocket:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            # Should close with 4001 (auth failure)
            assert exc_info.value.code == 4001

    def test_websocket_events_with_session_cookie(self, auth_client):
        """Test that /ws/events accepts valid session cookie.

        Web UI clients send session cookies automatically.

        Expected behavior:
        - Extract session cookie from headers
        - Validate cookie signature and expiration
        - Accept connection and receive events
        """
        # Generate valid session cookie
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie"
        ) as mock_validate:
            mock_validate.return_value = {"user_id": "test_user", "exp": 9999999999}

            # Mock cookie in headers (simulating browser behavior)
            headers = {"cookie": "session=valid_session_cookie_abc123"}

            with auth_client.websocket_connect("/ws/events", headers=headers) as websocket:
                # Should be connected without close
                assert websocket is not None
                # Can send ping to verify connection is alive
                websocket.send_text(json.dumps({"type": "ping"}))
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "pong"

    def test_websocket_events_with_jwt_token(self, auth_client):
        """Test that /ws/events accepts valid JWT token in query parameter.

        API/mobile clients use ?token=<jwt> for authentication.

        Expected behavior:
        - Extract JWT from query parameter
        - Validate JWT signature and expiration
        - Accept connection and receive events
        """
        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "user_123", "exp": 9999999999}

            with auth_client.websocket_connect(
                "/ws/events?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid"
            ) as websocket:
                # Should be connected
                assert websocket is not None
                # Verify connection is functional
                websocket.send_text(json.dumps({"type": "ping"}))
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "pong"

    def test_websocket_events_with_api_key(self, auth_client):
        """Test that /ws/events still accepts API key (existing functionality).

        Backward compatibility: existing API key auth should continue working.

        Expected behavior:
        - Extract API key from query parameter
        - Validate using existing auth logic
        - Accept connection
        """
        with auth_client.websocket_connect("/ws/events?api_key=test_api_key_123") as websocket:
            # Should be connected (existing auth still works)
            assert websocket is not None
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            data = json.loads(response)
            assert data["type"] == "pong"


# =============================================================================
# Token Refresh Integration Tests
# =============================================================================


class TestWebSocketTokenRefreshFlow:
    """Integration tests for token refresh during active WebSocket connections."""

    @pytest.fixture
    def refresh_client(self):
        """Create test client with token refresh enabled."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        original_jwt_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "test_jwt_secret_key_for_refresh"

        get_settings.cache_clear()

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        if original_jwt_secret:
            os.environ["JWT_SECRET"] = original_jwt_secret
        else:
            os.environ.pop("JWT_SECRET", None)

        get_settings.cache_clear()

    @pytest.mark.xfail(reason="Token refresh feature not yet implemented (TDD RED phase)")
    def test_websocket_connection_survives_token_refresh(self, refresh_client):
        """Test that WebSocket connection remains active after token refresh.

        Long-lived connections need to refresh tokens before expiration.

        Expected behavior:
        - Connect with initial JWT token
        - Send token_refresh message with new token
        - Connection remains active
        - Can continue receiving events
        """
        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            # First token is valid
            mock_validate.return_value = {"sub": "user_123", "exp": 9999999999}

            with refresh_client.websocket_connect(
                "/ws/events?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.initial"
            ) as websocket:
                # Connection established
                assert websocket is not None

                # Send token refresh message
                refresh_message = {
                    "type": "token_refresh",
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refreshed",
                }
                websocket.send_text(json.dumps(refresh_message))

                # Should receive acknowledgment
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "token_refresh_ack"
                assert data.get("success") is True

                # Connection should still be alive
                websocket.send_text(json.dumps({"type": "ping"}))
                pong_response = websocket.receive_text()
                pong_data = json.loads(pong_response)
                assert pong_data["type"] == "pong"


# =============================================================================
# Session Invalidation Tests
# =============================================================================


class TestWebSocketSessionInvalidation:
    """Integration tests for session invalidation and disconnection."""

    @pytest.fixture
    def session_client(self):
        """Create test client with session management enabled."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        original_session_secret = os.environ.get("SESSION_SECRET")
        os.environ["SESSION_SECRET"] = "test_session_secret_key"

        get_settings.cache_clear()

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        if original_session_secret:
            os.environ["SESSION_SECRET"] = original_session_secret
        else:
            os.environ.pop("SESSION_SECRET", None)

        get_settings.cache_clear()

    @pytest.mark.xfail(reason="Session invalidation feature not yet implemented (TDD RED phase)")
    def test_websocket_disconnects_on_session_invalidation(self, session_client):
        """Test that WebSocket disconnects when session is invalidated.

        Session invalidation triggers:
        - User logout
        - Session timeout
        - Security event (password change, etc.)

        Expected behavior:
        - WebSocket connection is active with valid session
        - Session is invalidated (simulated)
        - WebSocket receives disconnect signal
        - Connection closes with code 4002 (token expired)
        """
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie"
        ) as mock_validate:
            # Initially valid session
            mock_validate.return_value = {"user_id": "test_user", "exp": 9999999999}

            headers = {"cookie": "session=valid_session_cookie"}

            with session_client.websocket_connect("/ws/events", headers=headers) as websocket:
                # Connection established
                assert websocket is not None

                # Simulate session invalidation (mock returns None)
                mock_validate.return_value = None

                # Server should detect invalid session and close connection
                # This would happen on next heartbeat or message validation
                # For testing, we can simulate by sending a message that triggers validation
                websocket.send_text(json.dumps({"type": "ping"}))

                # Should receive disconnect
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    websocket.receive_text()

                # Should close with 4002 (token/session expired)
                assert exc_info.value.code == 4002


# =============================================================================
# System Status WebSocket Authentication Tests
# =============================================================================


class TestWebSocketSystemAuthFlow:
    """Integration tests for /ws/system endpoint with various auth methods."""

    @pytest.fixture
    def system_auth_client(self):
        """Create test client for system status endpoint with auth."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        original_jwt_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "test_jwt_secret_system"

        get_settings.cache_clear()

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        if original_jwt_secret:
            os.environ["JWT_SECRET"] = original_jwt_secret
        else:
            os.environ.pop("JWT_SECRET", None)

        get_settings.cache_clear()

    def test_websocket_system_with_jwt_auth(self, system_auth_client):
        """Test that /ws/system accepts JWT authentication.

        System status endpoint should support same auth methods as events.

        Expected behavior:
        - Connect with JWT token
        - Receive system status updates
        - Auth is validated before accepting connection
        """
        with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_validate:
            mock_validate.return_value = {"sub": "admin_user", "exp": 9999999999}

            with system_auth_client.websocket_connect(
                "/ws/system?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.system_token"
            ) as websocket:
                # Should be connected
                assert websocket is not None

                # Should receive system status update
                # (SystemBroadcaster sends initial status on connect)
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] in ["system_status", "ping"]


# =============================================================================
# Detections WebSocket Authentication Tests
# =============================================================================


class TestWebSocketDetectionsAuthFlow:
    """Integration tests for /ws/detections endpoint with various auth methods."""

    @pytest.fixture
    def detections_auth_client(self):
        """Create test client for detections endpoint with auth."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        original_jwt_secret = os.environ.get("JWT_SECRET")
        os.environ["JWT_SECRET"] = "test_jwt_secret_detections"

        get_settings.cache_clear()

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        if original_jwt_secret:
            os.environ["JWT_SECRET"] = original_jwt_secret
        else:
            os.environ.pop("JWT_SECRET", None)

        get_settings.cache_clear()

    def test_websocket_detections_with_cookie_auth(self, detections_auth_client):
        """Test that /ws/detections accepts cookie authentication.

        Detections endpoint should support same auth methods.

        Expected behavior:
        - Connect with session cookie
        - Receive detection events
        - Subscribe to detection.* events automatically
        """
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie"
        ) as mock_validate:
            mock_validate.return_value = {"user_id": "test_user", "exp": 9999999999}

            headers = {"cookie": "session=valid_detection_session"}

            with detections_auth_client.websocket_connect(
                "/ws/detections", headers=headers
            ) as websocket:
                # Should be connected
                assert websocket is not None

                # Verify connection is functional
                websocket.send_text(json.dumps({"type": "ping"}))
                response = websocket.receive_text()
                data = json.loads(response)
                assert data["type"] == "pong"


# =============================================================================
# Auth Priority Integration Tests
# =============================================================================


class TestWebSocketAuthPriorityIntegration:
    """Integration tests for authentication method priority in real endpoints."""

    @pytest.fixture
    def priority_client(self):
        """Create test client for testing auth priority."""
        import os

        from backend.core.config import get_settings
        from backend.main import app

        original_jwt_secret = os.environ.get("JWT_SECRET")
        original_session_secret = os.environ.get("SESSION_SECRET")

        os.environ["JWT_SECRET"] = "test_jwt_secret_priority"
        os.environ["SESSION_SECRET"] = "test_session_secret_priority"

        get_settings.cache_clear()

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            client = stack.enter_context(TestClient(app))
            yield client

        if original_jwt_secret:
            os.environ["JWT_SECRET"] = original_jwt_secret
        else:
            os.environ.pop("JWT_SECRET", None)

        if original_session_secret:
            os.environ["SESSION_SECRET"] = original_session_secret
        else:
            os.environ.pop("SESSION_SECRET", None)

        get_settings.cache_clear()

    def test_websocket_cookie_takes_precedence_over_query_param(self, priority_client):
        """Test that cookie auth is used when both cookie and query param present.

        Expected behavior:
        - Both cookie and JWT token are provided
        - Cookie is validated first
        - Connection uses cookie credentials
        - Query param JWT is ignored
        """
        with patch("backend.api.middleware.websocket_auth.validate_session_cookie") as mock_cookie:
            with patch("backend.api.middleware.websocket_auth.validate_websocket_jwt") as mock_jwt:
                # Both return valid credentials
                mock_cookie.return_value = {"user_id": "cookie_user", "exp": 9999999999}
                mock_jwt.return_value = {"sub": "jwt_user", "exp": 9999999999}

                headers = {"cookie": "session=valid_cookie"}

                with priority_client.websocket_connect(
                    "/ws/events?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.jwt_token",
                    headers=headers,
                ) as websocket:
                    # Should be connected
                    assert websocket is not None

                    # Cookie should have been checked
                    mock_cookie.assert_called()

                    # JWT should NOT have been checked (cookie took precedence)
                    mock_jwt.assert_not_called()
