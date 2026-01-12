"""WebSocket subscription manager for event filtering.

This module provides subscription management so clients can subscribe to only
the events they need, reducing bandwidth and processing overhead.

Features:
- Wildcard pattern matching (e.g., "alert.*", "camera.*", "*")
- Per-connection subscription tracking
- Default behavior: all events (backwards compatible)
- Clean subscription cleanup on disconnect

Protocol:
    Client sends subscription message:
        {"action": "subscribe", "events": ["alert.*", "camera.status_changed", "job.progress"]}

    Server acknowledges:
        {"action": "subscribed", "events": ["alert.*", "camera.status_changed", "job.progress"]}

    Client can unsubscribe:
        {"action": "unsubscribe", "events": ["alert.*"]}

    Server acknowledges:
        {"action": "unsubscribed", "events": ["alert.*"]}

Example Usage:
    from backend.core.websocket.subscription_manager import SubscriptionManager, get_subscription_manager

    # Get the global subscription manager
    manager = get_subscription_manager()

    # Subscribe a connection to specific patterns
    manager.subscribe("conn-123", ["alert.*", "camera.status_changed"])

    # Check if a connection should receive an event
    if manager.should_send("conn-123", "alert.created"):
        await websocket.send_text(message)

    # Get all connections that should receive an event
    recipients = manager.get_recipients("alert.created")

    # Clean up on disconnect
    manager.unsubscribe("conn-123")
"""

from __future__ import annotations

import fnmatch
import threading
from typing import Any

from pydantic import BaseModel, Field

from backend.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionRequest(BaseModel):
    """Client subscription request message."""

    action: str = Field(..., description="Action: 'subscribe' or 'unsubscribe'")
    events: list[str] = Field(
        default_factory=list,
        description="Event patterns to subscribe/unsubscribe (supports wildcards)",
    )


class SubscriptionResponse(BaseModel):
    """Server subscription acknowledgment message."""

    action: str = Field(..., description="Action: 'subscribed' or 'unsubscribed'")
    events: list[str] = Field(..., description="Event patterns that were processed")


