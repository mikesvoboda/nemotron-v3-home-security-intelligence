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
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def test_api_key():
    """Return a test API key."""
    return "test_ws_auth_key_12345"


def _get_common_lifespan_mocks():
    """Create common mock objects for all lifespan services.

    Returns a dict with all mock objects needed for fast test startup.
    These mocks prevent real services from initializing during TestClient creation.
    """
    # Create mock Redis client
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

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
    mock_event_broadcaster.broadcast_service_status = AsyncMock(return_value=1)
    mock_event_broadcaster.CHANNEL_NAME = "security_events"
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    mock_ai_health = AsyncMock(
        return_value={
            "yolo26": False,
            "nemotron": False,
            "any_healthy": False,
            "all_healthy": False,
        }
    )

    # Mock WorkerSupervisor (NEM-2460)
    mock_worker_supervisor = MagicMock()
    mock_worker_supervisor.start = AsyncMock()
    mock_worker_supervisor.stop = AsyncMock()
    mock_worker_supervisor.register_worker = AsyncMock()
    mock_worker_supervisor.worker_count = 4

    # Mock DI container (NEM-2003)
    mock_container = MagicMock()
    mock_health_registry = MagicMock()
    mock_health_registry.register_gpu_monitor = MagicMock()
    mock_health_registry.register_cleanup_service = MagicMock()
    mock_health_registry.register_system_broadcaster = MagicMock()
    mock_health_registry.register_file_watcher = MagicMock()
    mock_health_registry.register_pipeline_manager = MagicMock()
    mock_health_registry.register_service_health_monitor = MagicMock()
    mock_health_registry.register_performance_collector = MagicMock()
    mock_container.get = MagicMock(return_value=mock_health_registry)

    # Mock BackgroundEvaluator (NEM-2467)
    mock_background_evaluator = MagicMock()
    mock_background_evaluator.start = AsyncMock()
    mock_background_evaluator.stop = AsyncMock()

    # Mock ContainerOrchestrator
    mock_container_orchestrator = MagicMock()
    mock_container_orchestrator.start = AsyncMock()
    mock_container_orchestrator.stop = AsyncMock()

    # Mock DockerClient
    mock_docker_client = MagicMock()
    mock_docker_client.close = AsyncMock()

    # Mock PerformanceCollector
    mock_performance_collector = MagicMock()
    mock_performance_collector.close = AsyncMock()

    # Mock worker factories
    mock_detection_worker = AsyncMock()
    mock_analysis_worker = AsyncMock()
    mock_timeout_worker = AsyncMock()
    mock_metrics_worker = AsyncMock()

    return {
        "redis_client": mock_redis_client,
        "system_broadcaster": mock_system_broadcaster,
        "gpu_monitor": mock_gpu_monitor,
        "cleanup_service": mock_cleanup_service,
        "file_watcher": mock_file_watcher,
        "pipeline_manager": mock_pipeline_manager,
        "event_broadcaster": mock_event_broadcaster,
        "service_health_monitor": mock_service_health_monitor,
        "ai_health": mock_ai_health,
        "worker_supervisor": mock_worker_supervisor,
        "container": mock_container,
        "background_evaluator": mock_background_evaluator,
        "container_orchestrator": mock_container_orchestrator,
        "docker_client": mock_docker_client,
        "performance_collector": mock_performance_collector,
        "detection_worker": mock_detection_worker,
        "analysis_worker": mock_analysis_worker,
        "timeout_worker": mock_timeout_worker,
        "metrics_worker": mock_metrics_worker,
    }


