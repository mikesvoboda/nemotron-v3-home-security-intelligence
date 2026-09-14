"""Integration tests for job timeout handling.

These tests verify the job timeout service works correctly with real Redis.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.core.redis import RedisClient
from backend.jobs.timeout_checker_job import TimeoutCheckerJob
from backend.services.job_status import JobState, JobStatusService
from backend.services.job_timeout_service import (
    JobTimeoutService,
    TimeoutConfig,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestJobTimeoutServiceIntegration:
    """Integration tests for JobTimeoutService with real Redis."""

    async def test_timeout_config_persistence(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test timeout config is persisted and retrieved correctly."""
        service = JobTimeoutService(real_redis)
        job_id = f"{test_prefix}:timeout-job-1"

        # Set config
        config = TimeoutConfig(
            timeout_seconds=300,
            deadline=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
            max_retry_attempts=5,
        )
        await service.set_timeout_config(job_id, config)

        # Retrieve config
        retrieved = await service.get_timeout_config(job_id)
        assert retrieved is not None
        assert retrieved.timeout_seconds == 300
        assert retrieved.deadline == datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
        assert retrieved.max_retry_attempts == 5

    async def test_attempt_count_persistence(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test attempt count is persisted and incremented correctly."""
        service = JobTimeoutService(real_redis)
        job_id = f"{test_prefix}:timeout-job-2"

        # Initial count should be 0
        count = await service.get_attempt_count(job_id)
        assert count == 0

        # Increment
        new_count = await service.increment_attempt_count(job_id)
        assert new_count == 1

        # Increment again
        new_count = await service.increment_attempt_count(job_id)
        assert new_count == 2

        # Verify persisted
        count = await service.get_attempt_count(job_id)
        assert count == 2

    async def test_job_times_out_and_is_marked_failed(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that a job times out and is marked as failed."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:ai_analysis"

        # Create a job
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Update progress to make it running
        await job_status_service.update_progress(
            job_id=job_id,
            progress=50,
            message="Processing...",
        )

        # Set a very short timeout that has already passed
        config = TimeoutConfig(
            timeout_seconds=0,  # 0 seconds = already timed out
            max_retry_attempts=1,  # Only one attempt allowed
        )
        await timeout_service.set_timeout_config(job_id, config)

        # Get job and check if timed out
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        is_timed_out = await timeout_service.is_job_timed_out(job, config)
        assert is_timed_out is True

        # Handle the timeout
        result = await timeout_service.handle_timeout(job)

        assert result.job_id == job_id
        assert result.was_rescheduled is False  # Only 1 attempt allowed
        assert "timed out" in result.error_message

        # Verify job is now failed
        updated_job = await job_status_service.get_job_status(job_id)
        assert updated_job is not None
        assert updated_job.status == JobState.FAILED
        assert "timed out" in (updated_job.error or "")

    async def test_timed_out_job_with_retries_gets_rescheduled(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that a timed-out job with remaining retries gets rescheduled."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:export"

        # Create a job
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata={"test": "data"},
        )

        # Update progress to make it running
        await job_status_service.update_progress(
            job_id=job_id,
            progress=25,
            message="Exporting...",
        )

        # Set a short timeout with 3 retries
        config = TimeoutConfig(
            timeout_seconds=0,  # Already timed out
            max_retry_attempts=3,
        )
        await timeout_service.set_timeout_config(job_id, config)

        # Handle the timeout
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        result = await timeout_service.handle_timeout(job)

        assert result.was_rescheduled is True
        assert result.attempt_count == 1
        assert result.max_attempts == 3

        # Original job should be failed
        original_job = await job_status_service.get_job_status(job_id)
        assert original_job is not None
        assert original_job.status == JobState.FAILED

    async def test_timed_out_job_at_max_attempts_stays_failed(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that a job at max attempts is not rescheduled."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:cleanup"

        # Create a job
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Update progress to make it running
        await job_status_service.update_progress(
            job_id=job_id,
            progress=75,
            message="Cleaning...",
        )

        # Set a short timeout with 3 retries
        config = TimeoutConfig(
            timeout_seconds=0,  # Already timed out
            max_retry_attempts=3,
        )
        await timeout_service.set_timeout_config(job_id, config)

        # Simulate already having 2 attempts (so this is the 3rd)
        await timeout_service.increment_attempt_count(job_id)
        await timeout_service.increment_attempt_count(job_id)

        # Handle the timeout
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        result = await timeout_service.handle_timeout(job)

        assert result.was_rescheduled is False
        assert result.attempt_count == 3  # This was the 3rd attempt
        assert result.max_attempts == 3

    async def test_custom_timeout_per_job_works(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that custom timeout per job is respected."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:ai_analysis"

        # Create two jobs with different timeouts
        job1_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )
        job2_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Make both running
        await job_status_service.update_progress(job1_id, 10, None)
        await job_status_service.update_progress(job2_id, 10, None)

        # Job 1: Short timeout (already expired)
        config1 = TimeoutConfig(timeout_seconds=0)
        await timeout_service.set_timeout_config(job1_id, config1)

        # Job 2: Long timeout (not expired)
        config2 = TimeoutConfig(timeout_seconds=3600)  # 1 hour
        await timeout_service.set_timeout_config(job2_id, config2)

        # Check timeouts
        job1 = await job_status_service.get_job_status(job1_id)
        job2 = await job_status_service.get_job_status(job2_id)
        assert job1 is not None
        assert job2 is not None

        is_timed_out_1 = await timeout_service.is_job_timed_out(job1, config1)
        is_timed_out_2 = await timeout_service.is_job_timed_out(job2, config2)

        assert is_timed_out_1 is True
        assert is_timed_out_2 is False

    async def test_deadline_absolute_time_timeout_works(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that absolute deadline timeout is respected."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:retention"

        # Create a job
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Make it running
        await job_status_service.update_progress(job_id, 50, "Retaining...")

        # Set a deadline that has already passed
        past_deadline = datetime.now(UTC) - timedelta(hours=1)
        config = TimeoutConfig(deadline=past_deadline)
        await timeout_service.set_timeout_config(job_id, config)

        # Check timeout
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        is_timed_out = await timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is True

    async def test_deadline_not_timed_out_before_deadline(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test that job is not timed out before deadline."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:backup"

        # Create a job
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )

        # Make it running
        await job_status_service.update_progress(job_id, 50, "Backing up...")

        # Set a deadline in the future
        future_deadline = datetime.now(UTC) + timedelta(hours=1)
        config = TimeoutConfig(deadline=future_deadline)
        await timeout_service.set_timeout_config(job_id, config)

        # Check timeout
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        is_timed_out = await timeout_service.is_job_timed_out(job, config)

        assert is_timed_out is False

    async def test_check_for_timeouts_batch_processing(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test batch processing of multiple timed-out jobs."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)

        job_type = f"{test_prefix}:export"

        # Create multiple jobs
        job_ids = []
        for i in range(3):
            job_id = await job_status_service.start_job(
                job_id=None,
                job_type=job_type,
                metadata={"index": i},
            )
            await job_status_service.update_progress(job_id, 50, f"Working on {i}")
            job_ids.append(job_id)

        # Set short timeouts on all of them
        for job_id in job_ids:
            config = TimeoutConfig(timeout_seconds=0, max_retry_attempts=1)
            await timeout_service.set_timeout_config(job_id, config)

        # Check for timeouts
        results = await timeout_service.check_for_timeouts()

        # Should have handled all 3 jobs
        handled_ids = {r.job_id for r in results}
        for job_id in job_ids:
            assert job_id in handled_ids

    async def test_cleanup_timeout_data(self, real_redis: RedisClient, test_prefix: str) -> None:
        """Test cleanup of timeout-related data."""
        service = JobTimeoutService(real_redis)
        job_id = f"{test_prefix}:cleanup-job"

        # Set up timeout data
        config = TimeoutConfig(timeout_seconds=300)
        await service.set_timeout_config(job_id, config)
        await service.increment_attempt_count(job_id)

        # Verify data exists
        assert await service.get_timeout_config(job_id) is not None
        assert await service.get_attempt_count(job_id) == 1

        # Clean up
        await service.cleanup_timeout_data(job_id)

        # Verify data is gone
        assert await service.get_timeout_config(job_id) is None
        assert await service.get_attempt_count(job_id) == 0


class TestTimeoutCheckerJobIntegration:
    """Integration tests for TimeoutCheckerJob with real Redis."""

    async def test_timeout_checker_run_once(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test running timeout checker once."""
        job_status_service = JobStatusService(real_redis)
        timeout_service = JobTimeoutService(real_redis, job_status_service)
        checker = TimeoutCheckerJob(
            redis_client=real_redis,
            timeout_service=timeout_service,
        )

        job_type = f"{test_prefix}:export"

        # Create a job that will timeout
        job_id = await job_status_service.start_job(
            job_id=None,
            job_type=job_type,
            metadata=None,
        )
        await job_status_service.update_progress(job_id, 50, "Working...")

        # Set it to timeout immediately
        config = TimeoutConfig(timeout_seconds=0, max_retry_attempts=1)
        await timeout_service.set_timeout_config(job_id, config)

        # Run the checker once
        count = await checker.run_once()

        assert count >= 1

        # Verify job is failed
        job = await job_status_service.get_job_status(job_id)
        assert job is not None
        assert job.status == JobState.FAILED

    async def test_timeout_checker_start_stop(
        self, real_redis: RedisClient, test_prefix: str
    ) -> None:
        """Test starting and stopping the timeout checker."""
        checker = TimeoutCheckerJob(
            redis_client=real_redis,
            check_interval=60,  # Long interval so it doesn't actually run
        )

        # Start
        await checker.start()
        assert checker.is_running is True

        # Stop
        await checker.stop()
        assert checker.is_running is False
