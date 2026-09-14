"""Job timeout detection and handling service.

This module provides timeout detection for running jobs, automatically
marking them as failed when they exceed their configured timeout.

Features:
- Per-job timeout configuration (timeout_seconds)
- Absolute deadline support (deadline timestamp)
- Automatic retry scheduling for timed-out jobs with remaining attempts
- Default timeouts by job type

Default Timeouts by Job Type:
    ai_analysis: 300 seconds (5 minutes)
    export: 1800 seconds (30 minutes)
    cleanup: 600 seconds (10 minutes)
    retention: 3600 seconds (1 hour)

Usage:
    service = JobTimeoutService(redis_client)

    # Check and handle all timed-out jobs
    timed_out_jobs = await service.check_for_timeouts()

    # Check if a specific job has timed out
    is_timed_out = await service.is_job_timed_out(job_id)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.job_status import (
    JOBS_ACTIVE_KEY,
    JobMetadata,
    JobState,
    JobStatusService,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


# Default timeouts by job type (in seconds)
JOB_TIMEOUTS: dict[str, int] = {
    "ai_analysis": 300,  # 5 minutes
    "export": 1800,  # 30 minutes
    "cleanup": 600,  # 10 minutes
    "retention": 3600,  # 1 hour
    "backup": 7200,  # 2 hours
}

# Default timeout for job types not in JOB_TIMEOUTS
# Note: This is now configurable via settings.default_job_timeout (NEM-2519)
DEFAULT_JOB_TIMEOUT = 600  # 10 minutes (default, use settings.default_job_timeout)

# Maximum retry attempts before permanent failure
DEFAULT_MAX_RETRY_ATTEMPTS = 3

# TTL for timeout config keys (in seconds)
# 48 hours: provides ample time for job lifecycle (max 2hr backup + 3 retries = 6hr)
# plus generous buffer for debugging while ensuring eventual cleanup
# This prevents unbounded memory growth from orphaned timeout config keys (NEM-2508)
TIMEOUT_CONFIG_TTL_SECONDS = 48 * 60 * 60  # 48 hours = 172800 seconds

# TTL for attempt counter keys (matches REDIS_JOB_TTL_SECONDS in job_tracker.py)
# This prevents unbounded memory growth from orphaned retry counters
ATTEMPT_COUNT_TTL_SECONDS = 3600  # 1 hour


@dataclass
class TimeoutConfig:
    """Configuration for job timeout.

    Attributes:
        timeout_seconds: Duration in seconds before job times out (optional)
        deadline: Absolute datetime by which job must complete (optional)
        max_retry_attempts: Maximum number of retry attempts (default: 3)

    At least one of timeout_seconds or deadline should be set.
    If both are set, the job times out when either condition is met.
    """

    timeout_seconds: int | None = None
    deadline: datetime | None = None
    max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "timeout_seconds": self.timeout_seconds,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "max_retry_attempts": self.max_retry_attempts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimeoutConfig:
        """Deserialize from dictionary."""
        deadline_str = data.get("deadline")
        deadline = datetime.fromisoformat(deadline_str) if deadline_str else None

        return cls(
            timeout_seconds=data.get("timeout_seconds"),
            deadline=deadline,
            max_retry_attempts=data.get("max_retry_attempts", DEFAULT_MAX_RETRY_ATTEMPTS),
        )


@dataclass
class TimeoutResult:
    """Result of handling a timed-out job.

    Attributes:
        job_id: The job that timed out
        job_type: Type of the job
        was_rescheduled: Whether the job was rescheduled for retry
        attempt_count: Current attempt number
        max_attempts: Maximum allowed attempts
        error_message: Error message set on the job
    """

    job_id: str
    job_type: str
    was_rescheduled: bool
    attempt_count: int
    max_attempts: int
    error_message: str


class JobTimeoutService:
    """Service for detecting and handling job timeouts.

    This service:
    - Monitors running jobs for timeout conditions
    - Marks timed-out jobs as failed
    - Reschedules jobs with remaining retry attempts
    - Supports both duration-based and deadline-based timeouts

    Redis Storage:
    - Timeout configs stored in job:{job_id}:timeout key
    - Attempt counts stored in job:{job_id}:attempts key
    """

    # Redis key suffixes
    TIMEOUT_CONFIG_SUFFIX = ":timeout"
    ATTEMPT_COUNT_SUFFIX = ":attempts"

    def __init__(
        self,
        redis_client: RedisClient,
        job_status_service: JobStatusService | None = None,
    ) -> None:
        """Initialize the job timeout service.

        Args:
            redis_client: Redis client for storage and retrieval.
            job_status_service: Optional job status service. If not provided,
                               a new instance will be created.
        """
        self._redis = redis_client
        self._job_status_service = job_status_service or JobStatusService(redis_client)

    def _get_timeout_key(self, job_id: str) -> str:
        """Get the Redis key for job timeout config."""
        return f"job:{job_id}{self.TIMEOUT_CONFIG_SUFFIX}"

    def _get_attempts_key(self, job_id: str) -> str:
        """Get the Redis key for job attempt count."""
        return f"job:{job_id}{self.ATTEMPT_COUNT_SUFFIX}"

    def get_default_timeout(self, job_type: str) -> int:
        """Get the default timeout for a job type.

        Args:
            job_type: The type of job.

        Returns:
            Default timeout in seconds.
        """
        return JOB_TIMEOUTS.get(job_type, DEFAULT_JOB_TIMEOUT)

    async def set_timeout_config(
        self,
        job_id: str,
        config: TimeoutConfig,
    ) -> None:
        """Set the timeout configuration for a job.

        The timeout config key is stored with a TTL to prevent unbounded memory
        growth from orphaned config keys for completed/abandoned jobs (NEM-2508).

        Args:
            job_id: The job ID.
            config: Timeout configuration.
        """
        key = self._get_timeout_key(job_id)
        await self._redis.set(key, config.to_dict(), expire=TIMEOUT_CONFIG_TTL_SECONDS)

        logger.debug(
            "Set timeout config for job",
            extra={
                "job_id": job_id,
                "timeout_seconds": config.timeout_seconds,
                "deadline": config.deadline.isoformat() if config.deadline else None,
                "ttl_seconds": TIMEOUT_CONFIG_TTL_SECONDS,
            },
        )

    async def get_timeout_config(self, job_id: str) -> TimeoutConfig | None:
        """Get the timeout configuration for a job.

        Args:
            job_id: The job ID.

        Returns:
            TimeoutConfig if set, None otherwise.
        """
        key = self._get_timeout_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            return None

        return TimeoutConfig.from_dict(data)

    async def get_attempt_count(self, job_id: str) -> int:
        """Get the current attempt count for a job.

        Args:
            job_id: The job ID.

        Returns:
            Current attempt count (0 if not set).
        """
        key = self._get_attempts_key(job_id)
        count = await self._redis.get(key)

        if count is None:
            return 0

        # Handle both int and string representations
        if isinstance(count, int):
            return count
        if isinstance(count, str):
            return int(count)
        if isinstance(count, dict) and "count" in count:
            return int(count["count"])
        return 0

    async def increment_attempt_count(self, job_id: str) -> int:
        """Increment the attempt count for a job.

        The attempt count key is stored with a TTL to prevent unbounded memory
        growth from orphaned retry counters for completed/abandoned jobs.

        Args:
            job_id: The job ID.

        Returns:
            New attempt count.
        """
        key = self._get_attempts_key(job_id)
        current = await self.get_attempt_count(job_id)
        new_count = current + 1
        await self._redis.set(key, {"count": new_count}, expire=ATTEMPT_COUNT_TTL_SECONDS)
        return new_count

    async def is_job_timed_out(
        self,
        job: JobMetadata,
        config: TimeoutConfig | None = None,
    ) -> bool:
        """Check if a job has timed out.

        Args:
            job: The job metadata.
            config: Optional timeout config. If not provided, will be fetched.

        Returns:
            True if the job has timed out.
        """
        # Only running jobs can time out
        if job.status != JobState.RUNNING:
            return False

        # Job must have a started_at time
        if job.started_at is None:
            return False

        # Get timeout config if not provided
        if config is None:
            config = await self.get_timeout_config(job.job_id)

        now = datetime.now(UTC)

        # Check timeout_seconds (duration since started_at)
        if config and config.timeout_seconds is not None:
            timeout_at = job.started_at + timedelta(seconds=config.timeout_seconds)
            if now >= timeout_at:
                return True

        # Check absolute deadline
        if config and config.deadline is not None:
            # Ensure deadline is timezone-aware
            deadline = config.deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            if now >= deadline:
                return True

        # If no explicit config, use default timeout based on job type
        if config is None or (config.timeout_seconds is None and config.deadline is None):
            default_timeout = self.get_default_timeout(job.job_type)
            timeout_at = job.started_at + timedelta(seconds=default_timeout)
            if now >= timeout_at:
                return True

        return False

    async def handle_timeout(self, job: JobMetadata) -> TimeoutResult:
        """Handle a timed-out job.

        This method:
        1. Marks the job as failed with timeout error
        2. Checks if retries are available
        3. If retries available, creates a new pending job for retry

        Args:
            job: The job that timed out.

        Returns:
            TimeoutResult with handling details.
        """
        config = await self.get_timeout_config(job.job_id)
        max_attempts = config.max_retry_attempts if config else DEFAULT_MAX_RETRY_ATTEMPTS

        current_attempts = await self.get_attempt_count(job.job_id)

        # Determine timeout duration for error message
        if config and config.timeout_seconds:
            timeout_msg = f"Job timed out after {config.timeout_seconds} seconds"
        elif config and config.deadline:
            timeout_msg = f"Job timed out (deadline: {config.deadline.isoformat()})"
        else:
            default_timeout = self.get_default_timeout(job.job_type)
            timeout_msg = f"Job timed out after {default_timeout} seconds (default timeout)"

        # Mark the current job as failed
        await self._job_status_service.fail_job(
            job_id=job.job_id,
            error=timeout_msg,
        )

        logger.warning(
            "Job timed out",
            extra={
                "job_id": job.job_id,
                "job_type": job.job_type,
                "attempt": current_attempts + 1,
                "max_attempts": max_attempts,
            },
        )

        # Check if we should retry
        was_rescheduled = False
        if current_attempts + 1 < max_attempts:
            # Increment attempt counter
            new_attempt = await self.increment_attempt_count(job.job_id)

            # Create a new job for retry with the same type
            # Note: In a real implementation, you might want to store and restore
            # the original job metadata for retry
            retry_job_id = await self._job_status_service.start_job(
                job_id=None,  # Generate new ID
                job_type=job.job_type,
                metadata={
                    "retry_of": job.job_id,
                    "attempt": new_attempt + 1,
                    "original_extra": job.extra,
                },
            )

            # Copy timeout config to new job
            if config:
                await self.set_timeout_config(retry_job_id, config)

            logger.info(
                "Job rescheduled for retry after timeout",
                extra={
                    "original_job_id": job.job_id,
                    "retry_job_id": retry_job_id,
                    "attempt": new_attempt + 1,
                    "max_attempts": max_attempts,
                },
            )

            was_rescheduled = True
        else:
            logger.error(
                "Job permanently failed after max timeout attempts",
                extra={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "attempts": current_attempts + 1,
                    "max_attempts": max_attempts,
                },
            )

        return TimeoutResult(
            job_id=job.job_id,
            job_type=job.job_type,
            was_rescheduled=was_rescheduled,
            attempt_count=current_attempts + 1,
            max_attempts=max_attempts,
            error_message=timeout_msg,
        )

    async def check_for_timeouts(self) -> list[TimeoutResult]:
        """Check all running jobs for timeouts and handle them.

        This method should be called periodically (e.g., every 30 seconds)
        to detect and handle stuck jobs.

        Returns:
            List of TimeoutResult for jobs that were handled.
        """
        results: list[TimeoutResult] = []

        # Get all active job IDs from the registry
        active_job_ids = await self._redis.zrangebyscore(
            JOBS_ACTIVE_KEY,
            "-inf",
            "+inf",
        )

        if not active_job_ids:
            return results

        logger.debug(
            "Checking for job timeouts",
            extra={"active_job_count": len(active_job_ids)},
        )

        # Check each active job
        for job_id in active_job_ids:
            try:
                job = await self._job_status_service.get_job_status(job_id)

                if job is None:
                    # Job might have been cleaned up
                    continue

                if await self.is_job_timed_out(job):
                    result = await self.handle_timeout(job)
                    results.append(result)

            except Exception as e:
                logger.error(
                    "Error checking job timeout",
                    extra={"job_id": job_id, "error": str(e)},
                )

        if results:
            logger.info(
                "Handled timed-out jobs",
                extra={
                    "timed_out_count": len(results),
                    "rescheduled_count": sum(1 for r in results if r.was_rescheduled),
                },
            )

        return results

    async def cleanup_timeout_data(self, job_id: str) -> None:
        """Clean up timeout-related data for a completed job.

        Args:
            job_id: The job ID to clean up.
        """
        timeout_key = self._get_timeout_key(job_id)
        attempts_key = self._get_attempts_key(job_id)

        await self._redis.delete(timeout_key)
        await self._redis.delete(attempts_key)

        logger.debug(
            "Cleaned up timeout data for job",
            extra={"job_id": job_id},
        )


# Module-level singleton
_job_timeout_service: JobTimeoutService | None = None


def get_job_timeout_service(redis_client: RedisClient) -> JobTimeoutService:
    """Get or create the singleton job timeout service instance.

    Args:
        redis_client: Redis client for storage.

    Returns:
        The job timeout service singleton.
    """
    global _job_timeout_service  # noqa: PLW0603
    if _job_timeout_service is None:
        _job_timeout_service = JobTimeoutService(redis_client)
    return _job_timeout_service


def reset_job_timeout_service() -> None:
    """Reset the job timeout service singleton. Used for testing."""
    global _job_timeout_service  # noqa: PLW0603
    _job_timeout_service = None
