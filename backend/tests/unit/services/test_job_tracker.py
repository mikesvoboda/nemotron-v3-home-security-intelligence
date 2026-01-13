"""Tests for the job tracker service."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.job_tracker import (
    PROGRESS_THROTTLE_INCREMENT,
    JobEventType,
    JobStatus,
    JobTracker,
    create_websocket_broadcast_callback,
    get_job_tracker,
    init_job_tracker_websocket,
    reset_job_tracker,
)


@pytest.fixture
def mock_broadcast_callback() -> MagicMock:
    """Create a mock broadcast callback."""
    return MagicMock()


@pytest.fixture
def job_tracker(mock_broadcast_callback: MagicMock) -> JobTracker:
    """Create a job tracker with mock broadcast callback."""
    return JobTracker(broadcast_callback=mock_broadcast_callback)


@pytest.fixture(autouse=True)
def cleanup_singleton() -> None:
    """Reset the job tracker singleton after each test."""
    yield
    reset_job_tracker()


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self) -> None:
        """Should have expected status values."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"


class TestJobEventType:
    """Tests for JobEventType enum."""

    def test_event_type_values(self) -> None:
        """Should have expected event type values."""
        assert JobEventType.JOB_PROGRESS == "job_progress"
        assert JobEventType.JOB_COMPLETED == "job_completed"
        assert JobEventType.JOB_FAILED == "job_failed"


class TestJobTrackerCreation:
    """Tests for job creation."""

    def test_create_job_returns_id(self, job_tracker: JobTracker) -> None:
        """Should return a job ID when creating a job."""
        job_id = job_tracker.create_job("export")
        assert job_id is not None
        assert isinstance(job_id, str)

    def test_create_job_with_custom_id(self, job_tracker: JobTracker) -> None:
        """Should use custom job ID when provided."""
        job_id = job_tracker.create_job("export", job_id="custom-123")
        assert job_id == "custom-123"

    def test_create_job_sets_pending_status(self, job_tracker: JobTracker) -> None:
        """Should set job status to PENDING on creation."""
        job_id = job_tracker.create_job("export")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.PENDING

    def test_create_job_sets_zero_progress(self, job_tracker: JobTracker) -> None:
        """Should set job progress to 0 on creation."""
        job_id = job_tracker.create_job("export")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["progress"] == 0

    def test_create_job_sets_job_type(self, job_tracker: JobTracker) -> None:
        """Should set job type correctly."""
        job_id = job_tracker.create_job("cleanup")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["job_type"] == "cleanup"

    def test_create_job_sets_timestamps(self, job_tracker: JobTracker) -> None:
        """Should set created_at timestamp."""
        job_id = job_tracker.create_job("backup")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["created_at"] is not None
        assert job["started_at"] is None
        assert job["completed_at"] is None


class TestJobTrackerStartJob:
    """Tests for starting jobs."""

    def test_start_job_sets_running_status(self, job_tracker: JobTracker) -> None:
        """Should set job status to RUNNING when started."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.RUNNING

    def test_start_job_sets_started_at(self, job_tracker: JobTracker) -> None:
        """Should set started_at timestamp when started."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["started_at"] is not None

    def test_start_job_unknown_id_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.start_job("unknown-id")


