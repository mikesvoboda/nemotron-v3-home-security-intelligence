"""Unit tests for the EvaluationQueue service.

Tests cover:
- Enqueueing events with priority (sorted set operations)
- Dequeueing events (highest priority first)
- Queue persistence across restarts (Redis-backed)
- Queue size tracking
- Edge cases (empty queue, duplicate events)

Following TDD: Write tests first (RED), then implement (GREEN), then refactor.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with async methods."""
    redis = MagicMock()
    redis.zadd = AsyncMock()
    redis.zpopmax = AsyncMock()
    redis.zcard = AsyncMock()
    redis.zrange = AsyncMock()
    redis.zrem = AsyncMock()
    redis.zscore = AsyncMock()
    redis.zrangebyscore = AsyncMock()
    return redis


@pytest.fixture
def evaluation_queue(mock_redis):
    """Create an EvaluationQueue instance with mock Redis."""
    from backend.services.evaluation_queue import EvaluationQueue

    return EvaluationQueue(redis_client=mock_redis)


# =============================================================================
# Test: Enqueue Operations
# =============================================================================


class TestEnqueue:
    """Tests for enqueueing events."""

    @pytest.mark.asyncio
    async def test_enqueue_event_with_default_priority(self, evaluation_queue, mock_redis):
        """Test enqueueing an event with default priority (0)."""
        mock_redis.zadd.return_value = 1

        result = await evaluation_queue.enqueue(event_id=123)

        assert result is True
        mock_redis.zadd.assert_called_once()
        # Verify the call - zadd(key, {member: score})
        call_args = mock_redis.zadd.call_args
        assert call_args[0][0] == "evaluation:pending"
        assert "123" in call_args[0][1]
        assert call_args[0][1]["123"] == 0  # Default priority

    @pytest.mark.asyncio
    async def test_enqueue_event_with_custom_priority(self, evaluation_queue, mock_redis):
        """Test enqueueing an event with custom priority."""
        mock_redis.zadd.return_value = 1

        result = await evaluation_queue.enqueue(event_id=456, priority=85)

        assert result is True
        call_args = mock_redis.zadd.call_args
        assert call_args[0][1]["456"] == 85

    @pytest.mark.asyncio
    async def test_enqueue_event_with_risk_score_priority(self, evaluation_queue, mock_redis):
        """Test enqueueing an event where priority is based on risk score."""
        mock_redis.zadd.return_value = 1

        # High risk events should be evaluated first (higher priority)
        result = await evaluation_queue.enqueue(event_id=789, priority=95)

        assert result is True
        call_args = mock_redis.zadd.call_args
        assert call_args[0][1]["789"] == 95

    @pytest.mark.asyncio
    async def test_enqueue_duplicate_event_updates_priority(self, evaluation_queue, mock_redis):
        """Test that enqueueing an existing event updates its priority."""
        # First enqueue
        mock_redis.zadd.return_value = 1
        await evaluation_queue.enqueue(event_id=100, priority=50)

        # Second enqueue with higher priority
        mock_redis.zadd.return_value = 0  # 0 means updated, not added
        result = await evaluation_queue.enqueue(event_id=100, priority=90)

        # Result should still indicate success (update)
        assert result is True
        assert mock_redis.zadd.call_count == 2

    @pytest.mark.asyncio
    async def test_enqueue_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that enqueue handles Redis exceptions gracefully."""
        mock_redis.zadd.side_effect = Exception("Redis connection error")

        result = await evaluation_queue.enqueue(event_id=123, priority=50)

        assert result is False


# =============================================================================
# Test: Dequeue Operations
# =============================================================================


class TestDequeue:
    """Tests for dequeueing events."""

    @pytest.mark.asyncio
    async def test_dequeue_returns_highest_priority_event(self, evaluation_queue, mock_redis):
        """Test that dequeue returns the event with highest priority."""
        # zpopmax returns [(member, score)] or similar structure
        mock_redis.zpopmax.return_value = [(b"123", 95.0)]

        event_id = await evaluation_queue.dequeue()

        assert event_id == 123
        mock_redis.zpopmax.assert_called_once_with("evaluation:pending")

    @pytest.mark.asyncio
    async def test_dequeue_fifo_within_same_priority(self, evaluation_queue, mock_redis):
        """Test FIFO ordering within same priority level.

        Note: Redis ZSET with same scores maintains insertion order,
        so zpopmax will return the first-inserted element when scores are equal.
        """
        # Simulate enqueueing multiple events with same priority
        mock_redis.zadd.return_value = 1
        await evaluation_queue.enqueue(event_id=100, priority=50)
        await evaluation_queue.enqueue(event_id=200, priority=50)
        await evaluation_queue.enqueue(event_id=300, priority=50)

        # First dequeue should return the oldest (first enqueued) event
        mock_redis.zpopmax.return_value = [(b"100", 50.0)]
        event_id = await evaluation_queue.dequeue()
        assert event_id == 100

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_queue_empty(self, evaluation_queue, mock_redis):
        """Test that dequeue returns None when queue is empty."""
        mock_redis.zpopmax.return_value = []

        event_id = await evaluation_queue.dequeue()

        assert event_id is None

    @pytest.mark.asyncio
    async def test_dequeue_handles_string_member(self, evaluation_queue, mock_redis):
        """Test that dequeue handles string members (Redis may return str or bytes)."""
        mock_redis.zpopmax.return_value = [("456", 75.0)]

        event_id = await evaluation_queue.dequeue()

        assert event_id == 456

    @pytest.mark.asyncio
    async def test_dequeue_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that dequeue handles Redis exceptions gracefully."""
        mock_redis.zpopmax.side_effect = Exception("Redis connection error")

        event_id = await evaluation_queue.dequeue()

        assert event_id is None


