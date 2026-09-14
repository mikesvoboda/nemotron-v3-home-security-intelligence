"""Unit tests for WebSocket connection health tracking (NEM-3740).

Tests the ConnectionHealthTracker which tracks:
- Message success/failure counts
- Latency measurements
- Health score calculation
- Connection status classification
"""

from __future__ import annotations

import pytest

from backend.core.websocket.connection_health import (
    ConnectionHealthStatus,
    ConnectionHealthTracker,
    ConnectionMetrics,
    get_health_tracker,
    reset_health_tracker_state,
)


@pytest.fixture(autouse=True)
def _reset_health_tracker() -> None:
    """Reset global health tracker state before each test for isolation."""
    reset_health_tracker_state()


# ==============================================================================
# ConnectionMetrics Tests
# ==============================================================================


class TestConnectionMetrics:
    """Tests for ConnectionMetrics dataclass."""

    def test_initial_state(self) -> None:
        """Test that new metrics start with correct initial values."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        assert metrics.connection_id == "test-conn"
        assert metrics.messages_sent == 0
        assert metrics.messages_failed == 0
        assert metrics.total_messages == 0
        assert metrics.failure_rate == 0.0
        assert metrics.average_latency is None
        assert metrics.max_latency is None
        assert metrics.last_success_at is None
        assert metrics.last_failure_at is None
        assert metrics.last_latency_at is None

    def test_record_success(self) -> None:
        """Test recording successful messages."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        metrics.record_success()
        assert metrics.messages_sent == 1
        assert metrics.total_messages == 1
        assert metrics.failure_rate == 0.0
        assert metrics.last_success_at is not None

        metrics.record_success()
        assert metrics.messages_sent == 2

    def test_record_failure(self) -> None:
        """Test recording failed messages."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        metrics.record_failure()
        assert metrics.messages_failed == 1
        assert metrics.total_messages == 1
        assert metrics.failure_rate == 1.0
        assert metrics.last_failure_at is not None

    def test_failure_rate_calculation(self) -> None:
        """Test failure rate calculation with mixed results."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        # 2 successes, 2 failures = 50% failure rate
        metrics.record_success()
        metrics.record_success()
        metrics.record_failure()
        metrics.record_failure()

        assert metrics.total_messages == 4
        assert metrics.failure_rate == 0.5

    def test_latency_recording(self) -> None:
        """Test latency measurement recording."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        metrics.record_latency(50.0)
        metrics.record_latency(100.0)
        metrics.record_latency(150.0)

        assert metrics.average_latency == 100.0
        assert metrics.max_latency == 150.0
        assert metrics.last_latency_at is not None
        assert len(metrics.latency_samples) == 3

    def test_latency_sample_limit(self) -> None:
        """Test that latency samples are limited (deque maxlen)."""
        metrics = ConnectionMetrics(connection_id="test-conn")

        # Record more than maxlen (10) samples
        for i in range(15):
            metrics.record_latency(float(i * 10))

        # Should only keep last 10 samples
        assert len(metrics.latency_samples) == 10
        # Average of last 10: 50, 60, 70, 80, 90, 100, 110, 120, 130, 140
        expected_avg = sum(range(50, 150, 10)) / 10
        assert metrics.average_latency == expected_avg


# ==============================================================================
# ConnectionHealthTracker Tests
# ==============================================================================


class TestConnectionHealthTracker:
    """Tests for ConnectionHealthTracker."""

    def test_register_connection(self) -> None:
        """Test registering a new connection."""
        tracker = ConnectionHealthTracker()

        tracker.register_connection("conn-1")
        assert tracker.get_connection_count() == 1

        # Registering same connection is idempotent
        tracker.register_connection("conn-1")
        assert tracker.get_connection_count() == 1

    def test_remove_connection(self) -> None:
        """Test removing a connection."""
        tracker = ConnectionHealthTracker()

        tracker.register_connection("conn-1")
        tracker.record_message_success("conn-1")

        metrics = tracker.remove_connection("conn-1")
        assert metrics is not None
        assert metrics.messages_sent == 1
        assert tracker.get_connection_count() == 0

    def test_remove_nonexistent_connection(self) -> None:
        """Test removing a nonexistent connection returns None."""
        tracker = ConnectionHealthTracker()

        metrics = tracker.remove_connection("nonexistent")
        assert metrics is None

    def test_record_message_success(self) -> None:
        """Test recording message success auto-registers connection."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_success("conn-1")
        assert tracker.get_connection_count() == 1

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.metrics.messages_sent == 1

    def test_record_message_failure(self) -> None:
        """Test recording message failure."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_failure("conn-1")

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.metrics.messages_failed == 1

    def test_record_latency(self) -> None:
        """Test recording latency measurements."""
        tracker = ConnectionHealthTracker()

        tracker.record_latency("conn-1", 45.5)
        tracker.record_latency("conn-1", 55.5)

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.metrics.average_latency == 50.5

    def test_health_score_healthy(self) -> None:
        """Test health score for healthy connection."""
        tracker = ConnectionHealthTracker()

        # 10 successful messages, no failures, low latency
        for _ in range(10):
            tracker.record_message_success("conn-1")
        tracker.record_latency("conn-1", 50.0)  # Below threshold

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.score == 100.0
        assert health.status == ConnectionHealthStatus.HEALTHY
        assert health.failure_penalty == 0.0
        assert health.latency_penalty == 0.0

    def test_health_score_with_failures(self) -> None:
        """Test health score penalized by failures."""
        tracker = ConnectionHealthTracker()

        # 8 successes, 2 failures = 20% failure rate
        for _ in range(8):
            tracker.record_message_success("conn-1")
        for _ in range(2):
            tracker.record_message_failure("conn-1")

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.score < 100.0
        assert health.failure_penalty > 0.0
        assert health.status in [ConnectionHealthStatus.HEALTHY, ConnectionHealthStatus.DEGRADED]

    def test_health_score_with_high_latency(self) -> None:
        """Test health score penalized by high latency."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_success("conn-1")
        # High latency: 300ms above 100ms threshold
        tracker.record_latency("conn-1", 300.0)

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.score < 100.0
        assert health.latency_penalty > 0.0

    def test_health_score_critical(self) -> None:
        """Test health score for critical connection (many failures)."""
        tracker = ConnectionHealthTracker()

        # All failures = 100% failure rate
        for _ in range(10):
            tracker.record_message_failure("conn-1")

        health = tracker.get_health_score("conn-1")
        assert health is not None
        assert health.score <= 20.0  # Below critical threshold
        assert health.status == ConnectionHealthStatus.CRITICAL

    def test_get_health_score_nonexistent(self) -> None:
        """Test getting health score for nonexistent connection."""
        tracker = ConnectionHealthTracker()

        health = tracker.get_health_score("nonexistent")
        assert health is None

    def test_get_all_health_scores(self) -> None:
        """Test getting health scores for all connections."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_success("conn-1")
        tracker.record_message_success("conn-2")
        tracker.record_message_failure("conn-3")

        all_health = tracker.get_all_health_scores()
        assert len(all_health) == 3

        connection_ids = {h.connection_id for h in all_health}
        assert connection_ids == {"conn-1", "conn-2", "conn-3"}

    def test_get_unhealthy_connections(self) -> None:
        """Test filtering unhealthy connections."""
        tracker = ConnectionHealthTracker()

        # Healthy connection
        for _ in range(10):
            tracker.record_message_success("healthy-conn")

        # Unhealthy connection (all failures)
        for _ in range(10):
            tracker.record_message_failure("unhealthy-conn")

        unhealthy = tracker.get_unhealthy_connections()
        assert len(unhealthy) == 1
        assert unhealthy[0].connection_id == "unhealthy-conn"

    def test_get_unhealthy_connections_custom_threshold(self) -> None:
        """Test filtering with custom threshold."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_success("conn-1")
        tracker.record_message_failure("conn-1")  # 50% failure rate

        # Default threshold (50) - should be unhealthy
        unhealthy_default = tracker.get_unhealthy_connections()

        # Higher threshold (90) - should catch more
        unhealthy_high = tracker.get_unhealthy_connections(threshold=90.0)

        # Connection with 50% failure rate has score around 50
        # It should be caught by threshold=90 but not by default threshold=50
        assert len(unhealthy_high) >= len(unhealthy_default)

    def test_get_stats(self) -> None:
        """Test getting aggregate statistics."""
        tracker = ConnectionHealthTracker()

        # Create some connections
        for _ in range(3):
            tracker.record_message_success("conn-1")
        tracker.record_message_failure("conn-1")

        for _ in range(5):
            tracker.record_message_success("conn-2")

        stats = tracker.get_stats()

        assert stats["total_connections"] == 2
        assert stats["total_messages_sent"] == 8  # 3 + 5
        assert stats["total_messages_failed"] == 1
        assert stats["average_score"] is not None
        assert "healthy_count" in stats
        assert "degraded_count" in stats

    def test_get_stats_empty(self) -> None:
        """Test stats when no connections."""
        tracker = ConnectionHealthTracker()

        stats = tracker.get_stats()

        assert stats["total_connections"] == 0
        assert stats["average_score"] is None
        assert stats["total_messages_sent"] == 0

    def test_connection_health_to_dict(self) -> None:
        """Test ConnectionHealth.to_dict() serialization."""
        tracker = ConnectionHealthTracker()

        tracker.record_message_success("conn-1")
        tracker.record_latency("conn-1", 50.0)

        health = tracker.get_health_score("conn-1")
        assert health is not None

        data = health.to_dict()

        assert data["connection_id"] == "conn-1"
        assert data["score"] == 100.0
        assert data["status"] == "healthy"
        assert data["messages_sent"] == 1
        assert data["messages_failed"] == 0
        assert data["failure_rate"] == 0.0
        assert data["average_latency_ms"] == 50.0


