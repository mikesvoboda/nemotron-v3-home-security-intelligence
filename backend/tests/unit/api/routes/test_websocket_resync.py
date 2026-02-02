"""Unit tests for WebSocket resync/replay functionality.

NEM-4983: Implement WebSocket message replay for gap recovery.

These tests verify the resync handler which:
- Receives resync requests with last_sequence
- Replays buffered messages since last_sequence
- Marks replayed messages with replay=True flag
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestResyncHandler:
    """Tests for WebSocket resync message handler."""

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket connection."""
        ws = MagicMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock()
        return ws

    @pytest.fixture
    def mock_message_buffer(self) -> MagicMock:
        """Create a mock message buffer."""
        buffer = MagicMock()
        buffer.get_since = MagicMock(return_value=[])
        buffer.get_oldest_sequence = MagicMock(return_value=None)
        buffer.get_newest_sequence = MagicMock(return_value=None)
        return buffer

    @pytest.mark.asyncio
    async def test_resync_replays_buffered_messages(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Test that resync handler replays buffered messages."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        # Setup: buffer has messages 5-10
        mock_message_buffer.get_since.return_value = [
            (6, {"type": "event", "data": {"id": 6}, "seq": 6, "replay": True}),
            (7, {"type": "event", "data": {"id": 7}, "seq": 7, "replay": True}),
            (8, {"type": "event", "data": {"id": 8}, "seq": 8, "replay": True}),
        ]

        # Create resync message
        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 5})

        connection_id = "test-conn-1"

        with patch(
            "backend.api.routes.websocket.get_message_buffer", return_value=mock_message_buffer
        ):
            await handle_resync_with_replay(mock_websocket, message, connection_id)

        # Verify buffer was queried correctly
        mock_message_buffer.get_since.assert_called_once_with(5, mark_as_replay=True)

        # Verify messages were sent (including ack)
        assert mock_websocket.send_text.call_count >= 1

        # Check that the replay messages were sent
        sent_messages = [
            json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list
        ]

        # Should include the replayed messages
        replay_messages = [m for m in sent_messages if m.get("type") == "event"]
        assert len(replay_messages) == 3

        for msg in replay_messages:
            assert msg.get("replay") is True

    @pytest.mark.asyncio
    async def test_resync_sends_ack_with_replay_count(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Test that resync sends acknowledgment with replay count."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        # Setup: buffer has 3 messages to replay
        mock_message_buffer.get_since.return_value = [
            (6, {"type": "event", "seq": 6, "replay": True}),
            (7, {"type": "event", "seq": 7, "replay": True}),
            (8, {"type": "event", "seq": 8, "replay": True}),
        ]

        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 5})

        with patch(
            "backend.api.routes.websocket.get_message_buffer", return_value=mock_message_buffer
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        # Find the ack message
        sent_messages = [
            json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list
        ]

        ack_messages = [m for m in sent_messages if m.get("type") == "resync_ack"]
        assert len(ack_messages) == 1

        ack = ack_messages[0]
        assert ack["channel"] == "events"
        assert ack["last_sequence"] == 5
        assert ack["replayed_count"] == 3

    @pytest.mark.asyncio
    async def test_resync_with_no_buffered_messages(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Test resync when no messages are available for replay."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        # Buffer returns empty list
        mock_message_buffer.get_since.return_value = []

        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 100})

        with patch(
            "backend.api.routes.websocket.get_message_buffer", return_value=mock_message_buffer
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        # Should send ack with replayed_count=0
        sent_messages = [
            json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list
        ]

        ack_messages = [m for m in sent_messages if m.get("type") == "resync_ack"]
        assert len(ack_messages) == 1
        assert ack_messages[0]["replayed_count"] == 0

    @pytest.mark.asyncio
    async def test_resync_with_gap_too_old(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Test resync when requested sequence is older than buffer."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        # Buffer's oldest is seq 50, client wants from seq 10
        mock_message_buffer.get_oldest_sequence.return_value = 50
        mock_message_buffer.get_newest_sequence.return_value = 100
        mock_message_buffer.get_since.return_value = [
            (i, {"type": "event", "seq": i, "replay": True}) for i in range(50, 101)
        ]

        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 10})

        with patch(
            "backend.api.routes.websocket.get_message_buffer", return_value=mock_message_buffer
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        # Should include gap_too_old flag in ack
        sent_messages = [
            json.loads(call.args[0]) for call in mock_websocket.send_text.call_args_list
        ]

        ack_messages = [m for m in sent_messages if m.get("type") == "resync_ack"]
        assert len(ack_messages) == 1

        ack = ack_messages[0]
        assert ack.get("gap_too_old") is True
        assert ack.get("oldest_available") == 50

    @pytest.mark.asyncio
    async def test_resync_with_missing_last_sequence(
        self, mock_websocket: MagicMock, mock_message_buffer: MagicMock
    ) -> None:
        """Test resync with missing last_sequence defaults to 0."""
        from backend.api.routes.websocket import handle_resync_with_replay
        from backend.api.schemas.websocket import WebSocketMessage

        mock_message_buffer.get_since.return_value = []

        # No last_sequence in data
        message = WebSocketMessage(type="resync", data={"channel": "events"})

        with patch(
            "backend.api.routes.websocket.get_message_buffer", return_value=mock_message_buffer
        ):
            await handle_resync_with_replay(mock_websocket, message, "test-conn-1")

        # Should query from 0
        mock_message_buffer.get_since.assert_called_once_with(0, mark_as_replay=True)


class TestMessageBufferBroadcast:
    """Tests for message buffering during broadcast."""

    @pytest.fixture
    def mock_broadcaster(self) -> MagicMock:
        """Create a mock event broadcaster."""
        broadcaster = MagicMock()
        broadcaster.broadcast_event = AsyncMock(return_value=1)
        return broadcaster

    @pytest.mark.asyncio
    async def test_broadcast_adds_to_buffer(self) -> None:
        """Test that broadcasting events also adds them to the buffer."""
        from backend.core.websocket.message_buffer import (
            get_message_buffer,
            reset_message_buffer_state,
        )

        # Reset buffer state
        reset_message_buffer_state()

        buffer = get_message_buffer()

        # Simulate adding a message during broadcast
        message = {"type": "event", "data": {"id": 1}, "seq": 1}
        buffer.add(1, message)

        # Verify message is in buffer
        messages = buffer.get_since(0)
        assert len(messages) == 1
        assert messages[0][0] == 1  # sequence
        assert messages[0][1]["type"] == "event"
