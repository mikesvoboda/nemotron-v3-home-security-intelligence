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

    Ported from the test_websocket_auth.py suite (R-T7-WS-OOM): the abbreviated
    version left get_pipeline_manager / FileWatcher / worker_supervisor REAL, so
    TestClient(app) started the production pipeline worker loops against
    AsyncMock stream consumers — the `if not messages: continue` spin then
    recorded a _Call per iteration forever and OOM-killed xdist workers at
    ~300 MB/s (docs/discoveries/pytest-oom-asyncmock-worker-loop.md).
    """
    # Mock Redis client
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


def _apply_common_lifespan_patches(stack, mocks):
    """Apply all common lifespan service patches to an ExitStack.

    Full suite ported from test_websocket_auth.py::_apply_common_lifespan_patches.
    get_pipeline_manager / FileWatcher / get_worker_supervisor MUST be patched:
    unpatched, the lifespan starts the production pipeline worker loops against
    AsyncMock stream consumers and spins recording one _Call per iteration
    (~300 MB/s, worker OOM — R-T7-WS-OOM /
    docs/discoveries/pytest-oom-asyncmock-worker-loop.md).
    """

    async def mock_init_db():
        pass

    async def mock_close_db():
        pass

    async def mock_seed_cameras():
        return 0

    async def mock_validate_cameras():
        return (0, 0)

    # Core Redis and database patches
    stack.enter_context(patch("backend.core.redis._redis_client", mocks["redis_client"]))
    stack.enter_context(patch("backend.core.redis.init_redis", return_value=mocks["redis_client"]))
    stack.enter_context(patch("backend.core.redis.close_redis", return_value=None))
    stack.enter_context(patch("backend.main.init_db", mock_init_db))
    stack.enter_context(patch("backend.core.database.init_db", mock_init_db))
    stack.enter_context(patch("backend.core.database.close_db", mock_close_db))
    stack.enter_context(patch("backend.main.seed_cameras_if_empty", mock_seed_cameras))
    stack.enter_context(
        patch("backend.main.validate_camera_paths_on_startup", mock_validate_cameras)
    )
    stack.enter_context(patch("backend.main.init_redis", return_value=mocks["redis_client"]))
    stack.enter_context(patch("backend.main.close_redis", return_value=None))

    # Background service patches
    stack.enter_context(
        patch(
            "backend.main.get_system_broadcaster",
            autospec=True,
            return_value=mocks["system_broadcaster"],
        )
    )
    stack.enter_context(
        patch("backend.main.GPUMonitor", autospec=True, return_value=mocks["gpu_monitor"])
    )
    stack.enter_context(
        patch("backend.main.CleanupService", autospec=True, return_value=mocks["cleanup_service"])
    )
    stack.enter_context(
        patch("backend.main.FileWatcher", autospec=True, return_value=mocks["file_watcher"])
    )
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
        patch(
            "backend.main.ServiceHealthMonitor",
            autospec=True,
            return_value=mocks["service_health_monitor"],
        )
    )
    stack.enter_context(
        patch(
            "backend.services.system_broadcaster.SystemBroadcaster._check_ai_health",
            mocks["ai_health"],
        )
    )

    # Services added after the initial fixtures
    stack.enter_context(
        patch(
            "backend.main.get_worker_supervisor",
            autospec=True,
            return_value=mocks["worker_supervisor"],
        )
    )
    stack.enter_context(patch("backend.main.get_container", return_value=mocks["container"]))
    stack.enter_context(patch("backend.main.wire_services", AsyncMock()))
    stack.enter_context(patch("backend.main.init_job_tracker_websocket", AsyncMock()))
    stack.enter_context(
        patch(
            "backend.main.PerformanceCollector",
            autospec=True,
            return_value=mocks["performance_collector"],
        )
    )
    stack.enter_context(
        patch(
            "backend.main.BackgroundEvaluator",
            autospec=True,
            return_value=mocks["background_evaluator"],
        )
    )
    stack.enter_context(patch("backend.main.get_evaluation_queue", MagicMock()))
    stack.enter_context(patch("backend.main.get_audit_service", MagicMock()))
    stack.enter_context(
        patch(
            "backend.main.ContainerOrchestrator",
            autospec=True,
            return_value=mocks["container_orchestrator"],
        )
    )
    stack.enter_context(
        patch("backend.main.DockerClient", autospec=True, return_value=mocks["docker_client"])
    )
    stack.enter_context(patch("backend.main.register_workers", MagicMock()))
    stack.enter_context(patch("backend.main.enable_deferred_db_logging", MagicMock()))
    stack.enter_context(
        patch(
            "backend.main.create_detection_worker",
            autospec=True,
            return_value=mocks["detection_worker"],
        )
    )
    stack.enter_context(
        patch(
            "backend.main.create_analysis_worker",
            autospec=True,
            return_value=mocks["analysis_worker"],
        )
    )
    stack.enter_context(
        patch(
            "backend.main.create_timeout_worker",
            autospec=True,
            return_value=mocks["timeout_worker"],
        )
    )
    stack.enter_context(
        patch(
            "backend.main.create_metrics_worker",
            autospec=True,
            return_value=mocks["metrics_worker"],
        )
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
        """Test that /ws/events accepts a valid session cookie (R55 contract).

        Web UI clients send session cookies automatically.

        Expected behavior:
        - Extract the cookie login sets (SESSION_COOKIE_NAME — not the
          literal "session" no response ever set)
        - Look the session id up in Redis (patched here; the live lookup is
          proven unpatched in TestR55CookieAuthenticatesSocketsLive)
        - Accept connection and receive events
        """
        from backend.services.session_service import SESSION_COOKIE_NAME

        # Session validation resolves to a username (new str contract)
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie", autospec=True
        ) as mock_validate:
            mock_validate.return_value = "test_user"

            # Mock cookie in headers (simulating browser behavior)
            headers = {"cookie": f"{SESSION_COOKIE_NAME}=valid_session_cookie_abc123"}

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
        with patch(
            "backend.api.middleware.websocket_auth.validate_websocket_jwt", autospec=True
        ) as mock_validate:
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
        with patch(
            "backend.api.middleware.websocket_auth.validate_websocket_jwt", autospec=True
        ) as mock_validate:
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
        - Connection closes with code 4001 (session dead) — R55 reserves 4002
          for JWT exp; a Redis-TTL'd session cookie is the 4001 family, and the
          handshake rejection for a stale cookie already closes 4001.
        """
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie", autospec=True
        ) as mock_validate:
            # Initially valid session (new contract: a username; and under the
            # name login actually sets — R55. The 4002 assertion below is about
            # the unbuilt invalidation feature's close code, deliberately left
            # as the placeholder author wrote it.)
            mock_validate.return_value = "test_user"

            from backend.services.session_service import SESSION_COOKIE_NAME

            headers = {"cookie": f"{SESSION_COOKIE_NAME}=valid_session_cookie"}

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

                # Should close with 4001 (R55 family: dead session, like the
                # handshake rejection; 4002 stays reserved for JWT exp)
                assert exc_info.value.code == 4001


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
        with patch(
            "backend.api.middleware.websocket_auth.validate_websocket_jwt", autospec=True
        ) as mock_validate:
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
        original_api_key = os.environ.get("API_KEY_ENABLED")
        # API_KEYS is set workspace-wide by integration_env (conftest); save
        # the original so teardown cannot strip the key other tests validate.
        original_api_keys = os.environ.get("API_KEYS")
        os.environ["JWT_SECRET"] = "test_jwt_secret_detections"
        # R55: the key gate must be ON or the cookie leg is never the thing
        # under test — with api_key_enabled=False the route's key check
        # returns True unconditionally and any cookie (or none) connects.
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["test_api_key_123"]'

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

        if original_api_key:
            os.environ["API_KEY_ENABLED"] = original_api_key
        else:
            os.environ.pop("API_KEY_ENABLED", None)
        if original_api_keys is not None:
            os.environ["API_KEYS"] = original_api_keys
        else:
            os.environ.pop("API_KEYS", None)

        get_settings.cache_clear()

    def test_websocket_detections_with_cookie_auth(self, detections_auth_client):
        """Test that /ws/detections accepts cookie authentication.

        Detections endpoint should support same auth methods.

        Expected behavior:
        - Connect with session cookie
        - Receive detection events
        - Subscribe to detection.* events automatically
        """
        from backend.services.session_service import SESSION_COOKIE_NAME

        # R55: pre-fix this test only passed because the patched validator
        # answered valid — the real chain could never have (dead cookie name).
        # And after the name fix it kept passing for a SECOND wrong reason:
        # this fixture never enabled API_KEY_ENABLED, so the route's key check
        # short-circuited disabled and authenticated the socket with no
        # credential at all. The fixture now enables the key gate (below), so
        # the cookie is the ONLY thing that can carry this connection.
        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie", autospec=True
        ) as mock_validate:
            mock_validate.return_value = "test_user"

            headers = {"cookie": f"{SESSION_COOKIE_NAME}=valid_detection_session"}

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
        from backend.services.session_service import SESSION_COOKIE_NAME

        with patch(
            "backend.api.middleware.websocket_auth.validate_session_cookie", autospec=True
        ) as mock_cookie:
            with patch(
                "backend.api.middleware.websocket_auth.validate_websocket_jwt", autospec=True
            ) as mock_jwt:
                # Both would authenticate; the cookie must win. New contract:
                # the session validator answers with a username, not claims.
                mock_cookie.return_value = "cookie_user"
                mock_jwt.return_value = {"sub": "jwt_user", "exp": 9999999999}

                headers = {"cookie": f"{SESSION_COOKIE_NAME}=valid_cookie"}

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


