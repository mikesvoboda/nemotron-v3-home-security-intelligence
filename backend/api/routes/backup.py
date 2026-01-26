"""API routes for backup and restore operations.

Provides endpoints for creating system backups, listing backups, downloading
backup files, and restoring from backup files.

Endpoints:
    POST /api/backup              - Create a new backup job
    GET  /api/backup              - List available backups
    GET  /api/backup/{job_id}     - Get backup job status
    GET  /api/backup/{job_id}/download - Download backup file
    DELETE /api/backup/{job_id}   - Delete a backup
    POST /api/backup/restore      - Start restore from uploaded file
    GET  /api/backup/restore/{job_id} - Get restore job status

NEM-3566: Backup/Restore implementation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.backup import (
    BackupJobCreate,
    BackupJobProgress,
    BackupJobResponse,
    BackupJobStartResponse,
    BackupJobStatus,
    BackupListItem,
    BackupListResponse,
    BackupManifest,
    RestoreJobProgress,
    RestoreJobResponse,
    RestoreJobStartResponse,
    RestoreJobStatus,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.backup_job import BackupJob, RestoreJob
from backend.models.backup_job import BackupJobStatus as BackupJobStatusModel
from backend.models.backup_job import RestoreJobStatus as RestoreJobStatusModel
from backend.services.backup_service import BACKUP_DIR, BackupService
from backend.services.restore_service import (
    BackupCorruptedError,
    BackupValidationError,
    RestoreError,
    RestoreService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _backup_model_to_response(job: BackupJob) -> BackupJobResponse:
    """Convert BackupJob model to BackupJobResponse schema.

    Args:
        job: BackupJob database model instance.

    Returns:
        BackupJobResponse schema instance.
    """
    progress = BackupJobProgress(
        total_tables=job.total_tables,
        completed_tables=job.completed_tables,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
    )

    manifest = None
    if job.manifest_json:
        try:
            manifest = BackupManifest.model_validate(job.manifest_json)
        except Exception:
            # Invalid manifest JSON, leave as None
            logger.debug("Failed to parse backup manifest JSON", extra={"job_id": job.id})

    return BackupJobResponse(
        id=job.id,
        status=BackupJobStatus(job.status.value),
        progress=progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        file_path=job.file_path,
        file_size_bytes=job.file_size_bytes,
        manifest=manifest,
        error_message=job.error_message,
    )


def _restore_model_to_response(job: RestoreJob) -> RestoreJobResponse:
    """Convert RestoreJob model to RestoreJobResponse schema.

    Args:
        job: RestoreJob database model instance.

    Returns:
        RestoreJobResponse schema instance.
    """
    progress = RestoreJobProgress(
        total_tables=job.total_tables,
        completed_tables=job.completed_tables,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
    )

    return RestoreJobResponse(
        id=job.id,
        status=RestoreJobStatus(job.status.value),
        progress=progress,
        backup_id=job.backup_id,
        backup_created_at=job.backup_created_at,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        items_restored=job.items_restored,
        error_message=job.error_message,
    )


async def _get_backup_job(job_id: str, db: AsyncSession) -> BackupJob:
    """Get backup job by ID or raise 404.

    Args:
        job_id: Backup job UUID.
        db: Database session.

    Returns:
        BackupJob instance.

    Raises:
        HTTPException: 404 if job not found.
    """
    result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup job not found: {job_id}",
        )

    return job


async def _get_restore_job(job_id: str, db: AsyncSession) -> RestoreJob:
    """Get restore job by ID or raise 404.

    Args:
        job_id: Restore job UUID.
        db: Database session.

    Returns:
        RestoreJob instance.

    Raises:
        HTTPException: 404 if job not found.
    """
    result = await db.execute(select(RestoreJob).where(RestoreJob.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restore job not found: {job_id}",
        )

    return job


async def run_backup_job(
    job_id: str,
    backup_service: BackupService,
    db: AsyncSession,
) -> None:
    """Run a backup job in the background.

    Updates the database with progress and results.

    Args:
        job_id: Backup job UUID.
        backup_service: BackupService instance.
        db: Database session.
    """
    try:
        # Update job to running
        result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
        job = result.scalar_one_or_none()

        if job is None:
            logger.error("Backup job not found in database", extra={"job_id": job_id})
            return

        job.status = BackupJobStatusModel.RUNNING
        job.started_at = utc_now()
        job.current_step = "Starting backup..."
        await db.commit()

        # Create a reference to job for the closure
        # job is guaranteed to be non-None at this point
        job_ref = job

        # Progress callback to update database
        async def progress_callback(percent: int, step: str) -> None:
            await db.refresh(job_ref)
            job_ref.progress_percent = percent
            job_ref.current_step = step
            job_ref.completed_tables = int((percent / 100) * job_ref.total_tables)
            await db.commit()

        # Run the backup
        backup_result = await backup_service.create_backup(
            db=db,
            job_id=job_id,
            progress_callback=progress_callback,
        )

        # Update database with result
        await db.refresh(job)
        job.status = BackupJobStatusModel.COMPLETED
        job.completed_at = utc_now()
        job.progress_percent = 100
        job.current_step = "Complete"
        job.file_path = str(backup_result.file_path)
        job.file_size_bytes = backup_result.file_size
        job.manifest_json = backup_result.manifest.to_dict() if backup_result.manifest else None
        await db.commit()

        logger.info(
            "Backup job completed",
            extra={
                "job_id": job_id,
                "file_path": backup_result.file_path,
                "file_size": backup_result.file_size,
            },
        )

    except Exception as e:
        logger.exception("Backup job failed", extra={"job_id": job_id})

        # Update database with failure
        try:
            result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
            job = result.scalar_one_or_none()
            if job is not None:
                job.status = BackupJobStatusModel.FAILED
                job.completed_at = utc_now()
                job.error_message = str(e)
                await db.commit()
        except Exception:
            logger.exception("Failed to update job failure status")


async def run_restore_job(
    job_id: str,
    backup_file_path: Path,
    restore_service: RestoreService,
    db: AsyncSession,
) -> None:
    """Run a restore job in the background.

    Updates the database with progress and results.

    Args:
        job_id: Restore job UUID.
        backup_file_path: Path to the uploaded backup file.
        restore_service: RestoreService instance.
        db: Database session.
    """
    try:
        # Update job to validating
        result = await db.execute(select(RestoreJob).where(RestoreJob.id == job_id))
        job = result.scalar_one_or_none()

        if job is None:
            logger.error("Restore job not found in database", extra={"job_id": job_id})
            return

        job.status = RestoreJobStatusModel.VALIDATING
        job.started_at = utc_now()
        job.current_step = "Validating backup..."
        await db.commit()

        # Create a reference to job for the closure
        # job is guaranteed to be non-None at this point
        job_ref = job

        # Progress callback to update database
        async def progress_callback(percent: int, step: str) -> None:
            await db.refresh(job_ref)

            # Determine status based on progress
            if percent < 20:
                job_ref.status = RestoreJobStatusModel.VALIDATING
            else:
                job_ref.status = RestoreJobStatusModel.RESTORING

            job_ref.progress_percent = percent
            job_ref.current_step = step
            job_ref.completed_tables = int((percent / 100) * job_ref.total_tables)
            await db.commit()

        # Run the restore
        restore_result = await restore_service.restore_from_backup(
            backup_file=backup_file_path,
            db=db,
            job_id=job_id,
            progress_callback=progress_callback,
        )

        # Update database with result
        await db.refresh(job)
        job.status = RestoreJobStatusModel.COMPLETED
        job.completed_at = utc_now()
        job.progress_percent = 100
        job.current_step = "Complete"
        job.backup_id = restore_result.backup_id
        job.backup_created_at = restore_result.backup_created_at
        job.items_restored = restore_result.items_restored
        await db.commit()

        logger.info(
            "Restore job completed",
            extra={
                "job_id": job_id,
                "backup_id": restore_result.backup_id,
                "total_items": restore_result.total_items,
            },
        )

    except (BackupValidationError, BackupCorruptedError, RestoreError) as e:
        logger.error("Restore job failed", extra={"job_id": job_id, "error": str(e)})

        # Update database with failure
        try:
            result = await db.execute(select(RestoreJob).where(RestoreJob.id == job_id))
            job = result.scalar_one_or_none()
            if job is not None:
                job.status = RestoreJobStatusModel.FAILED
                job.completed_at = utc_now()
                job.error_message = str(e)
                await db.commit()
        except Exception:
            logger.exception("Failed to update job failure status")

    except Exception as e:
        logger.exception("Restore job failed", extra={"job_id": job_id})

        # Update database with failure
        try:
            result = await db.execute(select(RestoreJob).where(RestoreJob.id == job_id))
            job = result.scalar_one_or_none()
            if job is not None:
                job.status = RestoreJobStatusModel.FAILED
                job.completed_at = utc_now()
                job.error_message = str(e)
                await db.commit()
        except Exception:
            logger.exception("Failed to update job failure status")

    finally:
        # Clean up the temporary backup file
        try:
            if backup_file_path.exists():
                backup_file_path.unlink()
        except Exception:
            logger.warning(
                "Failed to clean up temporary backup file",
                extra={"path": str(backup_file_path)},
            )


@router.post(
    "",
    response_model=BackupJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create backup job",
    description=(
        "Create a new backup job that runs in the background. "
        "Use GET /api/backup/{job_id} to track progress."
    ),
)
async def create_backup(
    request: BackupJobCreate,  # noqa: ARG001 - Required for OpenAPI schema
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> BackupJobStartResponse:
    """Create a new backup job.

    Creates a backup job record in the database and schedules background
    processing. Progress can be tracked via the status endpoint.

    Args:
        request: Backup job parameters (empty for full backup).
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        Job start response with job ID for tracking.
    """
    # Generate job ID
    job_id = str(uuid4())

    # Create database record
    backup_job = BackupJob(
        id=job_id,
        status=BackupJobStatusModel.PENDING,
    )

    db.add(backup_job)
    await db.commit()

    # Create service instance
    backup_service = BackupService()

    # Schedule background task
    background_tasks.add_task(
        run_backup_job,
        job_id=job_id,
        backup_service=backup_service,
        db=db,
    )

    logger.info("Backup job started", extra={"job_id": job_id})

    return BackupJobStartResponse(
        job_id=job_id,
        status=BackupJobStatus.PENDING,
        message=f"Backup job created. Use GET /api/backup/{job_id} to track progress.",
    )


@router.get(
    "",
    response_model=BackupListResponse,
    summary="List backups",
    description="List available backup files.",
)
async def list_backups(
    db: AsyncSession = Depends(get_db),
) -> BackupListResponse:
    """List available backups.

    Returns completed backup jobs that have files available for download.

    Args:
        db: Database session.

    Returns:
        List of available backups.
    """
    # Query completed backup jobs
    result = await db.execute(
        select(BackupJob)
        .where(BackupJob.status == BackupJobStatusModel.COMPLETED)
        .order_by(BackupJob.created_at.desc())
    )
    jobs = result.scalars().all()

    backups = []
    for job in jobs:
        download_url = None
        if job.file_path:
            download_url = f"/api/backup/{job.id}/download"

        backups.append(
            BackupListItem(
                id=job.id,
                created_at=job.created_at,
                file_size_bytes=job.file_size_bytes or 0,
                status=BackupJobStatus(job.status.value),
                download_url=download_url,
            )
        )

    return BackupListResponse(
        backups=backups,
        total=len(backups),
    )


@router.get(
    "/{job_id}",
    response_model=BackupJobResponse,
    summary="Get backup status",
    description="Get the current status and progress of a backup job.",
    responses={
        404: {"description": "Backup job not found"},
    },
)
async def get_backup_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> BackupJobResponse:
    """Get backup job status.

    Args:
        job_id: Backup job UUID.
        db: Database session.

    Returns:
        Backup job status and progress information.
    """
    job = await _get_backup_job(job_id, db)
    return _backup_model_to_response(job)


@router.get(
    "/{job_id}/download",
    summary="Download backup file",
    description="Download the completed backup file.",
    responses={
        404: {"description": "Backup job or file not found"},
        400: {"description": "Backup not yet complete"},
    },
)
async def download_backup(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download completed backup file.

    Args:
        job_id: Backup job UUID.
        db: Database session.

    Returns:
        File download response.
    """
    job = await _get_backup_job(job_id, db)

    # Check if complete
    if job.status != BackupJobStatusModel.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backup job is not complete (status: {job.status.value})",
        )

    if not job.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup file path not found",
        )

    # Extract filename from stored path
    filename = Path(job.file_path).name
    file_path = BACKUP_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup file not found on disk",
        )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/{job_id}",
    summary="Delete backup",
    description="Delete a backup file and its job record.",
    responses={
        404: {"description": "Backup job not found"},
    },
)
async def delete_backup(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Delete a backup.

    Deletes the backup file from disk and removes the job record.

    Args:
        job_id: Backup job UUID.
        db: Database session.

    Returns:
        Deletion confirmation.
    """
    job = await _get_backup_job(job_id, db)

    # Delete file if exists
    if job.file_path:
        filename = Path(job.file_path).name
        file_path = BACKUP_DIR / filename
        if file_path.exists():
            file_path.unlink()

    # Delete database record
    await db.delete(job)
    await db.commit()

    logger.info("Backup deleted", extra={"job_id": job_id})

    return {"deleted": True}


@router.post(
    "/restore",
    response_model=RestoreJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start restore",
    description=(
        "Start a restore operation from an uploaded backup file. "
        "Use GET /api/backup/restore/{job_id} to track progress."
    ),
    responses={
        400: {"description": "Invalid backup file"},
    },
)
async def start_restore(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Backup ZIP file"),
    db: AsyncSession = Depends(get_db),
) -> RestoreJobStartResponse:
    """Start a restore job from uploaded backup file.

    Creates a restore job record in the database, saves the uploaded file,
    and schedules background processing. Progress can be tracked via the
    status endpoint.

    Args:
        background_tasks: FastAPI background tasks.
        file: Uploaded backup ZIP file.
        db: Database session.

    Returns:
        Job start response with job ID for tracking.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Expected a .zip backup file.",
        )

    # Generate job ID
    job_id = str(uuid4())

    # Save uploaded file to temp location
    temp_dir = Path(tempfile.gettempdir()) / "backup_restore"
    temp_dir.mkdir(parents=True, exist_ok=True)
    backup_file_path = temp_dir / f"{job_id}.zip"

    try:
        content = await file.read()
        backup_file_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to save uploaded file: {e}",
        ) from e

    # Create database record
    restore_job = RestoreJob(
        id=job_id,
        status=RestoreJobStatusModel.PENDING,
    )

    db.add(restore_job)
    await db.commit()

    # Create service instance
    restore_service = RestoreService()

    # Schedule background task
    background_tasks.add_task(
        run_restore_job,
        job_id=job_id,
        backup_file_path=backup_file_path,
        restore_service=restore_service,
        db=db,
    )

    logger.info(
        "Restore job started",
        extra={"job_id": job_id, "filename": file.filename},
    )

    return RestoreJobStartResponse(
        job_id=job_id,
        status=RestoreJobStatus.PENDING,
        message=f"Restore job created. Use GET /api/backup/restore/{job_id} to track progress.",
    )


@router.get(
    "/restore/{job_id}",
    response_model=RestoreJobResponse,
    summary="Get restore status",
    description="Get the current status and progress of a restore job.",
    responses={
        404: {"description": "Restore job not found"},
    },
)
async def get_restore_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> RestoreJobResponse:
    """Get restore job status.

    Args:
        job_id: Restore job UUID.
        db: Database session.

    Returns:
        Restore job status and progress information.
    """
    job = await _get_restore_job(job_id, db)
    return _restore_model_to_response(job)
