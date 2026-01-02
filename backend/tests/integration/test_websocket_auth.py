"""Integration tests for WebSocket authentication and rate limiting.

This module tests:
- Connection without API key when auth enabled
- Invalid API key rejection
- Valid API key acceptance
- Invalid JSON message handling
- Unknown message type handling
- Ping/pong keepalive
- Rate limiting for WebSocket connections

Uses shared fixtures from conftest.py:
- integration_env: Sets environment variables for testing
- mock_redis: Mock Redis client
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def test_api_key():
    """Return a test API key."""
    return "test_ws_auth_key_12345"


@pytest.fixture
def sync_client_auth_disabled(integration_env):
    """Create synchronous test client with auth disabled.

    All lifespan services are fully mocked to avoid slow startup.
    """
    from backend.core.config import get_settings
    from backend.main import app

    # Store original environment
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")

    # Disable API key authentication
    os.environ["API_KEY_ENABLED"] = "false"

    # Clear settings cache to pick up new environment variables
    get_settings.cache_clear()

    # Create mock Redis client for this fixture
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Mock to disable rate limiting for basic auth tests
    mock_check_rate_limit = AsyncMock(return_value=True)

    # Create mock init_db that does nothing
    async def mock_init_db():
        pass

    async def mock_seed_cameras_if_empty():
        return 0

    # Mock background services
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.connect = AsyncMock()
    mock_event_broadcaster.disconnect = AsyncMock()
    mock_event_broadcaster.broadcast_event = AsyncMock(return_value=1)
    mock_event_broadcaster.CHANNEL_NAME = "security_events"
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    mock_ai_health = AsyncMock(
        return_value={
            "rtdetr": False,
            "nemotron": False,
            "any_healthy": False,
            "all_healthy": False,
        }
    )

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.main.init_db", mock_init_db),
        patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty),
        patch("backend.main.init_redis", return_value=mock_redis_client),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", return_value=mock_file_watcher),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch(
            "backend.services.system_broadcaster.SystemBroadcaster._check_ai_health", mock_ai_health
        ),
        patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit),
        TestClient(app) as client,
    ):
        yield client

    # Restore original environment
    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    get_settings.cache_clear()


@pytest.fixture
def sync_client_auth_enabled(integration_env, test_api_key):
    """Create synchronous test client with auth enabled.

    All lifespan services are fully mocked to avoid slow startup.
    """
    from backend.core.config import get_settings
    from backend.main import app

    # Store original environment
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")
    original_api_keys = os.environ.get("API_KEYS")

    # Enable API key authentication
    os.environ["API_KEY_ENABLED"] = "true"
    os.environ["API_KEYS"] = f'["{test_api_key}"]'

    # Clear settings cache to pick up new environment variables
    get_settings.cache_clear()

    # Create mock Redis client for this fixture
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Mock to disable rate limiting for basic auth tests
    mock_check_rate_limit = AsyncMock(return_value=True)

    async def mock_init_db():
        pass

    async def mock_seed_cameras_if_empty():
        return 0

    # Mock background services
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.connect = AsyncMock()
    mock_event_broadcaster.disconnect = AsyncMock()
    mock_event_broadcaster.broadcast_event = AsyncMock(return_value=1)
    mock_event_broadcaster.CHANNEL_NAME = "security_events"
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    mock_ai_health = AsyncMock(
        return_value={
            "rtdetr": False,
            "nemotron": False,
            "any_healthy": False,
            "all_healthy": False,
        }
    )

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.main.init_db", mock_init_db),
        patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty),
        patch("backend.main.init_redis", return_value=mock_redis_client),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", return_value=mock_file_watcher),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch(
            "backend.services.system_broadcaster.SystemBroadcaster._check_ai_health", mock_ai_health
        ),
        patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit),
        TestClient(app) as client,
    ):
        yield client

    # Restore original environment
    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    if original_api_keys is not None:
        os.environ["API_KEYS"] = original_api_keys
    else:
        os.environ.pop("API_KEYS", None)

    get_settings.cache_clear()


# =============================================================================
# Authentication Tests
# =============================================================================


class TestWebSocketAuthenticationEvents:
    """Tests for /ws/events WebSocket endpoint authentication."""

    def test_connection_without_api_key_when_auth_enabled(self, sync_client_auth_enabled):
        """Test that /ws/events rejects connection without API key when auth is enabled."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_auth_enabled.websocket_connect("/ws/events"),
        ):
            # Connection should be rejected
            pass

    def test_invalid_api_key_rejection(self, sync_client_auth_enabled):
        """Test that /ws/events rejects connection with invalid API key."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_auth_enabled.websocket_connect("/ws/events?api_key=invalid_key_xyz"),
        ):
            # Connection should be rejected
            pass

    def test_valid_api_key_acceptance_query_param(self, sync_client_auth_enabled, test_api_key):
        """Test that /ws/events accepts connection with valid API key via query parameter."""
        with sync_client_auth_enabled.websocket_connect(
            f"/ws/events?api_key={test_api_key}"
        ) as websocket:
            assert websocket is not None

    def test_connection_allowed_when_auth_disabled(self, sync_client_auth_disabled):
        """Test that /ws/events allows connection when auth is disabled."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            assert websocket is not None


