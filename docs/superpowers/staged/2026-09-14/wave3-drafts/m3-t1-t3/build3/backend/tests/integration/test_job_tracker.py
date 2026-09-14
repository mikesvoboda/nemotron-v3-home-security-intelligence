"""Integration tests for JobTracker service with real async operations.

These tests verify the JobTracker behavior with actual async operations and
WebSocket broadcasting, covering scenarios that cannot be properly tested with mocks:
- Async broadcast callback execution
- Thread-safe concurrent job operations
- Job lifecycle state transitions
- Progress throttling with real timing
- Error handling with actual dependencies

Uses real async operations to verify integration behavior.

IMPORTANT: These tests can run in parallel with pytest-xdist because JobTracker
uses in-memory state (no shared database or Redis). Each test creates its own
JobTracker instance with unique job IDs to avoid collisions.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services.job_tracker import (
    JobEventType,
    JobStatus,
    JobTracker,
    reset_job_tracker,
)

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_job_id(prefix: str = "job") -> str:
    """Generate a unique job ID for test isolation."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def job_tracker() -> JobTracker:
    """Create a fresh JobTracker instance for each test."""
    # Reset singleton to ensure clean state
    reset_job_tracker()
    return JobTracker()


@pytest.fixture
def broadcast_spy() -> AsyncMock:
    """Create a spy that records all broadcast calls."""
    spy = AsyncMock()
    spy.calls = []

    async def record_call(event_type: str, data: dict[str, Any]) -> None:
        spy.calls.append((event_type, data))

    spy.side_effect = record_call
    return spy


# =============================================================================
# Job Lifecycle Tests
# =============================================================================


class TestJobLifecycle:
    """Test complete job lifecycle from creation to completion."""

    @pytest.mark.asyncio
    async def test_complete_job_lifecycle_success(self, job_tracker: JobTracker) -> None:
        """Test successful job lifecycle: create -> start -> update -> complete."""
        job_id = _unique_job_id()

        # Create job
        created_id = job_tracker.create_job("test_job", job_id=job_id)
        assert created_id == job_id

        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.PENDING
        assert job["progress"] == 0
        assert job["started_at"] is None
        assert job["completed_at"] is None

        # Start job
        job_tracker.start_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job["status"] == JobStatus.RUNNING
        assert job["started_at"] is not None

        # Update progress
        job_tracker.update_progress(job_id, 50)
        job = job_tracker.get_job(job_id)
        assert job["progress"] == 50

        # Complete job
        result_data = {"processed": 100, "success": True}
        job_tracker.complete_job(job_id, result=result_data)
        job = job_tracker.get_job(job_id)
        assert job["status"] == JobStatus.COMPLETED
        assert job["progress"] == 100
        assert job["completed_at"] is not None
        assert job["result"] == result_data

    @pytest.mark.asyncio
    async def test_complete_job_lifecycle_failure(self, job_tracker: JobTracker) -> None:
        """Test failed job lifecycle: create -> start -> fail."""
        job_id = _unique_job_id()

        # Create and start job
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Fail job
        error_msg = "Processing failed due to invalid data"
        job_tracker.fail_job(job_id, error=error_msg)

        job = job_tracker.get_job(job_id)
        assert job["status"] == JobStatus.FAILED
        assert job["completed_at"] is not None
        assert job["error"] == error_msg

    @pytest.mark.asyncio
    async def test_job_not_found_raises_key_error(self, job_tracker: JobTracker) -> None:
        """Test that operations on non-existent jobs raise KeyError."""
        nonexistent_id = _unique_job_id()

        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.start_job(nonexistent_id)

        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.update_progress(nonexistent_id, 50)

        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.complete_job(nonexistent_id)

        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.fail_job(nonexistent_id, "error")


# =============================================================================
# Broadcast Integration Tests
# =============================================================================


