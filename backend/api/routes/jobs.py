"""API routes for background job tracking.

Provides endpoints for querying job status and starting export jobs.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.api.dependencies import get_export_service_dep, get_job_tracker_dep
from backend.api.schemas.jobs import (
    ExportFormat,
    ExportJobRequest,
    ExportJobStartResponse,
    JobResponse,
    JobStatusEnum,
)
from backend.core.logging import get_logger
from backend.services.export_service import ExportService
from backend.services.job_tracker import JobTracker

logger = get_logger(__name__)

router = APIRouter(tags=["jobs"])


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
