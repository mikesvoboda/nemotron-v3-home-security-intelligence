"""Tests for NEM-1688: WebSocket message sequencing, buffering, and ACK support.

This module tests the message delivery guarantee features added to the
EventBroadcaster for reliable WebSocket message delivery.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.event_broadcaster import (
    MESSAGE_BUFFER_SIZE,
    EventBroadcaster,
    requires_ack,
)


class TestRequiresAck:
    """Tests for the requires_ack function."""

    def test_non_event_message_does_not_require_ack(self) -> None:
        """Non-event messages should not require acknowledgment."""
        message = {"type": "ping"}
        assert requires_ack(message) is False

    def test_service_status_does_not_require_ack(self) -> None:
        """Service status messages should not require acknowledgment."""
        message = {"type": "service_status", "data": {"service": "redis", "status": "healthy"}}
        assert requires_ack(message) is False

    def test_low_risk_event_does_not_require_ack(self) -> None:
        """Events with low risk_score (< 80) should not require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 50, "risk_level": "medium"},
        }
        assert requires_ack(message) is False

    def test_high_risk_score_requires_ack(self) -> None:
        """Events with risk_score >= 80 should require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 80, "risk_level": "high"},
        }
        assert requires_ack(message) is True

    def test_very_high_risk_score_requires_ack(self) -> None:
        """Events with risk_score >= 90 should require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 95, "risk_level": "high"},
        }
        assert requires_ack(message) is True

    def test_critical_risk_level_requires_ack(self) -> None:
        """Events with risk_level == 'critical' should require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 50, "risk_level": "critical"},
        }
        assert requires_ack(message) is True

    def test_critical_with_high_score_requires_ack(self) -> None:
        """Events with both critical level and high score should require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 90, "risk_level": "critical"},
        }
        assert requires_ack(message) is True

    def test_event_without_data_does_not_require_ack(self) -> None:
        """Events without data should not require acknowledgment."""
        message = {"type": "event"}
        assert requires_ack(message) is False

    def test_event_with_empty_data_does_not_require_ack(self) -> None:
        """Events with empty data should not require acknowledgment."""
        message = {"type": "event", "data": {}}
        assert requires_ack(message) is False

    def test_boundary_risk_score_79_does_not_require_ack(self) -> None:
        """Events with risk_score == 79 should NOT require acknowledgment."""
        message = {
            "type": "event",
            "data": {"risk_score": 79, "risk_level": "high"},
        }
        assert requires_ack(message) is False


class TestEventBroadcasterSequencing:
    """Tests for EventBroadcaster message sequencing."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.subscribe = AsyncMock(return_value=MagicMock())
        redis.unsubscribe = AsyncMock()
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def broadcaster(self, mock_redis: AsyncMock) -> EventBroadcaster:
        """Create an EventBroadcaster instance for testing."""
        return EventBroadcaster(mock_redis)

    def test_initial_sequence_is_zero(self, broadcaster: EventBroadcaster) -> None:
        """Broadcaster should start with sequence counter at 0."""
        assert broadcaster.current_sequence == 0

    def test_next_sequence_increments(self, broadcaster: EventBroadcaster) -> None:
        """_next_sequence should return incrementing values."""
        assert broadcaster._next_sequence() == 1
        assert broadcaster._next_sequence() == 2
        assert broadcaster._next_sequence() == 3
        assert broadcaster.current_sequence == 3

    def test_add_sequence_and_buffer_adds_sequence(self, broadcaster: EventBroadcaster) -> None:
        """_add_sequence_and_buffer should add sequence number to message."""
        message = {"type": "event", "data": {"risk_score": 50}}
        result = broadcaster._add_sequence_and_buffer(message)

        assert result["sequence"] == 1
        assert result["type"] == "event"
        assert result["data"]["risk_score"] == 50

    def test_add_sequence_and_buffer_adds_requires_ack(self, broadcaster: EventBroadcaster) -> None:
        """_add_sequence_and_buffer should add requires_ack flag."""
        low_risk = {"type": "event", "data": {"risk_score": 50, "risk_level": "medium"}}
        high_risk = {"type": "event", "data": {"risk_score": 85, "risk_level": "high"}}

        low_result = broadcaster._add_sequence_and_buffer(low_risk)
        high_result = broadcaster._add_sequence_and_buffer(high_risk)

        assert low_result["requires_ack"] is False
        assert high_result["requires_ack"] is True

    def test_add_sequence_and_buffer_stores_in_buffer(self, broadcaster: EventBroadcaster) -> None:
        """_add_sequence_and_buffer should store message in buffer."""
        message = {"type": "event", "data": {"risk_score": 50}}
        broadcaster._add_sequence_and_buffer(message)

        assert len(broadcaster._message_buffer) == 1
        assert broadcaster._message_buffer[0]["sequence"] == 1

    def test_add_sequence_preserves_original(self, broadcaster: EventBroadcaster) -> None:
        """_add_sequence_and_buffer should not modify the original message."""
        message = {"type": "event", "data": {"risk_score": 50}}
        broadcaster._add_sequence_and_buffer(message)

        assert "sequence" not in message
        assert "requires_ack" not in message


class TestEventBroadcasterBuffer:
    """Tests for EventBroadcaster message buffering."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.subscribe = AsyncMock(return_value=MagicMock())
        redis.unsubscribe = AsyncMock()
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def broadcaster(self, mock_redis: AsyncMock) -> EventBroadcaster:
        """Create an EventBroadcaster instance for testing."""
        return EventBroadcaster(mock_redis)

    def test_buffer_size_constant(self) -> None:
        """MESSAGE_BUFFER_SIZE should be 100."""
        assert MESSAGE_BUFFER_SIZE == 100

    def test_buffer_respects_max_size(self, broadcaster: EventBroadcaster) -> None:
        """Buffer should not exceed MESSAGE_BUFFER_SIZE."""
        # Add more messages than buffer size
        for i in range(MESSAGE_BUFFER_SIZE + 50):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        assert len(broadcaster._message_buffer) == MESSAGE_BUFFER_SIZE

    def test_buffer_removes_oldest_when_full(self, broadcaster: EventBroadcaster) -> None:
        """Buffer should remove oldest messages when full."""
        # Fill buffer
        for i in range(MESSAGE_BUFFER_SIZE):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        # Add one more
        broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": "new"}})

        # First message should be gone, sequence 1 should be missing
        sequences = [msg["sequence"] for msg in broadcaster._message_buffer]
        assert 1 not in sequences
        assert MESSAGE_BUFFER_SIZE + 1 in sequences

    def test_get_messages_since_returns_newer(self, broadcaster: EventBroadcaster) -> None:
        """get_messages_since should return messages with sequence > last_sequence."""
        # Add 5 messages
        for i in range(5):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        # Get messages since sequence 2
        messages = broadcaster.get_messages_since(2)

        assert len(messages) == 3
        assert all(msg["sequence"] > 2 for msg in messages)

    def test_get_messages_since_returns_empty_when_caught_up(
        self, broadcaster: EventBroadcaster
    ) -> None:
        """get_messages_since should return empty list when client is caught up."""
        for i in range(5):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        messages = broadcaster.get_messages_since(5)
        assert messages == []

    def test_get_messages_since_with_mark_as_replay(self, broadcaster: EventBroadcaster) -> None:
        """get_messages_since should add replay=True when mark_as_replay is True."""
        for i in range(5):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        messages = broadcaster.get_messages_since(2, mark_as_replay=True)

        assert all(msg["replay"] is True for msg in messages)

    def test_get_messages_since_without_mark_as_replay(self, broadcaster: EventBroadcaster) -> None:
        """get_messages_since should not add replay field when mark_as_replay is False."""
        for i in range(5):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        messages = broadcaster.get_messages_since(2, mark_as_replay=False)

        assert all("replay" not in msg for msg in messages)

    def test_get_messages_since_zero_returns_all(self, broadcaster: EventBroadcaster) -> None:
        """get_messages_since(0) should return all buffered messages."""
        for i in range(5):
            broadcaster._add_sequence_and_buffer({"type": "event", "data": {"id": i}})

        messages = broadcaster.get_messages_since(0)
        assert len(messages) == 5