# =============================================================================
# R55: A login session authenticates a socket — live, no patched validator
# =============================================================================


class TestR55CookieAuthenticatesSocketsLive:
    """Done-when 1 (owner ruling 55): cookie login -> socket, end to end.

    Every other cookie test in this file patches validate_session_cookie,
    which is exactly the escape hatch that let the socket cookie path stay
    dead for so long: with the validator mocked, a suite cannot see that the
    real chain (cookie name -> Redis lookup) never ran. These two tests
    patch NONE of the authentication code. The Redis session store is the
    same boundary test_api_protection.py patches to reach a real server
    (_real_redis_optional); everything above it — extract_cookie_from_websocket,
    validate_session_cookie, the gate's _session_username, verify_websocket_auth
    — is the shipped code under review.
    """

    @pytest.fixture
    def live_wired(self, worker_redis_url):
        """App + REAL Redis session store; no auth code patched.

        Yields (client, session_service, bridge).
        """
        import asyncio
        import os

        import redis as redispy

        from backend.api.middleware import auth as auth_middleware
        from backend.core.config import get_settings
        from backend.main import app
        from backend.services.session_service import SessionService

        originals = {
            k: os.environ.get(k)
            for k in ("API_KEY_ENABLED", "API_KEYS", "JWT_SECRET", "SESSION_SECRET")
        }
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["r55_live_key"]'
        os.environ["JWT_SECRET"] = "test_jwt_secret_r55_live"  # pragma: allowlist secret
        os.environ["SESSION_SECRET"] = "test_session_secret_r55_live"  # pragma: allowlist secret
        get_settings.cache_clear()

        sync_store = redispy.Redis.from_url(worker_redis_url)

        class _RealStoreRedis:
            """Async front for a sync redis-py pool: real bytes, any loop.

            backend.core.redis.RedisClient opens its connection on whichever
            event loop calls connect(), and TestClient runs the app on its
            own portal loop — an async client built outside would be pinned
            to the wrong loop. SessionService only needs get/set/delete, so
            bridging each over the thread-safe sync pool keeps every read a
            real Redis read without the pinning. The calls list doubles as
            the test's evidence that the gate actually consulted Redis.
            """

            def __init__(self, store):
                self._store = store
                self.calls = []

            async def get(self, key):
                self.calls.append(("get", key))
                return await asyncio.to_thread(self._store.get, key)

            async def set(self, key, value, expire=None):
                self.calls.append(("set", key))
                if expire is not None:
                    return await asyncio.to_thread(self._store.set, key, value, ex=expire)
                return await asyncio.to_thread(self._store.set, key, value)

            async def delete(self, *keys):
                self.calls.append(("delete", *keys))
                return await asyncio.to_thread(self._store.delete, *keys)

        bridge = _RealStoreRedis(sync_store)

        async def _live_redis_optional():
            return bridge

        mocks = _get_common_lifespan_mocks()
        mock_check_rate_limit = AsyncMock(return_value=True)

        with ExitStack() as stack:
            _apply_common_lifespan_patches(stack, mocks)
            stack.enter_context(
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit", mock_check_rate_limit
                )
            )
            # The session-store boundary only. This is test_api_protection's
            # _real_redis_optional idiom; validate_session_cookie and
            # _session_username are NOT patched — the real lookup runs.
            stack.enter_context(
                patch.object(auth_middleware, "get_redis_optional", _live_redis_optional)
            )
            client = stack.enter_context(TestClient(app))
            yield client, SessionService(bridge), bridge

        for key, value in originals.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        sync_store.close()

    def test_real_redis_session_opens_socket_without_patched_validator(self, live_wired):
        """The ruling's can-fail proof: login's session_id opens /ws/events.

        The session is created with SessionService.create_session — the exact
        call POST /api/auth/login makes (routes/auth.py), with the same
        key/value shape Redis holds after a real login. (The HTTP leg itself
        — that login SETs a cookie named SESSION_COOKIE_SECURE-safe session_id
        carrying that id — is proven against this same real Redis in
        test_api_protection.py; this closes the second half.) With the fix,
        the socket reads it; at the pre-fix name ("session") the extractor
        found nothing, the cookie leg never ran, and first-message auth
        timed out into a 4001 — this test fails there, which is why it is
        worth writing.
        """
        import asyncio
        from datetime import timedelta

        from backend.services.session_service import SESSION_COOKIE_NAME

        client, service, bridge = live_wired
        session_id = asyncio.run(
            service.create_session(
                "r55-user-id",
                {"username": "r55-user", "is_admin": True},
                ttl=timedelta(seconds=120),
            )
        )
        try:
            headers = {"cookie": f"{SESSION_COOKIE_NAME}={session_id}"}
            with client.websocket_connect("/ws/events", headers=headers) as websocket:
                websocket.send_text(json.dumps({"type": "ping"}))
                data = json.loads(websocket.receive_text())
                assert data["type"] == "pong"
            # The gate really consulted Redis for THIS session key — no
            # mocked validator could have answered without it.
            assert ("get", f"session:{session_id}") in bridge.calls
        finally:
            asyncio.run(service.delete_session(session_id))

    def test_fabricated_session_id_closes_4001_through_the_real_gate(self, live_wired):
        """Negative control against the yes-man pathology.

        A fabricated id through a validator patched to "valid" would connect
        (that's how the old suite hid the defect); through the real gate it
        finds no session, falls through, times out first-message auth, and
        closes 4001.
        """
        from backend.services.session_service import SESSION_COOKIE_NAME

        client, _service, bridge = live_wired
        headers = {"cookie": f"{SESSION_COOKIE_NAME}=r55-fabricated-never-issued-id"}
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/events", headers=headers) as websocket:
                websocket.receive_text()
        assert exc_info.value.code == 4001
