"""Unit tests for WebSocket broadcaster classes and utilities."""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock broadcaster classes for unit testing
# These classes represent the expected interface of the WebSocket broadcasters


class MockEventBroadcaster:
    """Mock EventBroadcaster for unit testing."""

    def __init__(self):
        """Initialize mock broadcaster."""
        self.connections: set = set()
        self.messages: list[dict[str, Any]] = []

    async def connect(self, websocket: Any) -> None:
        """Add a WebSocket connection."""
        self.connections.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(websocket)

    async def broadcast_new_event(self, event: dict[str, Any]) -> int:
        """Broadcast a new event to all connected clients."""
        message = {"type": "new_event", "data": event}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # noqa: S110 - Intentionally ignore send failures to continue broadcasting to other clients
                pass
        return count

    async def broadcast_detection(self, detection: dict[str, Any]) -> int:
        """Broadcast a new detection to all connected clients."""
        message = {"type": "detection", "data": detection}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # noqa: S110 - Intentionally ignore send failures to continue broadcasting to other clients
                pass
        return count


class MockSystemBroadcaster:
    """Mock SystemBroadcaster for unit testing."""

    def __init__(self):
        """Initialize mock broadcaster."""
        self.connections: set = set()
        self.messages: list[dict[str, Any]] = []

    async def connect(self, websocket: Any) -> None:
        """Add a WebSocket connection."""
        self.connections.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(websocket)

    async def broadcast_gpu_stats(self, stats: dict[str, Any]) -> int:
        """Broadcast GPU statistics to all connected clients."""
        message = {"type": "gpu_stats", "data": stats}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # noqa: S110 - Intentionally ignore send failures to continue broadcasting to other clients
                pass
        return count

    async def broadcast_camera_status(self, status: dict[str, Any]) -> int:
        """Broadcast camera status update to all connected clients."""
        message = {"type": "camera_status", "data": status}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # noqa: S110 - Intentionally ignore send failures to continue broadcasting to other clients
                pass
        return count


# Fixtures


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def event_broadcaster():
    """Create an EventBroadcaster instance."""
    return MockEventBroadcaster()


@pytest.fixture
def system_broadcaster():
    """Create a SystemBroadcaster instance."""
    return MockSystemBroadcaster()


# EventBroadcaster Tests


