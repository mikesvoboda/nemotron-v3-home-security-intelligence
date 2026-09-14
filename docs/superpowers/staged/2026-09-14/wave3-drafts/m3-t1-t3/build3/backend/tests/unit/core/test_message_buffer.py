"""Unit tests for WebSocket message buffer for replay functionality.

NEM-4983: Implement WebSocket message replay for gap recovery.

These tests verify the MessageBuffer class which provides:
- Ring buffer storage with configurable max size
- Message storage with sequence numbers
- Retrieval of messages since a given sequence number
- Thread-safe operations
"""

import threading
from collections.abc import Iterator
from typing import Any

import pytest


class TestMessageBuffer:
    """Tests for MessageBuffer class."""

    @pytest.fixture
    def buffer(self) -> Iterator[Any]:
        """Create a MessageBuffer instance for testing."""
        from backend.core.websocket.message_buffer import MessageBuffer

        buf = MessageBuffer(max_size=100)
        yield buf

    @pytest.fixture
    def small_buffer(self) -> Iterator[Any]:
        """Create a small MessageBuffer for testing overflow behavior."""
        from backend.core.websocket.message_buffer import MessageBuffer

        buf = MessageBuffer(max_size=5)
        yield buf

    def test_init_default_size(self) -> None:
        """Test that MessageBuffer initializes with default size of 1000."""
        from backend.core.websocket.message_buffer import MessageBuffer

        buf = MessageBuffer()
        assert buf.max_size == 1000

    def test_init_custom_size(self) -> None:
        """Test that MessageBuffer initializes with custom size."""
        from backend.core.websocket.message_buffer import MessageBuffer

        buf = MessageBuffer(max_size=500)
        assert buf.max_size == 500

    def test_add_message(self, buffer: Any) -> None:
        """Test adding a single message to the buffer."""
        message = {"type": "event", "data": {"id": 1}}
        buffer.add(1, message)

        assert buffer.size() == 1

    def test_add_multiple_messages(self, buffer: Any) -> None:
        """Test adding multiple messages to the buffer."""
        for i in range(10):
            message = {"type": "event", "data": {"id": i}}
            buffer.add(i + 1, message)

        assert buffer.size() == 10

    def test_get_since_returns_messages_after_sequence(self, buffer: Any) -> None:
        """Test that get_since returns messages with sequence > last_seq."""
        # Add messages with sequences 1-10
        for i in range(1, 11):
            message = {"type": "event", "data": {"id": i}}
            buffer.add(i, message)

        # Get messages since sequence 5
        messages = buffer.get_since(5)

        # Should get messages 6-10 (5 messages)
        assert len(messages) == 5

        # Verify sequences are in order
        sequences = [seq for seq, _ in messages]
        assert sequences == [6, 7, 8, 9, 10]

    def test_get_since_returns_empty_when_no_messages_after(self, buffer: Any) -> None:
        """Test that get_since returns empty list when no messages after last_seq."""
        # Add messages with sequences 1-10
        for i in range(1, 11):
            message = {"type": "event", "data": {"id": i}}
            buffer.add(i, message)

        # Get messages since sequence 10 (no messages after)
        messages = buffer.get_since(10)

        assert len(messages) == 0

    def test_get_since_returns_all_when_last_seq_is_zero(self, buffer: Any) -> None:
        """Test that get_since(0) returns all messages."""
        # Add messages with sequences 1-10
        for i in range(1, 11):
            message = {"type": "event", "data": {"id": i}}
            buffer.add(i, message)

        # Get all messages
        messages = buffer.get_since(0)

        assert len(messages) == 10

    def test_get_since_returns_empty_on_empty_buffer(self, buffer: Any) -> None:
        """Test that get_since returns empty list on empty buffer."""
        messages = buffer.get_since(0)
        assert len(messages) == 0

    def test_buffer_overflow_removes_oldest(self, small_buffer: Any) -> None:
        """Test that buffer overflow removes oldest messages (ring buffer)."""
        # Add 10 messages to a buffer with max_size=5
        for i in range(1, 11):
            message = {"type": "event", "data": {"id": i}}
            small_buffer.add(i, message)

        # Should only have 5 messages (newest)
        assert small_buffer.size() == 5

        # Get all messages
        messages = small_buffer.get_since(0)

        # Should have sequences 6-10 (oldest were dropped)
        sequences = [seq for seq, _ in messages]
        assert sequences == [6, 7, 8, 9, 10]

    def test_get_since_respects_buffer_bounds(self, small_buffer: Any) -> None:
        """Test get_since when requested sequence is older than buffer start."""
        # Add 10 messages to a buffer with max_size=5
        for i in range(1, 11):
            message = {"type": "event", "data": {"id": i}}
            small_buffer.add(i, message)

        # Request messages since seq 2 (which was evicted)
        messages = small_buffer.get_since(2)

        # Should return what's available: sequences 6-10
        assert len(messages) == 5
        sequences = [seq for seq, _ in messages]
        assert sequences == [6, 7, 8, 9, 10]

    def test_clear_removes_all_messages(self, buffer: Any) -> None:
        """Test that clear() removes all messages."""
        for i in range(1, 11):
            buffer.add(i, {"type": "event"})

        buffer.clear()

        assert buffer.size() == 0
        assert buffer.get_since(0) == []

    def test_get_oldest_sequence(self, buffer: Any) -> None:
        """Test getting the oldest sequence number in buffer."""
        assert buffer.get_oldest_sequence() is None

        for i in range(5, 15):
            buffer.add(i, {"type": "event"})

        assert buffer.get_oldest_sequence() == 5

    def test_get_newest_sequence(self, buffer: Any) -> None:
        """Test getting the newest sequence number in buffer."""
        assert buffer.get_newest_sequence() is None

        for i in range(5, 15):
            buffer.add(i, {"type": "event"})

        assert buffer.get_newest_sequence() == 14

    def test_messages_include_replay_flag_when_requested(self, buffer: Any) -> None:
        """Test that get_since can add replay=True to messages."""
        for i in range(1, 6):
            buffer.add(i, {"type": "event", "data": {"id": i}})

        # Get with replay flag
        messages = buffer.get_since(2, mark_as_replay=True)

        # All returned messages should have replay=True
        for _, msg in messages:
            assert msg.get("replay") is True

    def test_messages_without_replay_flag(self, buffer: Any) -> None:
        """Test that get_since does not add replay flag by default."""
        for i in range(1, 6):
            buffer.add(i, {"type": "event", "data": {"id": i}})

        # Get without replay flag
        messages = buffer.get_since(2, mark_as_replay=False)

        # Messages should NOT have replay=True
        for _, msg in messages:
            assert "replay" not in msg

    def test_thread_safety(self, buffer: Any) -> None:
        """Test that buffer operations are thread-safe."""
        errors: list[Exception] = []
        results: list[int] = []

        def writer(start: int) -> None:
            try:
                for i in range(start, start + 100):
                    buffer.add(i, {"type": "event", "id": i})
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(100):
                    messages = buffer.get_since(0)
                    results.append(len(messages))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1000,)),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0


