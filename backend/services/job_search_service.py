"""Job search service for advanced job filtering and aggregation.

This module provides search and filtering capabilities for background jobs,
supporting:
- Free text search across job type, error message, and metadata
- Filtering by status, job type, queue, timestamps
- Duration-based filtering
- Aggregations by status and type
- Pagination with offset/limit
- Sorting by multiple fields
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from backend.core.logging import get_logger
from backend.services.job_tracker import JobInfo, JobTracker

logger = get_logger(__name__)


class JobSortField(StrEnum):
    """Valid fields for sorting job search results."""

    CREATED_AT = "created_at"
    STARTED_AT = "started_at"
    COMPLETED_AT = "completed_at"
    PROGRESS = "progress"
    JOB_TYPE = "job_type"
    STATUS = "status"


class SortOrder(StrEnum):
    """Sort order direction."""

    ASC = "asc"
    DESC = "desc"


@dataclass(slots=True)
class JobSearchFilters:
    """Filters for job search."""

    query: str | None = None
    statuses: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    queue: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    completed_after: datetime | None = None
    completed_before: datetime | None = None
    has_error: bool | None = None
    min_duration: float | None = None
    max_duration: float | None = None


@dataclass(slots=True)
class JobAggregations:
    """Aggregation counts for job search results."""

    by_status: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "by_status": self.by_status,
            "by_type": self.by_type,
        }


@dataclass(slots=True)
class JobSearchResult:
    """Result from job search including jobs, total count, and aggregations."""

    jobs: list[JobInfo]
    total: int
    aggregations: JobAggregations

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "jobs": [dict(j) for j in self.jobs],
            "total": self.total,
            "aggregations": self.aggregations.to_dict(),
        }


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse datetime from ISO string or return as-is if already datetime.

    Args:
        value: ISO datetime string or datetime object

    Returns:
        datetime object or None
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # Handle ISO format with or without Z suffix
        if isinstance(value, str):
            value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    return None


def _calculate_job_duration(job: JobInfo) -> float | None:
    """Calculate job duration in seconds.

    Args:
        job: Job information dict

    Returns:
        Duration in seconds or None if not calculable
    """
    started_at_str = job.get("started_at")
    completed_at_str = job.get("completed_at")

    if not started_at_str or not completed_at_str:
        return None

    started_at = _parse_datetime(started_at_str)
    completed_at = _parse_datetime(completed_at_str)

    if started_at and completed_at:
        return (completed_at - started_at).total_seconds()

    return None


def _matches_text_query(job: JobInfo, query: str) -> bool:  # noqa: PLR0911
    """Check if job matches free text query.

    Searches across job_type, error, message, and result fields.

    Args:
        job: Job information dict
        query: Search query string (case-insensitive)

    Returns:
        True if job matches the query
    """
    if not query:
        return True

    query_lower = query.lower()

    # Search in job_type
    if query_lower in job.get("job_type", "").lower():
        return True

    # Search in error message
    error = job.get("error")
    if error and query_lower in str(error).lower():
        return True

    # Search in status message
    message = job.get("message")
    if message and query_lower in str(message).lower():
        return True

    # Search in result (if it's a string or dict with string values)
    result = job.get("result")
    if result:
        if isinstance(result, str) and query_lower in result.lower():
            return True
        if isinstance(result, dict):
            for value in result.values():
                if isinstance(value, str) and query_lower in value.lower():
                    return True

    return False


def _matches_status_filter(job: JobInfo, statuses: list[str]) -> bool:
    """Check if job matches status filter.

    Args:
        job: Job information dict
        statuses: List of status values to match

    Returns:
        True if job status matches any in the list
    """
    if not statuses:
        return True

    job_status = str(job.get("status", ""))
    return job_status in statuses


def _matches_type_filter(job: JobInfo, job_types: list[str]) -> bool:
    """Check if job matches type filter.

    Args:
        job: Job information dict
        job_types: List of job type values to match

    Returns:
        True if job type matches any in the list
    """
    if not job_types:
        return True

    return job.get("job_type", "") in job_types


def _matches_timestamp_filter(
    job: JobInfo,
    created_after: datetime | None,
    created_before: datetime | None,
    completed_after: datetime | None,
    completed_before: datetime | None,
) -> bool:
    """Check if job matches timestamp filters.

    Args:
        job: Job information dict
        created_after: Filter for jobs created after this time
        created_before: Filter for jobs created before this time
        completed_after: Filter for jobs completed after this time
        completed_before: Filter for jobs completed before this time

    Returns:
        True if job matches all timestamp filters
    """
    # Check created_at filters
    created_at = _parse_datetime(job.get("created_at"))
    if created_at:
        if created_after and created_at < created_after:
            return False
        if created_before and created_at > created_before:
            return False

    # Check completed_at filters
    completed_at = _parse_datetime(job.get("completed_at"))
    if completed_after or completed_before:
        if not completed_at:
            # Job not completed yet, can't match completed filters
            return False
        if completed_after and completed_at < completed_after:
            return False
        if completed_before and completed_at > completed_before:
            return False

    return True


def _matches_error_filter(job: JobInfo, has_error: bool | None) -> bool:
    """Check if job matches error filter.

    Args:
        job: Job information dict
        has_error: If True, only jobs with errors; if False, only jobs without errors

    Returns:
        True if job matches error filter
    """
    if has_error is None:
        return True

    error = job.get("error")
    job_has_error = error is not None and str(error).strip() != ""

    return job_has_error == has_error


def _matches_duration_filter(
    job: JobInfo,
    min_duration: float | None,
    max_duration: float | None,
) -> bool:
    """Check if job matches duration filters.

    Args:
        job: Job information dict
        min_duration: Minimum duration in seconds
        max_duration: Maximum duration in seconds

    Returns:
        True if job matches duration filters
    """
    if min_duration is None and max_duration is None:
        return True

    duration = _calculate_job_duration(job)

    # If job has no duration (not completed), it can't match duration filters
    if duration is None:
        return False

    if min_duration is not None and duration < min_duration:
        return False
    return not (max_duration is not None and duration > max_duration)


def _filter_job(job: JobInfo, filters: JobSearchFilters) -> bool:
    """Check if a job matches all search filters.

    Args:
        job: Job information dict
        filters: Search filters to apply

    Returns:
        True if job matches all filters
    """
    if not _matches_text_query(job, filters.query or ""):
        return False

    if not _matches_status_filter(job, filters.statuses):
        return False

    if not _matches_type_filter(job, filters.job_types):
        return False

    if not _matches_timestamp_filter(
        job,
        filters.created_after,
        filters.created_before,
        filters.completed_after,
        filters.completed_before,
    ):
        return False

    if not _matches_error_filter(job, filters.has_error):
        return False

    return _matches_duration_filter(job, filters.min_duration, filters.max_duration)


def _compute_aggregations(jobs: list[JobInfo]) -> JobAggregations:
    """Compute aggregations for a list of jobs.

    Args:
        jobs: List of jobs to aggregate

    Returns:
        JobAggregations with counts by status and type
    """
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}

    for job in jobs:
        # Count by status
        status = str(job.get("status", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1

        # Count by type
        job_type = job.get("job_type", "unknown")
        by_type[job_type] = by_type.get(job_type, 0) + 1

    return JobAggregations(by_status=by_status, by_type=by_type)


def _get_sort_key(
    job: JobInfo,
    sort_by: str,
) -> Any:
    """Get the sort key value for a job.

    Args:
        job: Job information dict
        sort_by: Field to sort by

    Returns:
        Sortable value for the job
    """
    sort_field_map: dict[str, Any] = {
        JobSortField.CREATED_AT: job.get("created_at", ""),
        JobSortField.STARTED_AT: job.get("started_at") or "",
        JobSortField.COMPLETED_AT: job.get("completed_at") or "",
        JobSortField.PROGRESS: job.get("progress", 0),
        JobSortField.JOB_TYPE: job.get("job_type", ""),
        JobSortField.STATUS: str(job.get("status", "")),
    }
    # Default to created_at
    return sort_field_map.get(sort_by, job.get("created_at", ""))


async def search_jobs(
    job_tracker: JobTracker,
    query: str | None = None,
    statuses: list[str] | None = None,
    job_types: list[str] | None = None,
    queue: str | None = None,
    created_range: tuple[datetime | None, datetime | None] | None = None,
    completed_range: tuple[datetime | None, datetime | None] | None = None,
    has_error: bool | None = None,
    duration_range: tuple[float | None, float | None] | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[JobInfo], int]:
    """Search jobs with filtering, sorting, and pagination.

    Args:
        job_tracker: JobTracker instance to query
        query: Free text search across job type, error, message, metadata
        statuses: List of status values to filter by
        job_types: List of job type values to filter by
        queue: Queue name filter (reserved for future use)
        created_range: Tuple of (after, before) datetime for created_at filter
        completed_range: Tuple of (after, before) datetime for completed_at filter
        has_error: If True, only jobs with errors; if False, only jobs without
        duration_range: Tuple of (min, max) duration in seconds
        limit: Maximum number of jobs to return (default 50)
        offset: Number of jobs to skip for pagination (default 0)
        sort_by: Field to sort by (default "created_at")
        sort_order: Sort direction "asc" or "desc" (default "desc")

    Returns:
        Tuple of (list of jobs, total count before pagination)
    """
    # Build filters
    created_after, created_before = created_range if created_range else (None, None)
    completed_after, completed_before = completed_range if completed_range else (None, None)
    min_duration, max_duration = duration_range if duration_range else (None, None)

    filters = JobSearchFilters(
        query=query,
        statuses=statuses or [],
        job_types=job_types or [],
        queue=queue,
        created_after=created_after,
        created_before=created_before,
        completed_after=completed_after,
        completed_before=completed_before,
        has_error=has_error,
        min_duration=min_duration,
        max_duration=max_duration,
    )

    # Get all jobs from tracker (no server-side filtering yet)
    all_jobs = job_tracker.get_all_jobs()

    # Apply filters
    filtered_jobs = [job for job in all_jobs if _filter_job(job, filters)]

    # Get total count before pagination
    total = len(filtered_jobs)

    # Sort jobs
    reverse = sort_order.lower() == "desc"
    filtered_jobs.sort(key=lambda j: _get_sort_key(j, sort_by), reverse=reverse)

    # Apply pagination
    paginated_jobs = filtered_jobs[offset : offset + limit]

    logger.debug(
        "Job search completed",
        extra={
            "total": total,
            "returned": len(paginated_jobs),
            "filters": {
                "query": query,
                "statuses": statuses,
                "job_types": job_types,
                "has_error": has_error,
            },
        },
    )

    return paginated_jobs, total


async def search_jobs_with_aggregations(
    job_tracker: JobTracker,
    query: str | None = None,
    statuses: list[str] | None = None,
    job_types: list[str] | None = None,
    queue: str | None = None,
    created_range: tuple[datetime | None, datetime | None] | None = None,
    completed_range: tuple[datetime | None, datetime | None] | None = None,
    has_error: bool | None = None,
    duration_range: tuple[float | None, float | None] | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> JobSearchResult:
    """Search jobs with filtering, sorting, pagination, and aggregations.

    This is the main entry point for job search that includes aggregation data.

    Args:
        job_tracker: JobTracker instance to query
        query: Free text search across job type, error, message, metadata
        statuses: List of status values to filter by
        job_types: List of job type values to filter by
        queue: Queue name filter (reserved for future use)
        created_range: Tuple of (after, before) datetime for created_at filter
        completed_range: Tuple of (after, before) datetime for completed_at filter
        has_error: If True, only jobs with errors; if False, only jobs without
        duration_range: Tuple of (min, max) duration in seconds
        limit: Maximum number of jobs to return (default 50)
        offset: Number of jobs to skip for pagination (default 0)
        sort_by: Field to sort by (default "created_at")
        sort_order: Sort direction "asc" or "desc" (default "desc")

    Returns:
        JobSearchResult with jobs, total count, and aggregations
    """
    # Build filters for aggregation computation
    created_after, created_before = created_range if created_range else (None, None)
    completed_after, completed_before = completed_range if completed_range else (None, None)
    min_duration, max_duration = duration_range if duration_range else (None, None)

    filters = JobSearchFilters(
        query=query,
        statuses=statuses or [],
        job_types=job_types or [],
        queue=queue,
        created_after=created_after,
        created_before=created_before,
        completed_after=completed_after,
        completed_before=completed_before,
        has_error=has_error,
        min_duration=min_duration,
        max_duration=max_duration,
    )

    # Get all jobs from tracker
    all_jobs = job_tracker.get_all_jobs()

    # Apply filters
    filtered_jobs = [job for job in all_jobs if _filter_job(job, filters)]

    # Compute aggregations on filtered jobs (before pagination)
    aggregations = _compute_aggregations(filtered_jobs)

    # Get total count
    total = len(filtered_jobs)

    # Sort jobs
    reverse = sort_order.lower() == "desc"
    filtered_jobs.sort(key=lambda j: _get_sort_key(j, sort_by), reverse=reverse)

    # Apply pagination
    paginated_jobs = filtered_jobs[offset : offset + limit]

    logger.info(
        "Job search with aggregations completed",
        extra={
            "total": total,
            "returned": len(paginated_jobs),
            "aggregations": aggregations.to_dict(),
        },
    )

    return JobSearchResult(
        jobs=paginated_jobs,
        total=total,
        aggregations=aggregations,
    )


class JobSearchService:
    """Service class for job search operations.

    This class wraps the search functions and provides a convenient interface
    for dependency injection in FastAPI routes.
    """

    def __init__(self, job_tracker: JobTracker) -> None:
        """Initialize the job search service.

        Args:
            job_tracker: JobTracker instance to query
        """
        self._job_tracker = job_tracker

    async def search(
        self,
        query: str | None = None,
        statuses: list[str] | None = None,
        job_types: list[str] | None = None,
        queue: str | None = None,
        created_range: tuple[datetime | None, datetime | None] | None = None,
        completed_range: tuple[datetime | None, datetime | None] | None = None,
        has_error: bool | None = None,
        duration_range: tuple[float | None, float | None] | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> JobSearchResult:
        """Search jobs with filtering, sorting, pagination, and aggregations.

        Args:
            query: Free text search across job type, error, message, metadata
            statuses: List of status values to filter by
            job_types: List of job type values to filter by
            queue: Queue name filter (reserved for future use)
            created_range: Tuple of (after, before) datetime for created_at filter
            completed_range: Tuple of (after, before) datetime for completed_at filter
            has_error: If True, only jobs with errors; if False, only jobs without
            duration_range: Tuple of (min, max) duration in seconds
            limit: Maximum number of jobs to return (default 50)
            offset: Number of jobs to skip for pagination (default 0)
            sort_by: Field to sort by (default "created_at")
            sort_order: Sort direction "asc" or "desc" (default "desc")

        Returns:
            JobSearchResult with jobs, total count, and aggregations
        """
        return await search_jobs_with_aggregations(
            job_tracker=self._job_tracker,
            query=query,
            statuses=statuses,
            job_types=job_types,
            queue=queue,
            created_range=created_range,
            completed_range=completed_range,
            has_error=has_error,
            duration_range=duration_range,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