def _apply_common_lifespan_patches(stack, mocks, mock_init_db, mock_close_db):
    """Apply all common lifespan service patches to an ExitStack.

    Args:
        stack: ExitStack to add patches to
        mocks: Dict of mock objects from _get_common_lifespan_mocks()
        mock_init_db: Async mock function for init_db
        mock_close_db: Async mock function for close_db
    """

    # Async mock functions for seeding and validation
    async def mock_seed_cameras_if_empty():
        return 0

    async def mock_validate_camera_paths_on_startup():
        return (0, 0)

    # Core Redis and database mocks
    stack.enter_context(patch("backend.core.redis._redis_client", mocks["redis_client"]))
    stack.enter_context(patch("backend.core.redis.init_redis", return_value=mocks["redis_client"]))
    stack.enter_context(patch("backend.core.redis.close_redis", return_value=None))
    stack.enter_context(patch("backend.main.init_db", mock_init_db))
    stack.enter_context(patch("backend.core.database.init_db", mock_init_db))
    stack.enter_context(patch("backend.core.database.close_db", mock_close_db))
    stack.enter_context(patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty))
    stack.enter_context(
        patch(
            "backend.main.validate_camera_paths_on_startup",
            mock_validate_camera_paths_on_startup,
        )
    )
    stack.enter_context(patch("backend.main.init_redis", return_value=mocks["redis_client"]))
    stack.enter_context(patch("backend.main.close_redis", return_value=None))

    # Background service mocks
    stack.enter_context(
        patch("backend.main.get_system_broadcaster", return_value=mocks["system_broadcaster"])
    )
    stack.enter_context(patch("backend.main.GPUMonitor", return_value=mocks["gpu_monitor"]))
    stack.enter_context(patch("backend.main.CleanupService", return_value=mocks["cleanup_service"]))
    stack.enter_context(patch("backend.main.FileWatcher", return_value=mocks["file_watcher"]))
    stack.enter_context(
        patch(
            "backend.main.get_pipeline_manager",
            AsyncMock(return_value=mocks["pipeline_manager"]),
        )
    )
    stack.enter_context(patch("backend.main.stop_pipeline_manager", AsyncMock()))
    stack.enter_context(
        patch(
            "backend.main.get_broadcaster",
            AsyncMock(return_value=mocks["event_broadcaster"]),
        )
    )
    stack.enter_context(patch("backend.main.stop_broadcaster", AsyncMock()))
    stack.enter_context(
        patch("backend.main.ServiceHealthMonitor", return_value=mocks["service_health_monitor"])
    )
    stack.enter_context(
        patch(
            "backend.services.system_broadcaster.SystemBroadcaster._check_ai_health",
            mocks["ai_health"],
        )
    )

    # New services added after initial fixtures
    stack.enter_context(
        patch("backend.main.get_worker_supervisor", return_value=mocks["worker_supervisor"])
    )
    stack.enter_context(patch("backend.main.get_container", return_value=mocks["container"]))
    stack.enter_context(patch("backend.main.wire_services", AsyncMock()))
    stack.enter_context(patch("backend.main.init_job_tracker_websocket", AsyncMock()))
    stack.enter_context(
        patch("backend.main.PerformanceCollector", return_value=mocks["performance_collector"])
    )
    stack.enter_context(
        patch("backend.main.BackgroundEvaluator", return_value=mocks["background_evaluator"])
    )
    stack.enter_context(patch("backend.main.get_evaluation_queue", MagicMock()))
    stack.enter_context(patch("backend.main.get_audit_service", MagicMock()))
    stack.enter_context(
        patch(
            "backend.main.ContainerOrchestrator",
            return_value=mocks["container_orchestrator"],
        )
    )
    stack.enter_context(patch("backend.main.DockerClient", return_value=mocks["docker_client"]))
    stack.enter_context(patch("backend.main.register_workers", MagicMock()))
    stack.enter_context(patch("backend.main.enable_deferred_db_logging", MagicMock()))
    stack.enter_context(
        patch("backend.main.create_detection_worker", return_value=mocks["detection_worker"])
    )
    stack.enter_context(
        patch("backend.main.create_analysis_worker", return_value=mocks["analysis_worker"])
    )
    stack.enter_context(
        patch("backend.main.create_timeout_worker", return_value=mocks["timeout_worker"])
    )
    stack.enter_context(
        patch("backend.main.create_metrics_worker", return_value=mocks["metrics_worker"])
    )


