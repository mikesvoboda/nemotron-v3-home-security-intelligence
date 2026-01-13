"""API routes for background job tracking.

Provides endpoints for querying job status, listing jobs, and job management.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    get_export_service_dep,
    get_job_history_service_dep,
    get_job_search_service_dep,
    get_job_service_dep,
    get_job_tracker_dep,
)
from backend.api.schemas.export import ExportJobStartResponse
from backend.api.schemas.jobs import (
    BulkCancelError,
    BulkCancelRequest,
    BulkCancelResponse,
    ExportFormat,
    ExportJobRequest,
    JobAbortResponse,
    JobAttemptResponse,
    JobCancelResponse,
    JobDetailResponse,
    JobHistoryResponse,
    JobListResponse,
    JobLogEntryResponse,
    JobLogsResponse,
    JobResponse,
    JobSearchAggregations,
    JobSearchResponse,
    JobStatsResponse,
    JobStatusCount,
    JobStatusEnum,
    JobTransitionResponse,
    JobTypeCount,
    JobTypeInfo,
    JobTypesResponse,
)
from backend.api.schemas.pagination import create_pagination_meta
from backend.core.logging import get_logger
from backend.services.export_service import ExportService
from backend.services.job_history_service import JobHistoryService
from backend.services.job_search_service import JobSearchService
from backend.services.job_service import JobService
from backend.services.job_tracker import JobStatus, JobTracker

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])

# Define available job types with descriptions
JOB_TYPES: dict[str, str] = {
    "export": "Export events to CSV, JSON, or ZIP format",
    "cleanup": "Clean up old data and temporary files",
    "backup": "Create a backup of system data",
    "import": "Import events from external files",
    "batch_audit": "Batch AI pipeline audit processing for multiple events",
}


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List all jobs",
    description="List all background jobs with optional filtering by type and status.",
)
async def list_jobs(
    job_type: str | None = Query(
        None,
        description="Filter by job type (e.g., 'export', 'cleanup')",
    ),
    status_filter: JobStatusEnum | None = Query(
        None,
        alias="status",
        description="Filter by job status",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=1000,
        description="Maximum number of jobs to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of jobs to skip (for pagination)",
    ),
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobListResponse:
    """List all jobs with optional filtering and pagination.

    Args:
        job_type: Optional filter by job type.
        status_filter: Optional filter by job status.
        limit: Maximum number of jobs to return.
        offset: Number of jobs to skip for pagination.
        job_tracker: Job tracker service.

    Returns:
        Paginated list of jobs matching the filters.
    """
    # Convert schema enum to service enum if provided
    service_status = JobStatus(status_filter.value) if status_filter else None

    # Get all jobs matching filters (sorted by created_at descending)
    all_jobs = job_tracker.get_all_jobs(
        job_type=job_type,
        status_filter=service_status,
    )

    # Calculate total before pagination
    total = len(all_jobs)

    # Apply pagination
    paginated_jobs = all_jobs[offset : offset + limit]

    # Convert to response models
    job_responses = [
        JobResponse(
            job_id=job["job_id"],
            job_type=job["job_type"],
            status=JobStatusEnum(job["status"]),
            progress=job["progress"],
            message=job.get("message"),
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            result=job.get("result"),
            error=job.get("error"),
        )
        for job in paginated_jobs
    ]

    return JobListResponse(
        items=job_responses,
        pagination=create_pagination_meta(
            total=total,
            limit=limit,
            offset=offset,
            items_count=len(job_responses),
        ),
    )


@router.get(
    "/jobs/types",
    response_model=JobTypesResponse,
    summary="List available job types",
    description="List all available job types that can be created.",
)
async def list_job_types() -> JobTypesResponse:
    """List all available job types.

    Returns:
        List of available job types with descriptions.
    """
    job_type_list = [JobTypeInfo(name=name, description=desc) for name, desc in JOB_TYPES.items()]

    return JobTypesResponse(job_types=job_type_list)


@router.get(
    "/jobs/stats",
    response_model=JobStatsResponse,
    summary="Get job statistics",
    description="Get aggregate statistics about jobs including counts by status, counts by type, and timing information.",
)
async def get_job_stats(
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobStatsResponse:
    """Get aggregate statistics about tracked jobs.

    Provides counts by status and type, average duration for completed jobs,
    and the age of the oldest pending job.

    Args:
        job_tracker: Job tracker service.

    Returns:
        Job statistics including counts and timing information.
    """
    # Get all jobs (no filtering)
    all_jobs = job_tracker.get_all_jobs()

    # Count by status
    status_counts: dict[JobStatusEnum, int] = {}
    for job_status in JobStatusEnum:
        status_counts[job_status] = 0

    # Count by type
    type_counts: dict[str, int] = {}

    # Track completed job durations for average calculation
    completed_durations: list[float] = []

    # Track oldest pending job
    oldest_pending_created_at: datetime | None = None
    now = datetime.now(UTC)

    for job in all_jobs:
        # Count by status
        job_status_enum = JobStatusEnum(job["status"])
        status_counts[job_status_enum] = status_counts.get(job_status_enum, 0) + 1

        # Count by type
        job_type = job["job_type"]
        type_counts[job_type] = type_counts.get(job_type, 0) + 1

        # Calculate duration for completed jobs
        if job_status_enum == JobStatusEnum.COMPLETED:
            started_at = job.get("started_at")
            completed_at = job.get("completed_at")
            if started_at and completed_at:
                try:
                    start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds()
                    if duration >= 0:
                        completed_durations.append(duration)
                except (ValueError, TypeError):
                    pass

        # Track oldest pending job
        if job_status_enum == JobStatusEnum.PENDING:
            created_at_str = job.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if oldest_pending_created_at is None or created_at < oldest_pending_created_at:
                        oldest_pending_created_at = created_at
                except (ValueError, TypeError):
                    pass

    # Calculate average duration
    average_duration: float | None = None
    if completed_durations:
        average_duration = sum(completed_durations) / len(completed_durations)

    # Calculate oldest pending age
    oldest_pending_age: float | None = None
    if oldest_pending_created_at:
        oldest_pending_age = (now - oldest_pending_created_at).total_seconds()

    # Build response
    by_status = [
        JobStatusCount(status=status, count=count)
        for status, count in status_counts.items()
        if count > 0
    ]

    by_type = [
        JobTypeCount(job_type=job_type, count=count)
        for job_type, count in sorted(type_counts.items())
    ]

    return JobStatsResponse(
        total_jobs=len(all_jobs),
        by_status=by_status,
        by_type=by_type,
        average_duration_seconds=average_duration,
        oldest_pending_job_age_seconds=oldest_pending_age,
    )


@router.get(
    "/jobs/search",
    response_model=JobSearchResponse,
    summary="Search and filter jobs",
    description=(
        "Search and filter jobs with advanced query capabilities. "
        "Supports free text search, filtering by status/type/timestamps/duration, "
        "and returns aggregation data for faceted filtering. "
        "NEM-2392: Advanced job search endpoint."
    ),
)
async def search_jobs(
    q: str | None = Query(
        None,
        description="Free text search across job type, error message, and metadata",
    ),
    job_status: str | None = Query(
        None,
        alias="status",
        description="Comma-separated status values to filter (e.g., 'running,pending')",
    ),
    job_type: str | None = Query(
        None,
        description="Comma-separated job types to filter (e.g., 'export,cleanup')",
    ),
    queue: str | None = Query(
        None,
        description="Queue name filter (reserved for future use)",
    ),
    created_after: datetime | None = Query(
        None,
        description="Filter jobs created after this ISO timestamp",
    ),
    created_before: datetime | None = Query(
        None,
        description="Filter jobs created before this ISO timestamp",
    ),
    completed_after: datetime | None = Query(
        None,
        description="Filter jobs completed after this ISO timestamp",
    ),
    completed_before: datetime | None = Query(
        None,
        description="Filter jobs completed before this ISO timestamp",
    ),
    has_error: bool | None = Query(
        None,
        description="If true, only jobs with errors; if false, only jobs without errors",
    ),
    min_duration: float | None = Query(
        None,
        ge=0,
        description="Minimum job duration in seconds (only completed jobs)",
    ),
    max_duration: float | None = Query(
        None,
        ge=0,
        description="Maximum job duration in seconds (only completed jobs)",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=1000,
        description="Maximum number of jobs to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of jobs to skip (for pagination)",
    ),
    sort: str = Query(
        "created_at",
        description="Field to sort by (created_at, started_at, completed_at, progress, job_type, status)",
    ),
    order: str = Query(
        "desc",
        description="Sort direction (asc or desc)",
    ),
    job_search_service: JobSearchService = Depends(get_job_search_service_dep),
) -> JobSearchResponse:
    """Search and filter jobs with advanced query capabilities.

    Provides powerful filtering options:
    - Free text search across job type, error message, and result metadata
    - Filter by multiple statuses and job types (comma-separated)
    - Filter by creation and completion timestamps
    - Filter by whether job has errors
    - Filter by job duration (for completed jobs)

    Returns aggregation counts for faceted filtering.

    Args:
        q: Free text search query.
        job_status: Comma-separated status values.
        job_type: Comma-separated job types.
        queue: Queue name filter (reserved for future use).
        created_after: Filter by creation time lower bound.
        created_before: Filter by creation time upper bound.
        completed_after: Filter by completion time lower bound.
        completed_before: Filter by completion time upper bound.
        has_error: Filter by error presence.
        min_duration: Minimum duration filter.
        max_duration: Maximum duration filter.
        limit: Page size.
        offset: Page offset.
        sort: Sort field.
        order: Sort direction.
        job_search_service: Job search service.

    Returns:
        Search results with pagination metadata and aggregations.
    """
    # Parse comma-separated filters
    statuses = [s.strip() for s in job_status.split(",")] if job_status else None
    job_types = [t.strip() for t in job_type.split(",")] if job_type else None

    # Build range tuples
    created_range = (created_after, created_before) if created_after or created_before else None
    completed_range = (
        (completed_after, completed_before) if completed_after or completed_before else None
    )
    duration_range = (min_duration, max_duration) if min_duration or max_duration else None

    # Execute search
    result = await job_search_service.search(
        query=q,
        statuses=statuses,
        job_types=job_types,
        queue=queue,
        created_range=created_range,
        completed_range=completed_range,
        has_error=has_error,
        duration_range=duration_range,
        limit=limit,
        offset=offset,
        sort_by=sort,
        sort_order=order,
    )

    # Convert to response models
    job_responses = [
        JobResponse(
            job_id=job["job_id"],
            job_type=job["job_type"],
            status=JobStatusEnum(job["status"]),
            progress=job["progress"],
            message=job.get("message"),
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            result=job.get("result"),
            error=job.get("error"),
        )
        for job in result.jobs
    ]

    return JobSearchResponse(
        data=job_responses,
        meta=create_pagination_meta(
            total=result.total,
            limit=limit,
            offset=offset,
            items_count=len(job_responses),
        ),
        aggregations=JobSearchAggregations(
            by_status=result.aggregations.by_status,
            by_type=result.aggregations.by_type,
        ),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the current status and progress of a background job.",
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_status(
    job_id: str,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobResponse:
    """Get the current status of a job.

    Args:
        job_id: The job ID to look up.
        job_tracker: Job tracker service.

    Returns:
        Job status information.

    Raises:
        HTTPException: If the job is not found.
    """
    # First try in-memory, then Redis
    job = job_tracker.get_job(job_id)

    if job is None:
        # Try Redis for completed/failed jobs
        job = await job_tracker.get_job_from_redis(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        )

    return JobResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        status=JobStatusEnum(job["status"]),
        progress=job["progress"],
        message=job.get("message"),
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        result=job.get("result"),
        error=job.get("error"),
    )


@router.get(
    "/jobs/{job_id}/detail",
    response_model=JobDetailResponse,
    summary="Get detailed job information",
    description=(
        "Get detailed information about a specific job including full progress history, "
        "timing information, retry details, and execution metadata. "
        "NEM-2390: Provides comprehensive job status for monitoring and debugging."
    ),
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_detail(
    job_id: str,
    job_service: JobService = Depends(get_job_service_dep),
) -> JobDetailResponse:
    """Get detailed information about a specific job.

    Returns comprehensive job information including:
    - Progress details (percent, current step, items processed/total)
    - Timing information (created, started, completed, duration, estimated remaining)
    - Retry information (attempt number, max attempts, previous errors)
    - Execution metadata (input params, worker ID)

    Args:
        job_id: The job ID to look up.
        job_service: Job service for detailed job retrieval.

    Returns:
        Detailed job information with nested progress, timing, and retry schemas.

    Raises:
        HTTPException: 404 if the job is not found.
    """
    return await job_service.get_job_detail(job_id)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel a job",
    description=(
        "Request cancellation of a background job. "
        "Jobs that are already completed or failed cannot be cancelled."
    ),
    responses={
        404: {"description": "Job not found"},
        409: {"description": "Job cannot be cancelled (already completed or failed)"},
    },
)
async def cancel_job(
    job_id: str,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobCancelResponse:
    """Cancel a background job.

    Args:
        job_id: The job ID to cancel.
        job_tracker: Job tracker service.

    Returns:
        Cancellation response with updated status.

    Raises:
        HTTPException: If job not found or cannot be cancelled.
    """
    try:
        cancelled = job_tracker.cancel_job(job_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        ) from None

    if not cancelled:
        # Job was already completed or failed
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be cancelled - it has already completed or failed",
        )

    logger.info("Job cancelled via API", extra={"job_id": job_id})

    return JobCancelResponse(
        job_id=job_id,
        status=JobStatusEnum.FAILED,
        message="Job cancellation requested",
    )


@router.post(
    "/jobs/{job_id}/abort",
    response_model=JobAbortResponse,
    summary="Abort a running job",
    description=(
        "Abort a running background job by sending a signal to the worker. "
        "Only jobs with status 'running' can be aborted. "
        "Queued jobs should use the /cancel endpoint instead."
    ),
    responses={
        400: {"description": "Job is not running (use cancel for queued jobs)"},
        404: {"description": "Job not found"},
    },
)
async def abort_job(
    job_id: str,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobAbortResponse:
    """Abort a running background job.

    Sends an abort signal to the worker via Redis pub/sub.
    The worker is responsible for checking for abort signals and
    gracefully stopping the job.

    Args:
        job_id: The job ID to abort.
        job_tracker: Job tracker service.

    Returns:
        Abort response with status.

    Raises:
        HTTPException: If job not found or cannot be aborted.
    """
    try:
        success, error_msg = await job_tracker.abort_job(job_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        ) from None

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    logger.info("Job abort requested via API", extra={"job_id": job_id})

    return JobAbortResponse(
        job_id=job_id,
        status=JobStatusEnum.RUNNING,  # Still running until worker acknowledges
        message="Job abort requested - worker notified",
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=JobCancelResponse,
    summary="Cancel or abort a job",
    description=(
        "Cancel or abort a job based on its current state. "
        "Queued jobs will be cancelled, running jobs will be aborted."
    ),
    responses={
        400: {"description": "Job cannot be cancelled or aborted"},
        404: {"description": "Job not found"},
    },
)
async def delete_job(
    job_id: str,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> JobCancelResponse:
    """Cancel or abort a job based on its state.

    This endpoint intelligently handles both queued and running jobs:
    - Queued (pending) jobs are cancelled immediately
    - Running jobs receive an abort signal via Redis pub/sub

    Args:
        job_id: The job ID to cancel/abort.
        job_tracker: Job tracker service.

    Returns:
        Response with updated job status.

    Raises:
        HTTPException: If job not found or cannot be stopped.
    """
    # Get job status first
    job = job_tracker.get_job(job_id)
    if job is None:
        job = await job_tracker.get_job_from_redis(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        )

    job_status = job["status"]

    # Route to appropriate action based on status
    if job_status == JobStatus.PENDING:
        # Cancel queued job
        success, error_msg = job_tracker.cancel_queued_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
        message = "Job cancelled"
        final_status = JobStatusEnum.FAILED
    elif job_status == JobStatus.RUNNING:
        # Abort running job
        success, error_msg = await job_tracker.abort_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
        message = "Job abort requested - worker notified"
        final_status = JobStatusEnum.RUNNING
    else:
        # Job is already completed or failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop job with status: {job_status}",
        )

    logger.info(
        "Job stopped via DELETE",
        extra={"job_id": job_id, "original_status": str(job_status)},
    )

    return JobCancelResponse(
        job_id=job_id,
        status=final_status,
        message=message,
    )


@router.post(
    "/jobs/bulk-cancel",
    response_model=BulkCancelResponse,
    summary="Bulk cancel jobs",
    description=(
        "Cancel multiple jobs at once. Returns counts of successful and failed cancellations."
    ),
)
async def bulk_cancel_jobs(
    request: BulkCancelRequest,
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> BulkCancelResponse:
    """Cancel multiple jobs at once.

    Attempts to cancel each job in the provided list. Jobs that cannot
    be cancelled (not found, already completed, etc.) are reported in
    the errors list.

    Args:
        request: List of job IDs to cancel.
        job_tracker: Job tracker service.

    Returns:
        Summary of cancellation results.
    """
    cancelled_count = 0
    failed_count = 0
    errors: list[BulkCancelError] = []

    for job_id in request.job_ids:
        try:
            # Use the general cancel_job which handles both pending and running
            cancelled = job_tracker.cancel_job(job_id)
            if cancelled:
                cancelled_count += 1
            else:
                failed_count += 1
                errors.append(
                    BulkCancelError(
                        job_id=job_id,
                        error="Job already completed or failed",
                    )
                )
        except KeyError:
            failed_count += 1
            errors.append(
                BulkCancelError(
                    job_id=job_id,
                    error="Job not found",
                )
            )
        except Exception as e:
            failed_count += 1
            errors.append(
                BulkCancelError(
                    job_id=job_id,
                    error=str(e),
                )
            )

    logger.info(
        "Bulk job cancellation completed",
        extra={
            "cancelled": cancelled_count,
            "failed": failed_count,
            "total_requested": len(request.job_ids),
        },
    )

    return BulkCancelResponse(
        cancelled=cancelled_count,
        failed=failed_count,
        errors=errors,
    )


# =============================================================================
# Job History and Audit Trail Endpoints (NEM-2396)
# =============================================================================


@router.get(
    "/jobs/{job_id}/history",
    response_model=JobHistoryResponse,
    summary="Get job history",
    description=(
        "Retrieve complete job execution history including state transitions, "
        "retry attempts, and execution timeline. Provides audit trail for "
        "debugging and compliance purposes. NEM-2396."
    ),
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_history(
    job_id: str,
    job_history_service: JobHistoryService = Depends(get_job_history_service_dep),
) -> JobHistoryResponse:
    """Get complete job history with transitions and attempts.

    Retrieves the full execution history of a job including:
    - State transitions (queued -> running -> completed/failed)
    - Retry attempts with timing and error details
    - Worker assignments

    Args:
        job_id: The job ID to retrieve history for.
        job_history_service: Job history service for database queries.

    Returns:
        Complete job history with transitions and attempts.

    Raises:
        HTTPException: 404 if job not found.
    """
    history = await job_history_service.get_job_history(job_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        )

    # Convert transitions to response models
    transitions = [
        JobTransitionResponse(
            from_status=t.from_status,
            to_status=t.to_status,
            at=t.at,
            triggered_by=t.triggered_by,
            details=t.details,
        )
        for t in history.transitions
    ]

    # Convert attempts to response models
    attempts = [
        JobAttemptResponse(
            attempt_number=a.attempt_number,
            started_at=a.started_at,
            ended_at=a.ended_at,
            status=a.status,
            error=a.error,
            worker_id=a.worker_id,
            duration_seconds=a.duration_seconds,
            result=a.result,
        )
        for a in history.attempts
    ]

    return JobHistoryResponse(
        job_id=history.job_id,
        job_type=history.job_type,
        status=history.status,
        created_at=history.created_at,
        started_at=history.started_at,
        completed_at=history.completed_at,
        transitions=transitions,
        attempts=attempts,
    )


@router.get(
    "/jobs/{job_id}/logs",
    response_model=JobLogsResponse,
    summary="Get job logs",
    description=(
        "Retrieve execution logs for a job with optional filtering by level "
        "and time range. Useful for debugging and monitoring job execution. NEM-2396."
    ),
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_logs(
    job_id: str,
    level: str | None = Query(
        None,
        description="Minimum log level to return (DEBUG, INFO, WARNING, ERROR)",
    ),
    since: datetime | None = Query(
        None,
        description="Return logs from this timestamp onwards (ISO format)",
    ),
    limit: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of log entries to return",
    ),
    job_history_service: JobHistoryService = Depends(get_job_history_service_dep),
) -> JobLogsResponse:
    """Get execution logs for a job.

    Retrieves log entries generated during job execution, with optional
    filtering by log level and time range.

    Log Level Filtering:
    - DEBUG: All logs including detailed debugging info
    - INFO: Info, warnings, and errors
    - WARNING: Warnings and errors only
    - ERROR: Errors only

    Args:
        job_id: The job ID to retrieve logs for.
        level: Minimum log level filter (inclusive).
        since: Time filter - return logs from this time onwards.
        limit: Maximum number of log entries to return.
        job_history_service: Job history service for database queries.

    Returns:
        Job logs with metadata.

    Raises:
        HTTPException: 404 if job not found (checked via history).
    """
    # First check if job exists by getting history
    history = await job_history_service.get_job_history(job_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found with ID: {job_id}",
        )

    # Get logs with filtering
    logs = await job_history_service.get_job_logs(
        job_id=job_id,
        level=level,
        since=since,
        limit=limit + 1,  # Get one extra to check has_more
    )

    # Check if there are more logs beyond the limit
    has_more = len(logs) > limit
    if has_more:
        logs = logs[:limit]

    # Convert to response models
    log_entries = [
        JobLogEntryResponse(
            timestamp=log.timestamp,
            level=log.level.upper(),
            message=log.message,
            context=log.context,
            attempt_number=log.attempt_number,
        )
        for log in logs
    ]

    return JobLogsResponse(
        job_id=job_id,
        logs=log_entries,
        total=len(log_entries),
        has_more=has_more,
    )


async def run_export_job(
    job_id: str,
    export_format: ExportFormat,
    camera_id: str | None,
    risk_level: str | None,
    start_date: str | None,
    end_date: str | None,
    reviewed: bool | None,
    export_service: ExportService,
    job_tracker: JobTracker,
) -> None:
    """Run an export job in the background.

    Args:
        job_id: The job ID.
        export_format: Export format (csv, json, zip).
        camera_id: Optional camera filter.
        risk_level: Optional risk level filter.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        reviewed: Optional reviewed filter.
        export_service: Export service instance.
        job_tracker: Job tracker instance.
    """
    try:
        job_tracker.start_job(job_id, message=f"Starting {export_format} export...")

        result = await export_service.export_events_with_progress(
            job_id=job_id,
            job_tracker=job_tracker,
            export_format=export_format,
            camera_id=camera_id,
            risk_level=risk_level,
            start_date=start_date,
            end_date=end_date,
            reviewed=reviewed,
        )

        job_tracker.complete_job(job_id, result=result)

    except Exception as e:
        logger.exception("Export job failed", extra={"job_id": job_id})
        job_tracker.fail_job(job_id, str(e))


@router.post(
    "/events/export",
    response_model=ExportJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start export job",
    description=(
        "Start a background export job for events. "
        "Returns a job ID that can be used to track progress via GET /api/jobs/{job_id}."
    ),
)
async def start_export_job(
    request: ExportJobRequest,
    background_tasks: BackgroundTasks,
    export_service: ExportService = Depends(get_export_service_dep),
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> ExportJobStartResponse:
    """Start an export job.

    Args:
        request: Export job parameters.
        background_tasks: FastAPI background tasks.
        export_service: Export service.
        job_tracker: Job tracker service.

    Returns:
        Job start response with job ID for tracking.
    """
    # Create the job
    job_id = job_tracker.create_job("export")

    # Convert dates to ISO strings if present
    start_date_str = request.start_date.isoformat() if request.start_date else None
    end_date_str = request.end_date.isoformat() if request.end_date else None

    # Schedule background task
    background_tasks.add_task(
        run_export_job,
        job_id=job_id,
        export_format=request.format,
        camera_id=request.camera_id,
        risk_level=request.risk_level,
        start_date=start_date_str,
        end_date=end_date_str,
        reviewed=request.reviewed,
        export_service=export_service,
        job_tracker=job_tracker,
    )

    logger.info(
        "Export job started",
        extra={"job_id": job_id, "format": request.format},
    )

    return ExportJobStartResponse(
        job_id=job_id,
        status=JobStatusEnum.PENDING,
        message=f"Export job created. Use GET /api/jobs/{job_id} to track progress.",
    )
