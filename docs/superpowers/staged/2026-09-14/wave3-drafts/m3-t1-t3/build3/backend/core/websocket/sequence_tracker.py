"""WebSocket message sequence tracking for reliable message delivery.

This module provides per-connection sequence number tracking to enable:
- Client-side gap detection (identify missed messages)
- Message ordering verification
- Reliable message delivery patterns

Each WebSocket connection has its own monotonically increasing sequence counter
starting at 1. The sequence is included in all outgoing messages.

NEM-3142: Added sequence tracking for reliable message delivery.

Example Usage:
    from backend.core.websocket.sequence_tracker import get_sequence_tracker

    # Get the global sequence tracker
    tracker = get_sequence_tracker()

    # Register a new connection with its WebSocket object
    tracker.register_connection("conn-123", websocket)

    # Get next sequence number for a message
    seq = tracker.next_sequence("conn-123")
    message = {"seq": seq, "type": "event", "data": {...}}

    # Get connection_id from WebSocket object
    conn_id = tracker.get_connection_id(websocket)

    # Get current sequence without incrementing
    last_seq = tracker.get_current_sequence("conn-123")

    # Clean up on disconnect
    tracker.remove_connection("conn-123")
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = get_logger(__name__)


class SequenceTracker:
    """Tracks per-connection message sequence numbers.

    Each WebSocket connection has its own sequence counter that starts at 0
    and increments with each message sent. This allows clients to detect
    gaps in message delivery.

    Also maintains a mapping from WebSocket objects to connection IDs to allow
    the broadcasters to look up the connection_id for a given WebSocket.

    Thread Safety:
    - Uses threading.RLock for thread-safe operations
    - Safe to use from multiple async tasks

    Sequence Numbers:
    - Start at 0 for each connection
    - Increment by 1 for each message
    - Are unique per connection (not global)
    """

    def __init__(self) -> None:
        """Initialize the sequence tracker."""
        self._sequences: dict[str, int] = {}  # connection_id -> current sequence
        self._ws_to_connection: dict[int, str] = {}  # id(websocket) -> connection_id
        self._lock = threading.RLock()

    def register_connection(self, connection_id: str, websocket: WebSocket | None = None) -> None:
        """Register a new connection with sequence starting at 0.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            websocket: Optional WebSocket object to map to this connection_id.
        """
        with self._lock:
            if connection_id not in self._sequences:
                self._sequences[connection_id] = 0
                logger.debug(
                    f"Registered connection {connection_id} with sequence 0",
                    extra={"connection_id": connection_id},
                )
            if websocket is not None:
                self._ws_to_connection[id(websocket)] = connection_id

    def remove_connection(self, connection_id: str, websocket: WebSocket | None = None) -> None:
        """Remove a connection and its sequence counter.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            websocket: Optional WebSocket object to also remove from mapping.
        """
        with self._lock:
            if connection_id in self._sequences:
                final_seq = self._sequences.pop(connection_id)
                logger.debug(
                    f"Removed connection {connection_id} (final sequence: {final_seq})",
                    extra={"connection_id": connection_id, "final_sequence": final_seq},
                )
            if websocket is not None:
                self._ws_to_connection.pop(id(websocket), None)
            # Also clean up any stale mappings for this connection_id
            stale_keys = [k for k, v in self._ws_to_connection.items() if v == connection_id]
            for key in stale_keys:
                del self._ws_to_connection[key]

    def next_sequence(self, connection_id: str) -> int:
        """Get the next sequence number for a connection and increment.

        If the connection is not registered, it will be auto-registered
        with sequence 0, then incremented to 1.

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            The next sequence number (1, 2, 3, ...).
        """
        with self._lock:
            if connection_id not in self._sequences:
                self._sequences[connection_id] = 0
                logger.debug(
                    f"Auto-registered connection {connection_id} for sequencing",
                    extra={"connection_id": connection_id},
                )

            self._sequences[connection_id] += 1
            return self._sequences[connection_id]

    def get_current_sequence(self, connection_id: str) -> int:
        """Get the current sequence number without incrementing.

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            The current sequence number (0 if not registered).
        """
        with self._lock:
            return self._sequences.get(connection_id, 0)

    def get_connection_id(self, websocket: WebSocket) -> str | None:
        """Get the connection_id for a WebSocket object.

        Args:
            websocket: The WebSocket object to look up.

        Returns:
            The connection_id if found, None otherwise.
        """
        with self._lock:
            return self._ws_to_connection.get(id(websocket))

    def register_websocket(self, connection_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket object with an existing connection_id.

        This should be called after registering the connection to associate
        the WebSocket object with the connection_id for lookup.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            websocket: The WebSocket object to associate.
        """
        with self._lock:
            self._ws_to_connection[id(websocket)] = connection_id

    def get_connection_count(self) -> int:
        """Get the number of registered connections.

        Returns:
            Number of connections currently being tracked.
        """
        with self._lock:
            return len(self._sequences)

    def get_stats(self) -> dict[str, Any]:
        """Get sequence tracker statistics.

        Returns:
            Dictionary with tracker statistics.
        """
        with self._lock:
            total_connections = len(self._sequences)
            total_sequences = sum(self._sequences.values())
            max_sequence = max(self._sequences.values()) if self._sequences else 0

            return {
                "total_connections": total_connections,
                "total_messages_sent": total_sequences,
                "max_sequence": max_sequence,
            }


# =============================================================================
# Global Singleton Instance
# =============================================================================

_sequence_tracker: SequenceTracker | None = None
_tracker_lock = threading.Lock()


def get_sequence_tracker() -> SequenceTracker:
    """Get or create the global sequence tracker instance.

    This function provides a thread-safe singleton pattern for the
    SequenceTracker.

    Returns:
        SequenceTracker instance.

    Example:
        tracker = get_sequence_tracker()
        seq = tracker.next_sequence("conn-123")
    """
    global _sequence_tracker  # noqa: PLW0603

    # Fast path: tracker already exists
    if _sequence_tracker is not None:
        return _sequence_tracker

    # Slow path: need to initialize with lock
    with _tracker_lock:
        # Double-check after acquiring lock
        if _sequence_tracker is None:
            _sequence_tracker = SequenceTracker()
            logger.info("Global sequence tracker initialized")

    return _sequence_tracker


def reset_sequence_tracker_state() -> None:
    """Reset the global sequence tracker state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _sequence_tracker  # noqa: PLW0603
    _sequence_tracker = None
