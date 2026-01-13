"""Comprehensive unit tests for WorkerSupervisor (PipelineWorkerManager).

This test suite focuses on supervisor-level functionality including:
- Worker registration and deregistration
- Health check logic and state transitions
- Restart behavior and backoff
- Graceful shutdown and queue draining
- Error handling and edge cases
- Global singleton management

These tests complement the existing pipeline_workers tests by focusing
specifically on the supervisor/manager aspects of worker lifecycle management.

NEM-2463: Create Comprehensive Test Suite for WorkerSupervisor
"""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    QueueMetricsWorker,
    WorkerState,
    drain_queues,
    get_pipeline_manager,
    reset_pipeline_manager_state,
    stop_pipeline_manager,
)

# =============================================================================
# Test Constants
# =============================================================================

TEST_STOP_TIMEOUT = 0.5  # Fast stop timeout for tests
TEST_POLL_TIMEOUT = 1  # Fast poll timeout for tests


# =============================================================================
# Test Helpers
# =============================================================================


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 2.0,
    poll_interval: float = 0.01,
    description: str = "condition",
) -> bool:
    """Wait for a condition to become true with a timeout.

    Args:
        condition: A callable that returns True when the condition is met
        timeout: Maximum time to wait in seconds
        poll_interval: How often to check the condition
        description: Description for error messages

    Returns:
        True if condition was met within timeout

    Raises:
        TimeoutError: If the condition is not met within the timeout
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(poll_interval)
    raise TimeoutError(f"Timeout waiting for {description}")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client with proper async behavior."""
    client = MagicMock(spec=RedisClient)

    async def mock_get_from_queue(*args, **kwargs):
        """Mock that yields control like real BLPOP would."""
        await asyncio.sleep(0.01)

    client.get_from_queue = mock_get_from_queue
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.get_queue_length = AsyncMock(return_value=0)
    client._client = MagicMock()
    client._client.keys = AsyncMock(return_value=[])
    return client


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global pipeline manager state before and after each test."""
    reset_pipeline_manager_state()
    yield
    reset_pipeline_manager_state()


# =============================================================================
# Worker Registration Tests
# =============================================================================


class TestWorkerRegistration:
    """Tests for worker registration and deregistration behavior."""

    @pytest.mark.asyncio
    async def test_manager_initializes_with_all_workers_by_default(self, mock_redis_client):
        """Test that manager creates all workers by default."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        assert manager._detection_worker is not None
        assert manager._analysis_worker is not None
        assert manager._timeout_worker is not None
        assert manager._metrics_worker is not None

    @pytest.mark.asyncio
    async def test_manager_selective_worker_creation(self, mock_redis_client):
        """Test that workers can be selectively enabled/disabled."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            enable_detection_worker=True,
            enable_analysis_worker=False,
            enable_timeout_worker=True,
            enable_metrics_worker=False,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        assert manager._detection_worker is not None
        assert manager._analysis_worker is None
        assert manager._timeout_worker is not None
        assert manager._metrics_worker is None

    @pytest.mark.asyncio
    async def test_manager_no_workers_enabled(self, mock_redis_client):
        """Test manager with all workers disabled."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        assert manager._detection_worker is None
        assert manager._analysis_worker is None
        assert manager._timeout_worker is None
        assert manager._metrics_worker is None

        # Should still be able to start/stop
        await manager.start()
        assert manager.running is True
        await manager.stop()
        assert manager.running is False

    @pytest.mark.asyncio
    async def test_manager_shares_batch_aggregator_between_workers(self, mock_redis_client):
        """Test that detection and timeout workers share the same batch aggregator."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            enable_detection_worker=True,
            enable_analysis_worker=False,
            enable_timeout_worker=True,
            enable_metrics_worker=False,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Both workers should use the same aggregator instance
        assert manager._detection_worker._aggregator is manager._aggregator
        assert manager._timeout_worker._aggregator is manager._aggregator


# =============================================================================
# Health Check and State Transition Tests
# =============================================================================


class TestHealthCheckLogic:
    """Tests for worker health monitoring and state transitions."""

    @pytest.mark.asyncio
    async def test_worker_state_transitions_through_lifecycle(self, mock_redis_client):
        """Test worker state transitions from STOPPED -> STARTING -> RUNNING -> STOPPING -> STOPPED."""
        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Initial state
        assert worker.stats.state == WorkerState.STOPPED
        assert worker.running is False

        # Start
        await worker.start()
        assert worker.stats.state == WorkerState.RUNNING
        assert worker.running is True

        # Stop
        await worker.stop()
        assert worker.stats.state == WorkerState.STOPPED
        assert worker.running is False

    @pytest.mark.asyncio
    async def test_worker_stats_tracking(self, mock_redis_client):
        """Test that worker stats are properly tracked."""
        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Initial stats
        assert worker.stats.items_processed == 0
        assert worker.stats.errors == 0
        assert worker.stats.last_processed_at is None

        # Stats should be accessible via to_dict
        stats_dict = worker.stats.to_dict()
        assert "items_processed" in stats_dict
        assert "errors" in stats_dict
        assert "last_processed_at" in stats_dict
        assert "state" in stats_dict

    @pytest.mark.asyncio
    async def test_worker_error_state_recovery(self, mock_redis_client):
        """Test that worker recovers from error state."""
        call_count = 0

        async def mock_get_from_queue_that_fails_then_succeeds(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated failure")
            await asyncio.sleep(0.01)

        mock_redis_client.get_from_queue = mock_get_from_queue_that_fails_then_succeeds

        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        await worker.start()

        # Wait for error to be recorded
        await wait_for_condition(
            lambda: worker.stats.errors >= 1,
            timeout=2.0,
            description="worker error recorded",
        )

        # Worker should recover and continue running
        assert worker.running is True
        await worker.stop()

    @pytest.mark.asyncio
    async def test_manager_get_status_reflects_worker_states(self, mock_redis_client):
        """Test that manager status accurately reflects worker states."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Before start
        status = manager.get_status()
        assert status["running"] is False
        assert status["workers"]["detection"]["state"] == "stopped"

        # After start
        await manager.start()
        status = manager.get_status()
        assert status["running"] is True
        assert status["workers"]["detection"]["state"] == "running"

        await manager.stop()


