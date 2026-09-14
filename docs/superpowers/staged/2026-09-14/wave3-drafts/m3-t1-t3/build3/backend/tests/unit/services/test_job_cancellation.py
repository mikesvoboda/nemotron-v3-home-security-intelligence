"""Tests for job cancellation and abortion functionality (NEM-2393).

Tests the cancel_queued_job and abort_job methods of JobTracker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.job_tracker import (
    JobEventType,
    JobStatus,
    JobTracker,
    reset_job_tracker,
)


@pytest.fixture
def mock_broadcast_callback() -> MagicMock:
    """Create a mock broadcast callback."""
    return MagicMock()


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def job_tracker(mock_broadcast_callback: MagicMock) -> JobTracker:
    """Create a job tracker with mock broadcast callback."""
    return JobTracker(broadcast_callback=mock_broadcast_callback)


@pytest.fixture
def job_tracker_with_redis(
    mock_broadcast_callback: MagicMock,
    mock_redis_client: AsyncMock,
) -> JobTracker:
    """Create a job tracker with mock broadcast callback and Redis client."""
    return JobTracker(
        broadcast_callback=mock_broadcast_callback,
        redis_client=mock_redis_client,
    )


@pytest.fixture(autouse=True)
def cleanup_singleton() -> None:
    """Reset the job tracker singleton after each test."""
    yield
    reset_job_tracker()


class TestCancelQueuedJob:
    """Tests for cancel_queued_job method."""

    def test_cancel_pending_job_succeeds(self, job_tracker: JobTracker) -> None:
        """Should successfully cancel a pending job."""
        job_id = job_tracker.create_job("export")

        success, error_msg = job_tracker.cancel_queued_job(job_id)

        assert success is True
        assert error_msg == ""

        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Cancelled by user"
        assert job["message"] == "Job cancelled by user request"
        assert job["completed_at"] is not None

    def test_cancel_running_job_fails(self, job_tracker: JobTracker) -> None:
        """Should fail to cancel a running job with helpful error."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        success, error_msg = job_tracker.cancel_queued_job(job_id)

        assert success is False
        assert "Cannot cancel running job" in error_msg
        assert "use abort instead" in error_msg

        # Job should still be running
        job = job_tracker.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.RUNNING

    def test_cancel_completed_job_fails(self, job_tracker: JobTracker) -> None:
        """Should fail to cancel a completed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.complete_job(job_id)

        success, error_msg = job_tracker.cancel_queued_job(job_id)

        assert success is False
        assert "completed" in error_msg

    def test_cancel_failed_job_fails(self, job_tracker: JobTracker) -> None:
        """Should fail to cancel a failed job."""
        job_id = job_tracker.create_job("export")
        job_tracker.fail_job(job_id, "Some error")

        success, error_msg = job_tracker.cancel_queued_job(job_id)

        assert success is False
        assert "failed" in error_msg

    def test_cancel_unknown_job_raises(self, job_tracker: JobTracker) -> None:
        """Should raise KeyError for unknown job."""
        with pytest.raises(KeyError, match="Job not found"):
            job_tracker.cancel_queued_job("unknown-id")

    def test_cancel_broadcasts_failure_event(
        self, job_tracker: JobTracker, mock_broadcast_callback: MagicMock
    ) -> None:
        """Should broadcast a failure event when job is cancelled."""
        job_id = job_tracker.create_job("export")

        job_tracker.cancel_queued_job(job_id)

        mock_broadcast_callback.assert_called()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == JobEventType.JOB_FAILED
        assert call_args[0][1]["data"]["job_id"] == job_id
        assert call_args[0][1]["data"]["error"] == "Cancelled by user"


class TestAbortJob:
    """Tests for abort_job method."""

    @pytest.mark.asyncio
    async def test_abort_running_job_succeeds(self, job_tracker_with_redis: JobTracker) -> None:
        """Should successfully abort a running job."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is True
        assert error_msg == ""

        # Job should still be running but with aborting message
        job = job_tracker_with_redis.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.RUNNING
        assert "Aborting" in job["message"]

    @pytest.mark.asyncio
    async def test_abort_sends_redis_pubsub_signal(
        self,
        job_tracker_with_redis: JobTracker,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Should send abort signal via Redis pub/sub."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        await job_tracker_with_redis.abort_job(job_id, reason="Test abort")

        # Verify Redis publish was called with correct channel and message
        mock_redis_client.publish.assert_called_once()
        call_args = mock_redis_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]

        assert channel == f"job:{job_id}:control"
        assert '"action": "abort"' in message
        assert '"reason": "Test abort"' in message

    @pytest.mark.asyncio
    async def test_abort_pending_job_fails(self, job_tracker_with_redis: JobTracker) -> None:
        """Should fail to abort a pending job with helpful error."""
        job_id = job_tracker_with_redis.create_job("export")

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "Cannot abort queued job" in error_msg
        assert "use cancel instead" in error_msg

    @pytest.mark.asyncio
    async def test_abort_completed_job_fails(self, job_tracker_with_redis: JobTracker) -> None:
        """Should fail to abort a completed job."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.complete_job(job_id)

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "completed" in error_msg

    @pytest.mark.asyncio
    async def test_abort_failed_job_fails(self, job_tracker_with_redis: JobTracker) -> None:
        """Should fail to abort a failed job."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.fail_job(job_id, "Error")

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "failed" in error_msg

    @pytest.mark.asyncio
    async def test_abort_unknown_job_raises(self, job_tracker_with_redis: JobTracker) -> None:
        """Should raise KeyError for unknown job."""
        with pytest.raises(KeyError, match="Job not found"):
            await job_tracker_with_redis.abort_job("unknown-id")

    @pytest.mark.asyncio
    async def test_abort_without_redis_client_logs_warning(
        self,
        job_tracker: JobTracker,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log warning but succeed when no Redis client is available."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        # Tracker without Redis client
        success, _error_msg = await job_tracker.abort_job(job_id)

        assert success is True
        assert "No Redis client" in caplog.text

    @pytest.mark.asyncio
    async def test_abort_with_redis_error_returns_failure(
        self,
        job_tracker_with_redis: JobTracker,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Should return failure when Redis publish fails."""
        mock_redis_client.publish.side_effect = Exception("Redis connection failed")

        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "Failed to send abort signal" in error_msg


class TestGetJobStatusString:
    """Tests for get_job_status_string helper method."""

    def test_returns_status_for_existing_job(self, job_tracker: JobTracker) -> None:
        """Should return status string for existing job."""
        job_id = job_tracker.create_job("export")

        status = job_tracker.get_job_status_string(job_id)

        assert status == "pending"

    def test_returns_running_status(self, job_tracker: JobTracker) -> None:
        """Should return running status after job starts."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        status = job_tracker.get_job_status_string(job_id)

        assert status == "running"

    def test_returns_none_for_unknown_job(self, job_tracker: JobTracker) -> None:
        """Should return None for unknown job."""
        status = job_tracker.get_job_status_string("unknown-id")

        assert status is None


class TestIsCancelledWithNewMethods:
    """Tests for is_cancelled with new cancellation methods."""

    def test_is_cancelled_true_after_cancel_queued_job(self, job_tracker: JobTracker) -> None:
        """Should return True after cancel_queued_job is called."""
        job_id = job_tracker.create_job("export")
        job_tracker.cancel_queued_job(job_id)

        assert job_tracker.is_cancelled(job_id) is True

    def test_is_cancelled_false_for_running_job(self, job_tracker: JobTracker) -> None:
        """Should return False for running job (not yet aborted)."""
        job_id = job_tracker.create_job("export")
        job_tracker.start_job(job_id)

        assert job_tracker.is_cancelled(job_id) is False

    @pytest.mark.asyncio
    async def test_is_cancelled_false_after_abort_signal(
        self, job_tracker_with_redis: JobTracker
    ) -> None:
        """Should return False after abort signal (job still running)."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)
        await job_tracker_with_redis.abort_job(job_id)

        # Job is still running, waiting for worker to acknowledge
        assert job_tracker_with_redis.is_cancelled(job_id) is False