# ==============================================================================
# Global Singleton Tests
# ==============================================================================


class TestGlobalHealthTracker:
    """Tests for global singleton health tracker."""

    def test_get_health_tracker_singleton(self) -> None:
        """Test that get_health_tracker returns singleton."""
        tracker1 = get_health_tracker()
        tracker2 = get_health_tracker()

        assert tracker1 is tracker2

    def test_reset_health_tracker_state(self) -> None:
        """Test that reset_health_tracker_state creates new instance."""
        tracker1 = get_health_tracker()
        tracker1.record_message_success("conn-1")

        reset_health_tracker_state()
        tracker2 = get_health_tracker()

        assert tracker1 is not tracker2
        assert tracker2.get_connection_count() == 0


# ==============================================================================
# Configuration Tests
# ==============================================================================


class TestHealthTrackerConfiguration:
    """Tests for configurable health tracker thresholds."""

    def test_custom_failure_weight(self) -> None:
        """Test custom failure weight affects score."""
        # Default weight
        tracker_default = ConnectionHealthTracker(failure_weight=20.0)
        tracker_default.record_message_success("conn-1")
        tracker_default.record_message_failure("conn-1")

        # Higher weight
        tracker_heavy = ConnectionHealthTracker(failure_weight=40.0)
        tracker_heavy.record_message_success("conn-1")
        tracker_heavy.record_message_failure("conn-1")

        health_default = tracker_default.get_health_score("conn-1")
        health_heavy = tracker_heavy.get_health_score("conn-1")

        assert health_default is not None
        assert health_heavy is not None
        # Higher weight should result in lower score
        assert health_heavy.score < health_default.score

    def test_custom_latency_threshold(self) -> None:
        """Test custom latency threshold affects scoring."""
        # Low threshold - 50ms
        tracker_strict = ConnectionHealthTracker(latency_threshold_ms=50.0)
        tracker_strict.record_latency("conn-1", 100.0)  # Above threshold

        # High threshold - 200ms
        tracker_lenient = ConnectionHealthTracker(latency_threshold_ms=200.0)
        tracker_lenient.record_latency("conn-1", 100.0)  # Below threshold

        health_strict = tracker_strict.get_health_score("conn-1")
        health_lenient = tracker_lenient.get_health_score("conn-1")

        assert health_strict is not None
        assert health_lenient is not None
        # Strict threshold should penalize, lenient should not
        assert health_strict.latency_penalty > 0
        assert health_lenient.latency_penalty == 0

    def test_custom_health_thresholds(self) -> None:
        """Test custom status thresholds."""
        tracker = ConnectionHealthTracker(
            healthy_threshold=90.0,
            degraded_threshold=60.0,
            critical_threshold=30.0,
        )

        # Create a connection with 10% failure rate
        for _ in range(9):
            tracker.record_message_success("conn-1")
        tracker.record_message_failure("conn-1")

        health = tracker.get_health_score("conn-1")
        assert health is not None
        # Score should be around 90, which with threshold=90 is DEGRADED
        assert health.status in [ConnectionHealthStatus.HEALTHY, ConnectionHealthStatus.DEGRADED]
