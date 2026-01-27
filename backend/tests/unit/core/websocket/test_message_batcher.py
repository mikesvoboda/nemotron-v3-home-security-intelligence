"""Unit tests for WebSocket message batching (NEM-3738).

Tests the MessageBatcher class which provides intelligent batching
for high-frequency WebSocket events to reduce overhead and rendering churn.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from backend.core.websocket.message_batcher import (
    BatchedMessage,
    BatchMetrics,
    MessageBatcher,
    reset_message_batcher_state,
)


@pytest.fixture
def batcher() -> MessageBatcher:
    """Create a fresh MessageBatcher for each test."""
    return MessageBatcher(
        batch_interval_ms=100,
        max_batch_size=5,
        batch_channels=["detections", "alerts"],
    )


@pytest.fixture
def send_callback() -> AsyncMock:
    """Create a mock send callback."""
    return AsyncMock()


class TestBatchedMessage:
    """Tests for the BatchedMessage dataclass."""

    def test_batched_message_defaults(self):
        """Test BatchedMessage has correct default values."""
        msg = BatchedMessage()
        assert msg.type == "batch"
        assert msg.channel == ""
        assert msg.count == 0
        assert msg.messages == []
        assert isinstance(msg.batched_at, float)

    def test_batched_message_to_dict(self):
        """Test BatchedMessage serializes to dictionary correctly."""
        msg = BatchedMessage(
            channel="detections",
            count=3,
            messages=[{"id": 1}, {"id": 2}, {"id": 3}],
            batched_at=1234567890.0,
        )
        result = msg.to_dict()
        assert result == {
            "type": "batch",
            "channel": "detections",
            "count": 3,
            "messages": [{"id": 1}, {"id": 2}, {"id": 3}],
            "batched_at": 1234567890.0,
        }


class TestBatchMetrics:
    """Tests for the BatchMetrics dataclass."""

    def test_batch_metrics_defaults(self):
        """Test BatchMetrics has correct default values."""
        metrics = BatchMetrics()
        assert metrics.total_messages_queued == 0
        assert metrics.total_batches_flushed == 0
        assert metrics.total_messages_flushed == 0
        assert metrics.total_immediate_sends == 0
        assert metrics.max_batch_size_reached == 0
        assert metrics.interval_flushes == 0

    def test_batch_metrics_to_dict(self):
        """Test BatchMetrics serializes to dictionary correctly."""
        metrics = BatchMetrics(
            total_messages_queued=100,
            total_batches_flushed=20,
            total_messages_flushed=100,
            total_immediate_sends=50,
            max_batch_size_reached=5,
            interval_flushes=15,
        )
        result = metrics.to_dict()
        assert result["total_messages_queued"] == 100
        assert result["total_batches_flushed"] == 20
        assert result["total_messages_flushed"] == 100
        assert result["total_immediate_sends"] == 50
        assert result["max_batch_size_reached"] == 5
        assert result["interval_flushes"] == 15
        assert result["batch_efficiency"] == 5.0  # 100 / 20

    def test_batch_metrics_efficiency_zero_batches(self):
        """Test batch efficiency is 0 when no batches flushed."""
        metrics = BatchMetrics()
        result = metrics.to_dict()
        assert result["batch_efficiency"] == 0.0


class TestMessageBatcherInit:
    """Tests for MessageBatcher initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        batcher = MessageBatcher()
        assert batcher.batch_interval_ms == 100
        assert batcher.max_batch_size == 50
        assert batcher.batch_channels == {"detections", "alerts"}
        assert not batcher.is_running()

    def test_custom_initialization(self):
        """Test custom initialization values."""
        batcher = MessageBatcher(
            batch_interval_ms=200,
            max_batch_size=100,
            batch_channels=["events", "system"],
        )
        assert batcher.batch_interval_ms == 200
        assert batcher.max_batch_size == 100
        assert batcher.batch_channels == {"events", "system"}


class TestMessageBatcherStartStop:
    """Tests for MessageBatcher start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_flush_task(self, batcher: MessageBatcher):
        """Test that start creates the background flush task."""
        assert not batcher.is_running()
        await batcher.start()
        assert batcher.is_running()
        await batcher.stop()
        assert not batcher.is_running()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, batcher: MessageBatcher):
        """Test that calling start multiple times is safe."""
        await batcher.start()
        await batcher.start()  # Should not raise
        assert batcher.is_running()
        await batcher.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, batcher: MessageBatcher):
        """Test that calling stop multiple times is safe."""
        await batcher.start()
        await batcher.stop()
        await batcher.stop()  # Should not raise
        assert not batcher.is_running()

    @pytest.mark.asyncio
    async def test_stop_flushes_pending_messages(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that stop flushes all pending messages."""
        await batcher.start()

        # Queue some messages
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("detections", {"id": 2}, send_callback)

        # Verify messages are pending
        assert batcher.get_pending_count("detections") == 2

        # Stop should flush
        await batcher.stop()

        # Callback should have been called with batched message
        send_callback.assert_called_once()
        call_args = send_callback.call_args[0][0]
        assert call_args["type"] == "batch"
        assert call_args["channel"] == "detections"
        assert call_args["count"] == 2


