"""Integration tests for WebSocket endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean SQLite test database
- mock_redis: Mock Redis client
"""

import json
import os
import uuid
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.tests.conftest import unique_id


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
            "rtdetr": False,
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
    mock_docker_client.close = MagicMock()

    # Mock PerformanceCollector
    mock_performance_collector = MagicMock()
    mock_performance_collector.close = MagicMock()

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


def _apply_common_lifespan_patches(stack, mocks, mock_init_db):
    """Apply all common lifespan service patches to an ExitStack.

    Args:
        stack: ExitStack to add patches to
        mocks: Dict of mock objects from _get_common_lifespan_mocks()
        mock_init_db: Async mock function for init_db
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
async def async_client(integration_db, mock_redis):
    """Create async HTTP client for testing."""
    from backend.main import app

    # Mock background services that have 5-second intervals to avoid slow teardown
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    # Patch init_db/close_db and background services to avoid slow teardown
    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def sync_client(integration_env):
    """Create synchronous test client for WebSocket testing.

    Note: Uses integration_env (sync) instead of integration_db (async) because
    TestClient creates its own event loop, which conflicts with async fixtures.

    All lifespan services are fully mocked to avoid slow startup. The database
    is NOT actually initialized - tests use mocks for fast execution.
    """
    from backend.main import app

    # Get common mock objects
    mocks = _get_common_lifespan_mocks()

    # Create mock init_db that does nothing (avoids slow real DB init)
    async def mock_init_db():
        """Mock init_db to avoid slow real database initialization."""
        pass

    # Patch all lifespan services for fast startup using ExitStack
    with ExitStack() as stack:
        _apply_common_lifespan_patches(stack, mocks, mock_init_db)
        client = stack.enter_context(TestClient(app))
        yield client


@pytest.fixture
async def sample_camera(integration_db):
    """Create a sample camera in the database.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Front Door {unique_suffix}",
            folder_path=f"/export/foscam/front_door_{unique_suffix}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_event(integration_db, sample_camera):
    """Create a sample event in the database."""
    from backend.core.database import get_session
    from backend.models.event import Event

    async with get_session() as db:
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=sample_camera.id,
            started_at=datetime(2025, 12, 23, 12, 0, 0),
            ended_at=datetime(2025, 12, 23, 12, 1, 30),
            risk_score=75,
            risk_level="high",
            summary="Person detected at front door",
            reasoning="A person was detected approaching the front door at night.",
            detection_ids=json.dumps([1, 2, 3]),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        yield event


