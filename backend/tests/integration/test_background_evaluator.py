"""Integration tests for BackgroundEvaluator service with JobTracker.

These tests verify the BackgroundEvaluator behavior with real JobTracker
integration, covering scenarios that cannot be properly tested with mocks:
- Job tracking lifecycle during evaluation
- Progress reporting through JobTracker
- Cancellation handling during evaluation
- Integration between BackgroundEvaluator and JobTracker

Uses real async operations and JobTracker instances to verify integration behavior.

IMPORTANT: These tests can run in parallel with pytest-xdist because:
- Each test creates its own BackgroundEvaluator and JobTracker instances
- JobTracker uses in-memory state (no shared database or Redis)
- Test isolation is maintained through unique job IDs
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.background_evaluator import BackgroundEvaluator
from backend.services.job_tracker import JobStatus, JobTracker, reset_job_tracker

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_job_id(prefix: str = "eval") -> str:
    """Generate a unique job ID for test isolation."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def job_tracker() -> JobTracker:
    """Create a fresh JobTracker instance for each test."""
    # Reset singleton state for test isolation
    reset_job_tracker()
    tracker = JobTracker()
    return tracker


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
    """Create a mock GPUMonitor that reports idle GPU."""
    monitor = MagicMock()
    monitor.get_current_stats = MagicMock(
        return_value={
            "gpu_utilization": 5.0,  # Below idle threshold
            "memory_used": 2000,
            "memory_total": 24576,
            "temperature": 45,
            "power_usage": 30.0,
        }
    )
    monitor.get_current_stats_async = AsyncMock(
        return_value={
            "gpu_utilization": 5.0,
            "memory_used": 2000,
            "memory_total": 24576,
            "temperature": 45,
            "power_usage": 30.0,
        }
    )
    return monitor


@pytest.fixture
def mock_evaluation_queue():
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
def background_evaluator(
    mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service, job_tracker
):
    """Create a BackgroundEvaluator instance with real JobTracker."""
    evaluator = BackgroundEvaluator(
        redis_client=mock_redis,
        gpu_monitor=mock_gpu_monitor,
        evaluation_queue=mock_evaluation_queue,
        audit_service=mock_audit_service,
        job_tracker=job_tracker,
        poll_interval=0.1,  # Fast polling for tests
        idle_duration_required=0,  # No idle wait for tests
    )
    return evaluator


# =============================================================================
# Test: JobTracker Integration
# =============================================================================


class TestBackgroundEvaluatorJobTracking:
    """Tests for BackgroundEvaluator integration with JobTracker."""

    @pytest.mark.asyncio
    async def test_evaluator_respects_job_cancellation(
        self, background_evaluator, job_tracker, mock_evaluation_queue
    ):
        """Verify evaluator stops processing when job is cancelled."""
        job_id = _unique_job_id()

        # Create a job and immediately cancel it
        job_tracker.create_job(job_id, "evaluation", total_items=10)
        job_tracker.cancel_job(job_id)

        # Verify job is cancelled
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.CANCELLED

        # The evaluator should check cancellation status
        assert background_evaluator._is_job_cancelled(job_id) is True

    @pytest.mark.asyncio
    async def test_evaluator_without_job_tracker_ignores_cancellation(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Verify evaluator works without JobTracker (backwards compatibility)."""
        # Create evaluator without job_tracker
        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            job_tracker=None,
        )

        # Without job tracker, cancellation check should return False
        assert evaluator._is_job_cancelled(None) is False
        assert evaluator._is_job_cancelled("any_id") is False

    @pytest.mark.asyncio
    async def test_evaluator_can_process_with_job_tracking(
        self, background_evaluator, job_tracker, mock_evaluation_queue
    ):
        """Verify evaluator processes events with job tracking enabled."""
        # No events in queue
        mock_evaluation_queue.get_size.return_value = 0
        mock_evaluation_queue.dequeue.return_value = None

        # Should be able to call process_one without errors
        result = await background_evaluator.process_one()
        # No events to process, should return False
        assert result is False

    @pytest.mark.asyncio
    async def test_job_tracker_progress_updates_during_evaluation(self, job_tracker):
        """Verify JobTracker correctly tracks progress during evaluation."""
        job_id = _unique_job_id()

        # Simulate evaluation job lifecycle
        job_tracker.create_job(job_id, "evaluation", total_items=5)
        job = job_tracker.get_job(job_id)
        assert job.status == JobStatus.PENDING

        job_tracker.start_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job.status == JobStatus.RUNNING

        # Update progress
        job_tracker.update_progress(job_id, processed=2, total=5)
        job = job_tracker.get_job(job_id)
        assert job.processed_items == 2
        assert job.total_items == 5

        # Complete job
        job_tracker.complete_job(job_id, result={"evaluated": 5})
        job = job_tracker.get_job(job_id)
        assert job.status == JobStatus.COMPLETED


class TestBackgroundEvaluatorCancellationChecks:
    """Tests for cancellation check logic in BackgroundEvaluator."""

    @pytest.mark.asyncio
    async def test_is_job_cancelled_with_no_tracker(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        """Verify _is_job_cancelled returns False when no tracker."""
        evaluator = BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            job_tracker=None,
        )
        assert evaluator._is_job_cancelled(None) is False
        assert evaluator._is_job_cancelled("test_job") is False

    @pytest.mark.asyncio
    async def test_is_job_cancelled_with_none_job_id(self, background_evaluator, job_tracker):
        """Verify _is_job_cancelled handles None job_id."""
        assert background_evaluator._is_job_cancelled(None) is False

    @pytest.mark.asyncio
    async def test_is_job_cancelled_with_nonexistent_job(self, background_evaluator, job_tracker):
        """Verify _is_job_cancelled handles nonexistent job."""
        assert background_evaluator._is_job_cancelled("nonexistent_job") is False

    @pytest.mark.asyncio
    async def test_is_job_cancelled_with_active_job(self, background_evaluator, job_tracker):
        """Verify _is_job_cancelled returns False for active job."""
        job_id = _unique_job_id()
        job_tracker.create_job(job_id, "evaluation", total_items=10)
        job_tracker.start_job(job_id)

        assert background_evaluator._is_job_cancelled(job_id) is False

    @pytest.mark.asyncio
    async def test_is_job_cancelled_with_cancelled_job(self, background_evaluator, job_tracker):
        """Verify _is_job_cancelled returns True for cancelled job."""
        job_id = _unique_job_id()
        job_tracker.create_job(job_id, "evaluation", total_items=10)
        job_tracker.cancel_job(job_id)

        assert background_evaluator._is_job_cancelled(job_id) is True
