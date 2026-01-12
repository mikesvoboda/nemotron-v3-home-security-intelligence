"""API routes for background job tracking.

Provides endpoints for querying job status, listing jobs, and job management.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from backend.api.dependencies import get_export_service_dep, get_job_tracker_dep
from backend.api.schemas.jobs import (
    ExportFormat,
    ExportJobRequest,
    ExportJobStartResponse,
    JobCancelResponse,
    JobListResponse,
    JobResponse,
    JobStatsResponse,
    JobStatusCount,
    JobStatusEnum,
    JobTypeCount,
    JobTypeInfo,
    JobTypesResponse,
)
from backend.api.schemas.pagination import create_pagination_meta
from backend.core.logging import get_logger
from backend.services.export_service import ExportService
from backend.services.job_tracker import JobStatus, JobTracker

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])

# Define available job types with descriptions
JOB_TYPES: dict[str, str] = {
    "export": "Export events to CSV, JSON, or ZIP format",
    "cleanup": "Clean up old data and temporary files",
    "backup": "Create a backup of system data",
    "import": "Import events from external files",
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
