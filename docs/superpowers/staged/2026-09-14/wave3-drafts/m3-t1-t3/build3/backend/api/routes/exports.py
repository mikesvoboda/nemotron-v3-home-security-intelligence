"""API routes for export job management with database persistence.

Provides dedicated endpoints for export jobs with progress tracking
stored in the database (ExportJob model). This complements the
in-memory/Redis job tracking in jobs.py with persistent export history.

Endpoints:
    POST /api/exports              - Start new export
    GET  /api/exports/{job_id}     - Get export status
    GET  /api/exports              - List recent exports
    DELETE /api/exports/{job_id}   - Cancel export
    GET  /api/exports/{job_id}/download - Download completed export
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_export_service_dep, get_job_tracker_dep
from backend.api.schemas.export import (
    ExportDownloadResponse,
    ExportJobCancelResponse,
    ExportJobCreate,
    ExportJobListResponse,
    ExportJobProgress,
    ExportJobResponse,
    ExportJobResult,
    ExportJobStartResponse,
    ExportJobStatusEnum,
)
from backend.api.schemas.pagination import create_pagination_meta
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.export_job import ExportJob, ExportJobStatus
from backend.services.export_service import EXPORT_DIR, ExportService

if TYPE_CHECKING:
    from backend.services.job_tracker import JobTracker

logger = get_logger(__name__)

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _model_to_response(job: ExportJob) -> ExportJobResponse:
    """Convert ExportJob model to ExportJobResponse schema.

    Args:
        job: ExportJob database model instance.

    Returns:
        ExportJobResponse schema instance.
    """
    progress = ExportJobProgress(
        total_items=job.total_items,
        processed_items=job.processed_items,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        estimated_completion=job.estimated_completion,
    )

    result = None
    if job.status == ExportJobStatus.COMPLETED and job.output_path:
        result = ExportJobResult(
            output_path=job.output_path,
            output_size_bytes=job.output_size_bytes,
            event_count=job.processed_items,
            format=job.export_format,
        )

    return ExportJobResponse(
        id=job.id,
        status=ExportJobStatusEnum(job.status.value),
        export_type=job.export_type,
        export_format=job.export_format,
        progress=progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        filter_params=job.filter_params,
        result=result,
        error_message=job.error_message,
    )


async def _get_export_job(job_id: str, db: AsyncSession) -> ExportJob:
    """Get export job by ID or raise 404.

    Args:
        job_id: Export job UUID.
        db: Database session.

    Returns:
        ExportJob instance.

    Raises:
        HTTPException: 404 if job not found.
    """
    result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job not found: {job_id}",
        )

    return job


async def run_export_job_with_db(
    job_id: str,
    export_format: str,
    camera_id: str | None,
    risk_level: str | None,
    start_date: str | None,
    end_date: str | None,
    reviewed: bool | None,
    columns: list[str] | None,
    export_service: ExportService,
    job_tracker: JobTracker,
    db: AsyncSession,
) -> None:
    """Run an export job and update database progress.

    This function runs in the background and updates both the in-memory
    job tracker (for WebSocket broadcasts) and the database (for persistence).

    Args:
        job_id: Export job UUID.
        export_format: Export format (csv, json, zip).
        camera_id: Optional camera filter.
        risk_level: Optional risk level filter.
        start_date: Optional start date filter (ISO format).
        end_date: Optional end date filter (ISO format).
        reviewed: Optional reviewed filter.
        export_service: Export service instance.
        job_tracker: Job tracker for WebSocket broadcasts.
        db: Database session for persistence.
    """
    try:
        # Update job to running
        result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
        job = result.scalar_one_or_none()

        if job is None:
            logger.error("Export job not found in database", extra={"job_id": job_id})
            return

        job.status = ExportJobStatus.RUNNING
        job.started_at = utc_now()
        job.current_step = f"Starting {export_format.upper()} export..."
        await db.commit()

        # Start job in tracker too
        job_tracker.start_job(job_id, message=f"Starting {export_format.upper()} export...")

        # Run the export with progress tracking
        export_result = await export_service.export_events_with_progress(
            job_id=job_id,
            job_tracker=job_tracker,
            export_format=export_format,
            camera_id=camera_id,
            risk_level=risk_level,
            start_date=start_date,
            end_date=end_date,
            reviewed=reviewed,
            columns=columns,
        )

        # Update database with result
        await db.refresh(job)
        job.status = ExportJobStatus.COMPLETED
        job.completed_at = utc_now()
        job.progress_percent = 100
        job.current_step = "Complete"
        job.output_path = export_result.get("file_path")
        job.output_size_bytes = export_result.get("file_size")
        job.processed_items = export_result.get("event_count", 0)
        job.total_items = export_result.get("event_count", 0)
        await db.commit()

        # Complete in tracker
        job_tracker.complete_job(job_id, result=export_result)

        logger.info(
            "Export job completed",
            extra={
                "job_id": job_id,
                "format": export_format,
                "event_count": export_result.get("event_count"),
            },
        )

    except Exception as e:
        logger.exception("Export job failed", extra={"job_id": job_id})

        # Update database with failure
        try:
            await db.refresh(job)
            if job is not None:
                job.status = ExportJobStatus.FAILED
                job.completed_at = utc_now()
                job.error_message = str(e)
                await db.commit()
        except Exception:
            logger.exception("Failed to update job failure status")

        # Fail in tracker
        job_tracker.fail_job(job_id, str(e))


@router.post(
    "",
    response_model=ExportJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start export job",
    description=(
        "Start a new background export job. Returns a job ID that can be used "
        "to track progress via GET /api/exports/{job_id}."
    ),
)
async def start_export(
    request: ExportJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    export_service: ExportService = Depends(get_export_service_dep),
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> ExportJobStartResponse:
    """Start a new export job.

    Creates an export job record in the database and schedules background
    processing. Progress can be tracked via the status endpoint or WebSocket.

    Args:
        request: Export job parameters.
        background_tasks: FastAPI background tasks.
        db: Database session.
        export_service: Export service.
        job_tracker: Job tracker for WebSocket broadcasts.

    Returns:
        Job start response with job ID for tracking.
    """
    # Generate job ID
    job_id = str(uuid4())

    # Serialize filter params for storage
    filter_params = json.dumps(
        {
            "camera_id": request.camera_id,
            "risk_level": request.risk_level,
            "start_date": request.start_date.isoformat() if request.start_date else None,
            "end_date": request.end_date.isoformat() if request.end_date else None,
            "reviewed": request.reviewed,
            "columns": request.columns,
        }
    )

    # Create database record
    export_job = ExportJob(
        id=job_id,
        status=ExportJobStatus.PENDING,
        export_type=request.export_type.value,
        export_format=request.export_format.value,
        filter_params=filter_params,
    )

    db.add(export_job)
    await db.commit()

    # Create in-memory job for WebSocket tracking
    job_tracker.create_job("export", job_id=job_id)

    # Convert dates to ISO strings
    start_date_str = request.start_date.isoformat() if request.start_date else None
    end_date_str = request.end_date.isoformat() if request.end_date else None

    # Schedule background task
    background_tasks.add_task(
        run_export_job_with_db,
        job_id=job_id,
        export_format=request.export_format.value,
        camera_id=request.camera_id,
        risk_level=request.risk_level,
        start_date=start_date_str,
        end_date=end_date_str,
        reviewed=request.reviewed,
        columns=request.columns,
        export_service=export_service,
        job_tracker=job_tracker,
        db=db,
    )

    logger.info(
        "Export job started",
        extra={
            "job_id": job_id,
            "export_type": request.export_type.value,
            "format": request.export_format.value,
        },
    )

    return ExportJobStartResponse(
        job_id=job_id,
        status=ExportJobStatusEnum.PENDING,
        message=f"Export job created. Use GET /api/exports/{job_id} to track progress.",
    )


@router.get(
    "",
    response_model=ExportJobListResponse,
    summary="List export jobs",
    description="List recent export jobs with optional filtering by status.",
)
async def list_exports(
    status_filter: ExportJobStatusEnum | None = Query(
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
    db: AsyncSession = Depends(get_db),
) -> ExportJobListResponse:
    """List export jobs with optional filtering.

    Args:
        status_filter: Optional filter by job status.
        limit: Maximum number of jobs to return.
        offset: Number of jobs to skip for pagination.
        db: Database session.

    Returns:
        Paginated list of export jobs.
    """
    # Build query
    query = select(ExportJob).order_by(ExportJob.created_at.desc())

    if status_filter:
        db_status = ExportJobStatus(status_filter.value)
        query = query.where(ExportJob.status == db_status)

    # Get total count using efficient database COUNT
    count_query = select(func.count()).select_from(ExportJob)
    if status_filter:
        db_status = ExportJobStatus(status_filter.value)
        count_query = count_query.where(ExportJob.status == db_status)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Convert to response models
    job_responses = [_model_to_response(job) for job in jobs]

    return ExportJobListResponse(
        items=job_responses,
        pagination=create_pagination_meta(
            total=total,
            limit=limit,
            offset=offset,
            items_count=len(job_responses),
        ),
    )


@router.get(
    "/{job_id}",
    response_model=ExportJobResponse,
    summary="Get export status",
    description="Get the current status and progress of an export job.",
    responses={
        404: {"description": "Export job not found"},
    },
)
async def get_export_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    """Get export job status.

    Args:
        job_id: Export job UUID.
        db: Database session.

    Returns:
        Export job status and progress information.
    """
    job = await _get_export_job(job_id, db)
    return _model_to_response(job)


@router.delete(
    "/{job_id}",
    response_model=ExportJobCancelResponse,
    summary="Cancel export job",
    description=(
        "Cancel a pending or running export job. Completed or failed jobs cannot be cancelled."
    ),
    responses={
        404: {"description": "Export job not found"},
        409: {"description": "Job cannot be cancelled (already completed or failed)"},
    },
)
async def cancel_export(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    job_tracker: JobTracker = Depends(get_job_tracker_dep),
) -> ExportJobCancelResponse:
    """Cancel an export job.

    Args:
        job_id: Export job UUID.
        db: Database session.
        job_tracker: Job tracker for WebSocket notification.

    Returns:
        Cancellation response.
    """
    job = await _get_export_job(job_id, db)

    # Check if cancellable
    if job.status in (ExportJobStatus.COMPLETED, ExportJobStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Export job cannot be cancelled - it has already completed or failed",
        )

    # Update database
    job.status = ExportJobStatus.FAILED
    job.completed_at = utc_now()
    job.error_message = "Cancelled by user"
    await db.commit()

    # Cancel in tracker (for WebSocket notification)
    try:
        job_tracker.cancel_job(job_id)
    except KeyError:
        # Job may not exist in in-memory tracker (already completed/expired).
        # This is expected during race conditions or if the job finished before cancel.
        # Database state is authoritative; in-memory tracker is for WebSocket notifications only.
        # See: NEM-2540 for rationale
        pass

    logger.info("Export job cancelled", extra={"job_id": job_id})

    return ExportJobCancelResponse(
        job_id=job_id,
        status=ExportJobStatusEnum.FAILED,
        message="Export job cancelled by user",
        cancelled=True,
    )


@router.get(
    "/{job_id}/download",
    summary="Download export file",
    description="Download the completed export file.",
    responses={
        404: {"description": "Export job or file not found"},
        400: {"description": "Export not yet complete"},
    },
)
async def download_export(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download completed export file.

    Args:
        job_id: Export job UUID.
        db: Database session.

    Returns:
        File download response.
    """
    job = await _get_export_job(job_id, db)

    # Check if complete
    if job.status != ExportJobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export job is not complete (status: {job.status.value})",
        )

    if not job.output_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file path not found",
        )

    # Extract filename from API path (e.g., /api/exports/file.csv -> file.csv)
    filename = job.output_path.split("/")[-1]
    file_path = EXPORT_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found on disk",
        )

    # Determine content type based on format
    content_types = {
        "csv": "text/csv",
        "json": "application/json",
        "zip": "application/zip",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    content_type = content_types.get(job.export_format, "application/octet-stream")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{job_id}/download/info",
    response_model=ExportDownloadResponse,
    summary="Get download info",
    description="Get metadata about the export file for download.",
    responses={
        404: {"description": "Export job not found"},
    },
)
async def get_download_info(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExportDownloadResponse:
    """Get export file download metadata.

    Args:
        job_id: Export job UUID.
        db: Database session.

    Returns:
        Download metadata including readiness status.
    """
    job = await _get_export_job(job_id, db)

    if job.status != ExportJobStatus.COMPLETED or not job.output_path:
        return ExportDownloadResponse(
            ready=False,
            filename=None,
            content_type=None,
            size_bytes=None,
            download_url=None,
        )

    filename = job.output_path.split("/")[-1]
    file_path = EXPORT_DIR / filename

    if not file_path.exists():
        return ExportDownloadResponse(
            ready=False,
            filename=None,
            content_type=None,
            size_bytes=None,
            download_url=None,
        )

    content_types = {
        "csv": "text/csv",
        "json": "application/json",
        "zip": "application/zip",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    content_type = content_types.get(job.export_format, "application/octet-stream")

    return ExportDownloadResponse(
        ready=True,
        filename=filename,
        content_type=content_type,
        size_bytes=job.output_size_bytes,
        download_url=f"/api/exports/{job_id}/download",
    )