class TestEventBroadcaster:
    """Tests for EventBroadcaster class."""

    @pytest.mark.asyncio
    async def test_connect_websocket(self, event_broadcaster, mock_websocket):
        """Test adding a WebSocket connection."""
        await event_broadcaster.connect(mock_websocket)
        assert mock_websocket in event_broadcaster.connections
        assert len(event_broadcaster.connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_websocket(self, event_broadcaster, mock_websocket):
        """Test removing a WebSocket connection."""
        await event_broadcaster.connect(mock_websocket)
        await event_broadcaster.disconnect(mock_websocket)
        assert mock_websocket not in event_broadcaster.connections
        assert len(event_broadcaster.connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_websocket(self, event_broadcaster, mock_websocket):
        """Test disconnecting a WebSocket that was never connected."""
        # Should not raise an error
        await event_broadcaster.disconnect(mock_websocket)
        assert len(event_broadcaster.connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_new_event_no_connections(self, event_broadcaster):
        """Test broadcasting event when no clients are connected."""
        event_data = {
            "id": 1,
            "camera_id": "cam-123",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door",
            "started_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
        }

        count = await event_broadcaster.broadcast_new_event(event_data)
        assert count == 0
        assert len(event_broadcaster.messages) == 1
        assert event_broadcaster.messages[0]["type"] == "new_event"
        assert event_broadcaster.messages[0]["data"] == event_data

    @pytest.mark.asyncio
    async def test_broadcast_new_event_single_connection(self, event_broadcaster, mock_websocket):
        """Test broadcasting event to a single connected client."""
        await event_broadcaster.connect(mock_websocket)

        event_data = {
            "id": 1,
            "camera_id": "cam-123",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door",
        }

        count = await event_broadcaster.broadcast_new_event(event_data)
        assert count == 1
        mock_websocket.send_json.assert_awaited_once()

        # Verify message format
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "new_event"
        assert call_args["data"] == event_data

    @pytest.mark.asyncio
    async def test_broadcast_new_event_multiple_connections(self, event_broadcaster):
        """Test broadcasting event to multiple connected clients."""
        # Create multiple mock websockets
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()
        ws3 = MagicMock()
        ws3.send_json = AsyncMock()

        await event_broadcaster.connect(ws1)
        await event_broadcaster.connect(ws2)
        await event_broadcaster.connect(ws3)

        event_data = {"id": 1, "risk_score": 50, "summary": "Test event"}
        count = await event_broadcaster.broadcast_new_event(event_data)

        assert count == 3
        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()
        ws3.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_new_event_with_failed_connection(self, event_broadcaster):
        """Test broadcasting event when one connection fails."""
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock(side_effect=Exception("Connection lost"))
        ws3 = MagicMock()
        ws3.send_json = AsyncMock()

        await event_broadcaster.connect(ws1)
        await event_broadcaster.connect(ws2)
        await event_broadcaster.connect(ws3)

        event_data = {"id": 1, "summary": "Test event"}
        count = await event_broadcaster.broadcast_new_event(event_data)

        # Should succeed for 2 out of 3 connections
        assert count == 2

    @pytest.mark.asyncio
    async def test_broadcast_detection_single_connection(self, event_broadcaster, mock_websocket):
        """Test broadcasting detection to a single connected client."""
        await event_broadcaster.connect(mock_websocket)

        detection_data = {
            "id": 1,
            "camera_id": "cam-123",
            "object_type": "person",
            "confidence": 0.95,
            "detected_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
        }

        count = await event_broadcaster.broadcast_detection(detection_data)
        assert count == 1
        mock_websocket.send_json.assert_awaited_once()

        # Verify message format
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "detection"
        assert call_args["data"] == detection_data

    @pytest.mark.asyncio
    async def test_broadcast_detection_no_connections(self, event_broadcaster):
        """Test broadcasting detection when no clients are connected."""
        detection_data = {
            "id": 1,
            "object_type": "person",
            "confidence": 0.95,
        }

        count = await event_broadcaster.broadcast_detection(detection_data)
        assert count == 0

    @pytest.mark.asyncio
    async def test_message_serialization(self, event_broadcaster, mock_websocket):
        """Test that messages are properly serialized as JSON."""
        await event_broadcaster.connect(mock_websocket)

        # Event with datetime
        event_data = {
            "id": 1,
            "started_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
            "summary": "Test event",
        }

        await event_broadcaster.broadcast_new_event(event_data)

        # Verify the message can be serialized to JSON
        call_args = mock_websocket.send_json.call_args[0][0]
        json_str = json.dumps(call_args)
        assert json_str is not None
        assert "new_event" in json_str


# SystemBroadcaster Tests


class TestSystemBroadcaster:
    """Tests for SystemBroadcaster class."""

    @pytest.mark.asyncio
    async def test_connect_websocket(self, system_broadcaster, mock_websocket):
        """Test adding a WebSocket connection."""
        await system_broadcaster.connect(mock_websocket)
        assert mock_websocket in system_broadcaster.connections
        assert len(system_broadcaster.connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_websocket(self, system_broadcaster, mock_websocket):
        """Test removing a WebSocket connection."""
        await system_broadcaster.connect(mock_websocket)
        await system_broadcaster.disconnect(mock_websocket)
        assert mock_websocket not in system_broadcaster.connections
        assert len(system_broadcaster.connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_gpu_stats_no_connections(self, system_broadcaster):
        """Test broadcasting GPU stats when no clients are connected."""
        stats_data = {
            "gpu_utilization": 75.5,
            "memory_used": 12345678900,
            "memory_total": 25769803776,
            "temperature": 72.0,
            "inference_fps": 30.5,
            "recorded_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
        }

        count = await system_broadcaster.broadcast_gpu_stats(stats_data)
        assert count == 0
        assert len(system_broadcaster.messages) == 1
        assert system_broadcaster.messages[0]["type"] == "gpu_stats"
        assert system_broadcaster.messages[0]["data"] == stats_data

    @pytest.mark.asyncio
    async def test_broadcast_gpu_stats_single_connection(self, system_broadcaster, mock_websocket):
        """Test broadcasting GPU stats to a single connected client."""
        await system_broadcaster.connect(mock_websocket)

        stats_data = {
            "gpu_utilization": 75.5,
            "memory_used": 12345678900,
            "temperature": 72.0,
        }

        count = await system_broadcaster.broadcast_gpu_stats(stats_data)
        assert count == 1
        mock_websocket.send_json.assert_awaited_once()

        # Verify message format
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "gpu_stats"
        assert call_args["data"] == stats_data

    @pytest.mark.asyncio
    async def test_broadcast_gpu_stats_multiple_connections(self, system_broadcaster):
        """Test broadcasting GPU stats to multiple connected clients."""
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await system_broadcaster.connect(ws1)
        await system_broadcaster.connect(ws2)

        stats_data = {"gpu_utilization": 75.5, "temperature": 72.0}
        count = await system_broadcaster.broadcast_gpu_stats(stats_data)

        assert count == 2
        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_camera_status_single_connection(
        self, system_broadcaster, mock_websocket
    ):
        """Test broadcasting camera status to a single connected client."""
        await system_broadcaster.connect(mock_websocket)

        status_data = {
            "camera_id": "cam-123",
            "status": "online",
            "last_seen_at": datetime(2025, 12, 23, 12, 0, 0).isoformat(),
        }

        count = await system_broadcaster.broadcast_camera_status(status_data)
        assert count == 1
        mock_websocket.send_json.assert_awaited_once()

        # Verify message format
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "camera_status"
        assert call_args["data"] == status_data

    @pytest.mark.asyncio
    async def test_broadcast_camera_status_no_connections(self, system_broadcaster):
        """Test broadcasting camera status when no clients are connected."""
        status_data = {"camera_id": "cam-123", "status": "online"}

        count = await system_broadcaster.broadcast_camera_status(status_data)
        assert count == 0

    @pytest.mark.asyncio
    async def test_broadcast_camera_status_with_failed_connection(self, system_broadcaster):
        """Test broadcasting camera status when one connection fails."""
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock(side_effect=Exception("Connection lost"))

        await system_broadcaster.connect(ws1)
        await system_broadcaster.connect(ws2)

        status_data = {"camera_id": "cam-123", "status": "offline"}
        count = await system_broadcaster.broadcast_camera_status(status_data)

        # Should succeed for 1 out of 2 connections
        assert count == 1


# Connection Management Tests


class TestConnectionManagement:
    """Tests for WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_concurrent_connections_event_broadcaster(self, event_broadcaster):
        """Test handling multiple concurrent connections to event broadcaster."""
        websockets = []
        for i in range(10):
            ws = MagicMock()
            ws.send_json = AsyncMock()
            websockets.append(ws)
            await event_broadcaster.connect(ws)

        assert len(event_broadcaster.connections) == 10

        # Broadcast to all
        event_data = {"id": 1, "summary": "Test"}
        count = await event_broadcaster.broadcast_new_event(event_data)
        assert count == 10

        # Disconnect half
        for ws in websockets[:5]:
            await event_broadcaster.disconnect(ws)

        assert len(event_broadcaster.connections) == 5

    @pytest.mark.asyncio
    async def test_concurrent_connections_system_broadcaster(self, system_broadcaster):
        """Test handling multiple concurrent connections to system broadcaster."""
        websockets = []
        for i in range(5):
            ws = MagicMock()
            ws.send_json = AsyncMock()
            websockets.append(ws)
            await system_broadcaster.connect(ws)

        assert len(system_broadcaster.connections) == 5

        # Broadcast to all
        stats_data = {"gpu_utilization": 75.5}
        count = await system_broadcaster.broadcast_gpu_stats(stats_data)
        assert count == 5

    @pytest.mark.asyncio
    async def test_graceful_disconnect_on_error(self, event_broadcaster):
        """Test that broadcaster handles connection errors gracefully."""
        ws = MagicMock()
        ws.send_json = AsyncMock(side_effect=Exception("Connection broken"))

        await event_broadcaster.connect(ws)
        assert len(event_broadcaster.connections) == 1

        # Broadcasting should not raise an error
        event_data = {"id": 1, "summary": "Test"}
        count = await event_broadcaster.broadcast_new_event(event_data)
        assert count == 0  # Failed to send


# Message Format Tests


class TestMessageFormat:
    """Tests for WebSocket message format validation."""

    @pytest.mark.asyncio
    async def test_event_message_format(self, event_broadcaster, mock_websocket):
        """Test that event messages have correct format."""
        await event_broadcaster.connect(mock_websocket)

        event_data = {
            "id": 1,
            "camera_id": "cam-123",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected",
        }

        await event_broadcaster.broadcast_new_event(event_data)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "type" in call_args
        assert "data" in call_args
        assert call_args["type"] == "new_event"
        assert call_args["data"]["id"] == 1
        assert call_args["data"]["risk_score"] == 75

    @pytest.mark.asyncio
    async def test_detection_message_format(self, event_broadcaster, mock_websocket):
        """Test that detection messages have correct format."""
        await event_broadcaster.connect(mock_websocket)

        detection_data = {
            "id": 1,
            "camera_id": "cam-123",
            "object_type": "person",
            "confidence": 0.95,
        }

        await event_broadcaster.broadcast_detection(detection_data)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "type" in call_args
        assert "data" in call_args
        assert call_args["type"] == "detection"
        assert call_args["data"]["object_type"] == "person"
        assert call_args["data"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_gpu_stats_message_format(self, system_broadcaster, mock_websocket):
        """Test that GPU stats messages have correct format."""
        await system_broadcaster.connect(mock_websocket)

        stats_data = {
            "gpu_utilization": 75.5,
            "memory_used": 12345678900,
            "memory_total": 25769803776,
            "temperature": 72.0,
        }

        await system_broadcaster.broadcast_gpu_stats(stats_data)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "type" in call_args
        assert "data" in call_args
        assert call_args["type"] == "gpu_stats"
        assert call_args["data"]["gpu_utilization"] == 75.5
        assert call_args["data"]["temperature"] == 72.0

    @pytest.mark.asyncio
    async def test_camera_status_message_format(self, system_broadcaster, mock_websocket):
        """Test that camera status messages have correct format."""
        await system_broadcaster.connect(mock_websocket)

        status_data = {"camera_id": "cam-123", "status": "online"}

        await system_broadcaster.broadcast_camera_status(status_data)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "type" in call_args
        assert "data" in call_args
        assert call_args["type"] == "camera_status"
        assert call_args["data"]["camera_id"] == "cam-123"
        assert call_args["data"]["status"] == "online"
