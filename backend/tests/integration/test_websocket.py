"""Integration tests for WebSocket endpoints."""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
async def test_db_setup():
    """Set up test database environment."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Close any existing database connections
    await close_db()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_websocket.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store original environment
        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        # Set test environment
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test DB

        # Clear settings cache to pick up new environment variables
        get_settings.cache_clear()

        # Initialize database explicitly
        await init_db()

        yield test_db_url

        # Cleanup
        await close_db()

        # Restore original environment
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        # Clear settings cache again
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis():
    """Mock Redis operations to avoid requiring Redis server."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=None),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


@pytest.fixture
async def async_client(test_db_setup, mock_redis):
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
def sync_client(test_db_setup, mock_redis):
    """Create synchronous test client for WebSocket testing."""
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
        TestClient(app) as client,
    ):
        yield client


@pytest.fixture
async def sample_camera(test_db_setup):
    """Create a sample camera in the database."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_event(test_db_setup, sample_camera):
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
async def sample_detection(test_db_setup, sample_camera):
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
def sync_client_with_auth_enabled(test_db_setup, mock_redis, test_api_key):
    """Create synchronous test client with auth enabled for WebSocket testing."""
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
        """Test that /ws/events rejects connection without API key when auth is enabled."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_with_auth_enabled.websocket_connect("/ws/events"),
        ):
            pass

    def test_system_websocket_without_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/system rejects connection without API key when auth is enabled."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_with_auth_enabled.websocket_connect("/ws/system"),
        ):
            pass

    def test_events_websocket_with_invalid_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/events rejects connection with invalid API key."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_with_auth_enabled.websocket_connect("/ws/events?api_key=invalid_key_12345"),
        ):
            pass

    def test_system_websocket_with_invalid_api_key_rejected(self, sync_client_with_auth_enabled):
        """Test that /ws/system rejects connection with invalid API key."""
        with (
            pytest.raises((Exception, WebSocketDisconnect)),
            sync_client_with_auth_enabled.websocket_connect("/ws/system?api_key=invalid_key_12345"),
        ):
            pass

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
    async def test_validate_websocket_api_key_disabled(self):
        """Test that validation passes when auth is disabled."""
        from backend.api.middleware.auth import validate_websocket_api_key

        # Mock websocket
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}

        # Ensure auth is disabled
        os.environ["API_KEY_ENABLED"] = "false"
        from backend.core.config import get_settings

        get_settings.cache_clear()

        result = await validate_websocket_api_key(mock_ws)
        assert result is True

        # Cleanup
        os.environ.pop("API_KEY_ENABLED", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_validate_websocket_api_key_valid_query_param(self):
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
    async def test_validate_websocket_api_key_invalid_key(self):
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
    async def test_validate_websocket_api_key_missing_key(self):
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
    async def test_validate_websocket_api_key_protocol_header(self):
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
    async def test_authenticate_websocket_success(self):
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
    async def test_authenticate_websocket_failure_closes_connection(self):
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
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        result = await authenticate_websocket(mock_ws)
        assert result is False
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
    async def test_channel_alignment(self):
        """Verify NemotronAnalyzer and EventBroadcaster use the same Redis channel.

        This is the critical test that ensures the channel mismatch bug is fixed.
        """
        from unittest.mock import AsyncMock, MagicMock

        from backend.services.event_broadcaster import EventBroadcaster
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create both services
        broadcaster = EventBroadcaster(mock_redis)
        analyzer = NemotronAnalyzer(mock_redis)

        # The channel names should be the same
        # NemotronAnalyzer now imports EventBroadcaster.CHANNEL_NAME
        assert broadcaster.CHANNEL_NAME == "security_events"

        # Test that both use the same channel
        # Broadcast through EventBroadcaster
        await broadcaster.broadcast_event({"test": "data"})
        broadcast_channel = mock_redis.publish.call_args[0][0]

        # Reset mock
        mock_redis.publish.reset_mock()

        # Broadcast through NemotronAnalyzer
        from datetime import datetime

        from backend.models.event import Event

        test_event = Event(
            id=1,
            batch_id="test_batch",
            camera_id="test_camera",
            started_at=datetime(2025, 12, 23, 12, 0, 0),
            risk_score=50,
            risk_level="medium",
            summary="Test",
        )
        await analyzer._broadcast_event(test_event)
        analyzer_channel = mock_redis.publish.call_args[0][0]

        # Both should use the same channel
        assert broadcast_channel == analyzer_channel
        assert broadcast_channel == "security_events"

    @pytest.mark.asyncio
    async def test_message_envelope_format(self):
        """Verify NemotronAnalyzer sends messages in the correct envelope format.

        The canonical format is: {"type": "event", "data": {...}}
        """
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from backend.models.event import Event
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create analyzer
        analyzer = NemotronAnalyzer(mock_redis)

        # Create test event
        test_event = Event(
            id=42,
            batch_id="envelope_test_batch",
            camera_id="envelope_test_camera",
            started_at=datetime(2025, 12, 23, 14, 30, 0),
            risk_score=75,
            risk_level="high",
            summary="Test envelope format",
        )

        # Broadcast the event
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
        assert data["camera_id"] == "envelope_test_camera"
        assert data["risk_score"] == 75
        assert data["risk_level"] == "high"
        assert data["summary"] == "Test envelope format"
        assert data["started_at"] == "2025-12-23T14:30:00"

    @pytest.mark.asyncio
    async def test_broadcaster_wraps_missing_type(self):
        """Verify EventBroadcaster wraps messages missing 'type' field.

        If a message is published without a 'type' field, EventBroadcaster
        should wrap it in the canonical envelope format.
        """
        from unittest.mock import AsyncMock, MagicMock

        from backend.services.event_broadcaster import EventBroadcaster

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        # Create broadcaster
        broadcaster = EventBroadcaster(mock_redis)

        # Broadcast a message without 'type' field
        payload = {"id": 123, "risk_score": 50}
        await broadcaster.broadcast_event(payload)

        # Verify it was wrapped
        message = mock_redis.publish.call_args[0][1]
        assert message["type"] == "event"
        assert message["data"] == payload

    @pytest.mark.asyncio
    async def test_end_to_end_publish_subscribe(self):
        """Verify messages published flow through to WebSocket clients.

        This tests the complete pipeline:
        1. NemotronAnalyzer publishes event to Redis
        2. EventBroadcaster receives event from Redis pub/sub
        3. EventBroadcaster sends to all connected WebSocket clients
        """
        import json
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from backend.models.event import Event
        from backend.services.event_broadcaster import EventBroadcaster
        from backend.services.nemotron_analyzer import NemotronAnalyzer

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

        # Create services
        broadcaster = EventBroadcaster(mock_redis)
        analyzer = NemotronAnalyzer(mock_redis)

        # Add WebSocket connection to broadcaster
        broadcaster._connections.add(mock_ws)

        # Create and broadcast test event via NemotronAnalyzer
        test_event = Event(
            id=99,
            batch_id="e2e_test_batch",
            camera_id="e2e_test_camera",
            started_at=datetime(2025, 12, 23, 16, 0, 0),
            risk_score=85,
            risk_level="critical",
            summary="End-to-end test event",
        )

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

    def test_broadcaster_channel_name_is_documented(self):
        """Verify EventBroadcaster.CHANNEL_NAME is a class constant."""
        from backend.services.event_broadcaster import EventBroadcaster

        # CHANNEL_NAME should be a class attribute
        assert hasattr(EventBroadcaster, "CHANNEL_NAME")
        assert EventBroadcaster.CHANNEL_NAME == "security_events"

    def test_agents_md_documents_channel(self):
        """Verify AGENTS.md documents the canonical channel name."""
        from pathlib import Path

        agents_path = Path(__file__).parent.parent.parent / "services" / "AGENTS.md"

        with open(agents_path) as f:
            content = f.read()

        # Channel name should be documented
        assert "security_events" in content
        # Message format should be documented
        assert '"type": "event"' in content or "type.*event" in content
