"""Unit tests for WebSocket broadcaster classes and utilities.

This module contains unit tests for the Mock broadcaster classes used in testing.
These mocks match the real implementation interfaces for EventBroadcaster and
SystemBroadcaster.

IMPORTANT: The mock classes in this file must match the public interface of the
real implementations. Tests at the end of this file verify this interface compatibility.

Real implementations:
- backend.services.event_broadcaster.EventBroadcaster
- backend.services.system_broadcaster.SystemBroadcaster
"""

import inspect
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock broadcaster classes for unit testing
# These classes represent the expected interface of the WebSocket broadcasters


class MockEventBroadcaster:
    """Mock EventBroadcaster for unit testing.

    Matches the interface of backend.services.event_broadcaster.EventBroadcaster:
    - __init__(redis_client, channel_name=None)
    - CHANNEL_NAME property (class-level, returns settings value)
    - channel_name property (instance-level)
    - start() -> None
    - stop() -> None
    - connect(websocket) -> None
    - disconnect(websocket) -> None
    - broadcast_event(event_data) -> int
    - broadcast_service_status(status_data) -> int
    - broadcast_scene_change(scene_change_data) -> int
    - broadcast_camera_status(camera_status_data) -> int
    - broadcast_alert(alert_data, event_type) -> int
    - broadcast_infrastructure_alert(alert_data) -> int
    - broadcast_worker_status(worker_status_data) -> int (NEM-2461)
    - broadcast_detection_new(detection_data) -> int (NEM-2506)
    - broadcast_detection_batch(batch_data) -> int (NEM-2506)
    - broadcast_batch_analysis_started(batch_data) -> int
    - broadcast_batch_analysis_completed(batch_data) -> int
    - broadcast_batch_analysis_failed(batch_data) -> int
    - get_circuit_state() -> str
    - get_broadcast_metrics() -> dict (NEM-2984)
    - get_instance() -> EventBroadcaster (class method)
    """

    CHANNEL_NAME = "security_events"  # Matches real implementation default

    def __init__(self, redis_client: Any = None, channel_name: str | None = None):
        """Initialize mock broadcaster.

        Args:
            redis_client: Mock Redis client (ignored in mock)
            channel_name: Optional channel name override
        """
        self._redis = redis_client
        self._channel_name = channel_name or self.CHANNEL_NAME
        self._connections: set = set()
        self._is_listening = False
        self._listener_healthy = True
        self.messages: list[dict[str, Any]] = []

    @property
    def channel_name(self) -> str:
        """Get the Redis channel name for this broadcaster instance."""
        return self._channel_name

    @property
    def connections(self) -> set:
        """Alias for _connections to maintain backward compatibility with tests."""
        return self._connections

    async def start(self) -> None:
        """Start listening for events from Redis pub/sub."""
        self._is_listening = True

    async def stop(self) -> None:
        """Stop listening for events and cleanup resources."""
        self._is_listening = False
        for ws in list(self._connections):
            await self.disconnect(ws)

    async def connect(self, websocket: Any) -> None:
        """Add a WebSocket connection."""
        self._connections.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        """Remove a WebSocket connection."""
        self._connections.discard(websocket)

    async def broadcast_event(self, event_data: dict[str, Any]) -> int:
        """Broadcast an event to all connected WebSocket clients via Redis pub/sub.

        Args:
            event_data: Event data dictionary containing event details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in event_data:
            event_data = {"type": "event", "data": event_data}

        self.messages.append(event_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(event_data)
                count += 1
            except Exception:
                pass
        return count

    async def broadcast_service_status(self, status_data: dict[str, Any]) -> int:
        """Broadcast a service status message to all connected WebSocket clients.

        Args:
            status_data: Status data dictionary containing service status details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in status_data:
            status_data = {"type": "service_status", "data": status_data}

        self.messages.append(status_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(status_data)
                count += 1
            except Exception:
                pass

        return count

    def get_circuit_state(self) -> str:
        """Get the current circuit breaker state.

        Returns:
            Circuit breaker state string (e.g., "closed", "open", "half_open")
        """
        return "closed"  # Mock always returns healthy state

    def is_listener_healthy(self) -> bool:
        """Check if the listener is currently healthy.

        Returns:
            True if listener is running and healthy, False otherwise
        """
        return self._is_listening and self._listener_healthy

    def is_degraded(self) -> bool:
        """Check if the broadcaster is in degraded mode.

        Returns:
            True if broadcaster is in degraded mode, False otherwise
        """
        return getattr(self, "_is_degraded", False)

    def get_messages_since(
        self, last_sequence: int, mark_as_replay: bool = False
    ) -> list[dict[str, Any]]:
        """Get all buffered messages since a given sequence number.

        Args:
            last_sequence: The last sequence number the client received.
            mark_as_replay: If True, add replay=True to returned messages.

        Returns:
            List of messages with sequence > last_sequence.
        """
        # Mock implementation returns empty list
        return []

    def get_broadcast_metrics(self) -> dict[str, Any]:
        """Get broadcast retry metrics as a dictionary.

        Returns:
            Dictionary with broadcast metrics for monitoring/logging
        """
        # Mock implementation returns empty metrics
        return {}

    def record_ack(self, websocket: Any, sequence: int) -> None:
        """Record a client's acknowledgment of a sequence number.

        Args:
            websocket: The client's WebSocket connection.
            sequence: The sequence number being acknowledged.
        """
        # Mock implementation does nothing
        pass

    def get_last_ack(self, websocket: Any) -> int:
        """Get the last acknowledged sequence for a client.

        Args:
            websocket: The client's WebSocket connection.

        Returns:
            The last acknowledged sequence number, or 0 if none.
        """
        return 0

    async def broadcast_scene_change(self, scene_change_data: dict[str, Any]) -> int:
        """Broadcast a scene change message to all connected WebSocket clients.

        Args:
            scene_change_data: Scene change data dictionary containing detection details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in scene_change_data:
            scene_change_data = {"type": "scene_change", "data": scene_change_data}

        self.messages.append(scene_change_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(scene_change_data)
                count += 1
            except Exception:
                pass
        return count

    async def broadcast_camera_status(self, camera_status_data: dict[str, Any]) -> int:
        """Broadcast a camera status change message to all connected WebSocket clients.

        Args:
            camera_status_data: Camera status data dictionary containing status details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in camera_status_data:
            camera_status_data = {"type": "camera_status", "data": camera_status_data}

        self.messages.append(camera_status_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(camera_status_data)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_alert(self, alert_data: dict[str, Any], event_type: Any) -> int:
        """Broadcast an alert message to all connected WebSocket clients.

        Args:
            alert_data: Alert data dictionary containing alert details
            event_type: Type of alert event (ALERT_CREATED, ALERT_ACKNOWLEDGED, ALERT_DISMISSED)

        Returns:
            Number of clients that received the message
        """
        # Determine message type based on event_type
        type_mapping = {
            "alert_created": "alert_created",
            "alert_acknowledged": "alert_acknowledged",
            "alert_dismissed": "alert_dismissed",
        }
        message_type = type_mapping.get(str(event_type).lower().split(".")[-1], "alert")

        message = {"type": message_type, "data": alert_data}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_infrastructure_alert(self, alert_data: dict[str, Any]) -> int:
        """Broadcast an infrastructure alert to all connected WebSocket clients.

        Infrastructure alerts originate from Prometheus/Alertmanager webhooks and represent
        system health issues (GPU memory, database connections, pipeline health, etc.)
        separate from AI-generated security alerts.

        Args:
            alert_data: Infrastructure alert data dictionary

        Returns:
            Number of clients that received the message
        """
        message = {"type": "infrastructure_alert", "data": alert_data}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_worker_status(self, worker_status_data: dict[str, Any]) -> int:
        """Broadcast a worker status message to all connected WebSocket clients (NEM-2461).

        Args:
            worker_status_data: Worker status data dictionary containing worker state details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in worker_status_data:
            worker_status_data = {"type": "worker_status", "data": worker_status_data}

        self.messages.append(worker_status_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(worker_status_data)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_detection_new(self, detection_data: dict[str, Any]) -> int:
        """Broadcast a new detection message to all connected WebSocket clients (NEM-2506).

        Args:
            detection_data: Detection data dictionary containing detection details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in detection_data:
            detection_data = {"type": "detection.new", "data": detection_data}

        self.messages.append(detection_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(detection_data)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_detection_batch(self, batch_data: dict[str, Any]) -> int:
        """Broadcast a detection batch message to all connected WebSocket clients (NEM-2506).

        Args:
            batch_data: Batch data dictionary containing batch details

        Returns:
            Number of clients that received the message
        """
        # Ensure the message has the correct structure (matches real implementation)
        if "type" not in batch_data:
            batch_data = {"type": "detection.batch", "data": batch_data}

        self.messages.append(batch_data)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(batch_data)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_batch_analysis_started(self, batch_data: dict[str, Any]) -> int:
        """Broadcast a batch.analysis_started message to all connected WebSocket clients.

        Args:
            batch_data: Batch data dictionary containing batch analysis details

        Returns:
            Number of clients that received the message
        """
        message = {"type": "batch.analysis_started", "data": batch_data}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_batch_analysis_completed(self, batch_data: dict[str, Any]) -> int:
        """Broadcast a batch.analysis_completed message to all connected WebSocket clients.

        Args:
            batch_data: Batch data dictionary containing batch analysis completion details

        Returns:
            Number of clients that received the message
        """
        message = {"type": "batch.analysis_completed", "data": batch_data}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_batch_analysis_failed(self, batch_data: dict[str, Any]) -> int:
        """Broadcast a batch.analysis_failed message to all connected WebSocket clients.

        Args:
            batch_data: Batch data dictionary containing batch analysis failure details

        Returns:
            Number of clients that received the message
        """
        message = {"type": "batch.analysis_failed", "data": batch_data}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    async def broadcast_summary_update(
        self,
        hourly: dict[str, Any] | None = None,
        daily: dict[str, Any] | None = None,
    ) -> int:
        """Broadcast a summary update message to all connected WebSocket clients (NEM-2893).

        Args:
            hourly: Hourly summary data dictionary (optional)
            daily: Daily summary data dictionary (optional)

        Returns:
            Number of clients that received the message
        """
        message = {
            "type": "summary_update",
            "data": {"hourly": hourly, "daily": daily},
        }
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:  # Intentionally ignore send failures
                pass
        return count

    @classmethod
    def get_instance(cls) -> MockEventBroadcaster:
        """Get the global mock event broadcaster instance.

        Returns:
            The mock EventBroadcaster instance (returns new instance for testing)
        """
        return cls()

    # Legacy test-only methods - NOT part of real EventBroadcaster interface
    # These are convenience methods used by existing tests in this file
    async def broadcast_new_event(self, event: dict[str, Any]) -> int:
        """Broadcast a new event (test-only method, not in real implementation)."""
        message = {"type": "new_event", "data": event}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:
                pass
        return count

    async def broadcast_detection(self, detection: dict[str, Any]) -> int:
        """Broadcast a new detection (test-only method, not in real implementation)."""
        message = {"type": "detection", "data": detection}
        self.messages.append(message)
        count = 0
        for connection in self._connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:
                pass
        return count


class MockSystemBroadcaster:
    """Mock SystemBroadcaster for unit testing.

    Matches the interface of backend.services.system_broadcaster.SystemBroadcaster:
    - __init__(redis_client=None, redis_getter=None)
    - connections: set[WebSocket] attribute
    - _broadcast_task: asyncio.Task | None attribute
    - _listener_task: asyncio.Task | None attribute
    - _running: bool attribute
    - _redis_client: RedisClient | None attribute
    - _redis_getter: Callable | None attribute
    - _pubsub: PubSub | None attribute
    - _pubsub_listening: bool attribute
    - _performance_collector: PerformanceCollector | None attribute
    - _get_redis() -> RedisClient | None
    - set_redis_client(redis_client) -> None
    - set_performance_collector(collector) -> None
    - connect(websocket) -> None
    - disconnect(websocket) -> None
    - broadcast_status(status_data) -> None
    - broadcast_performance() -> None
    - start_broadcasting(interval=5.0) -> None
    - stop_broadcasting() -> None
    - get_circuit_state() -> str
    - is_degraded() -> bool
    - get_performance_history(time_range) -> list[PerformanceUpdate]
    """

    def __init__(
        self,
        redis_client: Any = None,
        redis_getter: Any = None,
    ):
        """Initialize mock broadcaster.

        Args:
            redis_client: Optional Redis client instance
            redis_getter: Optional callable that returns a Redis client
        """
        self.connections: set = set()
        self._broadcast_task: Any = None
        self._listener_task: Any = None
        self._running = False
        self._redis_client = redis_client
        self._redis_getter = redis_getter
        self._pubsub: Any = None
        self._pubsub_listening = False
        self._performance_collector: Any = None
        # Test-only attribute for capturing broadcast messages
        self.messages: list[dict[str, Any]] = []

    def _get_redis(self) -> Any:
        """Get the Redis client instance.

        Returns the directly injected redis_client if available, otherwise
        calls redis_getter if provided.

        Returns:
            RedisClient instance or None if unavailable
        """
        if self._redis_client is not None:
            return self._redis_client
        if self._redis_getter is not None:
            return self._redis_getter()
        return None

    def set_redis_client(self, redis_client: Any) -> None:
        """Set the Redis client after initialization.

        Args:
            redis_client: Redis client instance or None
        """
        self._redis_client = redis_client

    def set_performance_collector(self, collector: Any) -> None:
        """Set the performance collector for metrics broadcasting.

        Args:
            collector: PerformanceCollector instance or None
        """
        self._performance_collector = collector

    async def broadcast_performance(self) -> None:
        """Broadcast performance metrics to all connected clients.

        Collects metrics from PerformanceCollector and broadcasts them.
        No-op if no collector is configured.
        """
        if self._performance_collector is None:
            return
        # In real impl, would collect and broadcast performance metrics
        pass

    async def connect(self, websocket: Any) -> None:
        """Add a WebSocket connection."""
        self.connections.add(websocket)

    async def disconnect(self, websocket: Any) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(websocket)

    async def broadcast_status(self, status_data: dict[str, Any]) -> None:
        """Broadcast system status to all connected clients.

        Args:
            status_data: System status data to broadcast
        """
        self.messages.append(status_data)
        failed_connections = set()

        for websocket in self.connections:
            try:
                await websocket.send_json(status_data)
            except Exception:
                failed_connections.add(websocket)

        # Remove failed connections
        self.connections -= failed_connections

    async def start_broadcasting(self, interval: float = 5.0) -> None:
        """Start periodic broadcasting of system status.

        Args:
            interval: Seconds between broadcasts (default: 5.0)
        """
        self._running = True

    async def stop_broadcasting(self) -> None:
        """Stop periodic broadcasting of system status."""
        self._running = False

    def get_circuit_state(self) -> str:
        """Get the current circuit breaker state.

        Returns:
            Circuit breaker state string (e.g., "closed", "open", "half_open")
        """
        return "closed"  # Mock always returns healthy state

    def is_degraded(self) -> bool:
        """Check if the broadcaster is in degraded mode.

        Returns:
            True if broadcaster is in degraded mode, False otherwise
        """
        return False  # Mock always returns healthy state

    def get_performance_history(self, time_range: Any) -> list:
        """Get historical performance snapshots for the requested time range.

        Args:
            time_range: TimeRange enum value (FIVE_MIN, FIFTEEN_MIN, SIXTY_MIN)

        Returns:
            List of PerformanceUpdate snapshots (empty for mock)
        """
        return []  # Mock returns empty history

    async def start(self) -> None:
        """Start the broadcaster (async context manager support).

        Sets _running to True. Added in NEM-1599 to support
        async context manager pattern.
        """
        self._running = True

    async def stop(self) -> None:
        """Stop the broadcaster (async context manager support).

        Sets _running to False. Added in NEM-1599 to support
        async context manager pattern.
        """
        self._running = False

    async def broadcast_circuit_breaker_states(self, states: dict[str, Any]) -> None:
        """Broadcast circuit breaker states to all connected clients.

        Args:
            states: Circuit breaker states data to broadcast
        """
        self.messages.append({"type": "circuit_breaker_states", "data": states})
        failed_connections = set()

        for websocket in self.connections:
            try:
                await websocket.send_json({"type": "circuit_breaker_states", "data": states})
            except Exception:
                failed_connections.add(websocket)

        # Remove failed connections
        self.connections -= failed_connections

    # ==========================================================================
    # Test-only methods below - NOT part of the real SystemBroadcaster interface
    # These are convenience methods for tests in this file only.
    # ==========================================================================

    async def broadcast_gpu_stats(self, stats: dict[str, Any]) -> int:
        """[TEST ONLY] Broadcast GPU statistics.

        Note: This method does NOT exist in the real SystemBroadcaster.
        It's a test convenience method for verifying broadcast behavior.
        """
        message = {"type": "gpu_stats", "data": stats}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:
                pass
        return count

    async def broadcast_camera_status(self, status: dict[str, Any]) -> int:
        """[TEST ONLY] Broadcast camera status update.

        Note: This method does NOT exist in the real SystemBroadcaster.
        It's a test convenience method for verifying broadcast behavior.
        """
        message = {"type": "camera_status", "data": status}
        self.messages.append(message)
        count = 0
        for connection in self.connections:
            try:
                await connection.send_json(message)
                count += 1
            except Exception:
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


# =============================================================================
# Interface Verification Tests
# =============================================================================
# These tests verify that mock classes match the public interfaces of real
# implementations. This prevents the mock from drifting out of sync with
# the real implementation.


class TestMockInterfaceCompatibility:
    """Verify mock classes match real implementation interfaces.

    These tests ensure that:
    1. All public methods in real implementations exist in mocks
    2. Method signatures are compatible
    3. Any drift between mock and real implementation is caught early

    This addresses the concern that tests pass with mocks but fail with real
    implementations due to interface mismatches (e.g., mock has broadcast_new_event
    but real implementation has broadcast_event).
    """

    def test_mock_event_broadcaster_has_real_public_methods(self):
        """Verify MockEventBroadcaster has all public methods from EventBroadcaster.

        This test imports the real EventBroadcaster and verifies that all its
        public methods (not starting with _) exist on MockEventBroadcaster.
        """
        from backend.services.event_broadcaster import EventBroadcaster

        real_public_methods = {
            name
            for name, method in inspect.getmembers(EventBroadcaster, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        # Also include async methods (coroutines)
        for name in dir(EventBroadcaster):
            if not name.startswith("_"):
                attr = getattr(EventBroadcaster, name, None)
                if inspect.iscoroutinefunction(attr) or inspect.isfunction(attr):
                    real_public_methods.add(name)

        # Remove __init__ as it has a different purpose in mocks
        real_public_methods.discard("__init__")

        mock_methods = {
            name
            for name in dir(MockEventBroadcaster)
            if not name.startswith("_") and callable(getattr(MockEventBroadcaster, name, None))
        }

        # Check that all real public methods exist in mock
        missing_methods = real_public_methods - mock_methods
        assert not missing_methods, (
            f"MockEventBroadcaster is missing methods from real EventBroadcaster: "
            f"{missing_methods}. Update MockEventBroadcaster to include these methods."
        )

    def test_mock_system_broadcaster_has_real_public_methods(self):
        """Verify MockSystemBroadcaster has all public methods from SystemBroadcaster.

        This test imports the real SystemBroadcaster and verifies that all its
        public methods (not starting with _) exist on MockSystemBroadcaster.
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        real_public_methods = {
            name
            for name, method in inspect.getmembers(SystemBroadcaster, predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        # Also include async methods (coroutines)
        for name in dir(SystemBroadcaster):
            if not name.startswith("_"):
                attr = getattr(SystemBroadcaster, name, None)
                if inspect.iscoroutinefunction(attr) or inspect.isfunction(attr):
                    real_public_methods.add(name)

        # Remove __init__ as it has a different purpose in mocks
        real_public_methods.discard("__init__")

        mock_methods = {
            name
            for name in dir(MockSystemBroadcaster)
            if not name.startswith("_") and callable(getattr(MockSystemBroadcaster, name, None))
        }

        # Check that all real public methods exist in mock
        missing_methods = real_public_methods - mock_methods
        assert not missing_methods, (
            f"MockSystemBroadcaster is missing methods from real SystemBroadcaster: "
            f"{missing_methods}. Update MockSystemBroadcaster to include these methods."
        )

    def test_event_broadcaster_broadcast_event_signature(self):
        """Verify broadcast_event method exists and is async in both mock and real."""
        from backend.services.event_broadcaster import EventBroadcaster

        # Verify real implementation has broadcast_event
        assert hasattr(EventBroadcaster, "broadcast_event"), (
            "EventBroadcaster should have broadcast_event method"
        )
        assert inspect.iscoroutinefunction(EventBroadcaster.broadcast_event), (
            "EventBroadcaster.broadcast_event should be async"
        )

        # Verify mock has broadcast_event
        assert hasattr(MockEventBroadcaster, "broadcast_event"), (
            "MockEventBroadcaster should have broadcast_event method"
        )
        assert inspect.iscoroutinefunction(MockEventBroadcaster.broadcast_event), (
            "MockEventBroadcaster.broadcast_event should be async"
        )

    def test_system_broadcaster_broadcast_status_signature(self):
        """Verify broadcast_status method exists and is async in both mock and real."""
        from backend.services.system_broadcaster import SystemBroadcaster

        # Verify real implementation has broadcast_status
        assert hasattr(SystemBroadcaster, "broadcast_status"), (
            "SystemBroadcaster should have broadcast_status method"
        )
        assert inspect.iscoroutinefunction(SystemBroadcaster.broadcast_status), (
            "SystemBroadcaster.broadcast_status should be async"
        )

        # Verify mock has broadcast_status
        assert hasattr(MockSystemBroadcaster, "broadcast_status"), (
            "MockSystemBroadcaster should have broadcast_status method"
        )
        assert inspect.iscoroutinefunction(MockSystemBroadcaster.broadcast_status), (
            "MockSystemBroadcaster.broadcast_status should be async"
        )

    def test_mock_only_methods_are_documented(self):
        """Verify that mock-only methods (not in real impl) are documented as such.

        This ensures any developer using the mock is aware that certain methods
        only exist for testing convenience and should not be relied upon in
        production code.
        """
        from backend.services.event_broadcaster import EventBroadcaster
        from backend.services.system_broadcaster import SystemBroadcaster

        # Get methods that exist in mock but not in real EventBroadcaster
        mock_event_methods = {
            name
            for name in dir(MockEventBroadcaster)
            if not name.startswith("_") and callable(getattr(MockEventBroadcaster, name, None))
        }
        real_event_methods = {
            name
            for name in dir(EventBroadcaster)
            if not name.startswith("_") and callable(getattr(EventBroadcaster, name, None))
        }
        mock_only_event_methods = mock_event_methods - real_event_methods

        # Verify mock-only methods have "test" in their docstring or name
        for method_name in mock_only_event_methods:
            method = getattr(MockEventBroadcaster, method_name, None)
            if method:
                docstring = method.__doc__ or ""
                assert "test" in docstring.lower() or "test" in method_name.lower(), (
                    f"MockEventBroadcaster.{method_name} exists only in mock but is not "
                    f"documented as test-only. Add 'test' to docstring or method name."
                )

        # Get methods that exist in mock but not in real SystemBroadcaster
        mock_system_methods = {
            name
            for name in dir(MockSystemBroadcaster)
            if not name.startswith("_") and callable(getattr(MockSystemBroadcaster, name, None))
        }
        real_system_methods = {
            name
            for name in dir(SystemBroadcaster)
            if not name.startswith("_") and callable(getattr(SystemBroadcaster, name, None))
        }
        mock_only_system_methods = mock_system_methods - real_system_methods

        # Verify mock-only methods have "test" in their docstring
        for method_name in mock_only_system_methods:
            method = getattr(MockSystemBroadcaster, method_name, None)
            if method:
                docstring = method.__doc__ or ""
                assert "test" in docstring.lower() or "test" in method_name.lower(), (
                    f"MockSystemBroadcaster.{method_name} exists only in mock but is not "
                    f"documented as test-only. Add 'test' to docstring or method name."
                )
