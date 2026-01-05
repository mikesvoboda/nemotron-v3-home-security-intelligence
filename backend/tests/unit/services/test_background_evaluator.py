"""Unit tests for the BackgroundEvaluator service.

Tests cover:
- GPU idle detection
- Processing loop behavior
- Event evaluation workflow
- Priority handling (detection pipeline takes precedence)
- Start/stop lifecycle
- Configuration options

Following TDD: Write tests first (RED), then implement (GREEN), then refactor.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.llen = AsyncMock(return_value=0)
    redis.zadd = AsyncMock()
    redis.zpopmax = AsyncMock()
    redis.zcard = AsyncMock()
    return redis


@pytest.fixture
def mock_gpu_monitor():
    """Create a mock GPUMonitor."""
    monitor = MagicMock()
    monitor.get_current_stats = MagicMock(
        return_value={
            "gpu_utilization": 15.0,
            "memory_used": 2000,
            "memory_total": 24576,
            "temperature": 45,
            "power_usage": 30.0,
        }
    )
    monitor.get_current_stats_async = AsyncMock(
        return_value={
            "gpu_utilization": 15.0,
            "memory_used": 2000,
            "memory_total": 24576,
            "temperature": 45,
            "power_usage": 30.0,
        }
    )
    return monitor


@pytest.fixture
def mock_evaluation_queue(mock_redis):
    """Create a mock EvaluationQueue."""
    from backend.services.evaluation_queue import EvaluationQueue

    queue = MagicMock(spec=EvaluationQueue)
    queue.dequeue = AsyncMock(return_value=None)
    queue.get_size = AsyncMock(return_value=0)
    queue.remove = AsyncMock(return_value=True)
    return queue


@pytest.fixture
def mock_audit_service():
    """Create a mock AuditService."""
    service = MagicMock()
    service.run_full_evaluation = AsyncMock()
    return service


@pytest.fixture
def background_evaluator(mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service):
    """Create a BackgroundEvaluator instance with mock dependencies."""
    from backend.services.background_evaluator import BackgroundEvaluator

    evaluator = BackgroundEvaluator(
        redis_client=mock_redis,
        gpu_monitor=mock_gpu_monitor,
        evaluation_queue=mock_evaluation_queue,
        audit_service=mock_audit_service,
    )
    return evaluator


# =============================================================================
# Test: GPU Idle Detection
# =============================================================================


class TestGPUIdleDetection:
    """Tests for GPU idle detection logic."""

    @pytest.mark.asyncio
    async def test_is_gpu_idle_when_utilization_below_threshold(
        self, background_evaluator, mock_gpu_monitor
    ):
        """Test that GPU is considered idle when utilization is below threshold."""
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "gpu_utilization": 10.0,  # Below 20% threshold
        }

        is_idle = await background_evaluator.is_gpu_idle()

        assert is_idle is True

    @pytest.mark.asyncio
    async def test_is_gpu_not_idle_when_utilization_above_threshold(
        self, background_evaluator, mock_gpu_monitor
    ):
        """Test that GPU is not considered idle when utilization is above threshold."""
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "gpu_utilization": 75.0,  # Above 20% threshold
        }

        is_idle = await background_evaluator.is_gpu_idle()

        assert is_idle is False

    @pytest.mark.asyncio
    async def test_is_gpu_idle_at_threshold(self, background_evaluator, mock_gpu_monitor):
        """Test that GPU at exactly threshold is considered idle."""
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "gpu_utilization": 20.0,  # Exactly at threshold
        }

        # At threshold should be idle (<=)
        is_idle = await background_evaluator.is_gpu_idle()
        assert is_idle is True

    @pytest.mark.asyncio
    async def test_is_gpu_idle_handles_missing_utilization(
        self, background_evaluator, mock_gpu_monitor
    ):
        """Test handling of missing GPU utilization data."""
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "memory_used": 2000,
            # No gpu_utilization key
        }

        # Should return False (not idle) when data is missing
        is_idle = await background_evaluator.is_gpu_idle()
        assert is_idle is False

    @pytest.mark.asyncio
    async def test_is_gpu_idle_handles_none_utilization(
        self, background_evaluator, mock_gpu_monitor
    ):
        """Test handling of None GPU utilization."""
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "gpu_utilization": None,
        }

        # Should return False (not idle) when utilization is None
        is_idle = await background_evaluator.is_gpu_idle()
        assert is_idle is False


# =============================================================================
# Test: Detection Pipeline Priority
# =============================================================================


class TestDetectionPipelinePriority:
    """Tests for detection pipeline priority over background evaluation."""

    @pytest.mark.asyncio
    async def test_detection_queue_not_empty_blocks_evaluation(
        self, background_evaluator, mock_redis
    ):
        """Test that evaluation is blocked when detection queue is not empty."""
        # Detection queue has items
        mock_redis.llen.return_value = 5

        can_evaluate = await background_evaluator.can_process_evaluation()

        assert can_evaluate is False
        mock_redis.llen.assert_called_once_with("detection_queue")

    @pytest.mark.asyncio
    async def test_analysis_queue_not_empty_blocks_evaluation(
        self, background_evaluator, mock_redis
    ):
        """Test that evaluation is blocked when analysis queue is not empty."""
        # Detection queue empty, but analysis queue has items
        mock_redis.llen.side_effect = [0, 3]  # detection empty, analysis has 3

        can_evaluate = await background_evaluator.can_process_evaluation()

        assert can_evaluate is False
        assert mock_redis.llen.call_count == 2

    @pytest.mark.asyncio
    async def test_can_evaluate_when_both_queues_empty_and_gpu_idle(
        self, background_evaluator, mock_redis, mock_gpu_monitor
    ):
        """Test that evaluation can proceed when both queues are empty and GPU is idle."""
        mock_redis.llen.return_value = 0  # Both queues empty
        mock_gpu_monitor.get_current_stats_async.return_value = {
            "gpu_utilization": 10.0,
        }

        can_evaluate = await background_evaluator.can_process_evaluation()

        assert can_evaluate is True


# =============================================================================
# Test: Evaluation Processing
# =============================================================================


class TestEvaluationProcessing:
    """Tests for the evaluation processing workflow."""

    @pytest.mark.asyncio
    async def test_process_single_evaluation(
        self, background_evaluator, mock_evaluation_queue, mock_audit_service
    ):
        """Test processing a single evaluation from the queue."""
        # Mock event exists
        mock_event = MagicMock()
        mock_event.id = 123

        mock_event_audit = MagicMock()
        mock_event_audit.event_id = 123

        mock_evaluation_queue.dequeue.return_value = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()

            # Mock event query result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_event

            # Mock audit query result
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_event_audit

            mock_session.execute.side_effect = [mock_result, mock_audit_result]
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            assert result is True
            mock_evaluation_queue.dequeue.assert_called_once()
            mock_audit_service.run_full_evaluation.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_returns_false_when_queue_empty(
        self, background_evaluator, mock_evaluation_queue
    ):
        """Test that process_one returns False when queue is empty."""
        mock_evaluation_queue.dequeue.return_value = None

        result = await background_evaluator.process_one()

        assert result is False
        mock_evaluation_queue.dequeue.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_handles_missing_event(self, background_evaluator, mock_evaluation_queue):
        """Test handling when event no longer exists in database."""
        mock_evaluation_queue.dequeue.return_value = 999  # Event ID

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Event not found

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            # Should return True (item processed, just skipped)
            assert result is True


# =============================================================================
# Test: Lifecycle Management
# =============================================================================


class TestLifecycleManagement:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self, background_evaluator):
        """Test that start creates a background processing task."""
        # Start should create a task
        await background_evaluator.start()

        assert background_evaluator.running is True
        assert background_evaluator._task is not None

        # Cleanup
        await background_evaluator.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self, background_evaluator):
        """Test that stop cancels the background task."""
        await background_evaluator.start()
        assert background_evaluator.running is True

        await background_evaluator.stop()

        assert background_evaluator.running is False
        assert background_evaluator._task is None

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, background_evaluator):
        """Test that calling start multiple times is safe."""
        await background_evaluator.start()
        task1 = background_evaluator._task

        await background_evaluator.start()
        task2 = background_evaluator._task

        # Same task should be reused
        assert task1 is task2

        await background_evaluator.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, background_evaluator):
        """Test that calling stop multiple times is safe."""
        # Stop without starting should not raise
        await background_evaluator.stop()
        await background_evaluator.stop()

        assert background_evaluator.running is False


# =============================================================================
# Test: Configuration
# =============================================================================


class TestConfiguration:
    """Tests for configuration options."""

    def test_default_idle_threshold(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test default GPU idle threshold is 20%."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
        )

        assert evaluator.gpu_idle_threshold == 20

    def test_custom_idle_threshold(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test custom GPU idle threshold."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            gpu_idle_threshold=30,
        )

        assert evaluator.gpu_idle_threshold == 30

    def test_default_idle_duration(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test default idle duration requirement is 5 seconds."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
        )

        assert evaluator.idle_duration_required == 5

    def test_custom_idle_duration(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test custom idle duration requirement."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            idle_duration_required=10,
        )

        assert evaluator.idle_duration_required == 10

    def test_disabled_by_default_respects_setting(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test that evaluator respects enabled setting."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            enabled=False,
        )

        assert evaluator.enabled is False


# =============================================================================
# Test: Singleton Pattern
# =============================================================================


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def test_get_background_evaluator_returns_instance(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test get_background_evaluator returns a BackgroundEvaluator instance."""
        from backend.services.background_evaluator import (
            BackgroundEvaluator,
            get_background_evaluator,
            reset_background_evaluator,
        )

        reset_background_evaluator()
        evaluator = get_background_evaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
        )
        assert isinstance(evaluator, BackgroundEvaluator)
        reset_background_evaluator()

    def test_get_background_evaluator_returns_same_instance(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test get_background_evaluator returns the same instance on repeated calls."""
        from backend.services.background_evaluator import (
            get_background_evaluator,
            reset_background_evaluator,
        )

        reset_background_evaluator()
        evaluator1 = get_background_evaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
        )
        evaluator2 = get_background_evaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
        )
        assert evaluator1 is evaluator2
        reset_background_evaluator()
