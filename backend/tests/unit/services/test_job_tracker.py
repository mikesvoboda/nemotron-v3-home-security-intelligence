"""Tests for the job tracker service."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from backend.services.job_tracker import (
    PROGRESS_THROTTLE_INCREMENT,
    JobEventType,
    JobStatus,
    JobTracker,
    get_job_tracker,
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


class TestJobTrackerQueries:
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


class TestJobTrackerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_job_creation(self) -> None:
        """Should handle concurrent job creation."""
        tracker = JobTracker()
        job_ids: list[str] = []
        lock = threading.Lock()

        def create_job() -> None:
            job_id = tracker.create_job("export")
            with lock:
                job_ids.append(job_id)

        threads = [threading.Thread(target=create_job) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All jobs should be created with unique IDs
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10

    def test_concurrent_progress_updates(self) -> None:
        """Should handle concurrent progress updates."""
        tracker = JobTracker()
        job_id = tracker.create_job("export")

        def update_progress(progress: int) -> None:
            tracker.update_progress(job_id, progress)

        threads = [threading.Thread(target=update_progress, args=(i * 10,)) for i in range(1, 11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        job = tracker.get_job(job_id)
        assert job is not None
        # Final progress should be one of the valid values
        assert 0 <= job["progress"] <= 100
