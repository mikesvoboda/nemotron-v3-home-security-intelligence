"""Job status tracking service for background jobs.

This module provides Redis-backed job status tracking for background jobs.
It tracks job state (queued, pending, running, completed, failed, cancelled),
progress percentage, metadata, and timestamps. Completed/failed/cancelled jobs
have TTL for auto-cleanup.

Redis Key Structure:
- job:{job_id}:status - JSON object containing job metadata
- job:status:list - Sorted set of job IDs by creation timestamp
- jobs:active - Sorted set of active job IDs (queued, pending, running)
- jobs:completed - Sorted set of completed job IDs (completed, failed, cancelled)

Features:
- Store job status (queued, pending, running, completed, failed, cancelled)
- Store job progress percentage (0-100)
- Store job metadata (start time, end time, error messages, custom data)
- TTL for completed/failed/cancelled jobs (auto-cleanup after 1 hour)
- List jobs with optional status filter and limit
- Job registry for tracking active and completed jobs
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Redis key prefixes
JOB_STATUS_KEY_PREFIX = "job:"
JOB_STATUS_SUFFIX = ":status"
JOB_STATUS_LIST_KEY = "job:status:list"

# Job registry keys (sets of job IDs by state)
JOBS_ACTIVE_KEY = "jobs:active"
JOBS_COMPLETED_KEY = "jobs:completed"

# TTL for completed/failed jobs (1 hour)
# Note: This is now configurable via settings.completed_job_ttl (NEM-2519)
DEFAULT_COMPLETED_JOB_TTL = 3600  # Default, use settings.completed_job_ttl

# Retention period for completed job entries in the sorted set (1 hour)
# This aligns with DEFAULT_COMPLETED_JOB_TTL for consistency
COMPLETED_JOB_RETENTION_SECONDS = 3600

# Stale threshold for active jobs (2 hours)
# Jobs that have been active for longer than this are likely orphaned
# due to process crashes and should be cleaned up
ACTIVE_JOB_STALE_THRESHOLD_SECONDS = 7200

# Maximum entries to keep in job:status:list sorted set (NEM-2510)
# This prevents unbounded growth of the job index.
# Individual job data has TTL for auto-cleanup, but the sorted set index
# entries remain until explicitly removed. This limit ensures memory stays bounded.
# 10,000 entries is sufficient for ~7 days of jobs at ~1 job/minute rate.
DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES = 10000


class JobState(StrEnum):
    """Status of a background job."""

    QUEUED = auto()
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class JobMetadata:
    """Metadata for a tracked job.

    Attributes:
        job_id: Unique job identifier
        job_type: Type of job (e.g., 'export', 'cleanup', 'backup')
        status: Current job state
        progress: Progress percentage (0-100)
        message: Optional status message
        created_at: Job creation timestamp
        started_at: Job start timestamp (when status became RUNNING)
        completed_at: Job completion timestamp (when status became COMPLETED/FAILED)
        result: Result data for completed jobs
        error: Error message for failed jobs
        extra: Additional metadata passed during job creation
    """

    job_id: str
    job_type: str
    status: JobState
    progress: int
    message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: Any | None
    error: str | None
    extra: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata to dictionary for Redis storage.

        Returns:
            Dictionary representation of the metadata.
        """
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": str(self.status),
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobMetadata:
        """Deserialize metadata from dictionary.

        Args:
            data: Dictionary containing job metadata.

        Returns:
            JobMetadata instance.
        """

        def parse_datetime(value: str | None) -> datetime | None:
            if value is None:
                return None
            return datetime.fromisoformat(value)

        return cls(
            job_id=data["job_id"],
            job_type=data["job_type"],
            status=JobState(data["status"]),
            progress=data["progress"],
            message=data.get("message"),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=parse_datetime(data.get("started_at")),
            completed_at=parse_datetime(data.get("completed_at")),
            result=data.get("result"),
            error=data.get("error"),
            extra=data.get("extra"),
        )


