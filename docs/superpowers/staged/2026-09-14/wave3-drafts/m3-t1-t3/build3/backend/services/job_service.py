"""Job service for background job management.

Provides a high-level service layer for job operations, wrapping the JobTracker
with additional functionality for detailed job information retrieval.

NEM-2389: Added database-backed list_jobs method for GET /api/jobs endpoint.
NEM-2390: Service layer for GET /api/jobs/{id} endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.jobs import (
    JobDetailResponse,
    JobMetadata,
    JobProgressDetail,
    JobRetryInfo,
    JobStatusEnum,
    JobTiming,
)
from backend.core.logging import get_logger
from backend.models.job import Job
from backend.models.job import JobStatus as JobStatusModel
from backend.services.job_tracker import JobInfo, JobTracker

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Valid sort fields for job listing
VALID_SORT_FIELDS = {"created_at", "started_at", "completed_at", "job_type", "status", "priority"}

# Type alias for sort order
SortOrder = Literal["asc", "desc"]

# Default values for retry configuration
DEFAULT_MAX_ATTEMPTS = 3


class JobService:
    """Service for job management and detailed information retrieval.

    Wraps the JobTracker to provide higher-level operations and
    transformation of job data into detailed response formats.
    """

    def __init__(
        self,
        job_tracker: JobTracker,
        redis_client: RedisClient | None = None,
    ) -> None:
        """Initialize the job service.

        Args:
            job_tracker: The job tracker instance for job state management.
            redis_client: Optional Redis client for persistent job storage.
        """
        self._job_tracker = job_tracker
        self._redis_client = redis_client

    def get_job(self, job_id: str | UUID) -> JobInfo | None:
        """Get job information by ID.

        Retrieves job information from in-memory storage.

        Args:
            job_id: The job ID to look up (string or UUID).

        Returns:
            Job information or None if not found.
        """
        job_id_str = str(job_id)
        return self._job_tracker.get_job(job_id_str)

    async def get_job_with_fallback(self, job_id: str | UUID) -> JobInfo | None:
        """Get job information by ID with Redis fallback.

        First checks in-memory storage, then falls back to Redis
        for completed/failed jobs that may have been persisted.

        Args:
            job_id: The job ID to look up (string or UUID).

        Returns:
            Job information or None if not found.
        """
        job_id_str = str(job_id)

        # Try in-memory first
        job = self._job_tracker.get_job(job_id_str)
        if job is not None:
            return job

        # Fall back to Redis for completed jobs
        return await self._job_tracker.get_job_from_redis(job_id_str)

    def get_job_or_404(self, job_id: str | UUID) -> JobInfo:
        """Get job information by ID or raise 404.

        Args:
            job_id: The job ID to look up (string or UUID).

        Returns:
            Job information.

        Raises:
            HTTPException: 404 if job not found.
        """
        job = self.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No job found with ID: {job_id}",
            )
        return job

    async def get_job_or_404_async(self, job_id: str | UUID) -> JobInfo:
        """Get job information by ID (with Redis fallback) or raise 404.

        Args:
            job_id: The job ID to look up (string or UUID).

        Returns:
            Job information.

        Raises:
            HTTPException: 404 if job not found.
        """
        job = await self.get_job_with_fallback(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No job found with ID: {job_id}",
            )
        return job

    def _parse_iso_timestamp(self, timestamp_str: str | None) -> datetime | None:
        """Parse an ISO 8601 timestamp string to datetime.

        Args:
            timestamp_str: ISO 8601 timestamp string or None.

        Returns:
            Parsed datetime or None.
        """
        if timestamp_str is None:
            return None

        try:
            # Handle various ISO formats
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            logger.warning(
                "Failed to parse timestamp",
                extra={"timestamp": timestamp_str},
            )
            return None

    def _calculate_duration(
        self,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> float | None:
        """Calculate job duration in seconds.

        Args:
            started_at: When the job started.
            completed_at: When the job completed (or current time if still running).

        Returns:
            Duration in seconds or None if not started.
        """
        if started_at is None:
            return None

        end_time = completed_at if completed_at is not None else datetime.now(UTC)
        duration = (end_time - started_at).total_seconds()
        return max(0.0, duration)

    def _estimate_remaining_time(
        self,
        progress_percent: int,
        duration_seconds: float | None,
        job_status: str,
    ) -> float | None:
        """Estimate remaining time based on current progress.

        Args:
            progress_percent: Current progress percentage (0-100).
            duration_seconds: Current duration in seconds.
            job_status: Current job status.

        Returns:
            Estimated remaining seconds or None if cannot estimate.
        """
        # Only estimate for running jobs with progress
        if job_status != "running" or duration_seconds is None or progress_percent <= 0:
            return None

        if progress_percent >= 100:
            return 0.0

        # Simple linear estimation
        rate = progress_percent / duration_seconds
        remaining_percent = 100 - progress_percent
        estimated = remaining_percent / rate if rate > 0 else None

        return estimated

    def _extract_progress_detail(self, job: JobInfo) -> JobProgressDetail:
        """Extract detailed progress information from job.

        Args:
            job: The job information.

        Returns:
            Detailed progress information.
        """
        message = job.get("message")

        # Extract items_processed and items_total from message patterns
        items_processed = None
        items_total = None
        current_step = message

        if message:
            import re

            # Match patterns like "Processing 450/1000" or "450 of 1000"
            match = re.search(r"(\d+)\s*[/of]+\s*(\d+)", message)
            if match:
                items_processed = int(match.group(1))
                items_total = int(match.group(2))
                # Extract step name before the numbers
                step_match = re.match(r"^([^:]+):", message)
                if step_match:
                    current_step = step_match.group(1).strip()

        return JobProgressDetail(
            percent=job["progress"],
            current_step=current_step,
            items_processed=items_processed,
            items_total=items_total,
        )

    def _extract_timing(self, job: JobInfo, progress_percent: int) -> JobTiming:
        """Extract timing information from job.

        Args:
            job: The job information.
            progress_percent: Current progress percentage.

        Returns:
            Timing information.
        """
        created_at = self._parse_iso_timestamp(job["created_at"])
        started_at = self._parse_iso_timestamp(job.get("started_at"))
        completed_at = self._parse_iso_timestamp(job.get("completed_at"))

        duration_seconds = self._calculate_duration(started_at, completed_at)
        estimated_remaining = self._estimate_remaining_time(
            progress_percent,
            duration_seconds,
            str(job["status"]),
        )

        # Ensure created_at is not None (required field)
        if created_at is None:
            created_at = datetime.now(UTC)

        return JobTiming(
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            estimated_remaining_seconds=estimated_remaining,
        )

    def _extract_retry_info(self, job: JobInfo) -> JobRetryInfo:  # noqa: ARG002
        """Extract retry information from job.

        Args:
            job: The job information (reserved for future retry tracking).

        Returns:
            Retry information with default values until retry tracking is implemented.
        """
        # The current job tracker doesn't store retry info,
        # so we provide default values. The job parameter is reserved
        # for when retry tracking is added to the job tracker.
        return JobRetryInfo(
            attempt_number=1,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            next_retry_at=None,
            previous_errors=[],
        )

    def _extract_metadata(self, job: JobInfo) -> JobMetadata:
        """Extract metadata from job.

        Args:
            job: The job information.

        Returns:
            Job metadata.
        """
        # The current job tracker stores result which may contain metadata
        result = job.get("result")
        input_params: dict[str, Any] | None = None

        if isinstance(result, dict) and "input_params" in result:
            input_params = result.get("input_params")

        return JobMetadata(
            input_params=input_params,
            worker_id=None,  # Not tracked in current implementation
        )

    def transform_to_detail_response(self, job: JobInfo) -> JobDetailResponse:
        """Transform a JobInfo to a detailed response.

        Args:
            job: The job information from the tracker.

        Returns:
            Detailed job response with nested progress, timing, and retry info.
        """
        progress_detail = self._extract_progress_detail(job)
        timing = self._extract_timing(job, progress_detail.percent)
        retry_info = self._extract_retry_info(job)
        metadata = self._extract_metadata(job)

        return JobDetailResponse(
            id=job["job_id"],
            job_type=job["job_type"],
            status=JobStatusEnum(job["status"]),
            queue_name=None,  # Not tracked in current implementation
            priority=0,  # Default priority
            progress=progress_detail,
            timing=timing,
            retry_info=retry_info,
            result=job.get("result"),
            error=job.get("error"),
            metadata=metadata,
        )

    async def get_job_detail(self, job_id: str | UUID) -> JobDetailResponse:
        """Get detailed job information by ID.

        Retrieves job and transforms to detailed response format.

        Args:
            job_id: The job ID to look up.

        Returns:
            Detailed job response.

        Raises:
            HTTPException: 404 if job not found.
        """
        job = await self.get_job_or_404_async(job_id)
        return self.transform_to_detail_response(job)


class DatabaseJobService:
    """Database-backed service for managing background jobs.

    Provides methods for creating, listing, updating, and querying jobs
    from the PostgreSQL database. This complements the in-memory JobTracker
    with persistent storage for job history and detailed queries.

    NEM-2389: Service layer for GET /api/jobs endpoint with database persistence.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the database job service.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self._db = db

    async def create_job(
        self,
        job_type: str,
        *,
        job_id: str | None = None,
        queue_name: str | None = None,
        priority: int = 2,
        max_attempts: int = 3,
    ) -> Job:
        """Create a new job in the database.

        Args:
            job_type: Type of job (e.g., 'export', 'cleanup', 'backup').
            job_id: Optional job ID. If not provided, a UUID will be generated.
            queue_name: Optional queue name for job assignment.
            priority: Job priority (0 = highest, 4 = lowest). Default: 2.
            max_attempts: Maximum retry attempts. Default: 3.

        Returns:
            The created Job instance.
        """
        import uuid as uuid_module

        if job_id is None:
            job_id = str(uuid_module.uuid4())

        job = Job(
            id=job_id,
            job_type=job_type,
            status=JobStatusModel.QUEUED.value,
            queue_name=queue_name,
            priority=priority,
            max_attempts=max_attempts,
            created_at=datetime.now(UTC),
        )

        self._db.add(job)
        await self._db.flush()

        logger.info(
            "Job created in database",
            extra={"job_id": job_id, "job_type": job_type},
        )

        return job

    async def get_job_by_id(self, job_id: str) -> Job | None:
        """Get a job by ID from the database.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job instance if found, None otherwise.
        """
        result = await self._db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "created_at",
        order: SortOrder = "desc",
    ) -> tuple[Sequence[Job], int]:
        """List jobs with filtering, pagination, and sorting.

        Args:
            status: Optional filter by job status (queued, running, completed, failed, cancelled).
            job_type: Optional filter by job type (e.g., 'export', 'cleanup').
            since: Optional filter for jobs created after this timestamp.
            limit: Maximum number of jobs to return. Default: 50.
            offset: Number of jobs to skip for pagination. Default: 0.
            sort: Field to sort by. Default: 'created_at'.
                Valid fields: created_at, started_at, completed_at, job_type, status, priority.
            order: Sort order ('asc' or 'desc'). Default: 'desc'.

        Returns:
            Tuple of (list of jobs, total count matching filters).
        """
        # Build base query
        query = select(Job)

        # Apply filters
        if status is not None:
            query = query.where(Job.status == status)

        if job_type is not None:
            query = query.where(Job.job_type == job_type)

        if since is not None:
            query = query.where(Job.created_at >= since)

        # Get total count (before pagination)
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_field = sort if sort in VALID_SORT_FIELDS else "created_at"
        sort_column = getattr(Job, sort_field)

        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await self._db.execute(query)
        jobs = result.scalars().all()

        return jobs, total

    async def start_job(self, job_id: str, current_step: str | None = None) -> Job | None:
        """Mark a job as started/running.

        Args:
            job_id: The job ID to start.
            current_step: Optional initial step description.

        Returns:
            Updated Job instance, or None if not found.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        job.start()
        if current_step is not None:
            job.current_step = current_step

        await self._db.flush()

        logger.info("Job started", extra={"job_id": job_id})

        return job

    async def update_progress(
        self,
        job_id: str,
        progress_percent: int,
        current_step: str | None = None,
    ) -> Job | None:
        """Update job progress.

        Args:
            job_id: The job ID to update.
            progress_percent: New progress value (0-100).
            current_step: Optional step description.

        Returns:
            Updated Job instance, or None if not found.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        job.update_progress(progress_percent, current_step)
        await self._db.flush()

        logger.debug(
            "Job progress updated",
            extra={"job_id": job_id, "progress": progress_percent},
        )

        return job

    async def complete_job(
        self,
        job_id: str,
        result: dict[str, Any] | None = None,
    ) -> Job | None:
        """Mark a job as completed.

        Args:
            job_id: The job ID to complete.
            result: Optional result data to store.

        Returns:
            Updated Job instance, or None if not found.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        job.complete(result)
        await self._db.flush()

        logger.info(
            "Job completed",
            extra={"job_id": job_id, "job_type": job.job_type},
        )

        return job

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_traceback: str | None = None,
    ) -> Job | None:
        """Mark a job as failed.

        Args:
            job_id: The job ID to fail.
            error_message: Human-readable error message.
            error_traceback: Optional full error traceback.

        Returns:
            Updated Job instance, or None if not found.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        job.fail(error_message, error_traceback)
        await self._db.flush()

        logger.error(
            "Job failed",
            extra={"job_id": job_id, "job_type": job.job_type, "error": error_message},
        )

        return job

    async def cancel_job(self, job_id: str) -> Job | None:
        """Cancel a job.

        Only active jobs (queued or running) can be cancelled.

        Args:
            job_id: The job ID to cancel.

        Returns:
            Updated Job instance, or None if not found or not cancellable.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        if not job.is_active:
            return None  # Cannot cancel finished jobs

        job.cancel()
        await self._db.flush()

        logger.info(
            "Job cancelled",
            extra={"job_id": job_id, "job_type": job.job_type},
        )

        return job

    async def get_active_jobs(self, job_type: str | None = None) -> Sequence[Job]:
        """Get all active (queued or running) jobs.

        Args:
            job_type: Optional filter by job type.

        Returns:
            List of active jobs sorted by priority and creation time.
        """
        query = select(Job).where(
            Job.status.in_([JobStatusModel.QUEUED.value, JobStatusModel.RUNNING.value])
        )

        if job_type is not None:
            query = query.where(Job.job_type == job_type)

        query = query.order_by(Job.priority.asc(), Job.created_at.asc())

        result = await self._db.execute(query)
        return result.scalars().all()

    async def get_job_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about jobs.

        Returns:
            Dictionary with job statistics including:
            - total_jobs: Total number of jobs
            - by_status: List of {status, count} objects
            - by_type: List of {job_type, count} objects
            - average_duration_seconds: Average duration for completed jobs
            - oldest_pending_job_age_seconds: Age of oldest queued job
        """
        # Count by status
        status_query = select(Job.status, func.count(Job.id)).group_by(Job.status)
        status_result = await self._db.execute(status_query)
        by_status = [{"status": row[0], "count": row[1]} for row in status_result.all()]

        # Count by type
        type_query = select(Job.job_type, func.count(Job.id)).group_by(Job.job_type)
        type_result = await self._db.execute(type_query)
        by_type = [{"job_type": row[0], "count": row[1]} for row in type_result.all()]

        # Total count
        total_query = select(func.count(Job.id))
        total_result = await self._db.execute(total_query)
        total = total_result.scalar() or 0

        # Average duration for completed jobs
        duration_query = select(
            func.avg(
                func.extract("epoch", Job.completed_at) - func.extract("epoch", Job.started_at)
            )
        ).where(
            Job.status == JobStatusModel.COMPLETED.value,
            Job.started_at.isnot(None),
            Job.completed_at.isnot(None),
        )
        duration_result = await self._db.execute(duration_query)
        avg_duration = duration_result.scalar()

        # Oldest pending job age
        oldest_pending_query = select(func.min(Job.created_at)).where(
            Job.status == JobStatusModel.QUEUED.value
        )
        oldest_pending_result = await self._db.execute(oldest_pending_query)
        oldest_pending_created = oldest_pending_result.scalar()

        oldest_pending_age = None
        if oldest_pending_created is not None:
            oldest_pending_age = (datetime.now(UTC) - oldest_pending_created).total_seconds()

        return {
            "total_jobs": total,
            "by_status": by_status,
            "by_type": by_type,
            "average_duration_seconds": float(avg_duration) if avg_duration else None,
            "oldest_pending_job_age_seconds": oldest_pending_age,
        }

    async def retry_job(self, job_id: str) -> Job | None:
        """Retry a failed job.

        Prepares the job for a retry attempt by incrementing the attempt
        number and resetting the status to QUEUED.

        Args:
            job_id: The job ID to retry.

        Returns:
            Updated Job instance, or None if not found or not retryable.
        """
        job = await self.get_job_by_id(job_id)
        if job is None:
            return None

        if not job.can_retry:
            return None

        job.prepare_retry()
        await self._db.flush()

        logger.info(
            "Job prepared for retry",
            extra={"job_id": job_id, "attempt": job.attempt_number},
        )

        return job

    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete jobs older than the specified number of days.

        Only deletes completed, failed, or cancelled jobs.

        Args:
            days: Delete jobs older than this many days. Default: 30.

        Returns:
            Number of jobs deleted.
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff - timedelta(days=days)

        stmt = delete(Job).where(
            Job.status.in_(
                [
                    JobStatusModel.COMPLETED.value,
                    JobStatusModel.FAILED.value,
                    JobStatusModel.CANCELLED.value,
                ]
            ),
            Job.completed_at < cutoff,
        )

        result = await self._db.execute(stmt)
        deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]

        if deleted_count > 0:
            logger.info(
                "Cleaned up old jobs",
                extra={"deleted_count": deleted_count, "older_than_days": days},
            )

        return deleted_count


# Module-level factory function
def create_job_service(
    job_tracker: JobTracker,
    redis_client: RedisClient | None = None,
) -> JobService:
    """Create a job service instance.

    Args:
        job_tracker: The job tracker instance.
        redis_client: Optional Redis client.

    Returns:
        JobService instance.
    """
    return JobService(job_tracker=job_tracker, redis_client=redis_client)


def create_database_job_service(db: AsyncSession) -> DatabaseJobService:
    """Create a database job service instance.

    Args:
        db: SQLAlchemy async session.

    Returns:
        DatabaseJobService instance.
    """
    return DatabaseJobService(db=db)
