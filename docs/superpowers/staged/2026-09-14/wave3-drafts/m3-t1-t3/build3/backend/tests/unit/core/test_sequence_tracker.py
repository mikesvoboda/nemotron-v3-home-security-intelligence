"""Unit tests for WebSocket message sequence tracker.

These tests verify the per-connection sequence tracking implementation for:
- Sequence number generation
- Gap detection support
- WebSocket object to connection_id mapping
- Thread safety

NEM-3142: Implement WebSocket message sequence numbers
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.core.websocket.sequence_tracker import (
    SequenceTracker,
    get_sequence_tracker,
    reset_sequence_tracker_state,
)

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def tracker() -> SequenceTracker:
    """Create a fresh SequenceTracker instance for each test."""
    return SequenceTracker()


@pytest.fixture
def mock_websocket() -> MagicMock:
    """Create a mock WebSocket object for testing."""
    return MagicMock()


@pytest.fixture(autouse=True)
def reset_global_state() -> None:
    """Reset global sequence tracker state before each test."""
    reset_sequence_tracker_state()


# ==============================================================================
# SequenceTracker Basic Tests
# ==============================================================================


class TestSequenceTrackerBasics:
    """Tests for basic SequenceTracker functionality."""

    def test_register_connection_starts_at_zero(self, tracker: SequenceTracker) -> None:
        """Test that a new connection starts with sequence 0."""
        tracker.register_connection("conn-1")
        assert tracker.get_current_sequence("conn-1") == 0

    def test_next_sequence_increments(self, tracker: SequenceTracker) -> None:
        """Test that next_sequence increments the counter."""
        tracker.register_connection("conn-1")
        assert tracker.next_sequence("conn-1") == 1
        assert tracker.next_sequence("conn-1") == 2
        assert tracker.next_sequence("conn-1") == 3

    def test_next_sequence_auto_registers(self, tracker: SequenceTracker) -> None:
        """Test that next_sequence auto-registers unregistered connections."""
        # Without explicit registration
        assert tracker.next_sequence("conn-new") == 1
        assert tracker.next_sequence("conn-new") == 2

    def test_get_current_sequence_unregistered_returns_zero(self, tracker: SequenceTracker) -> None:
        """Test that get_current_sequence returns 0 for unregistered connections."""
        assert tracker.get_current_sequence("conn-unknown") == 0

    def test_remove_connection_clears_sequence(self, tracker: SequenceTracker) -> None:
        """Test that removing a connection clears its sequence."""
        tracker.register_connection("conn-1")
        tracker.next_sequence("conn-1")
        tracker.next_sequence("conn-1")
        tracker.remove_connection("conn-1")
        assert tracker.get_current_sequence("conn-1") == 0

    def test_multiple_connections_independent(self, tracker: SequenceTracker) -> None:
        """Test that multiple connections have independent sequences."""
        tracker.register_connection("conn-1")
        tracker.register_connection("conn-2")

        # Advance conn-1 more than conn-2
        for _ in range(5):
            tracker.next_sequence("conn-1")
        for _ in range(2):
            tracker.next_sequence("conn-2")

        assert tracker.get_current_sequence("conn-1") == 5
        assert tracker.get_current_sequence("conn-2") == 2


# ==============================================================================
# WebSocket Object Mapping Tests
# ==============================================================================


class TestWebSocketMapping:
    """Tests for WebSocket object to connection_id mapping."""

    def test_register_with_websocket(
        self, tracker: SequenceTracker, mock_websocket: MagicMock
    ) -> None:
        """Test registering a connection with a WebSocket object."""
        tracker.register_connection("conn-1", mock_websocket)
        assert tracker.get_connection_id(mock_websocket) == "conn-1"

    def test_get_connection_id_unknown_websocket(
        self, tracker: SequenceTracker, mock_websocket: MagicMock
    ) -> None:
        """Test that get_connection_id returns None for unknown WebSocket."""
        assert tracker.get_connection_id(mock_websocket) is None

    def test_register_websocket_separately(
        self, tracker: SequenceTracker, mock_websocket: MagicMock
    ) -> None:
        """Test registering WebSocket mapping separately from connection."""
        tracker.register_connection("conn-1")
        tracker.register_websocket("conn-1", mock_websocket)
        assert tracker.get_connection_id(mock_websocket) == "conn-1"

    def test_remove_connection_clears_websocket_mapping(
        self, tracker: SequenceTracker, mock_websocket: MagicMock
    ) -> None:
        """Test that removing a connection clears WebSocket mapping."""
        tracker.register_connection("conn-1", mock_websocket)
        tracker.remove_connection("conn-1", mock_websocket)
        assert tracker.get_connection_id(mock_websocket) is None

    def test_remove_connection_clears_all_stale_mappings(self, tracker: SequenceTracker) -> None:
        """Test that remove_connection clears all mappings for the connection_id."""
        ws1 = MagicMock()
        ws2 = MagicMock()

        # Register same connection_id with two different WebSocket objects
        # (simulating a reconnection scenario)
        tracker.register_connection("conn-1", ws1)
        tracker.register_websocket("conn-1", ws2)

        # Remove should clear both mappings
        tracker.remove_connection("conn-1")

        assert tracker.get_connection_id(ws1) is None
        assert tracker.get_connection_id(ws2) is None


# ==============================================================================
# Statistics Tests
# ==============================================================================


class TestSequenceTrackerStats:
    """Tests for SequenceTracker statistics."""

    def test_get_connection_count_empty(self, tracker: SequenceTracker) -> None:
        """Test connection count is 0 for empty tracker."""
        assert tracker.get_connection_count() == 0

    def test_get_connection_count(self, tracker: SequenceTracker) -> None:
        """Test connection count reflects registered connections."""
        tracker.register_connection("conn-1")
        tracker.register_connection("conn-2")
        tracker.register_connection("conn-3")
        assert tracker.get_connection_count() == 3

    def test_get_stats(self, tracker: SequenceTracker) -> None:
        """Test that get_stats returns correct statistics."""
        tracker.register_connection("conn-1")
        tracker.register_connection("conn-2")

        # Advance sequences
        for _ in range(10):
            tracker.next_sequence("conn-1")
        for _ in range(5):
            tracker.next_sequence("conn-2")

        stats = tracker.get_stats()
        assert stats["total_connections"] == 2
        assert stats["total_messages_sent"] == 15  # 10 + 5
        assert stats["max_sequence"] == 10

    def test_get_stats_empty(self, tracker: SequenceTracker) -> None:
        """Test get_stats with no connections."""
        stats = tracker.get_stats()
        assert stats["total_connections"] == 0
        assert stats["total_messages_sent"] == 0
        assert stats["max_sequence"] == 0


# ==============================================================================
# Global Instance Tests
# ==============================================================================


class TestGlobalSequenceTracker:
    """Tests for the global sequence tracker singleton."""

    def test_get_sequence_tracker_returns_instance(self) -> None:
        """Test that get_sequence_tracker returns a SequenceTracker instance."""
        tracker = get_sequence_tracker()
        assert isinstance(tracker, SequenceTracker)

    def test_get_sequence_tracker_returns_same_instance(self) -> None:
        """Test that get_sequence_tracker returns the same instance."""
        tracker1 = get_sequence_tracker()
        tracker2 = get_sequence_tracker()
        assert tracker1 is tracker2

    def test_reset_sequence_tracker_state(self) -> None:
        """Test that reset_sequence_tracker_state creates a new instance."""
        tracker1 = get_sequence_tracker()
        tracker1.register_connection("conn-1")
        tracker1.next_sequence("conn-1")

        reset_sequence_tracker_state()

        tracker2 = get_sequence_tracker()
        assert tracker2.get_connection_count() == 0
        assert tracker2.get_current_sequence("conn-1") == 0


# ==============================================================================
# Thread Safety Tests
# ==============================================================================


class TestSequenceTrackerThreadSafety:
    """Tests for thread safety of SequenceTracker."""

    def test_concurrent_registrations(self, tracker: SequenceTracker) -> None:
        """Test concurrent connection registrations don't cause issues."""
        import threading

        def register_and_increment(conn_id: str) -> None:
            tracker.register_connection(conn_id)
            for _ in range(100):
                tracker.next_sequence(conn_id)

        threads = []
        for i in range(10):
            t = threading.Thread(target=register_and_increment, args=(f"conn-{i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each connection should have sequence 100
        for i in range(10):
            assert tracker.get_current_sequence(f"conn-{i}") == 100

    def test_concurrent_sequence_increments(self, tracker: SequenceTracker) -> None:
        """Test concurrent sequence increments on same connection."""
        import threading

        tracker.register_connection("conn-shared")

        sequences: list[int] = []
        lock = threading.Lock()

        def increment_and_record() -> None:
            for _ in range(100):
                seq = tracker.next_sequence("conn-shared")
                with lock:
                    sequences.append(seq)

        threads = []
        for _ in range(5):
            t = threading.Thread(target=increment_and_record)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All sequences should be unique (500 total)
        assert len(sequences) == 500
        assert len(set(sequences)) == 500  # No duplicates
        # Final sequence should be 500
        assert tracker.get_current_sequence("conn-shared") == 500