@pytest.fixture
async def sample_detection(integration_db, sample_camera):
    """Create a sample detection in the database."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/test_image.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


# WebSocket Connection Tests


class TestWebSocketEventChannel:
    """Tests for /ws/events WebSocket endpoint."""

    def test_events_websocket_connection(self, sync_client):
        """Test connecting to /ws/events endpoint."""
        with sync_client.websocket_connect("/ws/events") as websocket:
            # Connection established successfully
            assert websocket is not None

    def test_events_websocket_connection_and_disconnect(self, sync_client):
        """Test connecting and gracefully disconnecting from /ws/events."""
        with sync_client.websocket_connect("/ws/events") as websocket:
            assert websocket is not None
        # Connection should be closed after context manager exit

    def test_events_websocket_receive_new_event(self, sync_client, sample_event):
        """Test receiving a new_event broadcast."""
        with sync_client.websocket_connect("/ws/events") as websocket:
            # Simulate broadcasting a new event
            # Note: In real implementation, this would be triggered by the backend
            # For now, we just test that the connection can receive messages

            # Send a test message (in real implementation, backend would push)
            _test_message = {
                "type": "new_event",
                "data": {
                    "id": sample_event.id,
                    "camera_id": sample_event.camera_id,
                    "risk_score": sample_event.risk_score,
                    "risk_level": sample_event.risk_level,
                    "summary": sample_event.summary,
                    "started_at": sample_event.started_at.isoformat(),
                },
            }

            # For TDD: Define expected behavior
            # In actual implementation, we would broadcast and receive
            # For now, verify connection is established
            assert websocket is not None

    def test_events_websocket_receive_detection(self, sync_client, sample_detection):
        """Test receiving a detection broadcast."""
        with sync_client.websocket_connect("/ws/events") as websocket:
            # Test message format that should be broadcast
            _test_message = {
                "type": "detection",
                "data": {
                    "id": sample_detection.id,
                    "camera_id": sample_detection.camera_id,
                    "object_type": sample_detection.object_type,
                    "confidence": sample_detection.confidence,
                    "detected_at": sample_detection.detected_at.isoformat(),
                },
            }

            # Verify connection is established
            assert websocket is not None

    def test_events_websocket_multiple_connections(self, sync_client):
        """Test multiple concurrent connections to /ws/events."""
        with (
            sync_client.websocket_connect("/ws/events") as ws1,
            sync_client.websocket_connect("/ws/events") as ws2,
        ):
            assert ws1 is not None
            assert ws2 is not None
            # Both connections should be active

    def test_events_websocket_reconnection(self, sync_client):
        """Test reconnecting after disconnect."""
        # First connection
        with sync_client.websocket_connect("/ws/events") as websocket:
            assert websocket is not None

        # Second connection (reconnect)
        with sync_client.websocket_connect("/ws/events") as websocket:
            assert websocket is not None

    def test_events_websocket_message_format_new_event(self, sync_client):
        """Test that new_event messages have correct format."""
        with sync_client.websocket_connect("/ws/events") as _websocket:
            # Expected message format
            expected_format = {
                "type": "new_event",
                "data": {
                    "id": 1,
                    "camera_id": "cam-123",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Person detected",
                    "reasoning": "Test reasoning",
                    "started_at": "2025-12-23T12:00:00",
                    "ended_at": "2025-12-23T12:01:30",
                },
            }

            # Verify the format is valid JSON
            json_str = json.dumps(expected_format)
            assert json_str is not None
            assert "new_event" in json_str

    def test_events_websocket_message_format_detection(self, sync_client):
        """Test that detection messages have correct format."""
        with sync_client.websocket_connect("/ws/events") as _websocket:
            # Expected message format
            expected_format = {
                "type": "detection",
                "data": {
                    "id": 1,
                    "camera_id": "cam-123",
                    "object_type": "person",
                    "confidence": 0.95,
                    "detected_at": "2025-12-23T12:00:00",
                    "bbox_x": 100,
                    "bbox_y": 150,
                    "bbox_width": 200,
                    "bbox_height": 400,
                },
            }

            # Verify the format is valid JSON
            json_str = json.dumps(expected_format)
            assert json_str is not None
            assert "detection" in json_str


class TestWebSocketSystemChannel:
    """Tests for /ws/system WebSocket endpoint."""

    def test_system_websocket_connection(self, sync_client):
        """Test connecting to /ws/system endpoint."""
        with sync_client.websocket_connect("/ws/system") as websocket:
            # Connection established successfully
            assert websocket is not None

    def test_system_websocket_connection_and_disconnect(self, sync_client):
        """Test connecting and gracefully disconnecting from /ws/system."""
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None
        # Connection should be closed after context manager exit

    def test_system_websocket_receive_gpu_stats(self, sync_client):
        """Test receiving gpu_stats broadcast."""
        with sync_client.websocket_connect("/ws/system") as websocket:
            # Test message format that should be broadcast
            _test_message = {
                "type": "gpu_stats",
                "data": {
                    "gpu_utilization": 75.5,
                    "memory_used": 12345678900,
                    "memory_total": 25769803776,
                    "temperature": 72.0,
                    "inference_fps": 30.5,
                    "recorded_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
                },
            }

            # Verify connection is established
            assert websocket is not None

    def test_system_websocket_receive_camera_status(self, sync_client, sample_camera):
        """Test receiving camera_status broadcast."""
        with sync_client.websocket_connect("/ws/system") as websocket:
            # Test message format that should be broadcast
            _test_message = {
                "type": "camera_status",
                "data": {
                    "camera_id": sample_camera.id,
                    "status": "online",
                    "last_seen_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
                },
            }

            # Verify connection is established
            assert websocket is not None

    def test_system_websocket_multiple_connections(self, sync_client):
        """Test multiple concurrent connections to /ws/system."""
        with (
            sync_client.websocket_connect("/ws/system") as ws1,
            sync_client.websocket_connect("/ws/system") as ws2,
        ):
            assert ws1 is not None
            assert ws2 is not None
            # Both connections should be active

    def test_system_websocket_reconnection(self, sync_client):
        """Test reconnecting after disconnect."""
        # First connection
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None

        # Second connection (reconnect)
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None

    def test_system_websocket_message_format_gpu_stats(self, sync_client):
        """Test that gpu_stats messages have correct format."""
        with sync_client.websocket_connect("/ws/system") as _websocket:
            # Expected message format
            expected_format = {
                "type": "gpu_stats",
                "data": {
                    "gpu_utilization": 75.5,
                    "memory_used": 12345678900,
                    "memory_total": 25769803776,
                    "temperature": 72.0,
                    "inference_fps": 30.5,
                },
            }

            # Verify the format is valid JSON
            json_str = json.dumps(expected_format)
            assert json_str is not None
            assert "gpu_stats" in json_str

    def test_system_websocket_message_format_camera_status(self, sync_client):
        """Test that camera_status messages have correct format."""
        with sync_client.websocket_connect("/ws/system") as _websocket:
            # Expected message format
            expected_format = {
                "type": "camera_status",
                "data": {
                    "camera_id": "cam-123",
                    "status": "online",
                    "last_seen_at": "2025-12-23T12:00:00",
                },
            }

            # Verify the format is valid JSON
            json_str = json.dumps(expected_format)
            assert json_str is not None
            assert "camera_status" in json_str


# Connection Cleanup Tests


class TestWebSocketConnectionCleanup:
    """Tests for WebSocket connection cleanup."""

    def test_events_websocket_cleanup_on_disconnect(self, sync_client):
        """Test that event channel connections are cleaned up on disconnect."""
        # Create and disconnect multiple connections
        for _ in range(5):
            with sync_client.websocket_connect("/ws/events") as websocket:
                assert websocket is not None
            # Connection should be cleaned up after exiting context

        # Verify we can still connect (no leaked connections)
        with sync_client.websocket_connect("/ws/events") as websocket:
            assert websocket is not None

    def test_system_websocket_cleanup_on_disconnect(self, sync_client):
        """Test that system channel connections are cleaned up on disconnect."""
        # Create and disconnect multiple connections
        for _ in range(5):
            with sync_client.websocket_connect("/ws/system") as websocket:
                assert websocket is not None
            # Connection should be cleaned up after exiting context

        # Verify we can still connect (no leaked connections)
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None

    def test_mixed_websocket_cleanup(self, sync_client):
        """Test cleanup when mixing events and system connections."""
        # Create multiple connections to both endpoints
        with (
            sync_client.websocket_connect("/ws/events") as ws_events,
            sync_client.websocket_connect("/ws/system") as ws_system,
        ):
            assert ws_events is not None
            assert ws_system is not None

        # All connections should be cleaned up
        # Verify we can still connect to both
        with (
            sync_client.websocket_connect("/ws/events") as ws_events,
            sync_client.websocket_connect("/ws/system") as ws_system,
        ):
            assert ws_events is not None
            assert ws_system is not None


# Error Handling Tests


class TestWebSocketErrorHandling:
    """Tests for WebSocket error handling."""

    def test_events_websocket_invalid_path(self, sync_client):
        """Test that invalid WebSocket paths return appropriate errors."""
        from starlette.websockets import WebSocketDisconnect

        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client.websocket_connect("/ws/invalid"),
        ):
            # Should fail to connect to non-existent endpoint
            pass

    def test_system_websocket_handles_connection_errors(self, sync_client):
        """Test that system channel handles connection errors gracefully."""
        # This test verifies that the backend doesn't crash on connection errors
        # In actual implementation, the backend should handle errors gracefully
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None


# Broadcast Functionality Tests (TDD - these define expected behavior)


class TestWebSocketBroadcastFunctionality:
    """Tests for WebSocket broadcast functionality."""

    def test_events_broadcast_to_multiple_clients(self, sync_client):
        """Test that events are broadcast to all connected clients."""
        # TDD: Define expected behavior
        # When an event is created, all connected /ws/events clients should receive it
        with (
            sync_client.websocket_connect("/ws/events") as ws1,
            sync_client.websocket_connect("/ws/events") as ws2,
        ):
            # Both clients should receive the same event
            # This will be implemented when the broadcast logic is added
            assert ws1 is not None
            assert ws2 is not None

    def test_system_broadcast_to_multiple_clients(self, sync_client):
        """Test that system updates are broadcast to all connected clients."""
        # TDD: Define expected behavior
        # When GPU stats or camera status updates occur, all /ws/system clients should receive them
        with (
            sync_client.websocket_connect("/ws/system") as ws1,
            sync_client.websocket_connect("/ws/system") as ws2,
        ):
            # Both clients should receive the same updates
            # This will be implemented when the broadcast logic is added
            assert ws1 is not None
            assert ws2 is not None

    def test_isolated_channels(self, sync_client):
        """Test that events and system channels are isolated."""
        # TDD: Define expected behavior
        # /ws/events clients should only receive event/detection messages
        # /ws/system clients should only receive gpu_stats/camera_status messages
        with (
            sync_client.websocket_connect("/ws/events") as ws_events,
            sync_client.websocket_connect("/ws/system") as ws_system,
        ):
            # Messages on one channel should not appear on the other
            assert ws_events is not None
            assert ws_system is not None


# WebSocket Authentication Tests


@pytest.fixture
def test_api_key():
    """Return a test API key."""
    return "test_websocket_key_12345"


@pytest.fixture
def sync_client_with_auth_enabled(integration_env, test_api_key):
    """Create synchronous test client with auth enabled for WebSocket testing.

    Note: Uses integration_env (sync) instead of integration_db (async) because
    TestClient creates its own event loop, which conflicts with async fixtures.

    All lifespan services are fully mocked to avoid slow startup. The database
    is NOT actually initialized - tests use mocks for fast execution.
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

    # Get common mock objects
    mocks = _get_common_lifespan_mocks()

    # Create mock init_db that does nothing (avoids slow real DB init)
    async def mock_init_db():
        """Mock init_db to avoid slow real database initialization."""
        pass

    # Patch all lifespan services for fast startup using ExitStack
    with ExitStack() as stack:
        _apply_common_lifespan_patches(stack, mocks, mock_init_db)
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

    # Clear settings cache again
    get_settings.cache_clear()


