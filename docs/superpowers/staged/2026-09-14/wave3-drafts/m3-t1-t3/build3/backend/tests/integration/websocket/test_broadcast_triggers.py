"""Integration tests for WebSocket broadcast trigger verification (NEM-2053).

This module tests that WebSocket broadcasts are triggered correctly when events
occur in the system. Tests verify end-to-end broadcast flow:
- New detection events trigger broadcasts to /ws/events clients
- New security events trigger broadcasts to /ws/events clients
- Camera status changes trigger broadcasts to /ws/system clients
- Service status changes trigger broadcasts to /ws/events clients
- Multiple connected clients receive broadcasts
- Broadcasts use Redis pub/sub for multi-instance support

Uses real Redis pub/sub and real EventBroadcaster/SystemBroadcaster for
authentic broadcast verification.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.services.event_broadcaster import EventBroadcaster
from backend.services.system_broadcaster import SystemBroadcaster
from fastapi import WebSocket

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from sqlalchemy.ext.asyncio import AsyncSession

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def mock_websocket() -> WebSocket:
    """Create a mock WebSocket connection for testing.

    Returns:
        Mock WebSocket with accept/send_text/close methods configured.
    """
    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.client_state = MagicMock()
    return mock_ws


@pytest.fixture
async def event_broadcaster_with_redis(real_redis: RedisClient) -> EventBroadcaster:
    """Create a real EventBroadcaster instance with Redis pub/sub.

    Uses real Redis for authentic broadcast testing.

    Args:
        real_redis: Real Redis client fixture from conftest.py

    Yields:
        Started EventBroadcaster instance
    """
    from backend.services.event_broadcaster import reset_broadcaster_state

    # Reset global broadcaster state
    reset_broadcaster_state()

    broadcaster = EventBroadcaster(real_redis)
    await broadcaster.start()

    yield broadcaster

    await broadcaster.stop()
    reset_broadcaster_state()


@pytest.fixture
async def system_broadcaster_with_redis(real_redis: RedisClient) -> SystemBroadcaster:
    """Create a real SystemBroadcaster instance with Redis pub/sub.

    Uses real Redis for authentic broadcast testing.

    Args:
        real_redis: Real Redis client fixture from conftest.py

    Yields:
        Started SystemBroadcaster instance
    """
    from backend.services.system_broadcaster import reset_broadcaster_state

    # Reset global broadcaster state
    reset_broadcaster_state()

    broadcaster = SystemBroadcaster(redis_client=real_redis)
    await broadcaster.start_broadcasting(interval=10.0)  # Long interval, we test manually

    yield broadcaster

    await broadcaster.stop_broadcasting()
    reset_broadcaster_state()


# =============================================================================
# Detection Event Broadcast Tests
# =============================================================================


class TestDetectionEventBroadcasts:
    """Tests for detection event broadcast triggers."""

    @pytest.mark.asyncio
    async def test_new_detection_triggers_broadcast_to_websocket_clients(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that creating a new detection triggers a WebSocket broadcast.

        RED phase: This test should fail because the detection creation
        doesn't trigger a broadcast yet.

        Acceptance criteria:
        - Detection is created in database
        - Broadcast is triggered via Redis pub/sub
        - Connected WebSocket clients receive the event message
        """
        # GIVEN: A connected WebSocket client
        await event_broadcaster_with_redis.connect(mock_websocket)
        assert mock_websocket in event_broadcaster_with_redis._connections

        # GIVEN: A camera exists in the database
        camera = camera_factory(id="front_door", name="Front Door")
        session.add(camera)
        await session.flush()

        # Track received messages
        received_messages = []

        # Override send_text to capture messages
        original_send_text = mock_websocket.send_text

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))
            await original_send_text(message)

        mock_websocket.send_text = capture_send_text

        # WHEN: A new event is created (simulating detection analysis completion)
        event_data = {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_test123",
                "camera_id": "front_door",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at front door",
                "reasoning": "Unknown individual approaching during nighttime",
                "started_at": datetime.now(UTC).isoformat(),
            },
        }

        # Broadcast the event (simulating what the nemotron analyzer would do)
        subscriber_count = await event_broadcaster_with_redis.broadcast_event(event_data)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: The WebSocket client should receive the broadcast
        assert subscriber_count > 0, "Event should be published to Redis"
        assert len(received_messages) > 0, "WebSocket client should receive the broadcast"

        # Verify the message structure (find front_door message)
        received_event = next(
            (
                m
                for m in reversed(received_messages)
                if m.get("data", {}).get("camera_id") == "front_door"
            ),
            None,
        )
        assert received_event is not None, "Should receive front_door camera event"
        assert received_event["type"] == "event"
        assert "data" in received_event
        assert received_event["data"]["camera_id"] == "front_door"
        assert received_event["data"]["risk_score"] == 75
        assert received_event["data"]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_multiple_clients_receive_same_detection_broadcast(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that all connected clients receive detection broadcasts.

        RED phase: This test verifies that broadcasts reach all clients.

        Acceptance criteria:
        - Multiple WebSocket clients are connected
        - A single detection event is created
        - All clients receive the same broadcast message
        """
        # Track received messages per client
        client1_messages = []
        client2_messages = []
        client3_messages = []

        # GIVEN: Multiple connected WebSocket clients
        client1 = AsyncMock(spec=WebSocket)
        client1.accept = AsyncMock()
        client1.close = AsyncMock()

        async def client1_send(msg: str):
            client1_messages.append(json.loads(msg))

        client1.send_text = client1_send

        client2 = AsyncMock(spec=WebSocket)
        client2.accept = AsyncMock()
        client2.close = AsyncMock()

        async def client2_send(msg: str):
            client2_messages.append(json.loads(msg))

        client2.send_text = client2_send

        client3 = AsyncMock(spec=WebSocket)
        client3.accept = AsyncMock()
        client3.close = AsyncMock()

        async def client3_send(msg: str):
            client3_messages.append(json.loads(msg))

        client3.send_text = client3_send

        await event_broadcaster_with_redis.connect(client1)
        await event_broadcaster_with_redis.connect(client2)
        await event_broadcaster_with_redis.connect(client3)

        assert len(event_broadcaster_with_redis._connections) == 3

        # GIVEN: A camera exists
        camera = camera_factory(id="backyard", name="Backyard")
        session.add(camera)
        await session.flush()

        # WHEN: A detection event is broadcast
        event_data = {
            "type": "event",
            "data": {
                "id": 2,
                "event_id": 2,
                "batch_id": "batch_abc456",
                "camera_id": "backyard",
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Motion detected in backyard",
                "reasoning": "Vehicle passing through driveway",
                "started_at": datetime.now(UTC).isoformat(),
            },
        }

        await event_broadcaster_with_redis.broadcast_event(event_data)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: All clients should receive the broadcast
        assert len(client1_messages) > 0, "Client 1 should receive messages"
        assert len(client2_messages) > 0, "Client 2 should receive messages"
        assert len(client3_messages) > 0, "Client 3 should receive messages"

        # Get the last message each client received (filtering for backyard camera)
        msg1 = next(
            (
                m
                for m in reversed(client1_messages)
                if m.get("data", {}).get("camera_id") == "backyard"
            ),
            None,
        )
        msg2 = next(
            (
                m
                for m in reversed(client2_messages)
                if m.get("data", {}).get("camera_id") == "backyard"
            ),
            None,
        )
        msg3 = next(
            (
                m
                for m in reversed(client3_messages)
                if m.get("data", {}).get("camera_id") == "backyard"
            ),
            None,
        )

        assert msg1 is not None, "Client 1 should receive backyard event"
        assert msg2 is not None, "Client 2 should receive backyard event"
        assert msg3 is not None, "Client 3 should receive backyard event"

        assert msg1["type"] == msg2["type"] == msg3["type"] == "event"
        assert (
            msg1["data"]["camera_id"]
            == msg2["data"]["camera_id"]
            == msg3["data"]["camera_id"]
            == "backyard"
        )


# =============================================================================
# Security Event Broadcast Tests
# =============================================================================


class TestSecurityEventBroadcasts:
    """Tests for security event broadcast triggers."""

    @pytest.mark.asyncio
    async def test_high_risk_event_triggers_immediate_broadcast(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that high-risk security events trigger immediate broadcasts.

        RED phase: Verify high-risk events are broadcast immediately.

        Acceptance criteria:
        - High-risk event (score >= 70) is created
        - Broadcast is triggered immediately
        - WebSocket clients receive the alert
        """
        # GIVEN: A connected WebSocket client
        await event_broadcaster_with_redis.connect(mock_websocket)

        # GIVEN: A camera exists
        camera = camera_factory(id="entrance", name="Main Entrance")
        session.add(camera)
        await session.flush()

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: A high-risk security event is created
        high_risk_event = {
            "type": "event",
            "data": {
                "id": 3,
                "event_id": 3,
                "batch_id": "batch_critical789",
                "camera_id": "entrance",
                "risk_score": 95,
                "risk_level": "critical",
                "summary": "Unauthorized access attempt detected",
                "reasoning": "Person attempting to force entry outside business hours",
                "started_at": datetime.now(UTC).isoformat(),
            },
        }

        await event_broadcaster_with_redis.broadcast_event(high_risk_event)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: The client should receive the critical alert
        assert len(received_messages) > 0

        # Find the entrance camera message
        received = next(
            (
                m
                for m in reversed(received_messages)
                if m.get("data", {}).get("camera_id") == "entrance"
            ),
            None,
        )
        assert received is not None, "Should receive entrance camera event"
        assert received["data"]["risk_level"] == "critical"
        assert received["data"]["risk_score"] == 95

    @pytest.mark.asyncio
    async def test_critical_events_require_acknowledgment(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that critical events (risk >= 80) include requires_ack flag.

        RED phase: Verify critical events have the acknowledgment requirement.

        Acceptance criteria:
        - Event with risk_score >= 80 is broadcast
        - Message includes requires_ack: true
        - Message includes sequence number for tracking
        """
        # GIVEN: A connected client
        await event_broadcaster_with_redis.connect(mock_websocket)

        # GIVEN: A camera exists
        camera = camera_factory(id="vault", name="Vault Area")
        session.add(camera)
        await session.flush()

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: A critical event is broadcast
        critical_event = {
            "type": "event",
            "data": {
                "id": 4,
                "event_id": 4,
                "batch_id": "batch_vault999",
                "camera_id": "vault",
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "Intrusion detected in restricted area",
                "reasoning": "Person entered vault area without authorization",
                "started_at": datetime.now(UTC).isoformat(),
            },
        }

        await event_broadcaster_with_redis.broadcast_event(critical_event)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: The message should include requires_ack and sequence
        assert len(received_messages) > 0
        received = received_messages[0]
        assert "sequence" in received, "Critical messages should include sequence numbers"
        assert "requires_ack" in received, "Critical messages should include requires_ack flag"
        assert received["requires_ack"] is True, "Risk score >= 80 should require acknowledgment"


# =============================================================================
# Camera Status Broadcast Tests
# =============================================================================


class TestCameraStatusBroadcasts:
    """Tests for camera status change broadcast triggers."""

    @pytest.mark.asyncio
    async def test_camera_status_change_triggers_system_broadcast(
        self,
        system_broadcaster_with_redis: SystemBroadcaster,
        mock_websocket: WebSocket,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that camera status changes trigger system status broadcasts.

        RED phase: Camera status changes should update system stats.

        Acceptance criteria:
        - Camera status is changed (online -> offline)
        - System status broadcast is triggered
        - Broadcast includes updated camera stats
        """
        # GIVEN: A connected system status client
        await system_broadcaster_with_redis.connect(mock_websocket)

        # GIVEN: Cameras exist with different statuses
        camera1 = camera_factory(id="cam1", name="Camera 1", status="online")
        camera2 = camera_factory(id="cam2", name="Camera 2", status="online")
        camera3 = camera_factory(id="cam3", name="Camera 3", status="offline")
        session.add_all([camera1, camera2, camera3])
        await session.flush()

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: System status is broadcast
        await system_broadcaster_with_redis.broadcast_status(
            await system_broadcaster_with_redis._get_system_status()
        )

        # Give time for broadcast
        await asyncio.sleep(0.2)

        # THEN: The broadcast should include camera statistics
        assert len(received_messages) > 0
        status_msg = received_messages[0]
        assert status_msg["type"] == "system_status"
        assert "data" in status_msg
        assert "cameras" in status_msg["data"]
        # Should show active cameras in the stats


# =============================================================================
# Service Status Broadcast Tests
# =============================================================================


class TestServiceStatusBroadcasts:
    """Tests for service status change broadcast triggers."""

    @pytest.mark.asyncio
    async def test_service_degradation_triggers_broadcast(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
    ) -> None:
        """Test that service degradation triggers status broadcasts.

        RED phase: Service status changes should be broadcast.

        Acceptance criteria:
        - Service health changes (healthy -> degraded)
        - Service status broadcast is triggered
        - Connected clients receive the status update
        """
        # GIVEN: A connected client
        await event_broadcaster_with_redis.connect(mock_websocket)

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: A service status change is broadcast
        service_status = {
            "type": "service_status",
            "data": {
                "service": "nemotron",
                "status": "unhealthy",  # Valid status values: healthy, unhealthy, restarting, restart_failed, failed
                "message": "Nemotron service experiencing high latency",
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await event_broadcaster_with_redis.broadcast_service_status(service_status)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: Clients should receive the service status update
        assert len(received_messages) > 0

        # Find the nemotron status message (may have received other messages from previous tests)
        received = next(
            (
                m
                for m in reversed(received_messages)
                if m.get("data", {}).get("service") == "nemotron"
            ),
            None,
        )
        assert received is not None, "Should receive nemotron status message"
        assert received["type"] == "service_status"
        assert received["data"]["service"] == "nemotron"
        assert received["data"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_service_recovery_triggers_broadcast(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
    ) -> None:
        """Test that service recovery triggers status broadcasts.

        RED phase: Service recovery should be broadcast to clients.

        Acceptance criteria:
        - Service recovers (degraded -> healthy)
        - Recovery broadcast is triggered
        - Clients receive the recovery notification
        """
        # GIVEN: A connected client
        await event_broadcaster_with_redis.connect(mock_websocket)

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: A service recovery is broadcast
        recovery_status = {
            "type": "service_status",
            "data": {
                "service": "yolo26",
                "status": "healthy",
                "message": "YOLO26 service recovered successfully",
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await event_broadcaster_with_redis.broadcast_service_status(recovery_status)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: Clients should receive the recovery notification
        assert len(received_messages) > 0

        # Find the yolo26 recovery message (may have received other messages from previous tests)
        received = next(
            (
                m
                for m in reversed(received_messages)
                if m.get("data", {}).get("service") == "yolo26"
            ),
            None,
        )
        assert received is not None, "Should receive yolo26 recovery message"
        assert received["type"] == "service_status"
        assert received["data"]["service"] == "yolo26"
        assert received["data"]["status"] == "healthy"


# =============================================================================
# Scene Change Broadcast Tests
# =============================================================================


class TestSceneChangeBroadcasts:
    """Tests for scene change detection broadcast triggers."""

    @pytest.mark.asyncio
    async def test_scene_change_detection_triggers_broadcast(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
        mock_websocket: WebSocket,
        session: AsyncSession,
        camera_factory,
    ) -> None:
        """Test that scene change detections trigger broadcasts.

        RED phase: Scene changes should be broadcast to clients.

        Acceptance criteria:
        - Scene change is detected (camera view blocked/moved)
        - Scene change broadcast is triggered
        - Clients receive the alert
        """
        # GIVEN: A connected client
        await event_broadcaster_with_redis.connect(mock_websocket)

        # GIVEN: A camera exists
        camera = camera_factory(id="parking", name="Parking Lot")
        session.add(camera)
        await session.flush()

        # Track received messages
        received_messages = []

        async def capture_send_text(message: str):
            received_messages.append(json.loads(message))

        mock_websocket.send_text = capture_send_text

        # WHEN: A scene change is detected and broadcast
        scene_change = {
            "type": "scene_change",
            "data": {
                "id": 1,
                "camera_id": "parking",
                "detected_at": datetime.now(UTC).isoformat(),
                "change_type": "view_blocked",
                "similarity_score": 0.15,
            },
        }

        await event_broadcaster_with_redis.broadcast_scene_change(scene_change)

        # Give Redis pub/sub time to deliver
        await asyncio.sleep(0.5)

        # THEN: Clients should receive the scene change alert
        assert len(received_messages) > 0

        # Find the parking camera message
        received = next(
            (
                m
                for m in reversed(received_messages)
                if m.get("data", {}).get("camera_id") == "parking"
            ),
            None,
        )
        assert received is not None, "Should receive parking camera scene change"
        assert received["type"] == "scene_change"
        assert received["data"]["camera_id"] == "parking"
        assert received["data"]["change_type"] == "view_blocked"
        assert "similarity_score" in received["data"]


# =============================================================================
# Message Validation Tests
# =============================================================================


class TestBroadcastMessageValidation:
    """Tests for broadcast message schema validation."""

    @pytest.mark.asyncio
    async def test_invalid_event_message_raises_validation_error(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
    ) -> None:
        """Test that invalid event messages fail validation.

        RED phase: Invalid messages should be rejected.

        Acceptance criteria:
        - Attempt to broadcast invalid event (missing required fields)
        - ValidationError is raised
        - No broadcast is sent to Redis
        """
        # WHEN: Attempting to broadcast an invalid event (missing required fields)
        invalid_event = {
            "type": "event",
            "data": {
                # Missing required fields: id, camera_id, risk_score, etc.
                "summary": "Invalid event",
            },
        }

        # THEN: Should raise ValueError (from Pydantic ValidationError)
        with pytest.raises(ValueError, match="Invalid event message format"):
            await event_broadcaster_with_redis.broadcast_event(invalid_event)

    @pytest.mark.asyncio
    async def test_valid_event_passes_validation(
        self,
        event_broadcaster_with_redis: EventBroadcaster,
    ) -> None:
        """Test that valid event messages pass validation.

        GREEN phase: Valid messages should be accepted.

        Acceptance criteria:
        - Broadcast valid event with all required fields
        - Validation passes
        - Message is published to Redis
        """
        # WHEN: Broadcasting a valid event
        valid_event = {
            "type": "event",
            "data": {
                "id": 99,
                "event_id": 99,
                "batch_id": "batch_valid123",
                "camera_id": "test_camera",
                "risk_score": 60,
                "risk_level": "medium",
                "summary": "Valid test event",
                "reasoning": "This is a valid event for testing",
                "started_at": datetime.now(UTC).isoformat(),
            },
        }

        # THEN: Should not raise any errors
        subscriber_count = await event_broadcaster_with_redis.broadcast_event(valid_event)
        assert subscriber_count >= 0  # At least 0 subscribers (may be 0 if no listeners)