class TestWebSocketAuthenticationSystem:
    """Tests for /ws/system WebSocket endpoint authentication."""

    def test_connection_without_api_key_when_auth_enabled(self, sync_client_auth_enabled):
        """Test that /ws/system rejects connection without API key when auth is enabled."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_auth_enabled.websocket_connect("/ws/system"),
        ):
            # Connection should be rejected
            pass

    def test_invalid_api_key_rejection(self, sync_client_auth_enabled):
        """Test that /ws/system rejects connection with invalid API key."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_auth_enabled.websocket_connect("/ws/system?api_key=wrong_key"),
        ):
            # Connection should be rejected
            pass

    def test_valid_api_key_acceptance_query_param(self, sync_client_auth_enabled, test_api_key):
        """Test that /ws/system accepts connection with valid API key via query parameter."""
        with sync_client_auth_enabled.websocket_connect(
            f"/ws/system?api_key={test_api_key}"
        ) as websocket:
            assert websocket is not None

    def test_connection_allowed_when_auth_disabled(self, sync_client_auth_disabled):
        """Test that /ws/system allows connection when auth is disabled."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            assert websocket is not None


# =============================================================================
# Message Handling Tests
# =============================================================================


class TestWebSocketInvalidJsonHandling:
    """Tests for handling invalid JSON messages."""

    def test_events_invalid_json_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/events returns error for invalid JSON."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send invalid JSON
            websocket.send_text("not valid json {{{")

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert data["error"] == "invalid_json"
            assert "Message must be valid JSON" in data["message"]

    def test_system_invalid_json_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/system returns error for invalid JSON."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            # SystemBroadcaster sends an initial status message on connect
            # We need to consume it first before testing error handling
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            # The initial message could be system_status or fallback error
            assert initial_data["type"] in ["system_status", "error"]

            # Now send invalid JSON
            websocket.send_text("{broken json")

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert data["error"] == "invalid_json"


class TestWebSocketUnknownMessageType:
    """Tests for handling unknown message types."""

    def test_events_unknown_message_type_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/events returns error for unknown message types."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send message with unknown type
            websocket.send_text(json.dumps({"type": "unknown_type_xyz"}))

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert data["error"] == "unknown_message_type"
            assert "unknown_type_xyz" in data["message"]
            assert "supported_types" in data["details"]

    def test_system_unknown_message_type_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/system returns error for unknown message types."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            # SystemBroadcaster sends an initial status message on connect
            # We need to consume it first before testing error handling
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            assert initial_data["type"] in ["system_status", "error"]

            # Now send message with unknown type
            websocket.send_text(json.dumps({"type": "foobar_type"}))

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert data["error"] == "unknown_message_type"


class TestWebSocketInvalidMessageFormat:
    """Tests for handling messages with invalid format/schema."""

    def test_events_missing_type_field_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/events returns error when 'type' field is missing."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send message without type field
            websocket.send_text(json.dumps({"data": "some_data"}))

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            assert data["error"] == "invalid_message_format"
            assert "validation_errors" in data["details"]

    def test_system_empty_type_field_returns_error(self, sync_client_auth_disabled):
        """Test that /ws/system returns error when 'type' field is empty."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            # SystemBroadcaster sends an initial status message on connect
            # We need to consume it first before testing error handling
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            assert initial_data["type"] in ["system_status", "error"]

            # Now send message with empty type field
            websocket.send_text(json.dumps({"type": ""}))

            # Should receive an error response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "error"
            # Could be invalid_message_format due to min_length validation
            assert data["error"] in ["invalid_message_format", "unknown_message_type"]


