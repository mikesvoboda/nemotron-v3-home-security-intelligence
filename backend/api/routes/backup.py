"""API routes for backup and restore operations (B4.6 / 4n-restore.md)."""

from __future__ import annotations

import json
import tempfile
import zipfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
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
    TableRestoreSummary,
)
from backend.core.database import get_db, get_session_factory
from backend.core.logging import get_logger
from backend.core.time_utils import utc_now
from backend.models.backup_job import BackupJob, RestoreJob
from backend.models.backup_job import BackupJobStatus as BackupJobStatusModel
from backend.models.backup_job import RestoreJobStatus as RestoreJobStatusModel
from backend.services.backup_service import (
    BACKUP_DIR,
    SHARED_BACKUP_TABLES,
    BackupService,
    resolve_backup_dir,
)
from backend.services.restore_service import (
    BackupCorruptedError,
    BackupValidationError,
    RestoreError,
    RestoreService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])


@asynccontextmanager
async def _open_independent_session(
    fallback_db: AsyncSession,
) -> AsyncGenerator[AsyncSession]:
    """Open an independent AsyncSession, falling back to fallback_db only in mock-only tests."""
    try:
        factory = get_session_factory()
    except RuntimeError:
        yield fallback_db
        return

    async with factory() as session:
        yield session


def _extract_archive_label(backup_file_path: Path) -> str:
    """Read backup_id from the archive's manifest.json if possible, else file stem."""
    try:
        with zipfile.ZipFile(backup_file_path, "r") as zf:
            manifest_raw = json.loads(zf.read("manifest.json").decode("utf-8"))
            backup_id = manifest_raw.get("backup_id")
            if isinstance(backup_id, str) and backup_id:
                return backup_id
    except Exception:
        logger.debug("Could not read backup_id from archive manifest")
    return backup_file_path.stem


def _backup_model_to_response(job: BackupJob) -> BackupJobResponse:
    """Convert BackupJob model to BackupJobResponse schema."""
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
    """Convert RestoreJob model to RestoreJobResponse schema, unpacking JSONB _details."""
    progress = RestoreJobProgress(
        total_tables=job.total_tables,
        completed_tables=job.completed_tables,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
    )

    items_restored: dict[str, int] | None = None
    safety_backup_id: str | None = None
    tables: dict[str, TableRestoreSummary] | None = None
    added_rows: dict[str, list[str]] | None = None
    cleared_links: list[str] | None = None
    skipped_tables: list[str] | None = None
    same_installation: bool | None = None

    if isinstance(job.items_restored, dict):
        raw = dict(job.items_restored)
        details = raw.pop("_details", None)
        items_restored = {k: int(v) for k, v in raw.items() if isinstance(v, int | float)}
        if isinstance(details, dict):
            if isinstance(details.get("safety_backup_id"), str):
                safety_backup_id = details["safety_backup_id"]
            if isinstance(details.get("tables"), dict):
                tables = {
                    k: TableRestoreSummary.model_validate(v)
                    for k, v in details["tables"].items()
                    if isinstance(v, dict)
                }
            if isinstance(details.get("added_rows"), dict):
                added_rows = {
                    str(k): [str(item) for item in v]
                    for k, v in details["added_rows"].items()
                    if isinstance(v, list)
                }
            if isinstance(details.get("cleared_known_person_links"), list):
                cleared_links = [str(item) for item in details["cleared_known_person_links"]]
            if isinstance(details.get("skipped_tables"), list):
                skipped_tables = [str(item) for item in details["skipped_tables"]]
            if isinstance(details.get("same_installation"), bool):
                same_installation = details["same_installation"]

    return RestoreJobResponse(
        id=job.id,
        status=RestoreJobStatus(job.status.value),
        progress=progress,
        backup_id=job.backup_id,
        backup_created_at=job.backup_created_at,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        items_restored=items_restored,
        safety_backup_id=safety_backup_id,
        tables=tables,
        added_rows=added_rows,
        cleared_known_person_links=cleared_links,
        skipped_tables=skipped_tables,
        same_installation=same_installation,
        error_message=job.error_message,
    )


async def _get_backup_job(job_id: str, db: AsyncSession) -> BackupJob:
    """Get backup job by ID or raise 404."""
    result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup job not found: {job_id}",
        )

    return job


