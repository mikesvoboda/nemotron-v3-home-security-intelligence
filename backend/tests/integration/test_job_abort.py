"""Integration tests for job cancellation and abortion (NEM-2393).

Tests the job cancellation and abort methods with real Redis.
"""

from __future__ import annotations

import json

import pytest

from backend.core.redis import RedisClient
from backend.services.job_tracker import JobStatus, JobTracker, reset_job_tracker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
async def cleanup_job_tracker():
    """Reset job tracker singleton before and after each test."""
    reset_job_tracker()
    yield
    reset_job_tracker()


@pytest.fixture
def job_tracker_with_redis(real_redis: RedisClient) -> JobTracker:
    """Create a job tracker with real Redis."""
    tracker = JobTracker(redis_client=real_redis)
    return tracker


class TestCancelQueuedJobWithRedis:
    """Integration tests for cancel_queued_job with real Redis."""

    async def test_cancel_pending_job_with_redis(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should successfully cancel a pending job with Redis persistence."""
        job_id = job_tracker_with_redis.create_job("export")

        success, error_msg = job_tracker_with_redis.cancel_queued_job(job_id)

        assert success is True
        assert error_msg == ""

        job = job_tracker_with_redis.get_job(job_id)
        assert job is not None
        assert job["status"] == JobStatus.FAILED
        assert job["error"] == "Cancelled by user"

    async def test_cancel_running_job_fails_with_redis(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should fail to cancel a running job."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        success, error_msg = job_tracker_with_redis.cancel_queued_job(job_id)

        assert success is False
        assert "Cannot cancel running job" in error_msg

        # Job should still be running
        job = job_tracker_with_redis.get_job(job_id)
        assert job["status"] == JobStatus.RUNNING


class TestAbortJobWithRedis:
    """Integration tests for abort_job with real Redis."""

    async def test_abort_running_job_with_redis(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should successfully abort a running job with Redis pub/sub."""
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

    async def test_abort_pending_job_fails_with_redis(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should fail to abort a pending job."""
        job_id = job_tracker_with_redis.create_job("export")

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "use cancel instead" in error_msg

    async def test_abort_completed_job_fails_with_redis(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should fail to abort a completed job."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.complete_job(job_id)

        success, error_msg = await job_tracker_with_redis.abort_job(job_id)

        assert success is False
        assert "completed" in error_msg


class TestAbortJobRedisPubSub:
    """Integration tests for Redis pub/sub abort signaling."""

    async def test_abort_publishes_to_correct_channel(
        self,
        job_tracker_with_redis: JobTracker,
        real_redis: RedisClient,
    ) -> None:
        """Should publish abort message to job-specific control channel."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        # Subscribe to the control channel before abort
        pubsub = real_redis._client.pubsub()
        await pubsub.subscribe(f"job:{job_id}:control")

        # Abort the job
        success, _ = await job_tracker_with_redis.abort_job(job_id, reason="Test abort")
        assert success is True

        # Read the abort message from pubsub
        # First message is subscription confirmation
        msg = await pubsub.get_message(timeout=1.0)
        assert msg is not None
        assert msg["type"] == "subscribe"

        # Second message is the abort signal
        msg = await pubsub.get_message(timeout=1.0)
        assert msg is not None
        assert msg["type"] == "message"
        assert msg["channel"].decode() == f"job:{job_id}:control"

        data = json.loads(msg["data"])
        assert data["action"] == "abort"
        assert data["reason"] == "Test abort"

        await pubsub.unsubscribe(f"job:{job_id}:control")
        await pubsub.close()

    async def test_abort_with_custom_reason(
        self,
        job_tracker_with_redis: JobTracker,
        real_redis: RedisClient,
    ) -> None:
        """Should include custom reason in abort message."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)

        # Subscribe first
        pubsub = real_redis._client.pubsub()
        await pubsub.subscribe(f"job:{job_id}:control")

        # Abort with custom reason
        success, _ = await job_tracker_with_redis.abort_job(job_id, reason="Resource exhausted")
        assert success is True

        # Skip subscription message
        await pubsub.get_message(timeout=1.0)

        # Get abort message
        msg = await pubsub.get_message(timeout=1.0)
        data = json.loads(msg["data"])
        assert data["reason"] == "Resource exhausted"

        # Job message should reflect the reason
        job = job_tracker_with_redis.get_job(job_id)
        assert "Resource exhausted" in job["message"]

        await pubsub.unsubscribe(f"job:{job_id}:control")
        await pubsub.close()


class TestBulkCancelWithRedis:
    """Integration tests for bulk cancel operations with real Redis."""

    async def test_bulk_cancel_multiple_pending_jobs(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should cancel multiple pending jobs."""
        job_ids = [
            job_tracker_with_redis.create_job("export"),
            job_tracker_with_redis.create_job("export"),
            job_tracker_with_redis.create_job("export"),
        ]

        cancelled_count = 0
        for job_id in job_ids:
            if job_tracker_with_redis.cancel_job(job_id):
                cancelled_count += 1

        assert cancelled_count == 3

        # Verify all jobs are cancelled
        for job_id in job_ids:
            job = job_tracker_with_redis.get_job(job_id)
            assert job["status"] == JobStatus.FAILED
            assert job["error"] == "Cancelled by user"

    async def test_bulk_cancel_mixed_states(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should handle mixed job states correctly."""
        # Create jobs in different states
        pending_job = job_tracker_with_redis.create_job("export")

        running_job = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(running_job)

        completed_job = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.complete_job(completed_job)

        # Try to cancel all
        results = {}
        for job_id in [pending_job, running_job, completed_job]:
            results[job_id] = job_tracker_with_redis.cancel_job(job_id)

        # Pending and running should be cancelled
        assert results[pending_job] is True
        assert results[running_job] is True
        # Completed cannot be cancelled
        assert results[completed_job] is False


class TestJobStatusTransitions:
    """Integration tests for job status transitions with Redis."""

    async def test_cancel_updates_timestamps(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should update completed_at timestamp on cancel."""
        job_id = job_tracker_with_redis.create_job("export")

        job_before = job_tracker_with_redis.get_job(job_id)
        assert job_before["completed_at"] is None

        job_tracker_with_redis.cancel_queued_job(job_id)

        job_after = job_tracker_with_redis.get_job(job_id)
        assert job_after["completed_at"] is not None

    async def test_abort_preserves_job_progress(
        self,
        job_tracker_with_redis: JobTracker,
    ) -> None:
        """Should preserve job progress when aborting."""
        job_id = job_tracker_with_redis.create_job("export")
        job_tracker_with_redis.start_job(job_id)
        job_tracker_with_redis.update_progress(job_id, 75)

        await job_tracker_with_redis.abort_job(job_id)

        job = job_tracker_with_redis.get_job(job_id)
        # Progress should be preserved
        assert job["progress"] == 75
        # But message should indicate aborting
        assert "Aborting" in job["message"]