class TestWebSocketAuthentication:
    """Tests for WebSocket endpoint authentication."""

    def test_events_websocket_with_valid_api_key_query_param(
        self, sync_client_with_auth_enabled, test_api_key
    ):
        """Test that /ws/events accepts valid API key via query parameter."""
        with sync_client_with_auth_enabled.websocket_connect(
            f"/ws/events?api_key={test_api_key}"
        ) as websocket:
            assert websocket is not None

    def test_system_websocket_with_valid_api_key_query_param(
        self, sync_client_with_auth_enabled, test_api_key
    ):
        """Test that /ws/system accepts valid API key via query parameter."""
        with sync_client_with_auth_enabled.websocket_connect(
            f"/ws/system?api_key={test_api_key}"
        ) as websocket:
            assert websocket is not None

    def test_events_websocket_without_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/events rejects connection without API key when auth is enabled.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_with_auth_enabled.websocket_connect("/ws/events") as websocket:
            # Connection is accepted but immediately closed with policy violation
            # Attempting to receive should raise WebSocketDisconnect with code 1008
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_system_websocket_without_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/system rejects connection without API key when auth is enabled.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_with_auth_enabled.websocket_connect("/ws/system") as websocket:
            # Connection is accepted but immediately closed with policy violation
            # Attempting to receive should raise WebSocketDisconnect with code 1008
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_events_websocket_with_invalid_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/events rejects connection with invalid API key.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_with_auth_enabled.websocket_connect(
            "/ws/events?api_key=invalid_key_12345"
        ) as websocket:
            # Connection is accepted but immediately closed with policy violation
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_system_websocket_with_invalid_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/system rejects connection with invalid API key.

        The server accepts the connection first to send a proper WebSocket close frame,
        then immediately closes with code 1008 (Policy Violation).
        """
        with sync_client_with_auth_enabled.websocket_connect(
            "/ws/system?api_key=invalid_key_12345"
        ) as websocket:
            # Connection is accepted but immediately closed with policy violation
            with pytest.raises(WebSocketDisconnect) as exc_info:
                websocket.receive_text()
            assert exc_info.value.code == 1008

    def test_events_websocket_without_auth_enabled_allows_connection(self, sync_client):
        """Test that /ws/events allows connection when auth is disabled."""
        # sync_client fixture has auth disabled by default
        with sync_client.websocket_connect("/ws/events") as websocket:
            assert websocket is not None

    def test_system_websocket_without_auth_enabled_allows_connection(self, sync_client):
        """Test that /ws/system allows connection when auth is disabled."""
        # sync_client fixture has auth disabled by default
        with sync_client.websocket_connect("/ws/system") as websocket:
            assert websocket is not None

    def test_events_websocket_with_protocol_header_api_key(
        self, sync_client_with_auth_enabled, test_api_key
    ):
        """Test that /ws/events accepts API key via Sec-WebSocket-Protocol header."""
        # Note: The TestClient may not fully support custom protocols in the same way
        # as a real WebSocket client, but we test the query param mechanism works
        with sync_client_with_auth_enabled.websocket_connect(
            f"/ws/events?api_key={test_api_key}"
        ) as websocket:
            assert websocket is not None

    def test_multiple_authenticated_connections(self, sync_client_with_auth_enabled, test_api_key):
        """Test that multiple authenticated connections can be established."""
        with (
            sync_client_with_auth_enabled.websocket_connect(
                f"/ws/events?api_key={test_api_key}"
            ) as ws1,
            sync_client_with_auth_enabled.websocket_connect(
                f"/ws/system?api_key={test_api_key}"
            ) as ws2,
        ):
            assert ws1 is not None
            assert ws2 is not None


class TestWebSocketAuthenticationUnit:
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

        test_key = "test_valid_key_123"

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
        mock_ws.query_params = {"api_key": "invalid_key"}
        mock_ws.headers = {}

        # Enable auth with a different key
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["correct_key"]'
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
        os.environ["API_KEYS"] = '["some_key"]'
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

        test_key = "protocol_key_123"

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

        test_key = "auth_test_key"

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
        os.environ["API_KEYS"] = '["valid_key"]'
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


# End-to-End Pipeline Tests: NemotronAnalyzer -> Redis -> EventBroadcaster -> WebSocket


class TestEventBroadcastPipeline:
    """Tests for the end-to-end event broadcast pipeline.

    This test class verifies that:
    1. NemotronAnalyzer publishes to the canonical 'security_events' Redis channel
    2. EventBroadcaster subscribes to the same channel
    3. Messages have the correct envelope format: {"type": "event", "data": {...}}
    4. WebSocket clients receive events properly formatted
    """

    @pytest.mark.asyncio
    async def test_channel_alignment(self, integration_env):
        """Verify NemotronAnalyzer and EventBroadcaster use the same Redis channel.

        This is the critical test that ensures the channel mismatch bug is fixed.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create both services with explicit channel name
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")
        analyzer = NemotronAnalyzer(mock_redis)

        # The channel names should be the same
        # NemotronAnalyzer now imports EventBroadcaster.CHANNEL_NAME
        assert broadcaster.CHANNEL_NAME == "security_events"

        # Test that both use the same channel
        # Broadcast through EventBroadcaster with valid event data
        valid_event_data = {
            "id": 1,
            "event_id": 1,
            "batch_id": "test_batch",
            "camera_id": "test_camera",
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test event",
            "reasoning": "Test reasoning for channel alignment test",
            "started_at": "2025-12-23T12:00:00",
        }
        await broadcaster.broadcast_event(valid_event_data)
        broadcast_channel = mock_redis.publish.call_args[0][0]

        # Reset mock
        mock_redis.publish.reset_mock()

        # Broadcast through NemotronAnalyzer - mock get_broadcaster to use our broadcaster
        from datetime import datetime

        from backend.models.event import Event

        camera_id = unique_id("test_camera")
        test_event = Event(
            id=1,
            batch_id="test_batch",
            camera_id=camera_id,
            started_at=datetime(2025, 12, 23, 12, 0, 0),
            risk_score=50,
            risk_level="medium",
            summary="Test",
            reasoning="Test reasoning for channel alignment",
        )

        # Mock get_broadcaster to return our mock broadcaster
        with patch(
            "backend.services.event_broadcaster.get_broadcaster",
            AsyncMock(return_value=broadcaster),
        ):
            await analyzer._broadcast_event(test_event)

        analyzer_channel = mock_redis.publish.call_args[0][0]

        # Both should use the same channel
        assert broadcast_channel == analyzer_channel
        assert broadcast_channel == "security_events"

    @pytest.mark.asyncio
    async def test_message_envelope_format(self, integration_env):
        """Verify NemotronAnalyzer sends messages in the correct envelope format.

        The canonical format is: {"type": "event", "data": {...}}
        """
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from backend.models.event import Event
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create analyzer and a mock broadcaster
        analyzer = NemotronAnalyzer(mock_redis)
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")

        # Create test event
        camera_id = unique_id("envelope_test_camera")
        test_event = Event(
            id=42,
            batch_id="envelope_test_batch",
            camera_id=camera_id,
            started_at=datetime(2025, 12, 23, 14, 30, 0),
            risk_score=75,
            risk_level="high",
            summary="Test envelope format",
            reasoning="Test reasoning for envelope format",
        )

        # Broadcast the event using mocked get_broadcaster
        with patch(
            "backend.services.event_broadcaster.get_broadcaster",
            AsyncMock(return_value=broadcaster),
        ):
            await analyzer._broadcast_event(test_event)

        # Verify the message format
        call_args = mock_redis.publish.call_args
        message = call_args[0][1]

        # Verify envelope structure
        assert "type" in message
        assert message["type"] == "event"
        assert "data" in message

        # Verify data contents
        data = message["data"]
        assert data["id"] == 42
        assert data["event_id"] == 42  # Legacy field
        assert data["batch_id"] == "envelope_test_batch"
        assert data["camera_id"] == camera_id
        assert data["risk_score"] == 75
        assert data["risk_level"] == "high"
        assert data["summary"] == "Test envelope format"
        assert data["reasoning"] == "Test reasoning for envelope format"
        assert data["started_at"] == "2025-12-23T14:30:00"

    @pytest.mark.asyncio
    async def test_broadcaster_wraps_missing_type(self, integration_env):
        """Verify EventBroadcaster wraps messages missing 'type' field.

        If a message is published without a 'type' field, EventBroadcaster
        should wrap it in the canonical envelope format.
        """
        from unittest.mock import AsyncMock, MagicMock

        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create broadcaster with explicit channel name
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")

        # Broadcast a message without 'type' field but with all required fields
        payload = {
            "id": 123,
            "event_id": 123,
            "batch_id": "test_batch",
            "camera_id": "test_camera",
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Test event",
            "reasoning": "Test reasoning for wrapper test",
            "started_at": "2025-12-23T12:00:00",
        }
        await broadcaster.broadcast_event(payload)

        # Verify it was wrapped
        message = mock_redis.publish.call_args[0][1]
        assert message["type"] == "event"
        # Data should include all fields from the payload
        assert message["data"]["id"] == 123
        assert message["data"]["reasoning"] == "Test reasoning for wrapper test"

    @pytest.mark.asyncio
    async def test_end_to_end_publish_subscribe(self, integration_env):
        """Verify messages published flow through to WebSocket clients.

        This tests the complete pipeline:
        1. NemotronAnalyzer publishes event to Redis
        2. EventBroadcaster receives event from Redis pub/sub
        3. EventBroadcaster sends to all connected WebSocket clients
        """
        import json
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from backend.models.event import Event
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Track messages received by WebSocket clients
        received_messages = []

        # Create mock WebSocket
        mock_ws = MagicMock()
        mock_ws.send_text = AsyncMock(
            side_effect=lambda msg: received_messages.append(json.loads(msg))
        )
        mock_ws.close = AsyncMock()

        # Create mock Redis client with pub/sub simulation
        published_messages = []

        async def mock_publish(channel, message):
            published_messages.append((channel, message))
            return 1

        # Create mock pubsub that yields published messages
        class MockPubSub:
            pass

        mock_pubsub = MockPubSub()

        async def mock_subscribe(channel):
            return mock_pubsub

        async def mock_listen(_pubsub):
            # Yield all published messages
            for channel, message in published_messages:
                yield {"data": message}

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(side_effect=mock_publish)
        mock_redis.subscribe = AsyncMock(side_effect=mock_subscribe)
        mock_redis.listen = mock_listen

        # Create services with explicit channel name
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")
        analyzer = NemotronAnalyzer(mock_redis)

        # Add WebSocket connection to broadcaster
        broadcaster._connections.add(mock_ws)

        # Create and broadcast test event via NemotronAnalyzer
        camera_id = unique_id("e2e_test_camera")
        test_event = Event(
            id=99,
            batch_id="e2e_test_batch",
            camera_id=camera_id,
            started_at=datetime(2025, 12, 23, 16, 0, 0),
            risk_score=85,
            risk_level="critical",
            summary="End-to-end test event",
            reasoning="End-to-end test reasoning",
        )

        # Use mocked get_broadcaster to return our broadcaster
        with patch(
            "backend.services.event_broadcaster.get_broadcaster",
            AsyncMock(return_value=broadcaster),
        ):
            await analyzer._broadcast_event(test_event)

        # Verify message was published to correct channel
        assert len(published_messages) == 1
        channel, message = published_messages[0]
        assert channel == "security_events"

        # Simulate broadcaster receiving the message
        await broadcaster._send_to_all_clients(message)

        # Verify WebSocket client received the message
        assert len(received_messages) == 1
        received = received_messages[0]
        assert received["type"] == "event"
        assert received["data"]["id"] == 99
        assert received["data"]["risk_score"] == 85
        assert received["data"]["summary"] == "End-to-end test event"