class SubscriptionManager:
    """Manages WebSocket event subscriptions per connection.

    Tracks which event patterns each connection is subscribed to,
    supporting wildcard patterns for flexible event filtering.

    Pattern Matching:
    - `*` - Matches all events (default if no subscription sent)
    - `alert.*` - All alert events (alert.created, alert.updated, etc.)
    - `camera.*` - All camera events
    - `job.progress` - Exact match for specific event

    Thread Safety:
    - Uses threading.RLock for thread-safe operations
    - Safe to use from multiple async tasks

    Default Behavior:
    - New connections receive ALL events (backwards compatible)
    - Only after explicit subscribe() call are events filtered
    """

    def __init__(self) -> None:
        """Initialize the subscription manager."""
        self._subscriptions: dict[str, set[str]] = {}  # connection_id -> event patterns
        self._explicit_subscriptions: set[str] = set()  # connections with explicit subscriptions
        self._lock = threading.RLock()

    def subscribe(self, connection_id: str, patterns: list[str]) -> list[str]:
        """Subscribe a connection to event patterns.

        Adds the given patterns to the connection's subscription list.
        Supports wildcard patterns using fnmatch syntax.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            patterns: List of event patterns to subscribe to.
                      Supports wildcards: "alert.*", "*", etc.

        Returns:
            List of patterns that were added (for acknowledgment).

        Example:
            >>> manager.subscribe("conn-123", ["alert.*", "job.progress"])
            ["alert.*", "job.progress"]
        """
        with self._lock:
            if connection_id not in self._subscriptions:
                self._subscriptions[connection_id] = set()

            # Mark as having explicit subscriptions
            self._explicit_subscriptions.add(connection_id)

            # Add patterns (normalize to lowercase for consistent matching)
            normalized_patterns = [p.lower() for p in patterns]
            self._subscriptions[connection_id].update(normalized_patterns)

            logger.debug(
                f"Connection {connection_id} subscribed to patterns: {normalized_patterns}",
                extra={
                    "connection_id": connection_id,
                    "patterns": normalized_patterns,
                    "total_patterns": len(self._subscriptions[connection_id]),
                },
            )

            return normalized_patterns

    def unsubscribe(self, connection_id: str, patterns: list[str] | None = None) -> list[str]:
        """Unsubscribe a connection from event patterns.

        If patterns is None, removes all subscriptions for the connection
        (also cleans up the connection entirely).

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            patterns: List of patterns to unsubscribe from.
                      If None, removes all subscriptions and cleans up the connection.

        Returns:
            List of patterns that were removed.

        Example:
            >>> manager.unsubscribe("conn-123", ["alert.*"])
            ["alert.*"]
            >>> manager.unsubscribe("conn-123")  # Remove all
            ["job.progress"]
        """
        with self._lock:
            if connection_id not in self._subscriptions:
                return []

            if patterns is None:
                # Remove all subscriptions and clean up
                removed = list(self._subscriptions[connection_id])
                del self._subscriptions[connection_id]
                self._explicit_subscriptions.discard(connection_id)

                logger.debug(
                    f"Connection {connection_id} unsubscribed from all patterns",
                    extra={"connection_id": connection_id, "removed_patterns": removed},
                )
                return removed

            # Remove specific patterns
            normalized_patterns = [p.lower() for p in patterns]
            removed = []
            for pattern in normalized_patterns:
                if pattern in self._subscriptions[connection_id]:
                    self._subscriptions[connection_id].discard(pattern)
                    removed.append(pattern)

            logger.debug(
                f"Connection {connection_id} unsubscribed from patterns: {removed}",
                extra={
                    "connection_id": connection_id,
                    "removed_patterns": removed,
                    "remaining_patterns": len(self._subscriptions[connection_id]),
                },
            )

            return removed

    def should_send(self, connection_id: str, event_type: str) -> bool:
        """Check if a connection should receive an event type.

        If the connection has no explicit subscriptions, returns True
        (default: receive all events for backwards compatibility).

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            event_type: The event type to check (e.g., "alert.created").

        Returns:
            True if the event should be sent to the connection, False otherwise.

        Example:
            >>> manager.subscribe("conn-123", ["alert.*"])
            >>> manager.should_send("conn-123", "alert.created")
            True
            >>> manager.should_send("conn-123", "camera.offline")
            False
        """
        with self._lock:
            # If connection has no explicit subscriptions, send all events
            if connection_id not in self._explicit_subscriptions:
                return True

            # If connection has no patterns (explicit but empty), don't send anything
            if connection_id not in self._subscriptions:
                return False

            patterns = self._subscriptions[connection_id]
            if not patterns:
                return False

            # Normalize event type for matching
            normalized_event = event_type.lower()

            # Check if any pattern matches the event type
            return self._matches_any_pattern(normalized_event, patterns)

    def get_recipients(self, event_type: str) -> set[str]:
        """Get all connection IDs that should receive an event type.

        Returns the set of all connection IDs that are subscribed to
        patterns matching the given event type.

        Args:
            event_type: The event type to check (e.g., "alert.created").

        Returns:
            Set of connection IDs that should receive the event.

        Example:
            >>> manager.subscribe("conn-123", ["alert.*"])
            >>> manager.subscribe("conn-456", ["*"])
            >>> manager.get_recipients("alert.created")
            {"conn-123", "conn-456"}
        """
        with self._lock:
            recipients: set[str] = set()
            normalized_event = event_type.lower()

            for connection_id in self._subscriptions:
                # Connections without explicit subscriptions receive all events
                if connection_id not in self._explicit_subscriptions:
                    recipients.add(connection_id)
                    continue

                patterns = self._subscriptions[connection_id]
                if self._matches_any_pattern(normalized_event, patterns):
                    recipients.add(connection_id)

            return recipients

    def get_subscriptions(self, connection_id: str) -> set[str]:
        """Get all patterns a connection is subscribed to.

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            Set of patterns the connection is subscribed to.
            Empty set if connection has no subscriptions.
        """
        with self._lock:
            return self._subscriptions.get(connection_id, set()).copy()

    def has_explicit_subscriptions(self, connection_id: str) -> bool:
        """Check if a connection has explicit subscriptions.

        Connections without explicit subscriptions receive all events
        (default behavior for backwards compatibility).

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            True if the connection has called subscribe() at least once.
        """
        with self._lock:
            return connection_id in self._explicit_subscriptions

    def register_connection(self, connection_id: str) -> None:
        """Register a new connection (receives all events by default).

        Call this when a new WebSocket connection is established.
        The connection will receive all events until subscribe() is called.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
        """
        with self._lock:
            if connection_id not in self._subscriptions:
                self._subscriptions[connection_id] = set()
                logger.debug(
                    f"Registered connection {connection_id} (default: all events)",
                    extra={"connection_id": connection_id},
                )

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection and all its subscriptions.

        Call this when a WebSocket connection is closed to clean up.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
        """
        with self._lock:
            self._subscriptions.pop(connection_id, None)
            self._explicit_subscriptions.discard(connection_id)
            logger.debug(
                f"Removed connection {connection_id}",
                extra={"connection_id": connection_id},
            )

    def get_connection_count(self) -> int:
        """Get the number of registered connections.

        Returns:
            Number of connections currently registered.
        """
        with self._lock:
            return len(self._subscriptions)

    def get_stats(self) -> dict[str, Any]:
        """Get subscription statistics.

        Returns:
            Dictionary with subscription statistics.
        """
        with self._lock:
            total_connections = len(self._subscriptions)
            explicit_count = len(self._explicit_subscriptions)
            total_patterns = sum(len(patterns) for patterns in self._subscriptions.values())

            return {
                "total_connections": total_connections,
                "explicit_subscriptions": explicit_count,
                "default_subscriptions": total_connections - explicit_count,
                "total_patterns": total_patterns,
            }

    def _matches_any_pattern(self, event_type: str, patterns: set[str]) -> bool:
        """Check if an event type matches any of the given patterns.

        Uses fnmatch for wildcard matching:
        - "*" matches everything
        - "alert.*" matches "alert.created", "alert.updated", etc.
        - "alert.created" matches exactly "alert.created"

        Args:
            event_type: The event type to check (normalized to lowercase).
            patterns: Set of patterns to match against.

        Returns:
            True if the event type matches any pattern.
        """
        return any(fnmatch.fnmatch(event_type, pattern) for pattern in patterns)


# =============================================================================
# Global Singleton Instance
# =============================================================================

_subscription_manager: SubscriptionManager | None = None
_manager_lock = threading.Lock()


def get_subscription_manager() -> SubscriptionManager:
    """Get or create the global subscription manager instance.

    This function provides a thread-safe singleton pattern for the
    SubscriptionManager.

    Returns:
        SubscriptionManager instance.

    Example:
        manager = get_subscription_manager()
        manager.subscribe("conn-123", ["alert.*"])
    """
    global _subscription_manager  # noqa: PLW0603

    # Fast path: manager already exists
    if _subscription_manager is not None:
        return _subscription_manager

    # Slow path: need to initialize with lock
    with _manager_lock:
        # Double-check after acquiring lock
        if _subscription_manager is None:
            _subscription_manager = SubscriptionManager()
            logger.info("Global subscription manager initialized")

    return _subscription_manager


def reset_subscription_manager_state() -> None:
    """Reset the global subscription manager state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _subscription_manager  # noqa: PLW0603
    _subscription_manager = None