class JobStatusService:
    """Service for tracking background job status in Redis.

    This service provides methods for managing job lifecycle:
    - start_job: Create a new job with PENDING status
    - update_progress: Update job progress and optionally set to RUNNING
    - complete_job: Mark job as COMPLETED with optional result
    - fail_job: Mark job as FAILED with error message
    - get_job_status: Get current job metadata
    - list_jobs: List jobs with optional status filter

    Redis Storage:
    - Each job is stored as a JSON object at key job:status:{job_id}
    - A sorted set job:status:list maintains job IDs sorted by creation time
    - Completed/failed jobs have TTL for automatic cleanup
    """

    def __init__(
        self,
        redis_client: RedisClient,
        completed_job_ttl: int = DEFAULT_COMPLETED_JOB_TTL,
        job_status_list_max_entries: int = DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES,
    ) -> None:
        """Initialize the job status service.

        Args:
            redis_client: Redis client for storage.
            completed_job_ttl: TTL in seconds for completed/failed jobs.
                             Defaults to 3600 (1 hour).
            job_status_list_max_entries: Maximum entries to keep in job:status:list
                             sorted set. Defaults to 10000.
        """
        self._redis = redis_client
        self._completed_job_ttl = completed_job_ttl
        self._job_status_list_max_entries = job_status_list_max_entries

    def _get_job_key(self, job_id: str) -> str:
        """Get the Redis key for a job.

        Args:
            job_id: The job ID.

        Returns:
            Redis key string in format job:{job_id}:status.
        """
        return f"{JOB_STATUS_KEY_PREFIX}{job_id}{JOB_STATUS_SUFFIX}"

    async def _add_to_active_registry(self, job_id: str) -> None:
        """Add a job ID to the active jobs registry.

        Args:
            job_id: The job ID to add.
        """
        await self._redis.zadd(JOBS_ACTIVE_KEY, {job_id: datetime.now(UTC).timestamp()})

    async def _remove_from_active_registry(self, job_id: str) -> None:
        """Remove a job ID from the active jobs registry.

        Args:
            job_id: The job ID to remove.
        """
        await self._redis.zrem(JOBS_ACTIVE_KEY, job_id)

    async def _add_to_completed_registry(self, job_id: str) -> None:
        """Add a job ID to the completed jobs registry.

        Args:
            job_id: The job ID to add.
        """
        await self._redis.zadd(JOBS_COMPLETED_KEY, {job_id: datetime.now(UTC).timestamp()})

    async def get_active_job_ids(self, limit: int = 100) -> list[str]:
        """Get IDs of all active (queued, pending, running) jobs.

        Args:
            limit: Maximum number of job IDs to return.

        Returns:
            List of active job IDs, sorted by creation time (oldest first).
        """
        job_ids = await self._redis.zrangebyscore(
            JOBS_ACTIVE_KEY,
            "-inf",
            "+inf",
        )
        return job_ids[:limit] if job_ids else []

    async def get_completed_job_ids(self, limit: int = 100) -> list[str]:
        """Get IDs of all completed/failed/cancelled jobs.

        Args:
            limit: Maximum number of job IDs to return.

        Returns:
            List of completed job IDs, sorted by completion time (oldest first).
        """
        job_ids = await self._redis.zrangebyscore(
            JOBS_COMPLETED_KEY,
            "-inf",
            "+inf",
        )
        return job_ids[:limit] if job_ids else []

    async def cleanup_completed_jobs(
        self,
        retention_seconds: int = COMPLETED_JOB_RETENTION_SECONDS,
    ) -> int:
        """Remove completed job entries older than retention period from sorted set.

        The individual job status keys have their own TTL for auto-cleanup.
        This method cleans up the sorted set registry entries that track
        completed/failed/cancelled jobs to prevent unbounded growth.

        Args:
            retention_seconds: Remove entries older than this many seconds.
                Defaults to COMPLETED_JOB_RETENTION_SECONDS (1 hour).

        Returns:
            Number of entries removed from the sorted set.
        """
        import time

        cutoff_timestamp = time.time() - retention_seconds

        removed = await self._redis.zremrangebyscore(
            JOBS_COMPLETED_KEY,
            "-inf",
            cutoff_timestamp,
        )

        if removed > 0:
            logger.info(
                "Cleaned up old completed job entries",
                extra={"removed_count": removed, "retention_seconds": retention_seconds},
            )

        return removed

    async def cleanup_stale_active_jobs(
        self,
        stale_threshold_seconds: int = ACTIVE_JOB_STALE_THRESHOLD_SECONDS,
    ) -> int:
        """Remove stale entries from active jobs sorted set.

        Jobs that have been 'active' for longer than the threshold are likely
        orphaned due to process crashes and should be removed from the registry.
        This prevents the active jobs set from growing unbounded due to orphaned
        entries.

        Note: This only removes entries from the sorted set. The individual job
        status keys will expire via their TTL when the job is eventually completed
        or will remain as orphaned keys until manually cleaned up.

        Args:
            stale_threshold_seconds: Jobs active for longer than this are considered
                stale. Defaults to ACTIVE_JOB_STALE_THRESHOLD_SECONDS (2 hours).

        Returns:
            Number of entries removed from the sorted set.
        """
        import time

        cutoff_timestamp = time.time() - stale_threshold_seconds

        removed = await self._redis.zremrangebyscore(
            JOBS_ACTIVE_KEY,
            "-inf",
            cutoff_timestamp,
        )

        if removed > 0:
            logger.warning(
                "Removed stale active job entries (likely orphaned)",
                extra={
                    "removed_count": removed,
                    "stale_threshold_seconds": stale_threshold_seconds,
                },
            )

        return removed

    async def cleanup_job_status_list(
        self,
        max_entries: int | None = None,
    ) -> int:
        """Remove oldest entries from job:status:list to prevent unbounded growth.

        The job:status:list sorted set tracks all job IDs sorted by creation time.
        Individual job data keys have TTL for auto-cleanup, but the sorted set index
        entries remain until explicitly removed. This method uses ZREMRANGEBYRANK
        to keep only the most recent max_entries, removing the oldest entries.

        This is called automatically after adding new jobs to the list.

        Args:
            max_entries: Maximum entries to keep. If None, uses the configured
                value from __init__ (defaults to DEFAULT_JOB_STATUS_LIST_MAX_ENTRIES).

        Returns:
            Number of entries removed from the sorted set.
        """
        if max_entries is None:
            max_entries = self._job_status_list_max_entries

        # ZREMRANGEBYRANK removes by rank (index). Scores are timestamps,
        # so rank 0 is oldest (lowest score). To keep only the most recent
        # max_entries, we remove from rank 0 to -(max_entries + 1).
        # For example, to keep 10000 entries, we remove ranks 0 to -10001.
        # This removes all entries EXCEPT the last max_entries.
        removed = await self._redis.zremrangebyrank(
            JOB_STATUS_LIST_KEY,
            0,
            -(max_entries + 1),
        )

        if removed > 0:
            logger.info(
                "Cleaned up old job status list entries",
                extra={
                    "removed_count": removed,
                    "max_entries": max_entries,
                    "sorted_set": JOB_STATUS_LIST_KEY,
                },
            )

        return removed

    async def start_job(
        self,
        job_id: str | None,
        job_type: str,
        metadata: dict[str, Any] | None,
    ) -> str:
        """Create a new job with PENDING status.

        Args:
            job_id: Unique job identifier. If None, a UUID will be generated.
            job_type: Type of job (e.g., 'export', 'cleanup', 'backup').
            metadata: Optional additional metadata to store with the job.

        Returns:
            The job ID.
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        now = datetime.now(UTC)

        job_metadata = JobMetadata(
            job_id=job_id,
            job_type=job_type,
            status=JobState.PENDING,
            progress=0,
            message=None,
            created_at=now,
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
            extra=metadata,
        )

        # Store job data
        key = self._get_job_key(job_id)
        await self._redis.set(key, job_metadata.to_dict())

        # Add to sorted set for listing (score = timestamp for ordering)
        await self._redis.zadd(
            JOB_STATUS_LIST_KEY,
            {job_id: now.timestamp()},
        )

        # Cleanup old entries to prevent unbounded growth (NEM-2510)
        await self.cleanup_job_status_list()

        # Add to active jobs registry
        await self._add_to_active_registry(job_id)

        logger.info(
            "Job created",
            extra={"job_id": job_id, "job_type": job_type},
        )

        return job_id

    async def update_progress(
        self,
        job_id: str,
        progress: int,
        message: str | None,
    ) -> None:
        """Update job progress and optionally status message.

        If the job is in PENDING state, it will be automatically
        transitioned to RUNNING state with started_at timestamp set.

        Args:
            job_id: The job ID to update.
            progress: New progress value (0-100). Will be clamped.
            message: Optional status message describing current progress.

        Raises:
            KeyError: If the job ID is not found.
        """
        key = self._get_job_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            raise KeyError(f"Job not found: {job_id}")

        # Clamp progress to 0-100
        progress = max(0, min(100, progress))

        # Update fields
        data["progress"] = progress
        if message is not None:
            data["message"] = message

        # Transition from PENDING to RUNNING
        if data["status"] == str(JobState.PENDING):
            data["status"] = str(JobState.RUNNING)
            data["started_at"] = datetime.now(UTC).isoformat()

        await self._redis.set(key, data)

        logger.debug(
            "Job progress updated",
            extra={"job_id": job_id, "progress": progress},
        )

    async def complete_job(
        self,
        job_id: str,
        result: Any | None,
    ) -> None:
        """Mark a job as completed.

        Sets status to COMPLETED, progress to 100, and stores the result.
        The job will have TTL applied for automatic cleanup.

        Args:
            job_id: The job ID to complete.
            result: Optional result data to store.

        Raises:
            KeyError: If the job ID is not found.
        """
        key = self._get_job_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            raise KeyError(f"Job not found: {job_id}")

        now = datetime.now(UTC)

        data["status"] = str(JobState.COMPLETED)
        data["progress"] = 100
        data["completed_at"] = now.isoformat()
        data["result"] = result
        data["message"] = "Completed successfully"

        # Store with TTL for auto-cleanup
        await self._redis.set(key, data, expire=self._completed_job_ttl)

        # Update job registries
        await self._remove_from_active_registry(job_id)
        await self._add_to_completed_registry(job_id)

        logger.info(
            "Job completed",
            extra={"job_id": job_id, "job_type": data["job_type"]},
        )

    async def fail_job(
        self,
        job_id: str,
        error: str,
    ) -> None:
        """Mark a job as failed.

        Sets status to FAILED and stores the error message.
        The job will have TTL applied for automatic cleanup.

        Args:
            job_id: The job ID to fail.
            error: Error message describing the failure.

        Raises:
            KeyError: If the job ID is not found.
        """
        key = self._get_job_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            raise KeyError(f"Job not found: {job_id}")

        now = datetime.now(UTC)

        data["status"] = str(JobState.FAILED)
        data["completed_at"] = now.isoformat()
        data["error"] = error
        data["message"] = f"Failed: {error}"

        # Store with TTL for auto-cleanup
        await self._redis.set(key, data, expire=self._completed_job_ttl)

        # Update job registries
        await self._remove_from_active_registry(job_id)
        await self._add_to_completed_registry(job_id)

        logger.error(
            "Job failed",
            extra={"job_id": job_id, "job_type": data["job_type"], "error": error},
        )

    async def get_job_status(self, job_id: str) -> JobMetadata | None:
        """Get the current status of a job.

        Args:
            job_id: The job ID to look up.

        Returns:
            JobMetadata if found, None otherwise.
        """
        key = self._get_job_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            return None

        try:
            return JobMetadata.from_dict(data)
        except (KeyError, ValueError) as e:
            logger.warning(
                "Failed to parse job metadata",
                extra={"job_id": job_id, "error": str(e)},
            )
            return None

    async def list_jobs(
        self,
        status_filter: JobState | None,
        limit: int,
    ) -> list[JobMetadata]:
        """List jobs with optional status filter.

        Jobs are returned in reverse chronological order (newest first).

        Args:
            status_filter: Optional status to filter by. If None, returns all jobs.
            limit: Maximum number of jobs to return.

        Returns:
            List of JobMetadata objects.
        """
        # Get job IDs from sorted set (most recent first)
        # Use -inf to +inf for all scores
        job_ids = await self._redis.zrangebyscore(
            JOB_STATUS_LIST_KEY,
            "-inf",
            "+inf",
        )

        if not job_ids:
            return []

        # Fetch job data and filter
        jobs: list[JobMetadata] = []
        for job_id in job_ids:
            if len(jobs) >= limit:
                break

            key = self._get_job_key(job_id)
            data = await self._redis.get(key)

            if data is None:
                # Job expired (TTL), clean up the sorted set entry
                await self._redis.zrem(JOB_STATUS_LIST_KEY, job_id)
                continue

            try:
                metadata = JobMetadata.from_dict(data)

                # Apply status filter
                if status_filter is not None and metadata.status != status_filter:
                    continue

                jobs.append(metadata)
            except (KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse job metadata during list",
                    extra={"job_id": job_id, "error": str(e)},
                )
                continue

        return jobs

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's still active.

        Sets status to CANCELLED and moves to completed registry.
        Can only cancel jobs that are QUEUED, PENDING, or RUNNING.

        Args:
            job_id: The job ID to cancel.

        Returns:
            True if the job was cancelled, False if already completed/failed/cancelled.

        Raises:
            KeyError: If the job ID is not found.
        """
        key = self._get_job_key(job_id)
        data = await self._redis.get(key)

        if data is None:
            raise KeyError(f"Job not found: {job_id}")

        # Check if job can be cancelled
        current_status = JobState(data["status"])
        if current_status in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
            return False

        now = datetime.now(UTC)

        data["status"] = str(JobState.CANCELLED)
        data["completed_at"] = now.isoformat()
        data["error"] = "Cancelled by user"
        data["message"] = "Job cancelled by user request"

        # Store with TTL for auto-cleanup
        await self._redis.set(key, data, expire=self._completed_job_ttl)

        # Update job registries
        await self._remove_from_active_registry(job_id)
        await self._add_to_completed_registry(job_id)

        logger.info(
            "Job cancelled",
            extra={"job_id": job_id, "job_type": data["job_type"]},
        )

        return True


# Module-level singleton
_job_status_service: JobStatusService | None = None


def get_job_status_service(redis_client: RedisClient) -> JobStatusService:
    """Get or create the singleton job status service instance.

    Args:
        redis_client: Redis client for storage.

    Returns:
        The job status service singleton.
    """
    global _job_status_service  # noqa: PLW0603
    if _job_status_service is None:
        _job_status_service = JobStatusService(redis_client)
    return _job_status_service


def reset_job_status_service() -> None:
    """Reset the job status service singleton. Used for testing."""
    global _job_status_service  # noqa: PLW0603
    _job_status_service = None