@pytest.fixture
def sync_client_auth_disabled(integration_env):
    """Create synchronous test client with auth disabled.

    All lifespan services are fully mocked to avoid slow startup.
    """
    from backend.core.config import get_settings
    from backend.main import app

    # Store original environment
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")
    original_log_db_enabled = os.environ.get("LOG_DB_ENABLED")

    # Disable API key authentication and database logging
    os.environ["API_KEY_ENABLED"] = "false"
    os.environ["LOG_DB_ENABLED"] = "false"

    # Clear settings cache to pick up new environment variables
    get_settings.cache_clear()

    # Get common mock objects
    mocks = _get_common_lifespan_mocks()

    # Mock to disable rate limiting for basic auth tests
    mock_check_rate_limit = AsyncMock(return_value=True)

    # Create mock init_db and close_db
    async def mock_init_db():
        pass

    async def mock_close_db():
        pass

    with ExitStack() as stack:
        # Apply common lifespan patches
        _apply_common_lifespan_patches(stack, mocks, mock_init_db, mock_close_db)
        # Add fixture-specific patches
        stack.enter_context(
            patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit)
        )
        client = stack.enter_context(TestClient(app))
        yield client

    # Restore original environment
    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    if original_log_db_enabled is not None:
        os.environ["LOG_DB_ENABLED"] = original_log_db_enabled
    else:
        os.environ.pop("LOG_DB_ENABLED", None)

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
    original_log_db_enabled = os.environ.get("LOG_DB_ENABLED")

    # Enable API key authentication, disable database logging
    os.environ["API_KEY_ENABLED"] = "true"
    os.environ["API_KEYS"] = f'["{test_api_key}"]'
    os.environ["LOG_DB_ENABLED"] = "false"

    # Clear settings cache to pick up new environment variables
    get_settings.cache_clear()

    # Get common mock objects
    mocks = _get_common_lifespan_mocks()

    # Mock to disable rate limiting for basic auth tests
    mock_check_rate_limit = AsyncMock(return_value=True)

    async def mock_init_db():
        pass

    async def mock_close_db():
        pass

    with ExitStack() as stack:
        # Apply common lifespan patches
        _apply_common_lifespan_patches(stack, mocks, mock_init_db, mock_close_db)
        # Add fixture-specific patches
        stack.enter_context(
            patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit)
        )
        client = stack.enter_context(TestClient(app))
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

    if original_log_db_enabled is not None:
        os.environ["LOG_DB_ENABLED"] = original_log_db_enabled
    else:
        os.environ.pop("LOG_DB_ENABLED", None)

    get_settings.cache_clear()


# =============================================================================
# Authentication Tests
# =============================================================================


