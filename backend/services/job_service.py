"""Job service for background job management.

Provides a high-level service layer for job operations, wrapping the JobTracker
with additional functionality for detailed job information retrieval.

NEM-2389: Added database-backed list_jobs method for GET /api/jobs endpoint.
NEM-2390: Service layer for GET /api/jobs/{id} endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status

from backend.api.schemas.jobs import (
    JobDetailResponse,
    JobMetadata,
    JobProgressDetail,
    JobRetryInfo,
    JobStatusEnum,
    JobTiming,
)
from backend.core.logging import get_logger
from backend.services.job_tracker import JobInfo, JobTracker

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

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
        except ValueError, TypeError:
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