class TestMessageBufferIntegration:
    """Integration tests for MessageBuffer with sequence tracker."""

    def test_buffer_used_with_sequence_tracker(self) -> None:
        """Test that buffer integrates with sequence tracker for replay."""
        from backend.core.websocket.message_buffer import MessageBuffer
        from backend.core.websocket.sequence_tracker import SequenceTracker

        buffer = MessageBuffer(max_size=100)
        tracker = SequenceTracker()

        connection_id = "test-conn-1"
        tracker.register_connection(connection_id)

        # Simulate sending 5 messages
        for i in range(5):
            seq = tracker.next_sequence(connection_id)
            message = {"type": "event", "data": {"id": i}, "seq": seq}
            buffer.add(seq, message)

        # Verify last sequence
        last_seq = tracker.get_current_sequence(connection_id)
        assert last_seq == 5

        # Get replay messages since seq 2
        messages = buffer.get_since(2, mark_as_replay=True)
        assert len(messages) == 3  # seq 3, 4, 5

        for seq, msg in messages:
            assert msg.get("replay") is True
            assert msg.get("seq") == seq


class TestGetMessageBuffer:
    """Tests for the global message buffer singleton."""

    def test_get_message_buffer_returns_singleton(self) -> None:
        """Test that get_message_buffer returns the same instance."""
        from backend.core.websocket.message_buffer import (
            get_message_buffer,
            reset_message_buffer_state,
        )

        # Reset to ensure clean state
        reset_message_buffer_state()

        buffer1 = get_message_buffer()
        buffer2 = get_message_buffer()

        assert buffer1 is buffer2

    def test_reset_message_buffer_state(self) -> None:
        """Test that reset_message_buffer_state creates a new instance."""
        from backend.core.websocket.message_buffer import (
            get_message_buffer,
            reset_message_buffer_state,
        )

        # Reset and get first buffer
        reset_message_buffer_state()
        buffer1 = get_message_buffer()
        buffer1.add(1, {"type": "test"})

        # Reset and get second buffer
        reset_message_buffer_state()
        buffer2 = get_message_buffer()

        # Second buffer should be empty (new instance)
        assert buffer2.size() == 0
