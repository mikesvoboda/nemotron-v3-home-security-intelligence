"""WebSocket message batching for high-frequency events (NEM-3738).

This module provides intelligent message batching to reduce WebSocket overhead
and frontend rendering churn when handling high-frequency detection events.

The MessageBatcher collects messages by channel over a configurable interval
and flushes them as batched messages. This reduces:
- Network overhead from individual message framing
- JSON serialization overhead per message
- Frontend React re-renders per message

Usage:
    from backend.core.websocket.message_batcher import MessageBatcher

    # Create batcher with custom settings
    batcher = MessageBatcher(
        batch_interval_ms=100,
        max_batch_size=50,
        batch_channels=["detections", "alerts"],
    )

    # Start the batcher (creates background flush task)
    await batcher.start()

    # Queue messages (high-frequency channels get batched)
    await batcher.queue_message("detections", detection_data, send_callback)

    # Stop the batcher (flushes remaining messages)
    await batcher.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BatchedMessage:
    """Represents a batched WebSocket message.

    Attributes:
        type: Message type, always "batch" for batched messages
        channel: The channel these messages belong to
        count: Number of messages in the batch
        messages: List of individual message payloads
        batched_at: Unix timestamp when batch was created
    """

    type: str = "batch"
    channel: str = ""
    count: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    batched_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "channel": self.channel,
            "count": self.count,
            "messages": self.messages,
            "batched_at": self.batched_at,
        }


@dataclass
class BatchMetrics:
    """Metrics for message batching performance.

    Attributes:
        total_messages_queued: Total messages added to batches
        total_batches_flushed: Total batches sent to clients
        total_messages_flushed: Total individual messages sent via batches
        total_immediate_sends: Messages sent immediately (non-batched channels)
        max_batch_size_reached: Number of times max batch size triggered flush
        interval_flushes: Number of times interval timer triggered flush
    """

    total_messages_queued: int = 0
    total_batches_flushed: int = 0
    total_messages_flushed: int = 0
    total_immediate_sends: int = 0
    max_batch_size_reached: int = 0
    interval_flushes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_messages_queued": self.total_messages_queued,
            "total_batches_flushed": self.total_batches_flushed,
            "total_messages_flushed": self.total_messages_flushed,
            "total_immediate_sends": self.total_immediate_sends,
            "max_batch_size_reached": self.max_batch_size_reached,
            "interval_flushes": self.interval_flushes,
            "batch_efficiency": (
                self.total_messages_flushed / self.total_batches_flushed
                if self.total_batches_flushed > 0
                else 0.0
            ),
        }


# Type alias for the send callback function
SendCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class MessageBatcher:
    """Intelligent message batcher for high-frequency WebSocket events.

    Collects messages by channel and flushes them as batched payloads
    either when the batch interval expires or max batch size is reached.

    Thread-safe and designed for async usage with asyncio.

    Attributes:
        batch_interval_ms: Milliseconds between automatic batch flushes
        max_batch_size: Maximum messages per batch before immediate flush
        batch_channels: Set of channel names to batch (others sent immediately)
    """

    def __init__(
        self,
        batch_interval_ms: int = 100,
        max_batch_size: int = 50,
        batch_channels: list[str] | None = None,
    ):
        """Initialize the message batcher.

        Args:
            batch_interval_ms: Interval in milliseconds for automatic batch flushes.
                Default: 100ms provides good balance between latency and batching.
            max_batch_size: Maximum messages per channel before immediate flush.
                Default: 50 prevents memory buildup during detection bursts.
            batch_channels: List of channels to batch. Messages on other channels
                are sent immediately. Default: ["detections", "alerts"]
        """
        self.batch_interval_ms = batch_interval_ms
        self.max_batch_size = max_batch_size
        self.batch_channels: set[str] = set(
            batch_channels if batch_channels is not None else ["detections", "alerts"]
        )

        # Pending messages per channel: channel -> list of messages
        self._pending: dict[str, list[dict[str, Any]]] = defaultdict(list)

        # Send callbacks per channel (stored when first message queued)
        self._send_callbacks: dict[str, SendCallback] = {}

        # Lock for thread-safe access to pending messages
        self._lock = asyncio.Lock()

        # Background flush task
        self._flush_task: asyncio.Task[None] | None = None
        self._running = False

        # Metrics tracking
        self._metrics = BatchMetrics()

    @property
    def metrics(self) -> BatchMetrics:
        """Get current batch metrics."""
        return self._metrics

    def get_metrics(self) -> dict[str, Any]:
        """Get batch metrics as dictionary for monitoring/logging."""
        return self._metrics.to_dict()

    async def start(self) -> None:
        """Start the background batch flush task.

        Safe to call multiple times - will not create duplicate tasks.
        """
        if self._running:
            logger.debug("MessageBatcher already running")
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            f"MessageBatcher started (interval={self.batch_interval_ms}ms, "
            f"max_size={self.max_batch_size}, channels={self.batch_channels})"
        )

    async def stop(self) -> None:
        """Stop the background flush task and flush remaining messages.

        Ensures all pending messages are delivered before stopping.
        """
        if not self._running:
            logger.debug("MessageBatcher not running")
            return

        self._running = False

        # Cancel the flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Flush any remaining messages
        await self.flush_all()
        logger.info("MessageBatcher stopped")

    async def queue_message(
        self,
        channel: str,
        message: dict[str, Any],
        send_callback: SendCallback,
    ) -> bool:
        """Queue a message for batching or send immediately.

        Messages on channels in batch_channels are queued for batching.
        Messages on other channels are sent immediately via the callback.

        Args:
            channel: The WebSocket channel (e.g., "detections", "alerts", "events")
            message: The message payload to send
            send_callback: Async callback to send the message/batch

        Returns:
            True if message was queued for batching, False if sent immediately
        """
        # Check if this channel should be batched
        if channel not in self.batch_channels:
            # Send immediately for non-batched channels
            self._metrics.total_immediate_sends += 1
            await send_callback(message)
            return False

        async with self._lock:
            # Store the callback (use first callback received for channel)
            if channel not in self._send_callbacks:
                self._send_callbacks[channel] = send_callback

            # Add message to pending queue
            self._pending[channel].append(message)
            self._metrics.total_messages_queued += 1

            # Check if we need to flush due to max batch size
            if len(self._pending[channel]) >= self.max_batch_size:
                self._metrics.max_batch_size_reached += 1
                await self._flush_channel_locked(channel)

        return True

    async def flush_channel(self, channel: str) -> int:
        """Flush pending messages for a specific channel.

        Args:
            channel: The channel to flush

        Returns:
            Number of messages flushed
        """
        async with self._lock:
            return await self._flush_channel_locked(channel)

    async def _flush_channel_locked(self, channel: str) -> int:
        """Internal flush implementation (must be called with lock held).

        Args:
            channel: The channel to flush

        Returns:
            Number of messages flushed
        """
        messages = self._pending.get(channel, [])
        if not messages:
            return 0

        # Get the send callback
        callback = self._send_callbacks.get(channel)
        if not callback:
            logger.warning(
                f"No send callback for channel {channel}, dropping {len(messages)} messages"
            )
            self._pending[channel] = []
            return 0

        # Create batched message
        batch = BatchedMessage(
            type="batch",
            channel=channel,
            count=len(messages),
            messages=messages.copy(),
            batched_at=time.time(),
        )

        # Clear pending messages before sending (avoid re-sending on retry)
        self._pending[channel] = []

        # Send the batch
        try:
            await callback(batch.to_dict())
            self._metrics.total_batches_flushed += 1
            self._metrics.total_messages_flushed += batch.count
            logger.debug(f"Flushed batch for channel={channel}, count={batch.count}")
        except Exception as e:
            logger.error(f"Failed to send batch for channel={channel}: {e}")
            # Don't re-queue on failure to avoid infinite loops
            # The messages are lost but this prevents memory buildup

        return batch.count

    async def flush_all(self) -> int:
        """Flush pending messages for all channels.

        Returns:
            Total number of messages flushed across all channels
        """
        total_flushed = 0
        async with self._lock:
            channels = list(self._pending.keys())
            for channel in channels:
                flushed = await self._flush_channel_locked(channel)
                total_flushed += flushed
        return total_flushed

    async def _flush_loop(self) -> None:
        """Background task that periodically flushes pending messages."""
        interval_seconds = self.batch_interval_ms / 1000.0

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)

                # Flush all pending batches
                async with self._lock:
                    channels_to_flush = [ch for ch, msgs in self._pending.items() if msgs]

                for channel in channels_to_flush:
                    async with self._lock:
                        if self._pending.get(channel):
                            self._metrics.interval_flushes += 1
                            await self._flush_channel_locked(channel)

            except asyncio.CancelledError:
                # Normal shutdown - exit the loop
                break
            except Exception as e:
                logger.error(f"Error in batch flush loop: {e}")
                # Continue running despite errors
                await asyncio.sleep(interval_seconds)

    def get_pending_count(self, channel: str | None = None) -> int:
        """Get the count of pending messages.

        Args:
            channel: Specific channel to check, or None for all channels

        Returns:
            Number of pending messages
        """
        if channel:
            return len(self._pending.get(channel, []))
        return sum(len(msgs) for msgs in self._pending.values())

    def is_running(self) -> bool:
        """Check if the batcher is currently running."""
        return self._running


# Module-level singleton instance
_batcher: MessageBatcher | None = None
_batcher_lock: asyncio.Lock | None = None


def _get_batcher_lock() -> asyncio.Lock:
    """Get or create the batcher initialization lock.

    Returns:
        asyncio.Lock for thread-safe batcher initialization
    """
    global _batcher_lock  # noqa: PLW0603
    if _batcher_lock is None:
        _batcher_lock = asyncio.Lock()
    return _batcher_lock


async def get_message_batcher(
    batch_interval_ms: int | None = None,
    max_batch_size: int | None = None,
    batch_channels: list[str] | None = None,
) -> MessageBatcher:
    """Get or create the global MessageBatcher instance.

    Creates a singleton MessageBatcher with the provided settings on first call.
    Subsequent calls return the same instance (settings are ignored).

    Args:
        batch_interval_ms: Batch interval in milliseconds (default from settings)
        max_batch_size: Maximum batch size (default from settings)
        batch_channels: Channels to batch (default from settings)

    Returns:
        The global MessageBatcher instance
    """
    global _batcher  # noqa: PLW0603

    if _batcher is not None:
        return _batcher

    lock = _get_batcher_lock()
    async with lock:
        if _batcher is None:
            # Import here to avoid circular imports
            from backend.core.config import get_settings

            settings = get_settings()

            # Use provided values or fall back to settings
            interval = batch_interval_ms or settings.websocket_batch_interval_ms
            max_size = max_batch_size or settings.websocket_batch_max_size
            channels = batch_channels or settings.websocket_batch_channels

            _batcher = MessageBatcher(
                batch_interval_ms=interval,
                max_batch_size=max_size,
                batch_channels=channels,
            )

    return _batcher


async def stop_message_batcher() -> None:
    """Stop the global MessageBatcher if running."""
    global _batcher  # noqa: PLW0603

    lock = _get_batcher_lock()
    async with lock:
        if _batcher:
            await _batcher.stop()
            _batcher = None


def reset_message_batcher_state() -> None:
    """Reset global batcher state for testing.

    WARNING: Only use in tests. Clears the singleton without proper cleanup.
    """
    global _batcher, _batcher_lock  # noqa: PLW0603
    _batcher = None
    _batcher_lock = None