class TestEventBroadcasterAckTracking:
    """Tests for EventBroadcaster ACK tracking."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.subscribe = AsyncMock(return_value=MagicMock())
        redis.unsubscribe = AsyncMock()
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def broadcaster(self, mock_redis: AsyncMock) -> EventBroadcaster:
        """Create an EventBroadcaster instance for testing."""
        return EventBroadcaster(mock_redis)

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket."""
        return MagicMock()

    def test_get_last_ack_returns_zero_for_new_client(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """get_last_ack should return 0 for a client with no ACKs."""
        assert broadcaster.get_last_ack(mock_websocket) == 0

    def test_record_ack_stores_sequence(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """record_ack should store the sequence number for the client."""
        broadcaster.record_ack(mock_websocket, 42)
        assert broadcaster.get_last_ack(mock_websocket) == 42

    def test_record_ack_updates_higher_sequence(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """record_ack should update to a higher sequence number."""
        broadcaster.record_ack(mock_websocket, 10)
        broadcaster.record_ack(mock_websocket, 20)
        assert broadcaster.get_last_ack(mock_websocket) == 20

    def test_record_ack_ignores_lower_sequence(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """record_ack should not update to a lower sequence number."""
        broadcaster.record_ack(mock_websocket, 20)
        broadcaster.record_ack(mock_websocket, 10)
        assert broadcaster.get_last_ack(mock_websocket) == 20

    def test_record_ack_ignores_equal_sequence(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """record_ack should not update for equal sequence number."""
        broadcaster.record_ack(mock_websocket, 20)
        broadcaster.record_ack(mock_websocket, 20)
        assert broadcaster.get_last_ack(mock_websocket) == 20

    def test_acks_are_per_client(self, broadcaster: EventBroadcaster) -> None:
        """ACK tracking should be independent per client."""
        client1 = MagicMock()
        client2 = MagicMock()

        broadcaster.record_ack(client1, 10)
        broadcaster.record_ack(client2, 20)

        assert broadcaster.get_last_ack(client1) == 10
        assert broadcaster.get_last_ack(client2) == 20

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_acks(
        self, broadcaster: EventBroadcaster, mock_websocket: MagicMock
    ) -> None:
        """disconnect should clean up ACK tracking for the client."""
        # Setup: Add to connections and record an ACK
        broadcaster._connections.add(mock_websocket)
        broadcaster.record_ack(mock_websocket, 42)
        assert broadcaster.get_last_ack(mock_websocket) == 42

        # Disconnect
        await broadcaster.disconnect(mock_websocket)

        # ACK should be cleaned up
        assert broadcaster.get_last_ack(mock_websocket) == 0
        assert mock_websocket not in broadcaster._client_acks