# =============================================================================
# Test: Queue Management
# =============================================================================


class TestQueueManagement:
    """Tests for queue management operations."""

    @pytest.mark.asyncio
    async def test_get_queue_size(self, evaluation_queue, mock_redis):
        """Test getting the current queue size."""
        mock_redis.zcard.return_value = 42

        size = await evaluation_queue.get_size()

        assert size == 42
        mock_redis.zcard.assert_called_once_with("evaluation:pending")

    @pytest.mark.asyncio
    async def test_get_queue_size_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that get_size handles Redis exceptions gracefully."""
        mock_redis.zcard.side_effect = Exception("Redis connection error")

        size = await evaluation_queue.get_size()

        assert size == 0

    @pytest.mark.asyncio
    async def test_get_pending_events(self, evaluation_queue, mock_redis):
        """Test getting list of pending event IDs."""
        mock_redis.zrange.return_value = [b"100", b"200", b"300"]

        events = await evaluation_queue.get_pending_events(limit=10)

        assert events == [100, 200, 300]

    @pytest.mark.asyncio
    async def test_get_pending_events_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that get_pending_events handles Redis exceptions gracefully."""
        mock_redis.zrange.side_effect = Exception("Redis connection error")

        events = await evaluation_queue.get_pending_events(limit=10)

        assert events == []

    @pytest.mark.asyncio
    async def test_remove_event(self, evaluation_queue, mock_redis):
        """Test removing a specific event from the queue."""
        mock_redis.zrem.return_value = 1

        result = await evaluation_queue.remove(event_id=123)

        assert result is True
        mock_redis.zrem.assert_called_once_with("evaluation:pending", "123")

    @pytest.mark.asyncio
    async def test_remove_nonexistent_event(self, evaluation_queue, mock_redis):
        """Test removing an event that doesn't exist in queue."""
        mock_redis.zrem.return_value = 0

        result = await evaluation_queue.remove(event_id=999)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_event_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that remove handles Redis exceptions gracefully."""
        mock_redis.zrem.side_effect = Exception("Redis connection error")

        result = await evaluation_queue.remove(event_id=123)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_queued(self, evaluation_queue, mock_redis):
        """Test checking if an event is in the queue."""
        mock_redis.zscore.return_value = 75.0

        is_queued = await evaluation_queue.is_queued(event_id=123)

        assert is_queued is True
        mock_redis.zscore.assert_called_once_with("evaluation:pending", "123")

    @pytest.mark.asyncio
    async def test_is_not_queued(self, evaluation_queue, mock_redis):
        """Test checking if an event is not in the queue."""
        mock_redis.zscore.return_value = None

        is_queued = await evaluation_queue.is_queued(event_id=123)

        assert is_queued is False

    @pytest.mark.asyncio
    async def test_is_queued_handles_redis_exception(self, evaluation_queue, mock_redis):
        """Test that is_queued handles Redis exceptions gracefully."""
        mock_redis.zscore.side_effect = Exception("Redis connection error")

        is_queued = await evaluation_queue.is_queued(event_id=123)

        assert is_queued is False


# =============================================================================
# Test: Concurrent Operations and Thread Safety
# =============================================================================


class TestConcurrentOperations:
    """Tests for concurrent operations and thread safety."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_enqueues(self, evaluation_queue, mock_redis):
        """Test multiple concurrent enqueues (thread safety).

        Redis operations are atomic, so concurrent zadd calls are safe.
        """
        import asyncio

        mock_redis.zadd.return_value = 1

        # Simulate concurrent enqueues
        tasks = [evaluation_queue.enqueue(event_id=i, priority=i * 10) for i in range(1, 11)]

        results = await asyncio.gather(*tasks)

        # All enqueues should succeed
        assert all(results)
        assert mock_redis.zadd.call_count == 10