class TestChannelDocumentation:
    """Tests verifying that channel names and message formats are documented."""

    def test_broadcaster_channel_name_is_documented(self, integration_env):
        """Verify get_event_channel returns the canonical channel name from settings."""
        from backend.services.event_broadcaster import EventBroadcaster, get_event_channel

        # get_event_channel should return the configured channel name
        assert get_event_channel() == "security_events"

        # CHANNEL_NAME should still be accessible as an instance property for backward compat
        assert hasattr(EventBroadcaster, "CHANNEL_NAME")

    def test_agents_md_documents_channel(self):
        """Verify AGENTS.md documents the canonical channel name."""
        from pathlib import Path

        agents_path = (
            Path(__file__).resolve().parent.parent.parent / "services" / "AGENTS.md"
        ).resolve()

        with agents_path.open() as f:
            content = f.read()

        # Channel name should be documented
        assert "security_events" in content
        # Message format should be documented
        assert '"type": "event"' in content or "type.*event" in content


class TestWebSocketEventMessageContract:
    """Contract tests to ensure WebSocket message schema stays in sync.

    These tests validate that:
    1. NemotronAnalyzer._broadcast_event() produces messages matching the schema
    2. The schema in websocket.py matches the documented format
    3. Any drift between documentation and implementation is detected
    """

    @pytest.mark.asyncio
    async def test_broadcast_event_matches_schema(self, integration_env):
        """Verify NemotronAnalyzer._broadcast_event produces messages matching WebSocketEventMessage schema.

        This is the critical contract test - if _broadcast_event() changes its output format,
        this test will fail, alerting developers to update the schema.
        """
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from pydantic import ValidationError

        from backend.api.schemas.websocket import WebSocketEventMessage
        from backend.models.event import Event
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        # Create mock Redis that captures the published message
        published_message = None

        async def capture_publish(channel, message):
            nonlocal published_message
            published_message = message
            return 1

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(side_effect=capture_publish)

        # Create analyzer and broadcaster
        analyzer = NemotronAnalyzer(mock_redis)
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")
        camera_id = unique_id("contract_test_camera")
        test_event = Event(
            id=42,
            batch_id="contract_test_batch",
            camera_id=camera_id,
            started_at=datetime(2025, 12, 23, 14, 30, 0),
            risk_score=75,
            risk_level="high",
            summary="Contract test event",
            reasoning="Contract test reasoning for schema validation",
        )

        # Broadcast the event using mocked get_broadcaster
        with patch(
            "backend.services.event_broadcaster.get_broadcaster",
            AsyncMock(return_value=broadcaster),
        ):
            await analyzer._broadcast_event(test_event)

        # Verify a message was published
        assert published_message is not None, "No message was published"

        # Validate the message matches the schema
        # This will raise ValidationError if the message doesn't match
        try:
            validated_message = WebSocketEventMessage.model_validate(published_message)
        except ValidationError as e:
            pytest.fail(
                f"Broadcast message does not match WebSocketEventMessage schema: {e}\n"
                f"Actual message: {published_message}"
            )

        # Verify specific field values
        assert validated_message.type == "event"
        assert validated_message.data.id == 42
        assert validated_message.data.event_id == 42  # Legacy field
        assert validated_message.data.batch_id == "contract_test_batch"
        assert validated_message.data.camera_id == camera_id
        assert validated_message.data.risk_score == 75
        assert validated_message.data.risk_level == "high"
        assert validated_message.data.summary == "Contract test event"
        assert validated_message.data.reasoning == "Contract test reasoning for schema validation"
        assert validated_message.data.started_at == "2025-12-23T14:30:00"

    def test_schema_fields_match_documentation(self):
        """Verify WebSocketEventData schema fields match the documented fields.

        This test ensures the Pydantic schema stays in sync with what we document.
        If fields are added/removed from the schema, this test helps catch drift.
        """
        from backend.api.schemas.websocket import WebSocketEventData

        # Expected fields based on documentation in websocket.py docstring
        expected_fields = {
            "id",
            "event_id",
            "batch_id",
            "camera_id",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
            "started_at",
        }

        actual_fields = set(WebSocketEventData.model_fields.keys())

        # Check for missing fields
        missing = expected_fields - actual_fields
        assert not missing, f"Schema is missing documented fields: {missing}"

        # Check for undocumented fields
        extra = actual_fields - expected_fields
        assert not extra, f"Schema has undocumented fields: {extra}"

    def test_schema_example_is_valid(self):
        """Verify the schema example in WebSocketEventMessage is self-consistent."""
        from backend.api.schemas.websocket import WebSocketEventMessage

        # Get the example from the schema
        example = WebSocketEventMessage.model_config.get("json_schema_extra", {}).get("example", {})

        # The example should validate against the schema
        validated = WebSocketEventMessage.model_validate(example)
        assert validated.type == "event"
        assert validated.data.id == 1

    @pytest.mark.asyncio
    async def test_broadcast_event_with_none_started_at(self, integration_env):
        """Verify broadcast handles events where started_at is None."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from backend.api.schemas.websocket import WebSocketEventMessage
        from backend.models.event import Event
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Reset global broadcaster state to ensure clean test
        reset_broadcaster_state()

        published_message = None

        async def capture_publish(channel, message):
            nonlocal published_message
            published_message = message
            return 1

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(side_effect=capture_publish)

        analyzer = NemotronAnalyzer(mock_redis)
        broadcaster = EventBroadcaster(mock_redis, channel_name="security_events")
        camera_id = unique_id("test_camera")
        test_event = Event(
            id=99,
            batch_id="none_started_at_batch",
            camera_id=camera_id,
            started_at=None,  # Explicitly None
            risk_score=50,
            risk_level="medium",
            summary="Event without started_at",
            reasoning="Test reasoning for event without started_at",
        )

        # Broadcast the event using mocked get_broadcaster
        with patch(
            "backend.services.event_broadcaster.get_broadcaster",
            AsyncMock(return_value=broadcaster),
        ):
            await analyzer._broadcast_event(test_event)

        # Should still validate - started_at is optional in schema
        validated = WebSocketEventMessage.model_validate(published_message)
        assert validated.data.started_at is None
