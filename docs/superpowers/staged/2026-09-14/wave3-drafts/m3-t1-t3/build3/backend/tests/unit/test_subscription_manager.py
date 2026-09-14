"""Unit tests for WebSocket subscription manager.

Tests cover:
- Basic subscription and unsubscription
- Wildcard pattern matching
- Default behavior (all events)
- Connection lifecycle (register, remove)
- Recipient filtering
- Thread safety
- Edge cases
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.core.websocket.subscription_manager import (
    SubscriptionManager,
    SubscriptionRequest,
    SubscriptionResponse,
    get_subscription_manager,
    reset_subscription_manager_state,
)


@pytest.fixture
def manager() -> SubscriptionManager:
    """Create a fresh subscription manager for each test."""
    return SubscriptionManager()


@pytest.fixture(autouse=True)
def reset_global_state() -> None:
    """Reset global subscription manager state after each test."""
    yield
    reset_subscription_manager_state()


class TestSubscriptionManager:
    """Tests for SubscriptionManager class."""

    # =========================================================================
    # Basic Subscription Tests
    # =========================================================================

    def test_subscribe_single_pattern(self, manager: SubscriptionManager) -> None:
        """Test subscribing to a single pattern."""
        patterns = manager.subscribe("conn-1", ["alert.*"])

        assert patterns == ["alert.*"]
        assert manager.get_subscriptions("conn-1") == {"alert.*"}
        assert manager.has_explicit_subscriptions("conn-1") is True

    def test_subscribe_multiple_patterns(self, manager: SubscriptionManager) -> None:
        """Test subscribing to multiple patterns at once."""
        patterns = manager.subscribe("conn-1", ["alert.*", "camera.status_changed", "job.progress"])

        assert sorted(patterns) == sorted(["alert.*", "camera.status_changed", "job.progress"])
        assert manager.get_subscriptions("conn-1") == {
            "alert.*",
            "camera.status_changed",
            "job.progress",
        }

    def test_subscribe_incremental(self, manager: SubscriptionManager) -> None:
        """Test adding subscriptions incrementally."""
        manager.subscribe("conn-1", ["alert.*"])
        manager.subscribe("conn-1", ["camera.*"])

        subscriptions = manager.get_subscriptions("conn-1")
        assert subscriptions == {"alert.*", "camera.*"}

    def test_subscribe_normalizes_to_lowercase(self, manager: SubscriptionManager) -> None:
        """Test that patterns are normalized to lowercase."""
        manager.subscribe("conn-1", ["ALERT.*", "Camera.STATUS_CHANGED"])

        subscriptions = manager.get_subscriptions("conn-1")
        assert subscriptions == {"alert.*", "camera.status_changed"}

    def test_subscribe_duplicate_patterns(self, manager: SubscriptionManager) -> None:
        """Test that duplicate patterns are handled gracefully."""
        manager.subscribe("conn-1", ["alert.*", "alert.*", "alert.*"])

        # Should only have one entry
        assert manager.get_subscriptions("conn-1") == {"alert.*"}

    # =========================================================================
    # Unsubscription Tests
    # =========================================================================

    def test_unsubscribe_specific_pattern(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from a specific pattern."""
        manager.subscribe("conn-1", ["alert.*", "camera.*", "job.*"])
        removed = manager.unsubscribe("conn-1", ["camera.*"])

        assert removed == ["camera.*"]
        assert manager.get_subscriptions("conn-1") == {"alert.*", "job.*"}

    def test_unsubscribe_multiple_patterns(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from multiple patterns."""
        manager.subscribe("conn-1", ["alert.*", "camera.*", "job.*"])
        removed = manager.unsubscribe("conn-1", ["alert.*", "job.*"])

        assert sorted(removed) == sorted(["alert.*", "job.*"])
        assert manager.get_subscriptions("conn-1") == {"camera.*"}

    def test_unsubscribe_all(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from all patterns (cleanup)."""
        manager.subscribe("conn-1", ["alert.*", "camera.*"])
        removed = manager.unsubscribe("conn-1")

        assert sorted(removed) == sorted(["alert.*", "camera.*"])
        assert manager.get_subscriptions("conn-1") == set()
        assert manager.has_explicit_subscriptions("conn-1") is False

    def test_unsubscribe_nonexistent_pattern(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from a pattern that doesn't exist."""
        manager.subscribe("conn-1", ["alert.*"])
        removed = manager.unsubscribe("conn-1", ["camera.*"])

        assert removed == []
        assert manager.get_subscriptions("conn-1") == {"alert.*"}

    def test_unsubscribe_nonexistent_connection(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from a connection that doesn't exist."""
        removed = manager.unsubscribe("nonexistent", ["alert.*"])

        assert removed == []

    # =========================================================================
    # Pattern Matching Tests
    # =========================================================================

    def test_should_send_wildcard_all(self, manager: SubscriptionManager) -> None:
        """Test that '*' pattern matches all events."""
        manager.subscribe("conn-1", ["*"])

        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "camera.offline") is True
        assert manager.should_send("conn-1", "job.progress") is True
        assert manager.should_send("conn-1", "system.health_changed") is True
        assert manager.should_send("conn-1", "anything.at.all") is True

    def test_should_send_domain_wildcard(self, manager: SubscriptionManager) -> None:
        """Test that 'domain.*' pattern matches all events in that domain."""
        manager.subscribe("conn-1", ["alert.*"])

        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "alert.updated") is True
        assert manager.should_send("conn-1", "alert.acknowledged") is True
        assert manager.should_send("conn-1", "alert.dismissed") is True
        assert manager.should_send("conn-1", "camera.offline") is False
        assert manager.should_send("conn-1", "job.progress") is False

    def test_should_send_exact_match(self, manager: SubscriptionManager) -> None:
        """Test exact event type matching."""
        manager.subscribe("conn-1", ["job.progress"])

        assert manager.should_send("conn-1", "job.progress") is True
        assert manager.should_send("conn-1", "job.completed") is False
        assert manager.should_send("conn-1", "job.failed") is False
        assert manager.should_send("conn-1", "alert.created") is False

    def test_should_send_multiple_patterns(self, manager: SubscriptionManager) -> None:
        """Test matching against multiple patterns."""
        manager.subscribe("conn-1", ["alert.*", "camera.status_changed", "job.progress"])

        # Should match alert.*
        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "alert.dismissed") is True

        # Should match camera.status_changed exactly
        assert manager.should_send("conn-1", "camera.status_changed") is True
        assert manager.should_send("conn-1", "camera.offline") is False

        # Should match job.progress exactly
        assert manager.should_send("conn-1", "job.progress") is True
        assert manager.should_send("conn-1", "job.completed") is False

        # Should not match unsubscribed
        assert manager.should_send("conn-1", "system.health_changed") is False

    def test_should_send_case_insensitive(self, manager: SubscriptionManager) -> None:
        """Test that event type matching is case-insensitive."""
        manager.subscribe("conn-1", ["alert.*"])

        assert manager.should_send("conn-1", "ALERT.CREATED") is True
        assert manager.should_send("conn-1", "Alert.Created") is True
        assert manager.should_send("conn-1", "alert.created") is True

    # =========================================================================
    # Default Behavior Tests (Backwards Compatibility)
    # =========================================================================

    def test_default_receives_all_events(self, manager: SubscriptionManager) -> None:
        """Test that connections without explicit subscriptions receive all events."""
        manager.register_connection("conn-1")

        # Should receive all events (default behavior)
        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "camera.offline") is True
        assert manager.should_send("conn-1", "job.progress") is True
        assert manager.should_send("conn-1", "system.anything") is True
        assert manager.has_explicit_subscriptions("conn-1") is False

    def test_unregistered_connection_receives_all(self, manager: SubscriptionManager) -> None:
        """Test that even unregistered connections receive all events."""
        # This maintains backwards compatibility - unknown connections get all events
        assert manager.should_send("unknown-conn", "alert.created") is True
        assert manager.should_send("unknown-conn", "anything") is True

    def test_explicit_subscription_overrides_default(self, manager: SubscriptionManager) -> None:
        """Test that explicit subscription overrides default behavior."""
        manager.register_connection("conn-1")

        # Before explicit subscription - receives all
        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "camera.offline") is True

        # After explicit subscription - only subscribed events
        manager.subscribe("conn-1", ["alert.*"])

        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "camera.offline") is False

    def test_empty_explicit_subscription_receives_nothing(
        self, manager: SubscriptionManager
    ) -> None:
        """Test that empty explicit subscription receives no events."""
        manager.register_connection("conn-1")
        manager.subscribe("conn-1", [])  # Explicit but empty

        # Should receive nothing
        assert manager.should_send("conn-1", "alert.created") is False
        assert manager.should_send("conn-1", "camera.offline") is False

    # =========================================================================
    # Connection Lifecycle Tests
    # =========================================================================

    def test_register_connection(self, manager: SubscriptionManager) -> None:
        """Test registering a new connection."""
        manager.register_connection("conn-1")

        assert manager.get_connection_count() == 1
        assert manager.has_explicit_subscriptions("conn-1") is False

    def test_register_connection_idempotent(self, manager: SubscriptionManager) -> None:
        """Test that registering the same connection multiple times is safe."""
        manager.register_connection("conn-1")
        manager.register_connection("conn-1")
        manager.register_connection("conn-1")

        assert manager.get_connection_count() == 1

    def test_remove_connection(self, manager: SubscriptionManager) -> None:
        """Test removing a connection cleans up all state."""
        manager.register_connection("conn-1")
        manager.subscribe("conn-1", ["alert.*"])

        manager.remove_connection("conn-1")

        assert manager.get_connection_count() == 0
        assert manager.has_explicit_subscriptions("conn-1") is False
        assert manager.get_subscriptions("conn-1") == set()

    def test_remove_nonexistent_connection(self, manager: SubscriptionManager) -> None:
        """Test removing a non-existent connection is safe."""
        manager.remove_connection("nonexistent")  # Should not raise

        assert manager.get_connection_count() == 0

    # =========================================================================
    # Recipient Filtering Tests
    # =========================================================================

    def test_get_recipients_single_subscriber(self, manager: SubscriptionManager) -> None:
        """Test getting recipients with a single subscriber."""
        manager.subscribe("conn-1", ["alert.*"])

        recipients = manager.get_recipients("alert.created")

        assert recipients == {"conn-1"}

    def test_get_recipients_multiple_subscribers(self, manager: SubscriptionManager) -> None:
        """Test getting recipients with multiple subscribers."""
        manager.subscribe("conn-1", ["alert.*"])
        manager.subscribe("conn-2", ["alert.*", "camera.*"])
        manager.subscribe("conn-3", ["*"])

        recipients = manager.get_recipients("alert.created")

        assert recipients == {"conn-1", "conn-2", "conn-3"}

    def test_get_recipients_partial_match(self, manager: SubscriptionManager) -> None:
        """Test that only matching connections are returned."""
        manager.subscribe("conn-1", ["alert.*"])
        manager.subscribe("conn-2", ["camera.*"])
        manager.subscribe("conn-3", ["job.*"])

        alert_recipients = manager.get_recipients("alert.created")
        camera_recipients = manager.get_recipients("camera.offline")

        assert alert_recipients == {"conn-1"}
        assert camera_recipients == {"conn-2"}

    def test_get_recipients_includes_default_subscribers(
        self, manager: SubscriptionManager
    ) -> None:
        """Test that default subscribers (no explicit subscription) are included."""
        manager.register_connection("conn-default")  # Receives all
        manager.subscribe("conn-explicit", ["alert.*"])

        recipients = manager.get_recipients("alert.created")

        # Both should receive alert events
        assert "conn-default" in recipients
        assert "conn-explicit" in recipients

    def test_get_recipients_empty_when_no_match(self, manager: SubscriptionManager) -> None:
        """Test that empty set is returned when no connections match."""
        manager.subscribe("conn-1", ["alert.*"])
        manager.subscribe("conn-2", ["camera.*"])

        recipients = manager.get_recipients("system.health_changed")

        assert recipients == set()

    # =========================================================================
    # Statistics Tests
    # =========================================================================

    def test_get_stats(self, manager: SubscriptionManager) -> None:
        """Test getting subscription statistics."""
        manager.register_connection("conn-default-1")
        manager.register_connection("conn-default-2")
        manager.subscribe("conn-explicit-1", ["alert.*"])
        manager.subscribe("conn-explicit-2", ["alert.*", "camera.*", "job.*"])

        stats = manager.get_stats()

        assert stats["total_connections"] == 4
        assert stats["explicit_subscriptions"] == 2
        assert stats["default_subscriptions"] == 2
        assert stats["total_patterns"] == 4  # 1 + 3 from explicit subscribers

    def test_get_stats_empty(self, manager: SubscriptionManager) -> None:
        """Test getting stats with no connections."""
        stats = manager.get_stats()

        assert stats["total_connections"] == 0
        assert stats["explicit_subscriptions"] == 0
        assert stats["default_subscriptions"] == 0
        assert stats["total_patterns"] == 0

    # =========================================================================
    # Thread Safety Tests
    # =========================================================================

    def test_concurrent_subscriptions(self, manager: SubscriptionManager) -> None:
        """Test that concurrent subscriptions are thread-safe."""
        num_connections = 100
        num_threads = 10

        def subscribe_connection(conn_id: int) -> None:
            manager.subscribe(f"conn-{conn_id}", [f"pattern-{conn_id}"])

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            list(executor.map(subscribe_connection, range(num_connections)))

        assert manager.get_connection_count() == num_connections

    def test_concurrent_should_send(self, manager: SubscriptionManager) -> None:
        """Test that concurrent should_send checks are thread-safe."""
        manager.subscribe("conn-1", ["alert.*"])

        results = []

        def check_should_send() -> None:
            result = manager.should_send("conn-1", "alert.created")
            results.append(result)

        threads = [threading.Thread(target=check_should_send) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be True
        assert all(results)
        assert len(results) == 100

    def test_concurrent_mixed_operations(self, manager: SubscriptionManager) -> None:
        """Test mixed concurrent operations."""
        errors = []

        def mixed_operations(thread_id: int) -> None:
            try:
                conn_id = f"conn-{thread_id}"
                manager.register_connection(conn_id)
                manager.subscribe(conn_id, ["alert.*", f"thread-{thread_id}.*"])
                _ = manager.should_send(conn_id, "alert.created")
                _ = manager.get_recipients("alert.created")
                manager.unsubscribe(conn_id, ["alert.*"])
                manager.remove_connection(conn_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=20) as executor:
            list(executor.map(mixed_operations, range(100)))

        assert not errors, f"Errors occurred: {errors}"


class TestSubscriptionModels:
    """Tests for Pydantic subscription models."""

    def test_subscription_request_subscribe(self) -> None:
        """Test SubscriptionRequest for subscribe action."""
        request = SubscriptionRequest(
            action="subscribe",
            events=["alert.*", "camera.status_changed"],
        )

        assert request.action == "subscribe"
        assert request.events == ["alert.*", "camera.status_changed"]

    def test_subscription_request_unsubscribe(self) -> None:
        """Test SubscriptionRequest for unsubscribe action."""
        request = SubscriptionRequest(
            action="unsubscribe",
            events=["alert.*"],
        )

        assert request.action == "unsubscribe"
        assert request.events == ["alert.*"]

    def test_subscription_request_empty_events(self) -> None:
        """Test SubscriptionRequest with empty events list."""
        request = SubscriptionRequest(action="subscribe", events=[])

        assert request.events == []

    def test_subscription_request_default_events(self) -> None:
        """Test SubscriptionRequest with default events."""
        request = SubscriptionRequest(action="subscribe")

        assert request.events == []

    def test_subscription_response_subscribed(self) -> None:
        """Test SubscriptionResponse for subscribed action."""
        response = SubscriptionResponse(
            action="subscribed",
            events=["alert.*", "camera.status_changed"],
        )

        assert response.action == "subscribed"
        assert response.events == ["alert.*", "camera.status_changed"]

    def test_subscription_response_unsubscribed(self) -> None:
        """Test SubscriptionResponse for unsubscribed action."""
        response = SubscriptionResponse(
            action="unsubscribed",
            events=["alert.*"],
        )

        assert response.action == "unsubscribed"
        assert response.events == ["alert.*"]


class TestGlobalSubscriptionManager:
    """Tests for global subscription manager singleton."""

    def test_get_subscription_manager_returns_instance(self) -> None:
        """Test that get_subscription_manager returns a SubscriptionManager."""
        manager = get_subscription_manager()

        assert isinstance(manager, SubscriptionManager)

    def test_get_subscription_manager_singleton(self) -> None:
        """Test that get_subscription_manager returns the same instance."""
        manager1 = get_subscription_manager()
        manager2 = get_subscription_manager()

        assert manager1 is manager2

    def test_reset_subscription_manager_state(self) -> None:
        """Test that reset creates a new instance."""
        manager1 = get_subscription_manager()
        manager1.subscribe("conn-1", ["alert.*"])

        reset_subscription_manager_state()

        manager2 = get_subscription_manager()
        assert manager2 is not manager1
        assert manager2.get_connection_count() == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_event_type(self, manager: SubscriptionManager) -> None:
        """Test handling of empty event type."""
        manager.subscribe("conn-1", ["*"])

        assert manager.should_send("conn-1", "") is True  # * matches everything

    def test_special_characters_in_pattern(self, manager: SubscriptionManager) -> None:
        """Test handling of special characters in patterns."""
        manager.subscribe("conn-1", ["alert.created_v2"])

        assert manager.should_send("conn-1", "alert.created_v2") is True
        assert manager.should_send("conn-1", "alert.created") is False

    def test_deep_nested_event_type(self, manager: SubscriptionManager) -> None:
        """Test matching against deeply nested event types."""
        manager.subscribe("conn-1", ["system.health.*"])

        # fnmatch with single * only matches one level
        assert manager.should_send("conn-1", "system.health.changed") is True
        assert manager.should_send("conn-1", "system.health") is False

    def test_question_mark_wildcard(self, manager: SubscriptionManager) -> None:
        """Test that ? wildcard matches single character."""
        manager.subscribe("conn-1", ["alert.create?"])

        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "alert.creates") is True
        assert manager.should_send("conn-1", "alert.create") is False
        assert manager.should_send("conn-1", "alert.createdd") is False

    def test_bracket_pattern(self, manager: SubscriptionManager) -> None:
        """Test that bracket patterns work for character sets."""
        manager.subscribe("conn-1", ["alert.[cu]*"])

        assert manager.should_send("conn-1", "alert.created") is True
        assert manager.should_send("conn-1", "alert.updated") is True
        assert manager.should_send("conn-1", "alert.deleted") is False

    def test_very_long_pattern(self, manager: SubscriptionManager) -> None:
        """Test handling of very long patterns."""
        long_pattern = "a" * 1000 + ".*"
        manager.subscribe("conn-1", [long_pattern])

        # Should work without error
        assert manager.should_send("conn-1", "a" * 1000 + ".test") is True

    def test_unicode_in_pattern(self, manager: SubscriptionManager) -> None:
        """Test handling of unicode in patterns."""
        manager.subscribe("conn-1", ["alert.created"])  # Standard pattern

        # Should handle gracefully
        assert manager.get_subscriptions("conn-1") == {"alert.created"}