class TestMessageBatcherQueueMessage:
    """Tests for queuing messages."""

    @pytest.mark.asyncio
    async def test_queue_message_batched_channel(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that messages on batch channels are queued."""
        result = await batcher.queue_message("detections", {"id": 1}, send_callback)
        assert result is True  # Message was queued
        assert batcher.get_pending_count("detections") == 1
        send_callback.assert_not_called()  # Not sent yet

    @pytest.mark.asyncio
    async def test_queue_message_non_batched_channel(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that messages on non-batch channels are sent immediately."""
        result = await batcher.queue_message("events", {"id": 1}, send_callback)
        assert result is False  # Message was not queued
        assert batcher.get_pending_count("events") == 0
        send_callback.assert_called_once_with({"id": 1})

    @pytest.mark.asyncio
    async def test_queue_message_triggers_max_size_flush(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that reaching max_batch_size triggers immediate flush."""
        # Queue 5 messages (max_batch_size)
        for i in range(5):
            await batcher.queue_message("detections", {"id": i}, send_callback)

        # Batch should have been flushed
        send_callback.assert_called_once()
        call_args = send_callback.call_args[0][0]
        assert call_args["type"] == "batch"
        assert call_args["count"] == 5
        assert len(call_args["messages"]) == 5

        # Pending should be empty
        assert batcher.get_pending_count("detections") == 0

    @pytest.mark.asyncio
    async def test_queue_message_updates_metrics(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that queuing messages updates metrics."""
        # Queue to batched channel
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        assert batcher.metrics.total_messages_queued == 1

        # Send to non-batched channel
        await batcher.queue_message("events", {"id": 2}, send_callback)
        assert batcher.metrics.total_immediate_sends == 1


class TestMessageBatcherFlush:
    """Tests for flush operations."""

    @pytest.mark.asyncio
    async def test_flush_channel_sends_batch(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test flushing a specific channel sends batched messages."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("detections", {"id": 2}, send_callback)

        count = await batcher.flush_channel("detections")
        assert count == 2

        send_callback.assert_called_once()
        call_args = send_callback.call_args[0][0]
        assert call_args["type"] == "batch"
        assert call_args["channel"] == "detections"
        assert call_args["count"] == 2

    @pytest.mark.asyncio
    async def test_flush_channel_empty(self, batcher: MessageBatcher, send_callback: AsyncMock):
        """Test flushing an empty channel returns 0."""
        count = await batcher.flush_channel("detections")
        assert count == 0
        send_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_all_multiple_channels(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test flushing all channels at once."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("alerts", {"id": 2}, send_callback)

        total = await batcher.flush_all()
        assert total == 2

        assert send_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_flush_updates_metrics(self, batcher: MessageBatcher, send_callback: AsyncMock):
        """Test that flushing updates metrics correctly."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("detections", {"id": 2}, send_callback)
        await batcher.queue_message("detections", {"id": 3}, send_callback)

        await batcher.flush_channel("detections")

        assert batcher.metrics.total_batches_flushed == 1
        assert batcher.metrics.total_messages_flushed == 3


class TestMessageBatcherIntervalFlush:
    """Tests for interval-based automatic flushing."""

    @pytest.mark.asyncio
    async def test_interval_flush_sends_pending_messages(self, send_callback: AsyncMock):
        """Test that the background task flushes messages on interval."""
        # Use a short interval for testing
        batcher = MessageBatcher(
            batch_interval_ms=50,  # 50ms interval
            max_batch_size=100,  # High max to avoid immediate flush
            batch_channels=["detections"],
        )

        await batcher.start()
        try:
            # Queue a message
            await batcher.queue_message("detections", {"id": 1}, send_callback)
            assert batcher.get_pending_count("detections") == 1

            # Wait for interval flush (50ms + buffer)
            await asyncio.sleep(0.1)

            # Message should have been flushed
            send_callback.assert_called_once()
            assert batcher.get_pending_count("detections") == 0
        finally:
            await batcher.stop()

    @pytest.mark.asyncio
    async def test_interval_flush_updates_metrics(self, send_callback: AsyncMock):
        """Test that interval flushes update metrics."""
        batcher = MessageBatcher(
            batch_interval_ms=30,
            max_batch_size=100,
            batch_channels=["detections"],
        )

        await batcher.start()
        try:
            await batcher.queue_message("detections", {"id": 1}, send_callback)
            await asyncio.sleep(0.08)  # Wait for flush

            assert batcher.metrics.interval_flushes >= 1
        finally:
            await batcher.stop()


class TestMessageBatcherPendingCount:
    """Tests for pending message counting."""

    @pytest.mark.asyncio
    async def test_get_pending_count_specific_channel(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test getting pending count for specific channel."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("detections", {"id": 2}, send_callback)
        await batcher.queue_message("alerts", {"id": 3}, send_callback)

        assert batcher.get_pending_count("detections") == 2
        assert batcher.get_pending_count("alerts") == 1
        assert batcher.get_pending_count("events") == 0

    @pytest.mark.asyncio
    async def test_get_pending_count_all_channels(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test getting total pending count across all channels."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("detections", {"id": 2}, send_callback)
        await batcher.queue_message("alerts", {"id": 3}, send_callback)

        assert batcher.get_pending_count() == 3


class TestMessageBatcherMetrics:
    """Tests for metrics tracking."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, batcher: MessageBatcher, send_callback: AsyncMock):
        """Test get_metrics returns dictionary."""
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await batcher.queue_message("events", {"id": 2}, send_callback)
        await batcher.flush_channel("detections")

        metrics = batcher.get_metrics()
        assert isinstance(metrics, dict)
        assert metrics["total_messages_queued"] == 1
        assert metrics["total_immediate_sends"] == 1
        assert metrics["total_batches_flushed"] == 1
        assert metrics["total_messages_flushed"] == 1

    @pytest.mark.asyncio
    async def test_max_batch_size_reached_metric(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that max_batch_size_reached is tracked."""
        # Queue exactly max_batch_size messages
        for i in range(5):
            await batcher.queue_message("detections", {"id": i}, send_callback)

        assert batcher.metrics.max_batch_size_reached == 1


class TestMessageBatcherErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_send_callback_error_does_not_crash(self, batcher: MessageBatcher):
        """Test that callback errors don't crash the batcher."""
        error_callback = AsyncMock(side_effect=Exception("Send failed"))

        await batcher.queue_message("detections", {"id": 1}, error_callback)
        await batcher.queue_message("detections", {"id": 2}, error_callback)

        # Should not raise
        await batcher.flush_channel("detections")

        # Messages should be cleared (not re-queued)
        assert batcher.get_pending_count("detections") == 0

    @pytest.mark.asyncio
    async def test_missing_callback_logs_warning(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that missing callback is handled gracefully."""
        # Manually add messages without callback
        batcher._pending["detections"].append({"id": 1})

        # Should not raise
        count = await batcher.flush_channel("detections")
        assert count == 0  # No messages sent


class TestMessageBatcherConcurrency:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_queue_messages(
        self, batcher: MessageBatcher, send_callback: AsyncMock
    ):
        """Test that concurrent queue operations are safe."""
        # Create many concurrent queue operations
        tasks = [batcher.queue_message("detections", {"id": i}, send_callback) for i in range(20)]

        await asyncio.gather(*tasks)

        # All messages should be accounted for
        # Some may have been flushed due to max_batch_size
        total = batcher.get_pending_count() + batcher.metrics.total_messages_flushed
        assert total == 20


class TestModuleLevelFunctions:
    """Tests for module-level singleton functions."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset module state before each test."""
        reset_message_batcher_state()
        yield
        reset_message_batcher_state()

    @pytest.mark.asyncio
    async def test_get_message_batcher_creates_singleton(self):
        """Test that get_message_batcher creates a singleton."""
        from backend.core.websocket.message_batcher import get_message_batcher

        batcher1 = await get_message_batcher()
        batcher2 = await get_message_batcher()
        assert batcher1 is batcher2

    @pytest.mark.asyncio
    async def test_stop_message_batcher(self):
        """Test that stop_message_batcher stops the singleton."""
        from backend.core.websocket.message_batcher import (
            get_message_batcher,
            stop_message_batcher,
        )

        batcher = await get_message_batcher()
        await batcher.start()
        assert batcher.is_running()

        await stop_message_batcher()

        # Getting a new batcher should create a new instance
        new_batcher = await get_message_batcher()
        assert new_batcher is not batcher