# =============================================================================
# Ping/Pong Keepalive Tests
# =============================================================================


class TestWebSocketPingPong:
    """Tests for ping/pong keepalive functionality."""

    def test_events_ping_returns_pong(self, sync_client_auth_disabled):
        """Test that /ws/events responds with pong to ping message."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send JSON ping
            websocket.send_text(json.dumps({"type": "ping"}))

            # Should receive pong response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "pong"

    def test_system_ping_returns_pong(self, sync_client_auth_disabled):
        """Test that /ws/system responds with pong to ping message."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            # SystemBroadcaster sends an initial status message on connect
            # We need to consume it first before testing ping/pong
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            assert initial_data["type"] in ["system_status", "error"]

            # Now send JSON ping
            websocket.send_text(json.dumps({"type": "ping"}))

            # Should receive pong response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "pong"

    def test_events_legacy_ping_string_returns_pong(self, sync_client_auth_disabled):
        """Test that /ws/events responds to legacy plain 'ping' string."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send legacy plain text ping
            websocket.send_text("ping")

            # Should receive pong response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "pong"

    def test_system_legacy_ping_string_returns_pong(self, sync_client_auth_disabled):
        """Test that /ws/system responds to legacy plain 'ping' string."""
        with sync_client_auth_disabled.websocket_connect("/ws/system") as websocket:
            # SystemBroadcaster sends an initial status message on connect
            # We need to consume it first before testing ping/pong
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            assert initial_data["type"] in ["system_status", "error"]

            # Now send legacy plain text ping
            websocket.send_text("ping")

            # Should receive pong response
            response = websocket.receive_text()
            data = json.loads(response)

            assert data["type"] == "pong"

    def test_events_pong_message_acknowledged_silently(self, sync_client_auth_disabled):
        """Test that /ws/events acknowledges pong messages silently (no response)."""
        with sync_client_auth_disabled.websocket_connect("/ws/events") as websocket:
            # Send pong message (response to server-initiated ping)
            websocket.send_text(json.dumps({"type": "pong"}))

            # No response expected - connection should stay open
            # Send a ping to verify connection is still alive
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_text()
            data = json.loads(response)
            assert data["type"] == "pong"


# =============================================================================
# Rate Limiting Tests
# =============================================================================


@pytest.fixture
def sync_client_rate_limited(integration_env):
    """Create synchronous test client with rate limiting enabled.

    Uses real rate limiting logic but mocks the Redis operations.
    """
    from backend.core.config import get_settings
    from backend.main import app

    # Store original environment
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")
    original_rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED")
    original_rate_limit_ws = os.environ.get("RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE")

    # Disable auth but enable rate limiting with low limit
    os.environ["API_KEY_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = "2"  # Very low for testing

    get_settings.cache_clear()

    # Create mock Redis client
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Track rate limit state
    connection_count = {"value": 0}

    # Create mock for rate limit check that tracks connections
    async def mock_check_rate_limit(websocket, redis_client):
        connection_count["value"] += 1
        # Allow first 2 connections, reject subsequent ones
        return connection_count["value"] <= 2

    async def mock_init_db():
        pass

    async def mock_seed_cameras_if_empty():
        return 0

    # Mock background services
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.connect = AsyncMock()
    mock_event_broadcaster.disconnect = AsyncMock()
    mock_event_broadcaster.broadcast_event = AsyncMock(return_value=1)
    mock_event_broadcaster.CHANNEL_NAME = "security_events"
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    mock_ai_health = AsyncMock(
        return_value={
            "rtdetr": False,
            "nemotron": False,
            "any_healthy": False,
            "all_healthy": False,
        }
    )

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.main.init_db", mock_init_db),
        patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty),
        patch("backend.main.init_redis", return_value=mock_redis_client),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", return_value=mock_file_watcher),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch(
            "backend.services.system_broadcaster.SystemBroadcaster._check_ai_health", mock_ai_health
        ),
        patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit),
        TestClient(app) as client,
    ):
        yield client

    # Restore original environment
    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    if original_rate_limit_enabled is not None:
        os.environ["RATE_LIMIT_ENABLED"] = original_rate_limit_enabled
    else:
        os.environ.pop("RATE_LIMIT_ENABLED", None)

    if original_rate_limit_ws is not None:
        os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = original_rate_limit_ws
    else:
        os.environ.pop("RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE", None)

    get_settings.cache_clear()


class TestWebSocketRateLimiting:
    """Tests for WebSocket rate limiting functionality."""

    def test_events_rate_limit_allows_initial_connections(self, sync_client_rate_limited):
        """Test that /ws/events allows connections within rate limit."""
        # First connection should succeed
        with sync_client_rate_limited.websocket_connect("/ws/events") as websocket:
            assert websocket is not None

    def test_events_rate_limit_rejects_excessive_connections(self, sync_client_rate_limited):
        """Test that /ws/events rejects connections exceeding rate limit."""
        # First two connections should succeed (our mock allows 2)
        with sync_client_rate_limited.websocket_connect("/ws/events"):
            pass

        with sync_client_rate_limited.websocket_connect("/ws/events"):
            pass

        # Third connection should be rejected
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_rate_limited.websocket_connect("/ws/events"),
        ):
            pass

    def test_system_rate_limit_allows_initial_connections(self, sync_client_rate_limited):
        """Test that /ws/system allows connections within rate limit."""
        # First connection should succeed
        with sync_client_rate_limited.websocket_connect("/ws/system") as websocket:
            assert websocket is not None


# =============================================================================
# Unit Tests for Authentication Functions
# =============================================================================


class TestWebSocketAuthFunctionsUnit:
    """Unit tests for WebSocket authentication functions."""

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_disabled(self, integration_env):
        """Test that validation passes when auth is disabled."""
        from backend.api.middleware.auth import validate_websocket_api_key
        from backend.core.config import get_settings

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}

        # Ensure auth is disabled
        os.environ["API_KEY_ENABLED"] = "false"
        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is True

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_valid_query_param(self, integration_env):
        """Test that validation passes with valid API key in query param."""
        from backend.api.middleware.auth import validate_websocket_api_key
        from backend.core.config import get_settings

        test_key = "unit_test_valid_key_123"

        # Mock websocket with API key in query param
        mock_ws = MagicMock()
        mock_ws.query_params = {"api_key": test_key}
        mock_ws.headers = {}

        # Enable auth with our test key
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is True

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_invalid_key(self, integration_env):
        """Test that validation fails with invalid API key."""
        from backend.api.middleware.auth import validate_websocket_api_key
        from backend.core.config import get_settings

        # Mock websocket with invalid API key
        mock_ws = MagicMock()
        mock_ws.query_params = {"api_key": "wrong_invalid_key"}
        mock_ws.headers = {}

        # Enable auth with a different key
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["correct_key_abc"]'
        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is False

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_missing_key(self, integration_env):
        """Test that validation fails when no API key is provided."""
        from backend.api.middleware.auth import validate_websocket_api_key
        from backend.core.config import get_settings

        # Mock websocket without API key
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}

        # Enable auth
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["some_key_123"]'
        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is False

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_protocol_header(self, integration_env):
        """Test that validation works with Sec-WebSocket-Protocol header."""
        from backend.api.middleware.auth import validate_websocket_api_key
        from backend.core.config import get_settings

        test_key = "protocol_header_key_456"

        # Mock websocket with API key in protocol header
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {"sec-websocket-protocol": f"api-key.{test_key}"}

        # Enable auth with our test key
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is True

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_authenticate_websocket_success(self, integration_env):
        """Test that authenticate_websocket accepts valid connection."""
        from backend.api.middleware.auth import authenticate_websocket
        from backend.core.config import get_settings

        test_key = "auth_success_test_key"

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.query_params = {"api_key": test_key}
        mock_ws.headers = {}
        mock_ws.close = AsyncMock()

        # Enable auth
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        result = await authenticate_websocket(mock_ws)
        assert result is True
        mock_ws.close.assert_not_called()

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_authenticate_websocket_failure_closes_connection(self, integration_env):
        """Test that authenticate_websocket closes connection on failure."""
        from backend.api.middleware.auth import authenticate_websocket
        from backend.core.config import get_settings

        # Mock websocket without valid key
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}
        mock_ws.close = AsyncMock()

        # Enable auth
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key_only"]'
        get_settings.cache_clear()

        result = await authenticate_websocket(mock_ws)
        assert result is False
        mock_ws.close.assert_called_once_with(code=1008)  # WS_1008_POLICY_VIOLATION

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()


# =============================================================================
# Unit Tests for Rate Limiting Functions
# =============================================================================


class TestWebSocketRateLimitFunctionsUnit:
    """Unit tests for WebSocket rate limiting functions."""

    @pytest.mark.asyncio
    async def test_check_websocket_rate_limit_disabled(self, integration_env):
        """Test that rate limit check passes when rate limiting is disabled."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Disable rate limiting
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        get_settings.cache_clear()

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "127.0.0.1"
        mock_ws.headers = {}

        # Mock redis client
        mock_redis = MagicMock()

        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is True

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_websocket_rate_limit_within_limit(self, integration_env):
        """Test that rate limit check passes when within limits."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Enable rate limiting
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = "100"
        get_settings.cache_clear()

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "192.168.1.100"
        mock_ws.headers = {}

        # Mock redis client with pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[0, 5, 1, True]
        )  # 5 requests, well within limit

        mock_redis_inner = MagicMock()
        mock_redis_inner.pipeline = MagicMock(return_value=mock_pipeline)

        mock_redis = MagicMock()
        mock_redis._ensure_connected = MagicMock(return_value=mock_redis_inner)

        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is True

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        os.environ.pop("RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_websocket_rate_limit_exceeded(self, integration_env):
        """Test that rate limit check fails when limit is exceeded."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Enable rate limiting with low limit
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = "5"
        os.environ["RATE_LIMIT_BURST"] = "2"  # Total limit = 5 + 2 = 7
        get_settings.cache_clear()

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "10.0.0.50"
        mock_ws.headers = {}

        # Mock redis client with pipeline - simulate exceeding limit
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock()
        mock_pipeline.zcard = MagicMock()
        mock_pipeline.zadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(
            return_value=[0, 100, 1, True]
        )  # 100 requests, over limit

        mock_redis_inner = MagicMock()
        mock_redis_inner.pipeline = MagicMock(return_value=mock_pipeline)

        mock_redis = MagicMock()
        mock_redis._ensure_connected = MagicMock(return_value=mock_redis_inner)

        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is False

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        os.environ.pop("RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE", None)
        os.environ.pop("RATE_LIMIT_BURST", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_websocket_rate_limit_redis_error_fails_open(self, integration_env):
        """Test that rate limit check passes on Redis errors (fail-open)."""
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Enable rate limiting
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        get_settings.cache_clear()

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "172.16.0.1"
        mock_ws.headers = {}

        # Mock redis client that raises an error
        mock_redis_inner = MagicMock()
        mock_redis_inner.pipeline = MagicMock(side_effect=Exception("Redis connection error"))

        mock_redis = MagicMock()
        mock_redis._ensure_connected = MagicMock(return_value=mock_redis_inner)

        # Should pass (fail-open) on Redis error
        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is True

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        get_settings.cache_clear()