class TestBroadcastIntegration:
    """Test WebSocket broadcasting with real async operations."""

    @pytest.mark.asyncio
    async def test_async_broadcast_callback_execution(self, broadcast_spy: AsyncMock) -> None:
        """Test that async broadcast callbacks are properly executed."""
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        # Complete job (triggers broadcast)
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.complete_job(job_id, result={"test": True})

        # Give async callback time to execute
        await asyncio.sleep(0.1)

        # Verify broadcast was called
        assert len(broadcast_spy.calls) == 1
        event_type, data = broadcast_spy.calls[0]
        assert event_type == JobEventType.JOB_COMPLETED
        assert data["type"] == JobEventType.JOB_COMPLETED
        assert data["data"]["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_sync_broadcast_callback_execution(self) -> None:
        """Test that sync broadcast callbacks work correctly."""
        calls = []

        def sync_callback(event_type: str, data: dict[str, Any]) -> None:
            calls.append((event_type, data))

        job_tracker = JobTracker(broadcast_callback=sync_callback)
        job_id = _unique_job_id()

        # Complete job (triggers broadcast)
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.complete_job(job_id)

        # Sync callback should execute immediately
        assert len(calls) == 1
        assert calls[0][0] == JobEventType.JOB_COMPLETED

    @pytest.mark.asyncio
    async def test_progress_broadcast_throttling(self, broadcast_spy: AsyncMock) -> None:
        """Test that progress broadcasts are throttled to 10% increments."""
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Update progress through multiple thresholds
        for progress in [5, 9, 10, 15, 20, 25, 29, 30]:
            job_tracker.update_progress(job_id, progress)

        # Wait for async broadcasts
        await asyncio.sleep(0.1)

        # Should only broadcast on threshold crossings: 10, 20, 30
        progress_broadcasts = [
            call for call in broadcast_spy.calls if call[0] == JobEventType.JOB_PROGRESS
        ]
        assert len(progress_broadcasts) == 3

        # Verify the progress values
        progress_values = [call[1]["data"]["progress"] for call in progress_broadcasts]
        assert progress_values == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_failed_job_broadcast(self, broadcast_spy: AsyncMock) -> None:
        """Test that failed jobs trigger appropriate broadcast."""
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        error_msg = "Processing error occurred"
        job_tracker.fail_job(job_id, error=error_msg)

        # Wait for async broadcast
        await asyncio.sleep(0.1)

        # Find the failure broadcast
        failure_broadcasts = [
            call for call in broadcast_spy.calls if call[0] == JobEventType.JOB_FAILED
        ]
        assert len(failure_broadcasts) == 1

        _event_type, data = failure_broadcasts[0]
        assert data["type"] == JobEventType.JOB_FAILED
        assert data["data"]["job_id"] == job_id
        assert data["data"]["error"] == error_msg

    @pytest.mark.asyncio
    async def test_broadcast_callback_exception_handling(self) -> None:
        """Test that exceptions in broadcast callbacks are handled gracefully."""
        calls = []

        async def failing_callback(event_type: str, data: dict[str, Any]) -> None:
            calls.append(event_type)
            raise ValueError("Broadcast failed")

        job_tracker = JobTracker(broadcast_callback=failing_callback)
        job_id = _unique_job_id()

        # Should not raise even though callback fails
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.complete_job(job_id)

        # Wait for async callback
        await asyncio.sleep(0.1)

        # Callback was called (exception was caught)
        assert JobEventType.JOB_COMPLETED in calls

        # Job state is still updated correctly
        job = job_tracker.get_job(job_id)
        assert job["status"] == JobStatus.COMPLETED


# =============================================================================
# Concurrent Operations Tests
# =============================================================================


class TestConcurrentOperations:
    """Test thread-safe concurrent job operations."""

    @pytest.mark.asyncio
    async def test_concurrent_job_creation(self, job_tracker: JobTracker) -> None:
        """Test creating multiple jobs concurrently."""

        async def create_job(index: int) -> str:
            job_id = _unique_job_id(f"concurrent_{index}")
            return job_tracker.create_job(f"job_{index}", job_id=job_id)

        # Create 10 jobs concurrently
        job_ids = await asyncio.gather(*[create_job(i) for i in range(10)])

        # All jobs should be created
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10  # All unique

        # All jobs should be retrievable
        for job_id in job_ids:
            job = job_tracker.get_job(job_id)
            assert job is not None
            assert job["status"] == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_concurrent_progress_updates(self, job_tracker: JobTracker) -> None:
        """Test concurrent progress updates on multiple jobs."""
        # Create multiple jobs
        job_ids = [_unique_job_id(f"progress_{i}") for i in range(5)]
        for job_id in job_ids:
            job_tracker.create_job("test_job", job_id=job_id)
            job_tracker.start_job(job_id)

        async def update_job_progress(job_id: str, progress: int) -> None:
            job_tracker.update_progress(job_id, progress)
            await asyncio.sleep(0.01)  # Small delay to simulate work

        # Update all jobs to different progress values concurrently
        updates = [update_job_progress(job_id, (i + 1) * 20) for i, job_id in enumerate(job_ids)]
        await asyncio.gather(*updates)

        # Verify all updates applied correctly
        for i, job_id in enumerate(job_ids):
            job = job_tracker.get_job(job_id)
            assert job["progress"] == (i + 1) * 20

    @pytest.mark.asyncio
    async def test_concurrent_job_completion(self, job_tracker: JobTracker) -> None:
        """Test concurrent job completion operations."""
        # Create and start multiple jobs
        job_ids = [_unique_job_id(f"complete_{i}") for i in range(5)]
        for job_id in job_ids:
            job_tracker.create_job("test_job", job_id=job_id)
            job_tracker.start_job(job_id)

        async def complete_job(job_id: str, index: int) -> None:
            await asyncio.sleep(0.01 * index)  # Stagger completions
            job_tracker.complete_job(job_id, result={"index": index})

        # Complete all jobs concurrently
        await asyncio.gather(*[complete_job(job_id, i) for i, job_id in enumerate(job_ids)])

        # Verify all jobs completed
        for i, job_id in enumerate(job_ids):
            job = job_tracker.get_job(job_id)
            assert job["status"] == JobStatus.COMPLETED
            assert job["result"]["index"] == i

    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(self, job_tracker: JobTracker) -> None:
        """Test mixed concurrent operations (create, update, complete, fail)."""
        results = {"created": [], "completed": [], "failed": []}

        async def create_and_complete(index: int) -> None:
            job_id = _unique_job_id(f"mixed_{index}")
            job_tracker.create_job(f"job_{index}", job_id=job_id)
            results["created"].append(job_id)
            job_tracker.start_job(job_id)
            job_tracker.update_progress(job_id, 50)
            await asyncio.sleep(0.01)
            job_tracker.complete_job(job_id)
            results["completed"].append(job_id)

        async def create_and_fail(index: int) -> None:
            job_id = _unique_job_id(f"fail_{index}")
            job_tracker.create_job(f"job_{index}", job_id=job_id)
            results["created"].append(job_id)
            job_tracker.start_job(job_id)
            await asyncio.sleep(0.01)
            job_tracker.fail_job(job_id, "test error")
            results["failed"].append(job_id)

        # Run mixed operations concurrently
        operations = [create_and_complete(i) for i in range(3)] + [
            create_and_fail(i) for i in range(2)
        ]
        await asyncio.gather(*operations)

        # Verify results
        assert len(results["created"]) == 5
        assert len(results["completed"]) == 3
        assert len(results["failed"]) == 2


# =============================================================================
# Active Jobs Query Tests
# =============================================================================


class TestActiveJobsQuery:
    """Test querying for active jobs."""

    @pytest.mark.asyncio
    async def test_get_active_jobs_returns_pending_and_running(
        self, job_tracker: JobTracker
    ) -> None:
        """Test that get_active_jobs returns only pending and running jobs."""
        # Create jobs in different states
        pending_id = _unique_job_id("pending")
        running_id = _unique_job_id("running")
        completed_id = _unique_job_id("completed")
        failed_id = _unique_job_id("failed")

        job_tracker.create_job("test_job", job_id=pending_id)

        job_tracker.create_job("test_job", job_id=running_id)
        job_tracker.start_job(running_id)

        job_tracker.create_job("test_job", job_id=completed_id)
        job_tracker.start_job(completed_id)
        job_tracker.complete_job(completed_id)

        job_tracker.create_job("test_job", job_id=failed_id)
        job_tracker.start_job(failed_id)
        job_tracker.fail_job(failed_id, "error")

        # Get active jobs
        active_jobs = job_tracker.get_active_jobs()

        # Should only return pending and running
        assert len(active_jobs) == 2
        active_ids = {job["job_id"] for job in active_jobs}
        assert pending_id in active_ids
        assert running_id in active_ids
        assert completed_id not in active_ids
        assert failed_id not in active_ids

    @pytest.mark.asyncio
    async def test_get_active_jobs_empty_when_all_complete(self, job_tracker: JobTracker) -> None:
        """Test that get_active_jobs returns empty list when all jobs complete."""
        # Create and complete jobs
        for i in range(3):
            job_id = _unique_job_id(f"job_{i}")
            job_tracker.create_job("test_job", job_id=job_id)
            job_tracker.start_job(job_id)
            job_tracker.complete_job(job_id)

        # Should be no active jobs
        active_jobs = job_tracker.get_active_jobs()
        assert len(active_jobs) == 0


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestJobCleanup:
    """Test cleanup of completed jobs."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_completed_and_failed_jobs(self, job_tracker: JobTracker) -> None:
        """Test that cleanup removes completed and failed jobs."""
        # Create jobs in different states
        pending_id = _unique_job_id("pending")
        running_id = _unique_job_id("running")
        completed_id = _unique_job_id("completed")
        failed_id = _unique_job_id("failed")

        job_tracker.create_job("test_job", job_id=pending_id)

        job_tracker.create_job("test_job", job_id=running_id)
        job_tracker.start_job(running_id)

        job_tracker.create_job("test_job", job_id=completed_id)
        job_tracker.start_job(completed_id)
        job_tracker.complete_job(completed_id)

        job_tracker.create_job("test_job", job_id=failed_id)
        job_tracker.start_job(failed_id)
        job_tracker.fail_job(failed_id, "error")

        # Cleanup
        removed_count = job_tracker.cleanup_completed_jobs()

        # Should remove completed and failed (2 jobs)
        assert removed_count == 2

        # Active jobs should remain
        assert job_tracker.get_job(pending_id) is not None
        assert job_tracker.get_job(running_id) is not None

        # Completed jobs should be gone
        assert job_tracker.get_job(completed_id) is None
        assert job_tracker.get_job(failed_id) is None

    @pytest.mark.asyncio
    async def test_cleanup_with_no_completed_jobs(self, job_tracker: JobTracker) -> None:
        """Test cleanup when there are no completed jobs."""
        # Create only active jobs
        job_id = _unique_job_id()
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Cleanup should remove nothing
        removed_count = job_tracker.cleanup_completed_jobs()
        assert removed_count == 0

        # Job should still exist
        assert job_tracker.get_job(job_id) is not None


# =============================================================================
# Progress Clamping Tests
# =============================================================================


class TestProgressClamping:
    """Test progress value clamping behavior."""

    @pytest.mark.asyncio
    async def test_progress_clamped_to_zero(self, job_tracker: JobTracker) -> None:
        """Test that negative progress values are clamped to 0."""
        job_id = _unique_job_id()
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Try to set negative progress
        job_tracker.update_progress(job_id, -50)

        job = job_tracker.get_job(job_id)
        assert job["progress"] == 0

    @pytest.mark.asyncio
    async def test_progress_clamped_to_one_hundred(self, job_tracker: JobTracker) -> None:
        """Test that progress values over 100 are clamped to 100."""
        job_id = _unique_job_id()
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Try to set progress over 100
        job_tracker.update_progress(job_id, 150)

        job = job_tracker.get_job(job_id)
        assert job["progress"] == 100


# =============================================================================
# Broadcast Throttling Edge Cases
# =============================================================================


class TestBroadcastThrottlingEdgeCases:
    """Test edge cases in progress broadcast throttling."""

    @pytest.mark.asyncio
    async def test_progress_at_exact_threshold_broadcasts(self, broadcast_spy: AsyncMock) -> None:
        """Test that progress at exact threshold values broadcasts."""
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Update to exact thresholds
        for threshold in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            job_tracker.update_progress(job_id, threshold)

        # Wait for broadcasts
        await asyncio.sleep(0.1)

        # Should broadcast for each threshold
        progress_broadcasts = [
            call for call in broadcast_spy.calls if call[0] == JobEventType.JOB_PROGRESS
        ]
        assert len(progress_broadcasts) == 10

    @pytest.mark.asyncio
    async def test_progress_between_thresholds_does_not_broadcast(
        self, broadcast_spy: AsyncMock
    ) -> None:
        """Test that progress updates between thresholds do not broadcast."""
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Update with values between thresholds (1-9, all in first bucket)
        for progress in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            job_tracker.update_progress(job_id, progress)

        # Wait for broadcasts
        await asyncio.sleep(0.1)

        # Should not broadcast any progress updates (no threshold crossed)
        progress_broadcasts = [
            call for call in broadcast_spy.calls if call[0] == JobEventType.JOB_PROGRESS
        ]
        assert len(progress_broadcasts) == 0

    @pytest.mark.asyncio
    async def test_progress_backwards_does_not_broadcast(self, broadcast_spy: AsyncMock) -> None:
        """Test that progress moving backwards doesn't trigger new broadcasts.

        The throttling logic only broadcasts when crossing NEW thresholds upward.
        Once a threshold is crossed, the last_broadcast_progress is updated,
        and moving backwards doesn't reset it, so no new broadcasts occur.
        """
        job_tracker = JobTracker(broadcast_callback=broadcast_spy)
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        # Progress forward to 50 - should broadcast at 10, 20, 30, 40, 50
        job_tracker.update_progress(job_id, 50)

        # Wait for broadcasts
        await asyncio.sleep(0.1)

        # Clear previous broadcasts
        initial_count = len(broadcast_spy.calls)

        # Progress backward to 25 - should NOT broadcast (threshold 20 already crossed)
        job_tracker.update_progress(job_id, 25)

        # Wait for any broadcasts
        await asyncio.sleep(0.1)

        # Should not have any new broadcasts
        final_count = len(broadcast_spy.calls)
        assert final_count == initial_count  # No new broadcasts


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestSingletonPattern:
    """Test the singleton pattern for job tracker."""

    @pytest.mark.asyncio
    async def test_get_job_tracker_returns_singleton(self) -> None:
        """Test that get_job_tracker returns the same instance."""
        from backend.services.job_tracker import get_job_tracker

        reset_job_tracker()

        tracker1 = get_job_tracker()
        tracker2 = get_job_tracker()

        assert tracker1 is tracker2

    @pytest.mark.asyncio
    async def test_reset_job_tracker_clears_singleton(self) -> None:
        """Test that reset_job_tracker clears the singleton."""
        from backend.services.job_tracker import get_job_tracker

        tracker1 = get_job_tracker()
        job_id = _unique_job_id()
        tracker1.create_job("test_job", job_id=job_id)

        # Reset singleton
        reset_job_tracker()

        # New instance should be created
        tracker2 = get_job_tracker()
        assert tracker2 is not tracker1

        # Old job should not exist in new instance
        assert tracker2.get_job(job_id) is None


# =============================================================================
# Job Cancellation Tests (NEM-1974)
# =============================================================================


class TestJobCancellation:
    """Test job cancellation and is_cancelled method (NEM-1974)."""

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_active_job(self, job_tracker: JobTracker) -> None:
        """Test that is_cancelled returns False for active (pending/running) jobs."""
        job_id = _unique_job_id()

        # Pending job
        job_tracker.create_job("test_job", job_id=job_id)
        assert job_tracker.is_cancelled(job_id) is False

        # Running job
        job_tracker.start_job(job_id)
        assert job_tracker.is_cancelled(job_id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_completed_job(
        self, job_tracker: JobTracker
    ) -> None:
        """Test that is_cancelled returns False for completed jobs."""
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)
        job_tracker.complete_job(job_id)

        assert job_tracker.is_cancelled(job_id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_failed_job_with_error(
        self, job_tracker: JobTracker
    ) -> None:
        """Test that is_cancelled returns False for jobs that failed with an error."""
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)
        job_tracker.fail_job(job_id, "Database connection error")

        assert job_tracker.is_cancelled(job_id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_true_for_cancelled_job(
        self, job_tracker: JobTracker
    ) -> None:
        """Test that is_cancelled returns True for cancelled jobs."""
        job_id = _unique_job_id()

        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)
        job_tracker.cancel_job(job_id)

        assert job_tracker.is_cancelled(job_id) is True

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_for_unknown_job(
        self, job_tracker: JobTracker
    ) -> None:
        """Test that is_cancelled returns False for non-existent jobs."""
        unknown_id = _unique_job_id()
        assert job_tracker.is_cancelled(unknown_id) is False

    @pytest.mark.asyncio
    async def test_cancel_job_during_lifecycle(self, job_tracker: JobTracker) -> None:
        """Test cancellation during job lifecycle transitions."""
        job_id = _unique_job_id()

        # Create job
        job_tracker.create_job("test_job", job_id=job_id)
        assert job_tracker.is_cancelled(job_id) is False

        # Cancel before starting
        job_tracker.cancel_job(job_id)
        assert job_tracker.is_cancelled(job_id) is True

        # Job should have failed status
        job = job_tracker.get_job(job_id)
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Cancelled by user"

    @pytest.mark.asyncio
    async def test_concurrent_cancellation_check(self, job_tracker: JobTracker) -> None:
        """Test checking cancellation from multiple async tasks concurrently."""
        job_id = _unique_job_id()
        job_tracker.create_job("test_job", job_id=job_id)
        job_tracker.start_job(job_id)

        check_results = []

        async def check_cancelled() -> bool:
            result = job_tracker.is_cancelled(job_id)
            check_results.append(result)
            return result

        # Check cancellation concurrently multiple times
        results_before = await asyncio.gather(*[check_cancelled() for _ in range(10)])

        # All should return False before cancellation
        assert all(r is False for r in results_before)

        # Now cancel
        job_tracker.cancel_job(job_id)

        # Clear results
        check_results.clear()

        # Check again concurrently
        results_after = await asyncio.gather(*[check_cancelled() for _ in range(10)])

        # All should return True after cancellation
        assert all(r is True for r in results_after)