# =============================================================================
# Restart Behavior and Backoff Tests
# =============================================================================


class TestRestartBehavior:
    """Tests for worker restart behavior and backoff logic."""

    @pytest.mark.asyncio
    async def test_worker_idempotent_start(self, mock_redis_client):
        """Test that starting a running worker is idempotent."""
        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        await worker.start()
        first_task = worker._task

        # Start again - should not create new task
        await worker.start()
        assert worker._task is first_task
        assert worker.running is True

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_idempotent_stop(self, mock_redis_client):
        """Test that stopping a stopped worker is safe."""
        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Stop without starting
        await worker.stop()
        assert worker.running is False

        # Start and stop multiple times
        await worker.start()
        await worker.stop()
        await worker.stop()  # Double stop
        assert worker.running is False

    @pytest.mark.asyncio
    async def test_manager_idempotent_start(self, mock_redis_client):
        """Test that starting a running manager is idempotent."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        await manager.start()
        assert manager.running is True

        # Start again
        await manager.start()
        assert manager.running is True

        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_idempotent_stop(self, mock_redis_client):
        """Test that stopping a stopped manager is safe."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Stop without starting
        await manager.stop()
        assert manager.running is False

        # Start and stop multiple times
        await manager.start()
        await manager.stop()
        await manager.stop()  # Double stop
        assert manager.running is False


# =============================================================================
# Graceful Shutdown Tests
# =============================================================================


