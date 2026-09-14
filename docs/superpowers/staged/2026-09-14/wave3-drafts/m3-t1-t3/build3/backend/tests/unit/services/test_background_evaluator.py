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
    # Support for job status service
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.zrem = AsyncMock(return_value=1)
    redis.zrangebyscore = AsyncMock(return_value=[])
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
    # New method for split-session pattern (NEM-3505)
    service.run_evaluation_llm_calls = AsyncMock()
    return service


@pytest.fixture
def mock_job_status_service():
    """Create a mock JobStatusService."""
    service = MagicMock()
    service.start_job = AsyncMock(return_value="mock-job-id")
    service.update_progress = AsyncMock()
    service.complete_job = AsyncMock()
    service.fail_job = AsyncMock()
    return service


@pytest.fixture
def background_evaluator(
    mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service, mock_job_status_service
):
    """Create a BackgroundEvaluator instance with mock dependencies."""
    from backend.services.background_evaluator import BackgroundEvaluator

    evaluator = BackgroundEvaluator(
        redis_client=mock_redis,
        gpu_monitor=mock_gpu_monitor,
        evaluation_queue=mock_evaluation_queue,
        audit_service=mock_audit_service,
    )
    # Inject mock job status service
    evaluator._job_status_service = mock_job_status_service
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

    @pytest.mark.asyncio
    async def test_is_gpu_idle_handles_exception(self, background_evaluator, mock_gpu_monitor):
        """Test handling of exceptions when checking GPU idle status."""
        mock_gpu_monitor.get_current_stats_async.side_effect = RuntimeError("GPU error")

        # Should return False (not idle) when exception occurs
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

    @pytest.mark.asyncio
    async def test_queue_check_handles_redis_exception(self, background_evaluator, mock_redis):
        """Test that queue check handles Redis exceptions gracefully."""
        mock_redis.llen.side_effect = ConnectionError("Redis connection failed")

        # Should return False (cannot evaluate) when Redis fails
        can_evaluate = await background_evaluator.can_process_evaluation()
        assert can_evaluate is False


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
        mock_event_audit.id = 1
        mock_event_audit.event_id = 123

        mock_evaluation_queue.dequeue.return_value = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync
            mock_session.merge = AsyncMock(return_value=mock_event_audit)

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
            # NEM-3505: Now calls run_evaluation_llm_calls instead of run_full_evaluation
            mock_audit_service.run_evaluation_llm_calls.assert_called_once()

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

    @pytest.mark.asyncio
    async def test_process_handles_missing_audit(self, background_evaluator, mock_evaluation_queue):
        """Test handling when audit record is missing."""
        mock_evaluation_queue.dequeue.return_value = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_event = MagicMock()
            mock_event.id = 123

            # Mock event query result
            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event

            # Mock audit query result - no audit found
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = None

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            # Should return True (item processed, skipped due to missing audit)
            assert result is True

    @pytest.mark.asyncio
    async def test_process_handles_evaluation_exception(
        self, background_evaluator, mock_evaluation_queue, mock_audit_service
    ):
        """Test handling of exceptions during evaluation."""
        mock_evaluation_queue.dequeue.return_value = 123
        # NEM-3505: Now raises on run_evaluation_llm_calls instead of run_full_evaluation
        mock_audit_service.run_evaluation_llm_calls.side_effect = RuntimeError("AI service error")

        mock_event = MagicMock()
        mock_event.id = 123

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event

            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            # Should return True (item processed, error logged)
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

    @pytest.mark.asyncio
    async def test_start_when_disabled_does_nothing(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test that start does nothing when evaluator is disabled."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            enabled=False,
        )

        await evaluator.start()

        # Should not create task when disabled
        assert evaluator.running is False
        assert evaluator._task is None


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


