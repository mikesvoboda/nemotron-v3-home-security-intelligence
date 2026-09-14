"""Integration tests for job status service.

These tests verify the JobStatusService works correctly with real Redis.
"""

from __future__ import annotations

import pytest

from backend.core.redis import RedisClient
from backend.services.job_status import JobState, JobStatusService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestJobStatusServiceIntegration:
    """Integration tests for JobStatusService with real Redis."""

    async def test_job_lifecycle_with_real_redis(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test complete job lifecycle: create -> start -> update -> complete."""
        service = JobStatusService(real_redis)
        job_type = f"{test_prefix}:export"

        # Start a new job
        job_id = await service.start_job(
            job_id=None,
            job_type=job_type,
            metadata={"format": "csv"},
        )
        assert job_id is not None

        # Verify job was created with pending state
        job = await service.get_job_status(job_id)
        assert job is not None
        assert job.status == JobState.PENDING
        assert job.job_type == job_type
        assert job.progress == 0
        assert job.extra == {"format": "csv"}

        # Update progress
        await service.update_progress(
            job_id=job_id,
            progress=50,
            message="Processing rows...",
        )

        job = await service.get_job_status(job_id)
        assert job is not None
        assert job.status == JobState.RUNNING
        assert job.progress == 50
        assert job.message == "Processing rows..."
        assert job.started_at is not None

        # Complete the job
        await service.complete_job(
            job_id=job_id,
            result={"rows_exported": 100},
        )

        job = await service.get_job_status(job_id)
        assert job is not None
        assert job.status == JobState.COMPLETED
        assert job.progress == 100
        assert job.result == {"rows_exported": 100}
        assert job.completed_at is not None

    async def test_job_failure_with_real_redis(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test job failure flow with real Redis."""
        service = JobStatusService(real_redis)
        job_type = f"{test_prefix}:backup"

        # Start a job
        job_id = await service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Update progress
        await service.update_progress(job_id=job_id, progress=25, message=None)

        # Fail the job
        await service.fail_job(
            job_id=job_id,
            error="Connection timeout",
        )

        job = await service.get_job_status(job_id)
        assert job is not None
        assert job.status == JobState.FAILED
        assert job.error == "Connection timeout"
        assert job.completed_at is not None

    async def test_list_jobs_with_real_redis(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test listing jobs with optional status filter."""
        service = JobStatusService(real_redis)
        job_type = f"{test_prefix}:cleanup"

        # Create multiple jobs
        job1 = await service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )
        job2 = await service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )
        job3 = await service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Complete one, fail one, leave one pending
        await service.update_progress(job_id=job1, progress=100, message=None)
        await service.complete_job(job_id=job1, result=None)

        await service.update_progress(job_id=job2, progress=50, message=None)
        await service.fail_job(job_id=job2, error="Test error")

        # List all jobs
        all_jobs = await service.list_jobs(status_filter=None, limit=100)
        job_ids = [j.job_id for j in all_jobs]
        assert job1 in job_ids
        assert job2 in job_ids
        assert job3 in job_ids

        # Filter by status
        completed_jobs = await service.list_jobs(status_filter=JobState.COMPLETED, limit=100)
        completed_ids = [j.job_id for j in completed_jobs]
        assert job1 in completed_ids
        assert job2 not in completed_ids
        assert job3 not in completed_ids

    async def test_nonexistent_job_returns_none(self, real_redis: RedisClient) -> None:
        """Test that getting a nonexistent job returns None."""
        service = JobStatusService(real_redis)

        job = await service.get_job_status("nonexistent-job-id")
        assert job is None

    async def test_update_nonexistent_job_raises_error(self, real_redis: RedisClient) -> None:
        """Test that updating a nonexistent job raises KeyError."""
        import pytest

        service = JobStatusService(real_redis)

        with pytest.raises(KeyError, match="Job not found"):
            await service.update_progress(
                job_id="nonexistent-job-id",
                progress=50,
                message=None,
            )