class TestGracefulShutdown:
    """Tests for graceful shutdown behavior including queue draining."""

    @pytest.mark.asyncio
    async def test_stop_accepting_sets_flag(self, mock_redis_client):
        """Test that stop_accepting sets the accepting flag to False."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        assert manager.accepting is True

        manager.stop_accepting()
        assert manager.accepting is False

    @pytest.mark.asyncio
    async def test_stop_accepting_is_idempotent(self, mock_redis_client):
        """Test that stop_accepting can be called multiple times safely."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        manager.stop_accepting()
        assert manager.accepting is False

        # Call again - should not raise
        manager.stop_accepting()
        assert manager.accepting is False

    @pytest.mark.asyncio
    async def test_get_pending_count_returns_queue_depths(self, mock_redis_client):
        """Test that get_pending_count returns sum of queue depths."""
        mock_redis_client.get_queue_length = AsyncMock(side_effect=[5, 3])

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        count = await manager.get_pending_count()
        assert count == 8  # 5 + 3

    @pytest.mark.asyncio
    async def test_get_pending_count_handles_redis_error(self, mock_redis_client):
        """Test that get_pending_count handles Redis errors gracefully."""
        mock_redis_client.get_queue_length = AsyncMock(side_effect=RuntimeError("Redis error"))

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        count = await manager.get_pending_count()
        assert count == 0  # Returns 0 on error

    @pytest.mark.asyncio
    async def test_drain_queues_empty_queues(self, mock_redis_client):
        """Test drain_queues returns immediately when queues are empty."""
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        remaining = await manager.drain_queues(timeout=1.0)
        assert remaining == 0
        assert manager.accepting is False  # stop_accepting is called

    @pytest.mark.asyncio
    async def test_drain_queues_waits_for_completion(self, mock_redis_client):
        """Test drain_queues waits for queues to drain."""
        call_count = 0

        async def mock_queue_length(queue_name):
            nonlocal call_count
            call_count += 1
            # First few calls return pending items, then empty
            if call_count <= 2:
                return 5 if "detection" in queue_name else 3
            return 0

        mock_redis_client.get_queue_length = mock_queue_length

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        remaining = await manager.drain_queues(timeout=2.0)
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_drain_queues_timeout(self, mock_redis_client):
        """Test drain_queues returns remaining count on timeout."""
        # Always return items, simulating queues that never drain
        mock_redis_client.get_queue_length = AsyncMock(return_value=10)

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        remaining = await manager.drain_queues(timeout=0.2)
        assert remaining > 0  # Should have remaining items

    @pytest.mark.asyncio
    async def test_global_drain_queues_function(self, mock_redis_client):
        """Test the global drain_queues function."""
        import backend.services.pipeline_workers as module

        # Set up the global manager
        module._pipeline_manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)

        remaining = await drain_queues(timeout=1.0)
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_global_drain_queues_no_manager(self):
        """Test drain_queues returns 0 when no manager exists."""
        import backend.services.pipeline_workers as module

        module._pipeline_manager = None

        remaining = await drain_queues(timeout=1.0)
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_worker_stop_timeout_forces_cancel(self, mock_redis_client):
        """Test that worker cancels task when stop times out."""
        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=0.01,  # Very short timeout
        )

        async def long_running_loop():
            while True:
                await asyncio.sleep(0.1)

        await worker.start()

        # Replace task with one that won't stop easily
        original_task = worker._task
        worker._task = asyncio.create_task(long_running_loop())

        if original_task:
            original_task.cancel()
            try:
                await original_task
            except asyncio.CancelledError:
                pass

        # Stop should timeout and force cancel
        await worker.stop()

        assert worker.running is False
        assert worker.stats.state == WorkerState.STOPPED
        assert worker._task is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in supervisor operations."""

    @pytest.mark.asyncio
    async def test_manager_handles_worker_start_failure(self, mock_redis_client):
        """Test that manager handles worker start failures gracefully."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Mock a worker to fail on start
        original_start = manager._detection_worker.start

        async def failing_start():
            raise RuntimeError("Start failed")

        manager._detection_worker.start = failing_start

        # Should raise ExceptionGroup with the TaskGroup
        with pytest.raises(ExceptionGroup):
            await manager.start()

        # Restore for cleanup
        manager._detection_worker.start = original_start

    @pytest.mark.asyncio
    async def test_manager_continues_stop_on_worker_error(self, mock_redis_client):
        """Test that manager continues stopping other workers when one fails."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        await manager.start()

        # Mock detection worker stop to fail
        original_stop = manager._detection_worker.stop

        async def failing_stop():
            raise RuntimeError("Stop failed")

        manager._detection_worker.stop = failing_stop

        # Stop should complete without raising (best-effort shutdown)
        await manager.stop()
        assert manager.running is False

        # Restore for cleanup
        manager._detection_worker.stop = original_stop

    @pytest.mark.asyncio
    async def test_worker_loop_handles_cancelled_error(self, mock_redis_client):
        """Test that worker loop handles CancelledError gracefully."""
        call_count = 0

        async def mock_get_that_raises_cancelled(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(0.01)
                return None
            raise asyncio.CancelledError()

        mock_redis_client.get_from_queue = mock_get_that_raises_cancelled

        worker = DetectionQueueWorker(
            redis_client=mock_redis_client,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        await worker.start()
        await wait_for_condition(lambda: call_count >= 1, timeout=2.0)

        # Manually clean up since loop exited due to CancelledError
        worker._running = False
        if worker._task and not worker._task.done():
            worker._task.cancel()
            try:
                await worker._task
            except asyncio.CancelledError:
                pass
        worker._task = None
        worker._stats.state = WorkerState.STOPPED


# =============================================================================
# Global Singleton Tests
# =============================================================================


class TestGlobalSingleton:
    """Tests for global pipeline manager singleton management."""

    @pytest.mark.asyncio
    async def test_get_pipeline_manager_creates_singleton(self, mock_redis_client):
        """Test that get_pipeline_manager creates a singleton."""
        manager1 = await get_pipeline_manager(mock_redis_client)
        manager2 = await get_pipeline_manager(mock_redis_client)

        assert manager1 is manager2

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_stop_pipeline_manager_clears_singleton(self, mock_redis_client):
        """Test that stop_pipeline_manager clears the singleton."""
        import backend.services.pipeline_workers as module

        # Create a fast manager directly to avoid slow default timeouts
        fast_manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )
        module._pipeline_manager = fast_manager

        await fast_manager.start()

        await stop_pipeline_manager()

        assert module._pipeline_manager is None

    @pytest.mark.asyncio
    async def test_stop_pipeline_manager_when_none(self):
        """Test that stop_pipeline_manager is safe when no manager exists."""
        import backend.services.pipeline_workers as module

        module._pipeline_manager = None

        # Should not raise
        await stop_pipeline_manager()

    @pytest.mark.asyncio
    async def test_reset_pipeline_manager_state(self, mock_redis_client):
        """Test that reset_pipeline_manager_state clears all state."""
        import backend.services.pipeline_workers as module

        await get_pipeline_manager(mock_redis_client)
        assert module._pipeline_manager is not None

        reset_pipeline_manager_state()

        assert module._pipeline_manager is None
        assert module._pipeline_manager_lock is None

    @pytest.mark.asyncio
    async def test_concurrent_get_pipeline_manager(self, mock_redis_client):
        """Test that concurrent calls to get_pipeline_manager return same instance."""
        import backend.services.pipeline_workers as module

        module._pipeline_manager = None

        # Create a fast manager to avoid slow defaults
        fast_manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Manually set to test concurrent access
        module._pipeline_manager = fast_manager

        results = await asyncio.gather(
            get_pipeline_manager(mock_redis_client),
            get_pipeline_manager(mock_redis_client),
            get_pipeline_manager(mock_redis_client),
        )

        # All should be the same instance
        assert results[0] is results[1] is results[2]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_manager_with_custom_stop_timeout(self, mock_redis_client):
        """Test that custom stop timeout is passed to workers."""
        custom_timeout = 1.5

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=custom_timeout,
        )

        assert manager._detection_worker._stop_timeout == custom_timeout
        assert manager._analysis_worker._stop_timeout == custom_timeout
        assert manager._timeout_worker._stop_timeout == custom_timeout
        assert manager._metrics_worker._stop_timeout == custom_timeout

    @pytest.mark.asyncio
    async def test_manager_status_includes_accepting_flag(self, mock_redis_client):
        """Test that manager status includes accepting flag."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        status = manager.get_status()
        assert "accepting" in status
        assert status["accepting"] is True

        manager.stop_accepting()
        status = manager.get_status()
        assert status["accepting"] is False

    @pytest.mark.asyncio
    async def test_worker_stats_update_on_processing(self, mock_redis_client):
        """Test that worker stats are updated during processing."""
        call_count = 0

        async def mock_get_from_queue(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            if call_count == 1:
                return {
                    "batch_id": "batch_123",
                    "camera_id": "cam1",
                    "detection_ids": [1, 2, 3],
                }
            return None

        mock_redis_client.get_from_queue = mock_get_from_queue

        mock_analyzer = MagicMock()
        event = MagicMock()
        event.id = 1
        event.risk_score = 50
        mock_analyzer.analyze_batch = AsyncMock(return_value=event)

        worker = AnalysisQueueWorker(
            redis_client=mock_redis_client,
            analyzer=mock_analyzer,
            poll_timeout=TEST_POLL_TIMEOUT,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        await worker.start()
        await wait_for_condition(
            lambda: worker.stats.items_processed >= 1,
            timeout=2.0,
            description="item processed",
        )
        await worker.stop()

        assert worker.stats.items_processed == 1
        assert worker.stats.last_processed_at is not None

    @pytest.mark.asyncio
    async def test_batch_timeout_worker_maintains_interval(self, mock_redis_client):
        """Test that batch timeout worker maintains consistent check interval."""
        import time

        call_times: list[float] = []

        mock_aggregator = MagicMock()

        async def mock_check_timeouts():
            call_times.append(time.time())
            await asyncio.sleep(0.02)  # Simulate processing time
            return []

        mock_aggregator.check_batch_timeouts = mock_check_timeouts

        check_interval = 0.1
        worker = BatchTimeoutWorker(
            redis_client=mock_redis_client,
            batch_aggregator=mock_aggregator,
            check_interval=check_interval,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        await worker.start()
        await asyncio.sleep(0.35)  # Allow multiple check cycles
        await worker.stop()

        # Should have at least 3 calls
        assert len(call_times) >= 3

        # Check intervals are approximately correct
        for i in range(1, len(call_times)):
            interval = call_times[i] - call_times[i - 1]
            # Should be close to check_interval, not check_interval + processing_time
            assert interval < check_interval + 0.05

    @pytest.mark.asyncio
    async def test_queue_metrics_worker_updates_both_queues(self, mock_redis_client):
        """Test that queue metrics worker updates both detection and analysis queues."""
        mock_redis_client.get_queue_length = AsyncMock(side_effect=[10, 5, 8, 3])

        worker = QueueMetricsWorker(
            redis_client=mock_redis_client,
            update_interval=0.05,
            stop_timeout=TEST_STOP_TIMEOUT,
        )

        with patch("backend.services.pipeline_workers.set_queue_depth") as mock_set:
            await worker.start()
            await wait_for_condition(
                lambda: mock_set.call_count >= 2,
                timeout=2.0,
                description="metrics updated",
            )
            await worker.stop()

            queue_names = [call[0][0] for call in mock_set.call_args_list]
            assert "detection" in queue_names
            assert "analysis" in queue_names


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for supervisor functionality."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_full_lifecycle_with_all_workers(self, mock_redis_client):
        """Test complete lifecycle with all workers enabled."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            enable_detection_worker=True,
            enable_analysis_worker=True,
            enable_timeout_worker=True,
            enable_metrics_worker=True,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # Start
        await manager.start()
        assert manager.running is True
        assert manager._detection_worker.running is True
        assert manager._analysis_worker.running is True
        assert manager._timeout_worker.running is True
        assert manager._metrics_worker.running is True

        # Get status
        status = manager.get_status()
        assert status["running"] is True
        assert len(status["workers"]) == 4

        # Stop accepting
        manager.stop_accepting()
        assert manager.accepting is False

        # Drain queues
        mock_redis_client.get_queue_length = AsyncMock(return_value=0)
        remaining = await manager.drain_queues(timeout=1.0)
        assert remaining == 0

        # Stop
        await manager.stop()
        assert manager.running is False
        assert manager._detection_worker.running is False
        assert manager._analysis_worker.running is False
        assert manager._timeout_worker.running is False
        assert manager._metrics_worker.running is False

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_manager_restart_after_stop(self, mock_redis_client):
        """Test that manager can be restarted after stop."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        # First lifecycle
        await manager.start()
        assert manager.running is True
        await manager.stop()
        assert manager.running is False

        # Second lifecycle
        await manager.start()
        assert manager.running is True
        await manager.stop()
        assert manager.running is False

    @pytest.mark.asyncio
    async def test_signal_handler_installation(self, mock_redis_client):
        """Test that signal handlers are installed during start."""
        import signal

        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        with patch.object(asyncio, "get_running_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            await manager.start()

            # Verify signal handlers were installed
            assert mock_loop.add_signal_handler.call_count == 2
            signals = [call[0][0] for call in mock_loop.add_signal_handler.call_args_list]
            assert signal.SIGTERM in signals
            assert signal.SIGINT in signals

        await manager.stop()

    @pytest.mark.asyncio
    async def test_signal_handler_not_supported(self, mock_redis_client):
        """Test graceful handling when signal handlers are not supported."""
        manager = PipelineWorkerManager(
            redis_client=mock_redis_client,
            worker_stop_timeout=TEST_STOP_TIMEOUT,
        )

        with patch.object(asyncio, "get_running_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.add_signal_handler.side_effect = NotImplementedError()
            mock_get_loop.return_value = mock_loop

            # Should not raise
            await manager.start()
            assert manager._signal_handlers_installed is False

        await manager.stop()
