"""WebSocket message buffer for replay functionality.

NEM-4983: Implement WebSocket message replay for gap recovery.

This module provides a ring buffer for storing WebSocket messages with their
sequence numbers, enabling message replay when clients detect gaps in the
message stream.

Features:
- Ring buffer with configurable max size (default: 1000)
- Thread-safe operations
- Message retrieval since a given sequence number
- Replay flag support for marking replayed messages

Example Usage:
    from backend.core.websocket.message_buffer import get_message_buffer

    # Get the global message buffer
    buffer = get_message_buffer()

    # Add a message during broadcast
    buffer.add(seq=5, message={"type": "event", "data": {...}})

    # Get messages for replay (e.g., client missed seq 3, 4)
    messages = buffer.get_since(last_seq=2, mark_as_replay=True)
    # Returns: [(3, {..., "replay": True}), (4, {..., "replay": True}), ...]
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


class MessageBuffer:
    """Ring buffer for WebSocket messages with sequence numbers.

    Stores messages with their sequence numbers in a deque with a max size.
    When the buffer is full, oldest messages are automatically evicted.

    Thread Safety:
        Uses threading.RLock for thread-safe operations.
        Safe to use from multiple async tasks.

    Attributes:
        max_size: Maximum number of messages to store.
    """

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the message buffer.

        Args:
            max_size: Maximum number of messages to store. Defaults to 1000.
        """
        self._max_size = max_size
        self._buffer: deque[tuple[int, dict[str, Any]]] = deque(maxlen=max_size)
        self._lock = threading.RLock()
        logger.debug(f"Message buffer initialized with max_size={max_size}")

    @property
    def max_size(self) -> int:
        """Get the maximum buffer size."""
        return self._max_size

    def add(self, seq: int, message: dict[str, Any]) -> None:
        """Add a message to the buffer.

        Args:
            seq: The sequence number for this message.
            message: The message dictionary to store.

        Note:
            Messages are stored as copies to prevent mutation issues.
            When the buffer is full, the oldest message is automatically evicted.
        """
        with self._lock:
            # Store a shallow copy to prevent mutation
            self._buffer.append((seq, message.copy()))

    def get_since(
        self, last_seq: int, mark_as_replay: bool = False
    ) -> list[tuple[int, dict[str, Any]]]:
        """Get all messages with sequence number > last_seq.

        Args:
            last_seq: The last sequence number the client received.
            mark_as_replay: If True, add replay=True to returned messages.

        Returns:
            List of (sequence, message) tuples for messages after last_seq.
            Messages are returned in sequence order.
        """
        with self._lock:
            result: list[tuple[int, dict[str, Any]]] = []

            for seq, msg in self._buffer:
                if seq > last_seq:
                    if mark_as_replay:
                        # Create a copy with replay flag
                        msg_copy = msg.copy()
                        msg_copy["replay"] = True
                        result.append((seq, msg_copy))
                    else:
                        result.append((seq, msg.copy()))

            return result

    def size(self) -> int:
        """Get the current number of messages in the buffer.

        Returns:
            Number of messages currently stored.
        """
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        """Remove all messages from the buffer."""
        with self._lock:
            self._buffer.clear()
            logger.debug("Message buffer cleared")

    def get_oldest_sequence(self) -> int | None:
        """Get the oldest sequence number in the buffer.

        Returns:
            The oldest sequence number, or None if buffer is empty.
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[0][0]

    def get_newest_sequence(self) -> int | None:
        """Get the newest sequence number in the buffer.

        Returns:
            The newest sequence number, or None if buffer is empty.
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[-1][0]


# =============================================================================
# Global Singleton Instance
# =============================================================================

_message_buffer: MessageBuffer | None = None
_buffer_lock = threading.Lock()


def get_message_buffer() -> MessageBuffer:
    """Get or create the global message buffer instance.

    This function provides a thread-safe singleton pattern for the
    MessageBuffer.

    Returns:
        MessageBuffer instance.

    Example:
        buffer = get_message_buffer()
        buffer.add(5, {"type": "event", "data": {...}})
    """
    global _message_buffer  # noqa: PLW0603

    # Fast path: buffer already exists
    if _message_buffer is not None:
        return _message_buffer

    # Slow path: need to initialize with lock
    with _buffer_lock:
        # Double-check after acquiring lock
        if _message_buffer is None:
            _message_buffer = MessageBuffer()
            logger.info("Global message buffer initialized")

    return _message_buffer


def reset_message_buffer_state() -> None:
    """Reset the global message buffer state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _message_buffer  # noqa: PLW0603
    _message_buffer = None