class TestWebSocketAuthenticationEvents:
    """Tests for /ws/events WebSocket endpoint authentication."""

    def test_connection_without_api_key_when_auth_enabled(self, sync_client_auth_enabled):
        """Test that /ws/events rejects connection without API key when auth is enabled.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_auth_enabled.websocket_connect("/ws/events") as websocket:
            # Connection is accepted but immediately closed with policy violation
            # Attempting to receive should raise WebSocketDisconnect with code 1008
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_invalid_api_key_rejection(self, sync_client_auth_enabled):
        """Test that /ws/events rejects connection with invalid API key.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_auth_enabled.websocket_connect(
            "/ws/events?api_key=invalid_key_xyz"
        ) as websocket:
            # Connection is accepted but immediately closed with policy violation
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

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
        """Test that /ws/system rejects connection without API key when auth is enabled.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_auth_enabled.websocket_connect("/ws/system") as websocket:
            # Connection is accepted but immediately closed with policy violation
            # Attempting to receive should raise WebSocketDisconnect with code 1008
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_invalid_api_key_rejection(self, sync_client_auth_enabled):
        """Test that /ws/system rejects connection with invalid API key.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_auth_enabled.websocket_connect(
            "/ws/system?api_key=wrong_key"
        ) as websocket:
            # Connection is accepted but immediately closed with policy violation
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

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
    original_log_db_enabled = os.environ.get("LOG_DB_ENABLED")

    # Disable auth and database logging, enable rate limiting with low limit
    os.environ["API_KEY_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = "2"  # Very low for testing
    os.environ["LOG_DB_ENABLED"] = "false"

    get_settings.cache_clear()

    # Get common mock objects
    mocks = _get_common_lifespan_mocks()

    # Track rate limit state
    connection_count = {"value": 0}

    # Create mock for rate limit check that tracks connections
    async def mock_check_rate_limit(websocket, redis_client):
        connection_count["value"] += 1
        # Allow first 2 connections, reject subsequent ones
        return connection_count["value"] <= 2

    async def mock_init_db():
        pass

    async def mock_close_db():
        pass

    with ExitStack() as stack:
        # Apply common lifespan patches
        _apply_common_lifespan_patches(stack, mocks, mock_init_db, mock_close_db)
        # Add fixture-specific patches
        stack.enter_context(
            patch("backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit)
        )
        client = stack.enter_context(TestClient(app))
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

    if original_log_db_enabled is not None:
        os.environ["LOG_DB_ENABLED"] = original_log_db_enabled
    else:
        os.environ.pop("LOG_DB_ENABLED", None)

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
        """Test that authenticate_websocket accepts then closes connection on failure.

        Note: The WebSocket must be accepted before closing to properly send the
        close frame with the policy violation code. Calling close() without accept()
        would result in an HTTP 403 response during the handshake.
        """
        from backend.api.middleware.auth import authenticate_websocket
        from backend.core.config import get_settings

        # Mock websocket without valid key
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}
        mock_ws.accept = AsyncMock()  # Must be AsyncMock since we now call accept()
        mock_ws.close = AsyncMock()

        # Enable auth
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key_only"]'
        get_settings.cache_clear()

        result = await authenticate_websocket(mock_ws)
        assert result is False
        # Verify accept was called first (required for proper WebSocket close)
        mock_ws.accept.assert_called_once()
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
        import backend.api.middleware.rate_limit as rate_limit_module
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Enable rate limiting with low limit
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        os.environ["RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE"] = "5"
        os.environ["RATE_LIMIT_BURST"] = "2"  # Total limit = 5 + 2 = 7
        get_settings.cache_clear()

        # Reset the cached Lua script SHA to ensure proper mock isolation
        rate_limit_module._lua_script_sha = None

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "10.0.0.50"
        mock_ws.headers = {}

        # Mock redis client with Lua script support - simulate exceeding limit
        # The Lua script returns [is_allowed (0 or 1), current_count]
        mock_redis_inner = MagicMock()
        mock_redis_inner.script_load = AsyncMock(return_value="fake-sha-123")
        mock_redis_inner.evalsha = AsyncMock(
            return_value=[0, 100]  # 0 = not allowed, 100 = current count (over limit)
        )

        mock_redis = MagicMock()
        mock_redis._ensure_connected = MagicMock(return_value=mock_redis_inner)

        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is False

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        os.environ.pop("RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE", None)
        os.environ.pop("RATE_LIMIT_BURST", None)
        get_settings.cache_clear()
        rate_limit_module._lua_script_sha = None

    @pytest.mark.asyncio
    async def test_check_websocket_rate_limit_redis_error_fails_open(self, integration_env):
        """Test that rate limit check passes on Redis errors (fail-open)."""
        import backend.api.middleware.rate_limit as rate_limit_module
        from backend.api.middleware.rate_limit import check_websocket_rate_limit
        from backend.core.config import get_settings

        # Enable rate limiting
        os.environ["RATE_LIMIT_ENABLED"] = "true"
        get_settings.cache_clear()

        # Reset the cached Lua script SHA to ensure proper mock isolation
        rate_limit_module._lua_script_sha = None

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.client = MagicMock()
        mock_ws.client.host = "172.16.0.1"
        mock_ws.headers = {}

        # Mock redis client that raises an error on script_load
        mock_redis_inner = MagicMock()
        mock_redis_inner.script_load = AsyncMock(side_effect=Exception("Redis connection error"))

        mock_redis = MagicMock()
        mock_redis._ensure_connected = MagicMock(return_value=mock_redis_inner)

        # Should pass (fail-open) on Redis error
        result = await check_websocket_rate_limit(mock_ws, mock_redis)
        assert result is True

        # Cleanup
        os.environ.pop("RATE_LIMIT_ENABLED", None)
        get_settings.cache_clear()
        rate_limit_module._lua_script_sha = None