class TestJobTrackerProgress:
    """Tests for progress updates."""

    def test_update_progress_sets_value(self, job_tracker: JobTracker) -> None:
        """Should update job progress value."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job_tracker.update_progress(job_id, 50)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["progress"] == 50

    def test_update_progress_clamps_to_100(self, job_tracker: JobTracker) -> None:
        """Should clamp progress to 100."""
        job_id = job_tracker.create_job("export")
        job_tracker.update_progress(job_id, 150)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["progress"] == 100

    def test_update_progress_clamps_to_0(self, job_tracker: JobTracker) -> None:
        """Should clamp progress to 0."""
        job_id = job_tracker.create_job("export")
        job_tracker.update_progress(job_id, -10)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["progress"] == 0

    def test_update_progress_unknown_id_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.update_progress("unknown-id", 50)


class TestProgressThrottling:
    """Tests for progress broadcast throttling."""

    def test_throttle_increment_is_10(self) -> None:
        """Should have 10% throttle increment."""
        assert PROGRESS_THROTTLE_INCREMENT == 10

    def test_broadcasts_on_10_percent_threshold(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should broadcast when progress crosses 10% threshold."""
        job_id = job_tracker.create_job("export")
        job_tracker.update_progress(job_id, 10)

        mock_broadcast_callback.assert_called_once()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == JobEventType.JOB_PROGRESS

    def test_no_broadcast_within_threshold(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should not broadcast when progress stays within same 10% band."""
        job_id = job_tracker.create_job("export")
        job_tracker.update_progress(job_id, 5)

        mock_broadcast_callback.assert_not_called()

    def test_broadcasts_at_each_threshold(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should broadcast at each 10% threshold crossing."""
        job_id = job_tracker.create_job("export")

        # Progress: 0 -> 10 -> 20 -> 30
        job_tracker.update_progress(job_id, 10)
        job_tracker.update_progress(job_id, 20)
        job_tracker.update_progress(job_id, 30)

        assert mock_broadcast_callback.call_count == 3

    def test_no_duplicate_broadcast_same_threshold(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should not broadcast twice for same threshold."""
        job_id = job_tracker.create_job("export")

        # Cross 10% threshold
        job_tracker.update_progress(job_id, 10)
        # Stay within 10-19% band
        job_tracker.update_progress(job_id, 15)
        job_tracker.update_progress(job_id, 19)

        # Should only broadcast once (at 10)
        assert mock_broadcast_callback.call_count == 1


class TestJobTrackerCompletion:
    """Tests for job completion."""

    def test_complete_job_sets_completed_status(self, job_tracker: JobTracker) -> None:
        """Should set job status to COMPLETED."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job_tracker.complete_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.COMPLETED

    def test_complete_job_sets_progress_100(self, job_tracker: JobTracker) -> None:
        """Should set progress to 100 on completion."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job_tracker.complete_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["progress"] == 100

    def test_complete_job_sets_completed_at(self, job_tracker: JobTracker) -> None:
        """Should set completed_at timestamp."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["completed_at"] is not None

    def test_complete_job_stores_result(self, job_tracker: JobTracker) -> None:
        """Should store result data."""
        job_id = job_tracker.create_job("export")
        result = {"file_path": "/exports/test.json"}
        job_tracker.complete_job(job_id, result=result)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["result"] == result

    def test_complete_job_broadcasts(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should broadcast job completed event."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)

        mock_broadcast_callback.assert_called_once()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == JobEventType.JOB_COMPLETED
        assert call_args[0][1]["data"]["job_id"] == job_id

    def test_complete_job_unknown_id_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.complete_job("unknown-id")


class TestJobTrackerFailure:
    """Tests for job failure."""

    def test_fail_job_sets_failed_status(self, job_tracker: JobTracker) -> None:
        """Should set job status to FAILED."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Something went wrong")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED

    def test_fail_job_sets_completed_at(self, job_tracker: JobTracker) -> None:
        """Should set completed_at timestamp on failure."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Error")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["completed_at"] is not None

    def test_fail_job_stores_error(self, job_tracker: JobTracker) -> None:
        """Should store error message."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Database connection failed")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["error"] == "Database connection failed"

    def test_fail_job_broadcasts(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should broadcast job failed event."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Error message")

        mock_broadcast_callback.assert_called_once()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == JobEventType.JOB_FAILED
        assert call_args[0][1]["data"]["job_id"] == job_id
        assert call_args[0][1]["data"]["error"] == "Error message"

    def test_fail_job_unknown_id_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.fail_job("unknown-id", "Error")


class TestJobTrackerGetJob:
    """Tests for querying jobs."""

    def test_get_job_returns_none_for_unknown(self, job_tracker: JobTracker) -> None:
        """Should return None for unknown job ID."""
        job = job_tracker.get_job("unknown-id")
        assert job is None

    def test_get_active_jobs_returns_pending_and_running(self, job_tracker: JobTracker) -> None:
        """Should return pending and running jobs."""
        job1 = job_tracker.create_job("export")
        job2 = job_tracker.create_job("cleanup")
        job_tracker.start_job(job2)
        job3 = job_tracker.create_job("backup")
        job_tracker.complete_job(job3)

        active = job_tracker.get_active_jobs()
        active_ids = {j["job_id"] for j in active}

        assert job1 in active_ids  # pending
        assert job2 in active_ids  # running
        assert job3 not in active_ids  # completed

    def test_get_active_jobs_excludes_failed(self, job_tracker: JobTracker) -> None:
        """Should exclude failed jobs from active list."""
        job1 = job_tracker.create_job("export")
        job_tracker.fail_job(job1, "Error")

        active = job_tracker.get_active_jobs()
        assert len(active) == 0


class TestJobTrackerCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_removes_completed_jobs(self, job_tracker: JobTracker) -> None:
        """Should remove completed jobs."""
        job1 = job_tracker.create_job("export")
        job_tracker.complete_job(job1)

        removed = job_tracker.cleanup_completed_jobs()
        assert removed == 1
        assert job_tracker.get_job(job1) is None

    def test_cleanup_removes_failed_jobs(self, job_tracker: JobTracker) -> None:
        """Should remove failed jobs."""
        job1 = job_tracker.create_job("export")
        job_tracker.fail_job(job1, "Error")

        removed = job_tracker.cleanup_completed_jobs()
        assert removed == 1
        assert job_tracker.get_job(job1) is None

    def test_cleanup_keeps_active_jobs(self, job_tracker: JobTracker) -> None:
        """Should keep pending and running jobs."""
        job1 = job_tracker.create_job("export")  # pending
        job2 = job_tracker.create_job("cleanup")
        job_tracker.start_job(job2)  # running

        removed = job_tracker.cleanup_completed_jobs()
        assert removed == 0
        assert job_tracker.get_job(job1) is not None
        assert job_tracker.get_job(job2) is not None


class TestJobTrackerNoCallback:
    """Tests for job tracker without broadcast callback."""

    def test_operations_work_without_callback(self) -> None:
        """Should work when no broadcast callback is provided."""
        tracker = JobTracker(broadcast_callback=None)
        job_id = tracker.create_job("export")
        tracker.start_job(job_id)
        tracker.update_progress(job_id, 50)
        tracker.complete_job(job_id)

        job = tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.COMPLETED


class TestJobTrackerSingleton:
    """Tests for singleton management."""

    def test_get_job_tracker_returns_singleton(self) -> None:
        """Should return the same instance on repeated calls."""
        tracker1 = get_job_tracker()
        tracker2 = get_job_tracker()
        assert tracker1 is tracker2

    def test_reset_clears_singleton(self) -> None:
        """Should clear the singleton on reset."""
        tracker1 = get_job_tracker()
        reset_job_tracker()
        tracker2 = get_job_tracker()
        assert tracker1 is not tracker2


class TestJobTrackerAsyncSafety:
    """Tests for async safety with asyncio.Lock."""

    @pytest.mark.asyncio
    async def test_concurrent_job_creation(self) -> None:
        """Should handle concurrent job creation."""
        tracker = JobTracker()
        job_ids: list[str] = []

        async def create_job() -> None:
            job_id = tracker.create_job("export")
            job_ids.append(job_id)

        # Create jobs concurrently using asyncio
        await asyncio.gather(*[create_job() for _ in range(10)])

        # All jobs should be created with unique IDs
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10

    @pytest.mark.asyncio
    async def test_concurrent_progress_updates(self) -> None:
        """Should handle concurrent progress updates."""
        tracker = JobTracker()
        job_id = tracker.create_job("export")

        async def update_progress(progress: int) -> None:
            tracker.update_progress(job_id, progress)

        # Update progress concurrently using asyncio
        await asyncio.gather(*[update_progress(i * 10) for i in range(1, 11)])

        job = tracker.get_job(job_id)
        assert job is not None
        # Final progress should be one of the valid values
        assert 0 <= job["progress"] <= 100


class TestJobTrackerCancellation:
    """Tests for job cancellation checking (NEM-1974)."""

    def test_is_cancelled_returns_false_for_pending_job(self, job_tracker: JobTracker) -> None:
        """Should return False for pending job."""
        job_id = job_tracker.create_job("export")
        assert job_tracker.is_cancelled(job_id) is False

    def test_is_cancelled_returns_false_for_running_job(self, job_tracker: JobTracker) -> None:
        """Should return False for running job."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        assert job_tracker.is_cancelled(job_id) is False

    def test_is_cancelled_returns_false_for_completed_job(self, job_tracker: JobTracker) -> None:
        """Should return False for completed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)
        assert job_tracker.is_cancelled(job_id) is False

    def test_is_cancelled_returns_false_for_failed_job(self, job_tracker: JobTracker) -> None:
        """Should return False for job failed with error (not cancellation)."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Database error")
        assert job_tracker.is_cancelled(job_id) is False

    def test_is_cancelled_returns_true_for_cancelled_job(self, job_tracker: JobTracker) -> None:
        """Should return True for cancelled job."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job_tracker.cancel_job(job_id)
        assert job_tracker.is_cancelled(job_id) is True

    def test_is_cancelled_returns_false_for_unknown_job(self, job_tracker: JobTracker) -> None:
        """Should return False for unknown job ID."""
        assert job_tracker.is_cancelled("unknown-id") is False

    def test_is_cancelled_returns_true_for_cancelled_pending_job(
        self, job_tracker: JobTracker
    ) -> None:
        """Should return True for cancelled pending job."""
        job_id = job_tracker.create_job("export")
        # Cancel without starting
        job_tracker.cancel_job(job_id)
        assert job_tracker.is_cancelled(job_id) is True


class TestJobTrackerMessageField:
    """Tests for the message field (NEM-1989)."""

    def test_create_job_has_null_message(self, job_tracker: JobTracker) -> None:
        """Should have null message on creation."""
        job_id = job_tracker.create_job("export")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["message"] is None

    def test_start_job_with_message(self, job_tracker: JobTracker) -> None:
        """Should set message when starting job."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id, message="Starting export...")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["message"] == "Starting export..."

    def test_update_progress_with_message(self, job_tracker: JobTracker) -> None:
        """Should update message with progress."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)
        job_tracker.update_progress(job_id, 50, message="Processing 50/100 events")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["message"] == "Processing 50/100 events"

    def test_complete_job_sets_message(self, job_tracker: JobTracker) -> None:
        """Should set success message on completion."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["message"] == "Completed successfully"

    def test_fail_job_sets_message(self, job_tracker: JobTracker) -> None:
        """Should set failure message on fail."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Connection timeout")
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["message"] == "Failed: Connection timeout"


class TestJobTrackerBroadcastCallback:
    """Tests for broadcast callback functionality."""

    def test_set_broadcast_callback(self) -> None:
        """Should set broadcast callback after initialization."""
        tracker = JobTracker(broadcast_callback=None)
        callback = MagicMock()
        tracker.set_broadcast_callback(callback)

        # Verify callback is set by triggering a broadcast
        job_id = tracker.create_job("export")
        tracker.complete_job(job_id)

        callback.assert_called_once()

    def test_async_broadcast_callback_with_running_loop(self) -> None:
        """Should schedule async callback on running loop."""
        async_callback = AsyncMock()
        tracker = JobTracker(broadcast_callback=async_callback)

        async def test_job() -> None:
            job_id = tracker.create_job("export")
            tracker.complete_job(job_id)
            # Give the task time to be created
            await asyncio.sleep(0.01)
            # Verify the async callback was called
            async_callback.assert_called()

        asyncio.run(test_job())

    def test_async_broadcast_callback_no_running_loop(self) -> None:
        """Should handle async callback when no event loop is running."""

        # Create a coroutine function that returns a coroutine
        async def async_broadcast(event_type: str, data: dict) -> None:
            pass

        tracker = JobTracker(broadcast_callback=async_broadcast)

        # This should not raise even without a running loop
        job_id = tracker.create_job("export")
        tracker.complete_job(job_id)

    def test_broadcast_exception_handling(self) -> None:
        """Should handle exceptions in broadcast callback gracefully."""

        def failing_callback(event_type: str, data: dict) -> None:
            raise ValueError("Broadcast failed")

        tracker = JobTracker(broadcast_callback=failing_callback)

        # Should not raise exception
        job_id = tracker.create_job("export")
        tracker.complete_job(job_id)

        # Job should still be completed despite broadcast failure
        job = tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.COMPLETED


class TestJobTrackerRedisIntegration:
    """Tests for Redis persistence functionality."""

    @pytest.fixture
    def mock_redis_client(self) -> AsyncMock:
        """Create a mock Redis client."""
        return AsyncMock()

    def test_set_redis_client(self, mock_redis_client: AsyncMock) -> None:
        """Should set Redis client after initialization."""
        tracker = JobTracker()
        tracker.set_redis_client(mock_redis_client)

        assert tracker._redis_client is mock_redis_client

    @pytest.mark.asyncio
    async def test_persist_job_async(self, mock_redis_client: AsyncMock) -> None:
        """Should persist job to Redis."""
        tracker = JobTracker(redis_client=mock_redis_client)
        job_id = tracker.create_job("export")

        await tracker._persist_job_async(job_id)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == f"job:{job_id}"
        assert isinstance(call_args[0][1], dict)

    @pytest.mark.asyncio
    async def test_persist_job_async_with_ttl(self, mock_redis_client: AsyncMock) -> None:
        """Should persist job to Redis with TTL."""
        tracker = JobTracker(redis_client=mock_redis_client)
        job_id = tracker.create_job("export")

        await tracker._persist_job_async(job_id, ttl=3600)

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[1]["expire"] == 3600

    @pytest.mark.asyncio
    async def test_persist_job_async_handles_exception(self, mock_redis_client: AsyncMock) -> None:
        """Should handle Redis exceptions gracefully."""
        mock_redis_client.set.side_effect = Exception("Redis connection failed")
        tracker = JobTracker(redis_client=mock_redis_client)
        job_id = tracker.create_job("export")

        # Should not raise
        await tracker._persist_job_async(job_id)

    @pytest.mark.asyncio
    async def test_persist_job_async_nonexistent_job(self, mock_redis_client: AsyncMock) -> None:
        """Should handle nonexistent job gracefully."""
        tracker = JobTracker(redis_client=mock_redis_client)

        # Should not raise
        await tracker._persist_job_async("nonexistent-id")
        mock_redis_client.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_job_from_redis_in_memory_first(self, mock_redis_client: AsyncMock) -> None:
        """Should check in-memory cache before Redis."""
        tracker = JobTracker(redis_client=mock_redis_client)
        job_id = tracker.create_job("export")

        job = await tracker.get_job_from_redis(job_id)

        # Should return from memory without calling Redis
        mock_redis_client.get.assert_not_called()
        assert job is not None
        assert job["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_get_job_from_redis_fallback(self, mock_redis_client: AsyncMock) -> None:
        """Should fallback to Redis when not in memory."""
        tracker = JobTracker(redis_client=mock_redis_client)

        # Mock Redis response
        mock_redis_client.get.return_value = {
            "job_id": "test-123",
            "job_type": "export",
            "status": "completed",
            "progress": 100,
            "message": "Done",
            "created_at": "2024-01-01T00:00:00",
            "started_at": "2024-01-01T00:00:01",
            "completed_at": "2024-01-01T00:00:10",
            "result": {"count": 5},
            "error": None,
        }

        job = await tracker.get_job_from_redis("test-123")

        mock_redis_client.get.assert_called_once_with("job:test-123")
        assert job is not None
        assert job["job_id"] == "test-123"
        assert job["job_type"] == "export"
        assert job["status"] == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_job_from_redis_not_found(self, mock_redis_client: AsyncMock) -> None:
        """Should return None when job not found in Redis."""
        tracker = JobTracker(redis_client=mock_redis_client)
        mock_redis_client.get.return_value = None

        job = await tracker.get_job_from_redis("nonexistent")

        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_from_redis_no_client(self) -> None:
        """Should return None when no Redis client configured."""
        tracker = JobTracker()

        job = await tracker.get_job_from_redis("test-123")

        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_from_redis_handles_exception(self, mock_redis_client: AsyncMock) -> None:
        """Should handle Redis exceptions gracefully."""
        tracker = JobTracker(redis_client=mock_redis_client)
        mock_redis_client.get.side_effect = Exception("Redis error")

        job = await tracker.get_job_from_redis("test-123")

        assert job is None

    def test_schedule_persist_no_redis(self) -> None:
        """Should do nothing when no Redis client configured."""
        tracker = JobTracker()
        job_id = tracker.create_job("export")

        # Should not raise
        tracker._schedule_persist(job_id)

    def test_schedule_persist_with_event_loop(self, mock_redis_client: AsyncMock) -> None:
        """Should schedule persistence when event loop is available."""
        tracker = JobTracker(redis_client=mock_redis_client)

        async def test_schedule() -> None:
            job_id = tracker.create_job("export")
            tracker._schedule_persist(job_id)
            # Give the task time to be scheduled
            await asyncio.sleep(0.01)
            mock_redis_client.set.assert_called()

        asyncio.run(test_schedule())


class TestJobTrackerCancellationMethods:
    """Tests for job cancellation and abort methods."""

    def test_cancel_job_success(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should cancel a pending job."""
        job_id = job_tracker.create_job("export")

        result = job_tracker.cancel_job(job_id)

        assert result is True
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Cancelled by user"

        # Should broadcast failure event
        assert mock_broadcast_callback.call_count >= 1

    def test_cancel_job_running(self, job_tracker: JobTracker) -> None:
        """Should cancel a running job."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        result = job_tracker.cancel_job(job_id)

        assert result is True
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED

    def test_cancel_job_already_completed(self, job_tracker: JobTracker) -> None:
        """Should not cancel an already completed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)

        result = job_tracker.cancel_job(job_id)

        assert result is False
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.COMPLETED

    def test_cancel_job_already_failed(self, job_tracker: JobTracker) -> None:
        """Should not cancel an already failed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Previous error")

        result = job_tracker.cancel_job(job_id)

        assert result is False
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["error"] == "Previous error"

    def test_cancel_job_unknown_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.cancel_job("unknown-id")

    def test_cancel_queued_job_success(self, job_tracker: JobTracker) -> None:
        """Should cancel a queued (pending) job."""
        job_id = job_tracker.create_job("export")

        success, error = job_tracker.cancel_queued_job(job_id)

        assert success is True
        assert error == ""
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Cancelled by user"

    def test_cancel_queued_job_running_fails(self, job_tracker: JobTracker) -> None:
        """Should not cancel a running job via cancel_queued_job."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        success, error = job_tracker.cancel_queued_job(job_id)

        assert success is False
        assert "abort" in error
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.RUNNING

    def test_cancel_queued_job_completed_fails(self, job_tracker: JobTracker) -> None:
        """Should not cancel a completed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)

        success, error = job_tracker.cancel_queued_job(job_id)

        assert success is False
        assert "completed" in error

    def test_cancel_queued_job_unknown_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job ID."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.cancel_queued_job("unknown-id")

    @pytest.mark.asyncio
    async def test_abort_job_success(self) -> None:
        """Should abort a running job."""
        mock_redis = AsyncMock()
        tracker = JobTracker(redis_client=mock_redis)
        job_id = tracker.create_job("export")
        tracker.start_job(job_id)

        success, error = await tracker.abort_job(job_id, "User cancelled")

        assert success is True
        assert error == ""
        job = tracker.get_job(job_id)
        assert job is not None
        assert "Aborting" in job["message"]

        # Should publish abort signal
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == f"job:{job_id}:control"
        message = json.loads(call_args[0][1])
        assert message["action"] == "abort"
        assert message["reason"] == "User cancelled"

    @pytest.mark.asyncio
    async def test_abort_job_pending_fails(self) -> None:
        """Should not abort a pending job via abort_job."""
        mock_redis = AsyncMock()
        tracker = JobTracker(redis_client=mock_redis)
        job_id = tracker.create_job("export")

        success, error = await tracker.abort_job(job_id)

        assert success is False
        assert "cancel" in error
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_abort_job_completed_fails(self) -> None:
        """Should not abort a completed job."""
        mock_redis = AsyncMock()
        tracker = JobTracker(redis_client=mock_redis)
        job_id = tracker.create_job("export")
        tracker.complete_job(job_id)

        success, error = await tracker.abort_job(job_id)

        assert success is False
        assert "completed" in error

    @pytest.mark.asyncio
    async def test_abort_job_unknown_raises(self) -> None:
        """Should raise KeyError for unknown job ID."""
        mock_redis = AsyncMock()
        tracker = JobTracker(redis_client=mock_redis)

        with pytest.raises(KeyError, match="Job not found"):
            await tracker.abort_job("unknown-id")

    @pytest.mark.asyncio
    async def test_abort_job_no_redis(self) -> None:
        """Should handle abort when no Redis client configured."""
        tracker = JobTracker()
        job_id = tracker.create_job("export")
        tracker.start_job(job_id)

        success, _error = await tracker.abort_job(job_id)

        # Should still return success even without Redis
        assert success is True
        job = tracker.get_job(job_id)
        assert job is not None
        assert "Aborting" in job["message"]

    @pytest.mark.asyncio
    async def test_abort_job_redis_publish_fails(self) -> None:
        """Should handle Redis publish failure gracefully."""
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis error")
        tracker = JobTracker(redis_client=mock_redis)
        job_id = tracker.create_job("export")
        tracker.start_job(job_id)

        success, error = await tracker.abort_job(job_id)

        assert success is False
        assert "Redis error" in error


class TestJobTrackerQueries:
    """Tests for job query methods."""

    def test_get_all_jobs_no_filter(self, job_tracker: JobTracker) -> None:
        """Should return all jobs without filters."""
        job1 = job_tracker.create_job("export")
        job2 = job_tracker.create_job("cleanup")
        job3 = job_tracker.create_job("backup")

        jobs = job_tracker.get_all_jobs()

        assert len(jobs) == 3
        job_ids = {j["job_id"] for j in jobs}
        assert job1 in job_ids
        assert job2 in job_ids
        assert job3 in job_ids

    def test_get_all_jobs_filter_by_type(self, job_tracker: JobTracker) -> None:
        """Should filter jobs by type."""
        job1 = job_tracker.create_job("export")
        job_tracker.create_job("cleanup")
        job3 = job_tracker.create_job("export")

        jobs = job_tracker.get_all_jobs(job_type="export")

        assert len(jobs) == 2
        job_ids = {j["job_id"] for j in jobs}
        assert job1 in job_ids
        assert job3 in job_ids

    def test_get_all_jobs_filter_by_status(self, job_tracker: JobTracker) -> None:
        """Should filter jobs by status."""
        job1 = job_tracker.create_job("export")
        job2 = job_tracker.create_job("cleanup")
        job_tracker.start_job(job2)
        job3 = job_tracker.create_job("backup")
        job_tracker.complete_job(job3)

        jobs = job_tracker.get_all_jobs(status_filter=JobStatus.PENDING)

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job1

    def test_get_all_jobs_filter_by_type_and_status(self, job_tracker: JobTracker) -> None:
        """Should filter jobs by both type and status."""
        job1 = job_tracker.create_job("export")
        job2 = job_tracker.create_job("export")
        job_tracker.start_job(job2)
        job_tracker.create_job("cleanup")

        jobs = job_tracker.get_all_jobs(job_type="export", status_filter=JobStatus.PENDING)

        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job1

    def test_get_all_jobs_sorted_by_created_at(self, job_tracker: JobTracker) -> None:
        """Should return jobs sorted by created_at descending."""
        import time

        job1 = job_tracker.create_job("export")
        time.sleep(0.01)  # Ensure different timestamps
        job2 = job_tracker.create_job("cleanup")
        time.sleep(0.01)
        job3 = job_tracker.create_job("backup")

        jobs = job_tracker.get_all_jobs()

        # Most recent should be first
        assert jobs[0]["job_id"] == job3
        assert jobs[1]["job_id"] == job2
        assert jobs[2]["job_id"] == job1

    def test_get_job_status_string(self, job_tracker: JobTracker) -> None:
        """Should return job status as string."""
        job_id = job_tracker.create_job("export")

        status = job_tracker.get_job_status_string(job_id)

        assert status == "pending"

    def test_get_job_status_string_unknown(self, job_tracker: JobTracker) -> None:
        """Should return None for unknown job."""
        status = job_tracker.get_job_status_string("unknown-id")

        assert status is None


class TestJobTrackerWebSocketIntegration:
    """Tests for WebSocket broadcast integration."""

    @pytest.mark.asyncio
    async def test_create_websocket_broadcast_callback(self) -> None:
        """Should create a valid WebSocket broadcast callback."""
        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster"
        ) as mock_get_broadcaster:
            mock_broadcaster = AsyncMock()
            mock_get_broadcaster.return_value = mock_broadcaster

            callback = create_websocket_broadcast_callback()

            # Call the callback
            await callback(
                "job_completed", {"type": "job_completed", "data": {"job_id": "test-123"}}
            )

            # Should call broadcaster
            mock_broadcaster._send_to_local_clients.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_job_tracker_websocket(self) -> None:
        """Should initialize job tracker with WebSocket broadcasting."""
        mock_redis = AsyncMock()

        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster"
        ) as mock_get_broadcaster:
            mock_broadcaster = AsyncMock()
            mock_get_broadcaster.return_value = mock_broadcaster

            tracker = await init_job_tracker_websocket(redis_client=mock_redis)

            assert tracker._broadcast_callback is not None
            assert tracker._redis_client is mock_redis

    @pytest.mark.asyncio
    async def test_init_job_tracker_websocket_already_configured(self) -> None:
        """Should not override existing broadcast callback."""
        existing_callback = MagicMock()
        tracker = get_job_tracker()
        tracker.set_broadcast_callback(existing_callback)

        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster"
        ) as mock_get_broadcaster:
            mock_broadcaster = AsyncMock()
            mock_get_broadcaster.return_value = mock_broadcaster

            result = await init_job_tracker_websocket()

            # Should keep existing callback
            assert result._broadcast_callback is existing_callback