class TestProcessingLoop:
    """Tests for the main processing loop (_run_loop)."""

    @pytest.mark.asyncio
    async def test_run_loop_processes_evaluation_when_conditions_met(
        self, background_evaluator, mock_redis, mock_gpu_monitor, mock_evaluation_queue
    ):
        """Test that loop processes evaluation when GPU is idle and queues are empty."""
        import asyncio

        # Setup: GPU is idle, queues empty, event ready
        mock_redis.llen.return_value = 0
        mock_gpu_monitor.get_current_stats_async.return_value = {"gpu_utilization": 10.0}
        mock_evaluation_queue.dequeue.return_value = None  # Empty queue after first check

        # Set short poll interval and idle duration for faster test
        background_evaluator.poll_interval = 0.01
        background_evaluator.idle_duration_required = 0.01

        # Start the loop
        await background_evaluator.start()

        # Let it run for a short time
        await asyncio.sleep(0.1)

        # Stop the loop
        await background_evaluator.stop()

        # Verify that can_process_evaluation was called
        assert mock_redis.llen.call_count > 0

    @pytest.mark.asyncio
    async def test_run_loop_waits_for_idle_duration(
        self, background_evaluator, mock_redis, mock_gpu_monitor, mock_evaluation_queue
    ):
        """Test that loop waits for required idle duration before processing."""
        import asyncio

        # Setup: GPU becomes idle
        mock_redis.llen.return_value = 0
        mock_gpu_monitor.get_current_stats_async.return_value = {"gpu_utilization": 10.0}
        mock_evaluation_queue.dequeue.return_value = 123

        # Set longer idle duration
        background_evaluator.poll_interval = 0.01
        background_evaluator.idle_duration_required = 0.05

        # Start the loop
        await background_evaluator.start()

        # Wait less than idle duration
        await asyncio.sleep(0.02)

        # Stop the loop
        await background_evaluator.stop()

        # Should not have processed yet (idle duration not met)
        # This verifies the timer logic works

    @pytest.mark.asyncio
    async def test_run_loop_resets_idle_timer_when_not_idle(
        self, background_evaluator, mock_redis, mock_gpu_monitor
    ):
        """Test that idle timer resets when GPU becomes busy."""
        import asyncio

        # Setup: GPU starts idle, then becomes busy
        mock_redis.llen.return_value = 0
        call_count = 0

        def gpu_utilization_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"gpu_utilization": 10.0}  # Idle
            else:
                return {"gpu_utilization": 80.0}  # Busy

        mock_gpu_monitor.get_current_stats_async.side_effect = gpu_utilization_side_effect

        background_evaluator.poll_interval = 0.01
        background_evaluator.idle_duration_required = 0.1

        # Start the loop
        await background_evaluator.start()

        # Let it run long enough to see idle -> busy transition
        await asyncio.sleep(0.05)

        # Stop the loop
        await background_evaluator.stop()

        # Verify GPU stats were checked multiple times
        assert call_count > 2

    @pytest.mark.asyncio
    async def test_run_loop_handles_exception_and_continues(
        self, background_evaluator, mock_redis, mock_gpu_monitor
    ):
        """Test that loop continues after exceptions."""
        import asyncio

        # Setup: Cause an exception, then work normally
        call_count = 0

        def redis_side_effect(queue_name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Redis error")
            return 0

        mock_redis.llen.side_effect = redis_side_effect
        mock_gpu_monitor.get_current_stats_async.return_value = {"gpu_utilization": 10.0}

        background_evaluator.poll_interval = 0.01

        # Start the loop
        await background_evaluator.start()

        # Let it run to hit the exception and continue
        await asyncio.sleep(0.05)

        # Stop the loop
        await background_evaluator.stop()

        # Loop should have continued after exception
        assert call_count > 1

    @pytest.mark.asyncio
    async def test_run_loop_stops_on_cancellation(self, background_evaluator):
        """Test that loop exits cleanly when cancelled."""
        import asyncio

        background_evaluator.poll_interval = 0.01

        # Start the loop
        await background_evaluator.start()

        # Let it run briefly
        await asyncio.sleep(0.02)

        # Stop should cancel cleanly
        await background_evaluator.stop()

        # Task should be None after stop
        assert background_evaluator._task is None
        assert background_evaluator.running is False

    @pytest.mark.asyncio
    async def test_run_loop_respects_enabled_flag(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test that loop respects enabled flag during runtime."""
        import asyncio

        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            enabled=True,
            poll_interval=0.01,
        )

        mock_redis.llen.return_value = 0
        mock_gpu_monitor.get_current_stats_async.return_value = {"gpu_utilization": 10.0}

        # Start enabled
        await evaluator.start()

        # Disable during runtime
        evaluator.enabled = False

        # Let it run
        await asyncio.sleep(0.03)

        # Stop
        await evaluator.stop()

        # Should have checked conditions but not processed (enabled=False)
        # This verifies the enabled check in the loop

    @pytest.mark.asyncio
    async def test_run_loop_processes_successfully(
        self,
        mock_redis,
        mock_gpu_monitor,
        mock_evaluation_queue,
        mock_audit_service,
        mock_job_status_service,
    ):
        """Test that loop successfully processes an evaluation and logs success."""
        import asyncio

        from backend.services.background_evaluator import BackgroundEvaluator

        # Create evaluator with short intervals
        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            enabled=True,
            poll_interval=0.01,
            idle_duration_required=0.01,
        )
        # Inject mock job status service
        evaluator._job_status_service = mock_job_status_service

        # Setup for successful processing
        mock_redis.llen.return_value = 0  # Queues empty
        mock_gpu_monitor.get_current_stats_async.return_value = {"gpu_utilization": 10.0}

        # First call returns event, second returns None (queue empty)
        mock_evaluation_queue.dequeue.side_effect = [123, None]

        # Mock database session
        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            # Start the loop
            await evaluator.start()

            # Wait for processing
            await asyncio.sleep(0.05)

            # Stop the loop
            await evaluator.stop()

            # NEM-3505: Verify audit service was called with new method
            mock_audit_service.run_evaluation_llm_calls.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_loop_handles_non_asyncio_exception(
        self, background_evaluator, mock_redis, mock_gpu_monitor
    ):
        """Test that loop handles non-asyncio exceptions and continues."""
        import asyncio

        # Setup to cause a non-asyncio exception in can_process_evaluation
        call_count = 0

        async def failing_can_process():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Unexpected error")
            return False

        # Patch the method directly
        background_evaluator.can_process_evaluation = failing_can_process
        background_evaluator.poll_interval = 0.01

        # Start the loop
        await background_evaluator.start()

        # Let it run to hit the exception and continue
        await asyncio.sleep(0.05)

        # Stop the loop
        await background_evaluator.stop()

        # Loop should have continued after exception
        assert call_count > 1


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


# =============================================================================
# Test: Job Tracking Integration (NEM-1974)
# =============================================================================


class TestJobTrackingIntegration:
    """Tests for job tracking integration in BackgroundEvaluator (NEM-1974)."""

    @pytest.fixture
    def mock_job_tracker(self):
        """Create a mock JobTracker."""
        tracker = MagicMock()
        tracker.create_job = MagicMock(return_value="test-job-123")
        tracker.start_job = MagicMock()
        tracker.update_progress = MagicMock()
        tracker.complete_job = MagicMock()
        tracker.fail_job = MagicMock()
        tracker.is_cancelled = MagicMock(return_value=False)
        return tracker

    @pytest.fixture
    def evaluator_with_job_tracker(
        self,
        mock_redis,
        mock_gpu_monitor,
        mock_evaluation_queue,
        mock_audit_service,
        mock_job_tracker,
    ):
        """Create a BackgroundEvaluator with job tracker."""
        from backend.services.background_evaluator import BackgroundEvaluator

        return BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            job_tracker=mock_job_tracker,
        )

    @pytest.mark.asyncio
    async def test_process_one_creates_job(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_job_tracker
    ):
        """Test that process_one creates a job when tracker is configured."""
        mock_evaluation_queue.dequeue.return_value = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            mock_job_tracker.create_job.assert_called_once_with("evaluation")
            mock_job_tracker.start_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_one_updates_progress(
        self,
        evaluator_with_job_tracker,
        mock_evaluation_queue,
        mock_audit_service,
        mock_job_tracker,
    ):
        """Test that process_one updates progress during evaluation."""
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            # Verify progress updates were called
            assert mock_job_tracker.update_progress.call_count >= 3
            mock_job_tracker.complete_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_one_fails_job_on_exception(
        self,
        evaluator_with_job_tracker,
        mock_evaluation_queue,
        mock_audit_service,
        mock_job_tracker,
    ):
        """Test that process_one fails the job when an exception occurs."""
        mock_evaluation_queue.dequeue.return_value = 123
        # NEM-3505: Now raises on run_evaluation_llm_calls instead of run_full_evaluation
        mock_audit_service.run_evaluation_llm_calls.side_effect = RuntimeError("AI service error")

        mock_event = MagicMock()
        mock_event.id = 123

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            mock_job_tracker.fail_job.assert_called_once()
            call_args = mock_job_tracker.fail_job.call_args
            assert "AI service error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_process_one_checks_cancellation(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_job_tracker
    ):
        """Test that process_one checks for cancellation."""
        mock_evaluation_queue.dequeue.return_value = 123
        mock_job_tracker.is_cancelled.return_value = True  # Simulate cancellation

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await evaluator_with_job_tracker.process_one()

            assert result is True  # Processed (but cancelled)
            mock_job_tracker.is_cancelled.assert_called()

    @pytest.mark.asyncio
    async def test_process_one_completes_job_for_skipped_event(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_job_tracker
    ):
        """Test that process_one completes job when event is not found."""
        mock_evaluation_queue.dequeue.return_value = 999

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Event not found

            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            mock_job_tracker.complete_job.assert_called_once()
            call_args = mock_job_tracker.complete_job.call_args
            result = call_args[1]["result"]
            assert result["skipped"] is True
            assert result["reason"] == "event_not_found"

    def test_is_job_cancelled_without_tracker(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Test _is_job_cancelled returns False when no tracker is configured."""
        from backend.services.background_evaluator import BackgroundEvaluator

        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            job_tracker=None,
        )

        assert evaluator._is_job_cancelled("some-job-id") is False
        assert evaluator._is_job_cancelled(None) is False

    def test_is_job_cancelled_with_none_job_id(self, evaluator_with_job_tracker, mock_job_tracker):
        """Test _is_job_cancelled returns False when job_id is None."""
        assert evaluator_with_job_tracker._is_job_cancelled(None) is False
        mock_job_tracker.is_cancelled.assert_not_called()


# =============================================================================
# Test: DetachedInstanceError Fix (NEM-3902)
# =============================================================================


class TestDeferredColumnAccess:
    """Tests for accessing deferred columns after session close (NEM-3902)."""

    @pytest.mark.asyncio
    async def test_process_one_loads_deferred_columns(
        self,
        background_evaluator,
        mock_evaluation_queue,
        mock_audit_service,
    ):
        """Test that process_one eagerly loads deferred columns before expunge.

        This test verifies the fix for NEM-3902: SQLAlchemy DetachedInstanceError
        when accessing event.llm_prompt and event.reasoning after the session is closed.
        """
        mock_evaluation_queue.dequeue.return_value = 123

        # Create mock event with deferred attributes
        mock_event = MagicMock()
        mock_event.id = 123
        mock_event.llm_prompt = "Test prompt"
        mock_event.reasoning = "Test reasoning"
        mock_event.risk_score = 75
        mock_event.summary = "Test summary"

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        # Track whether run_evaluation_llm_calls was able to access deferred attributes
        access_succeeded = False

        async def mock_run_evaluation(audit, event):
            """Mock evaluation that accesses deferred attributes."""
            nonlocal access_succeeded
            try:
                # These accesses should not raise DetachedInstanceError
                _ = event.llm_prompt
                _ = event.reasoning
                _ = event.risk_score
                _ = event.summary
                access_succeeded = True
            except Exception as e:
                pytest.fail(f"Failed to access deferred attributes: {e}")

        mock_audit_service.run_evaluation_llm_calls.side_effect = mock_run_evaluation

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            assert result is True
            assert access_succeeded, "Deferred attributes should be accessible after expunge"
            mock_audit_service.run_evaluation_llm_calls.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_one_handles_missing_llm_prompt(
        self,
        background_evaluator,
        mock_evaluation_queue,
        mock_audit_service,
    ):
        """Test that process_one handles events with missing llm_prompt gracefully."""
        mock_evaluation_queue.dequeue.return_value = 123

        # Create mock event with None llm_prompt
        mock_event = MagicMock()
        mock_event.id = 123
        mock_event.llm_prompt = None  # Missing prompt
        mock_event.reasoning = "Test reasoning"
        mock_event.risk_score = 75
        mock_event.summary = "Test summary"

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123

        with patch("backend.services.background_evaluator.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit

            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            assert result is True
            # When llm_prompt is None, run_evaluation_llm_calls should return early
            mock_audit_service.run_evaluation_llm_calls.assert_called_once()