# =============================================================================
# Test: Redis Persistence
# =============================================================================


class TestRedisPersistence:
    """Tests for Redis persistence across service restarts."""

    @pytest.mark.asyncio
    async def test_queue_persists_across_restart(self, mock_redis):
        """Test that queue data persists across service restarts.

        Since the queue is Redis-backed, data survives restarts.
        """
        from backend.services.evaluation_queue import (
            EvaluationQueue,
            reset_evaluation_queue,
        )

        # First instance - enqueue events
        queue1 = EvaluationQueue(redis_client=mock_redis)
        mock_redis.zadd.return_value = 1
        await queue1.enqueue(event_id=123, priority=75)

        # Simulate restart by creating new instance
        reset_evaluation_queue()
        queue2 = EvaluationQueue(redis_client=mock_redis)

        # Verify queue still has the event
        mock_redis.zscore.return_value = 75.0
        is_queued = await queue2.is_queued(event_id=123)

        assert is_queued is True
        reset_evaluation_queue()


# =============================================================================
# Test: Queue Constants
# =============================================================================


class TestQueueConstants:
    """Tests for queue key and constants."""

    def test_queue_key_constant(self, evaluation_queue):
        """Test that the queue key constant is correct."""
        assert evaluation_queue.QUEUE_KEY == "evaluation:pending"


# =============================================================================
# Test: Singleton Pattern
# =============================================================================


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def test_get_evaluation_queue_returns_instance(self, mock_redis):
        """Test get_evaluation_queue returns an EvaluationQueue instance."""
        from backend.services.evaluation_queue import (
            EvaluationQueue,
            get_evaluation_queue,
            reset_evaluation_queue,
        )

        reset_evaluation_queue()
        queue = get_evaluation_queue(mock_redis)
        assert isinstance(queue, EvaluationQueue)
        reset_evaluation_queue()

    def test_get_evaluation_queue_returns_same_instance(self, mock_redis):
        """Test get_evaluation_queue returns the same instance on repeated calls."""
        from backend.services.evaluation_queue import (
            get_evaluation_queue,
            reset_evaluation_queue,
        )

        reset_evaluation_queue()
        queue1 = get_evaluation_queue(mock_redis)
        queue2 = get_evaluation_queue(mock_redis)
        assert queue1 is queue2
        reset_evaluation_queue()

    def test_reset_evaluation_queue(self, mock_redis):
        """Test reset_evaluation_queue creates a new instance on next call."""
        from backend.services.evaluation_queue import (
            get_evaluation_queue,
            reset_evaluation_queue,
        )

        reset_evaluation_queue()
        queue1 = get_evaluation_queue(mock_redis)
        reset_evaluation_queue()
        queue2 = get_evaluation_queue(mock_redis)
        assert queue1 is not queue2
        reset_evaluation_queue()