async def _get_restore_job(job_id: str, db: AsyncSession) -> RestoreJob:
    """Get restore job by ID or raise 404."""
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
    """Run a backup job in the background."""
    try:
        result = await db.execute(select(BackupJob).where(BackupJob.id == job_id))
        job = result.scalar_one_or_none()

        if job is None:
            logger.error("Backup job not found in database", extra={"job_id": job_id})
            return

        job.status = BackupJobStatusModel.RUNNING
        job.started_at = utc_now()
        job.total_tables = len(SHARED_BACKUP_TABLES)
        job.current_step = "Starting backup..."
        await db.commit()

        job_ref = job

        async def progress_callback(percent: int, step: str) -> None:
            await db.refresh(job_ref)
            job_ref.progress_percent = percent
            job_ref.current_step = step
            job_ref.completed_tables = int((percent / 100) * job_ref.total_tables)
            await db.commit()

        backup_result = await backup_service.create_backup(
            db=db,
            job_id=job_id,
            progress_callback=progress_callback,
        )

        await db.refresh(job)
        job.status = BackupJobStatusModel.COMPLETED
        job.completed_at = utc_now()
        job.progress_percent = 100
        job.completed_tables = job.total_tables
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
    *,
    backup_service: BackupService | None = None,
) -> None:
    """Run a restore job using three independent sessions (4n-restore.md §Shape):

    - Session A: creates and commits the automatic 'before restore' safety backup job.
    - Session B: runs RestoreService.restore_from_backup in one transaction with one commit.
    - Session C: writes RestoreJob progress and terminal status.
    """

    async def _update_restore_job(**fields: Any) -> bool:
        async with _open_independent_session(db) as progress_db:
            res = await progress_db.execute(select(RestoreJob).where(RestoreJob.id == job_id))
            job_row = res.scalar_one_or_none()
            if job_row is None:
                return False
            for k, v in fields.items():
                setattr(job_row, k, v)
            await progress_db.commit()
            return True

    try:
        found = await _update_restore_job(
            status=RestoreJobStatusModel.VALIDATING,
            started_at=utc_now(),
            total_tables=len(SHARED_BACKUP_TABLES),
            current_step="Creating safety backup before restore...",
        )
        if not found:
            logger.error("Restore job not found in database", extra={"job_id": job_id})
            return

        # Session A: take and commit the automatic safety backup before any row changes.
        safety_job_id = str(uuid4())
        source_label = _extract_archive_label(backup_file_path)
        safety_timestamp = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
        safety_label = f"before restore of {source_label} at {safety_timestamp}"
        active_backup_service = backup_service or BackupService(
            backup_dir=resolve_backup_dir(BACKUP_DIR)
        )

        try:
            async with _open_independent_session(db) as safety_db:
                safety_job = BackupJob(
                    id=safety_job_id,
                    status=BackupJobStatusModel.RUNNING,
                    started_at=utc_now(),
                    total_tables=len(SHARED_BACKUP_TABLES),
                    current_step=safety_label,
                )
                safety_db.add(safety_job)
                await safety_db.flush()

                safety_result = await active_backup_service.create_backup(
                    db=safety_db,
                    job_id=safety_job_id,
                    label=safety_label,
                )

                safety_job.status = BackupJobStatusModel.COMPLETED
                safety_job.completed_at = utc_now()
                safety_job.progress_percent = 100
                safety_job.completed_tables = len(SHARED_BACKUP_TABLES)
                safety_job.current_step = safety_label
                safety_job.file_path = str(safety_result.file_path)
                safety_job.file_size_bytes = safety_result.file_size
                safety_job.manifest_json = (
                    safety_result.manifest.to_dict() if safety_result.manifest else None
                )
                await safety_db.commit()
        except Exception as e:
            logger.error(
                "Safety backup failed; aborting restore before any row changes",
                extra={"job_id": job_id, "error": str(e)},
            )
            await _update_restore_job(
                status=RestoreJobStatusModel.FAILED,
                completed_at=utc_now(),
                error_message=f"Safety backup failed before restore: {e}",
            )
            return

        # Session C callback for progress updates during Session B's restore transaction.
        async def progress_callback(percent: int, step: str) -> None:
            next_status = (
                RestoreJobStatusModel.VALIDATING
                if percent < 20
                else RestoreJobStatusModel.RESTORING
            )
            await _update_restore_job(
                status=next_status,
                progress_percent=percent,
                current_step=step,
                completed_tables=int((percent / 100) * len(SHARED_BACKUP_TABLES)),
            )

        # Session B: run the restore in one transaction with one commit.
        async with _open_independent_session(db) as restore_db:
            try:
                restore_result = await restore_service.restore_from_backup(
                    backup_file=backup_file_path,
                    db=restore_db,
                    job_id=job_id,
                    progress_callback=progress_callback,
                )
                restore_result.safety_backup_id = safety_job_id
                await restore_db.commit()
            except Exception:
                await restore_db.rollback()
                raise

        tables_dict = {
            k: v.to_dict() if hasattr(v, "to_dict") else dict(v)
            for k, v in getattr(restore_result, "tables", {}).items()
        }
        stored_items: dict[str, Any] = {
            **restore_result.items_restored,
            "_details": {
                "safety_backup_id": restore_result.safety_backup_id,
                "tables": tables_dict,
                "added_rows": getattr(restore_result, "added_rows", {}),
                "cleared_known_person_links": getattr(
                    restore_result, "cleared_known_person_links", []
                ),
                "skipped_tables": getattr(restore_result, "skipped_tables", []),
                "same_installation": getattr(restore_result, "same_installation", False),
            },
        }

        await _update_restore_job(
            status=RestoreJobStatusModel.COMPLETED,
            completed_at=utc_now(),
            progress_percent=100,
            completed_tables=len(SHARED_BACKUP_TABLES),
            current_step="Complete",
            backup_id=restore_result.backup_id,
            backup_created_at=restore_result.backup_created_at,
            items_restored=stored_items,
        )

        logger.info(
            "Restore job completed",
            extra={
                "job_id": job_id,
                "backup_id": restore_result.backup_id,
                "safety_backup_id": safety_job_id,
                "total_items": restore_result.total_items,
            },
        )

    except (BackupValidationError, BackupCorruptedError, RestoreError) as e:
        logger.error("Restore job failed", extra={"job_id": job_id, "error": str(e)})
        try:
            await _update_restore_job(
                status=RestoreJobStatusModel.FAILED,
                completed_at=utc_now(),
                error_message=str(e),
            )
        except Exception:
            logger.exception("Failed to update job failure status")

    except Exception as e:
        logger.exception("Restore job failed", extra={"job_id": job_id})
        try:
            await _update_restore_job(
                status=RestoreJobStatusModel.FAILED,
                completed_at=utc_now(),
                error_message=str(e),
            )
        except Exception:
            logger.exception("Failed to update job failure status")

    finally:
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
    """Create a new backup job."""
    job_id = str(uuid4())

    backup_job = BackupJob(
        id=job_id,
        status=BackupJobStatusModel.PENDING,
        total_tables=len(SHARED_BACKUP_TABLES),
    )

    db.add(backup_job)
    await db.commit()

    backup_service = BackupService(backup_dir=resolve_backup_dir(BACKUP_DIR))

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
    """List available backups."""
    active_dir = resolve_backup_dir(BACKUP_DIR)
    active_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = await db.execute(
            select(BackupJob)
            .where(BackupJob.status == BackupJobStatusModel.COMPLETED)
            .order_by(BackupJob.created_at.desc())
        )
        jobs = result.scalars().all()
    except Exception as e:
        logger.warning(f"Failed to query backup jobs: {e}")
        return BackupListResponse(backups=[], total=0)

    backups = []
    for job in jobs:
        download_url = None
        if job.file_path:
            download_url = f"/api/backup/{job.id}/download"
        label = None
        if isinstance(job.manifest_json, dict) and isinstance(job.manifest_json.get("label"), str):
            label = job.manifest_json["label"]

        backups.append(
            BackupListItem(
                id=job.id,
                created_at=job.created_at,
                file_size_bytes=job.file_size_bytes or 0,
                status=BackupJobStatus(job.status.value),
                download_url=download_url,
                label=label,
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
    """Get backup job status."""
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
    """Download completed backup file."""
    job = await _get_backup_job(job_id, db)

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

    filename = Path(job.file_path).name
    active_dir = resolve_backup_dir(BACKUP_DIR)
    file_path = active_dir / filename
    if not file_path.exists() and Path(job.file_path).exists():
        file_path = Path(job.file_path)

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
    """Delete a backup."""
    job = await _get_backup_job(job_id, db)

    if job.file_path:
        filename = Path(job.file_path).name
        active_dir = resolve_backup_dir(BACKUP_DIR)
        file_path = active_dir / filename
        if file_path.exists():
            file_path.unlink()
        elif Path(job.file_path).exists():
            Path(job.file_path).unlink()

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
    """Start a restore job from uploaded backup file."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Expected a .zip backup file.",
        )

    job_id = str(uuid4())

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

    restore_job = RestoreJob(
        id=job_id,
        status=RestoreJobStatusModel.PENDING,
        total_tables=len(SHARED_BACKUP_TABLES),
    )

    db.add(restore_job)
    await db.commit()

    restore_service = RestoreService()

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
    """Get restore job status."""
    job = await _get_restore_job(job_id, db)
    return _restore_model_to_response(job)
