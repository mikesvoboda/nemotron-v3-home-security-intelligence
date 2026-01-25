"""Pydantic schemas for backup/restore API endpoints.

This module defines request/response schemas for the backup and restore
functionality. Supports full system backup with progress tracking and
restore operations with validation.

Backup Flow:
    1. Create backup job (POST /api/backup)
    2. Poll for progress (GET /api/backup/{job_id})
    3. Download when completed (GET /api/backup/{job_id}/download)

Restore Flow:
    1. Upload backup file (POST /api/backup/restore)
    2. Poll for progress (GET /api/backup/restore/{job_id})
    3. System restored when completed
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Enums
# =============================================================================


class BackupJobStatus(StrEnum):
    """Backup job status values."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class RestoreJobStatus(StrEnum):
    """Restore job status values."""

    PENDING = auto()
    VALIDATING = auto()
    RESTORING = auto()
    COMPLETED = auto()
    FAILED = auto()


# =============================================================================
# Backup Manifest (stored in backup ZIP)
# =============================================================================


class BackupContentInfo(BaseModel):
    """Information about a single backup content type.

    Stored inside the backup manifest to track what data is included
    and verify integrity via checksum.
    """

    count: int = Field(..., description="Number of records")
    checksum: str = Field(..., description="SHA256 checksum of the JSON file")


class BackupManifest(BaseModel):
    """Manifest file stored inside backup ZIP.

    The manifest is written as manifest.json at the root of the backup
    archive. It contains metadata about the backup and checksums for
    all included data files.
    """

    model_config = ConfigDict(from_attributes=True)

    backup_id: str = Field(..., description="Unique backup identifier")
    version: str = Field(..., description="Backup format version (e.g., '1.0')")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    app_version: str | None = Field(None, description="Application version")
    contents: dict[str, BackupContentInfo] = Field(
        default_factory=dict,
        description="Map of content type to info (events, alerts, cameras, etc.)",
    )


# =============================================================================
# API Request/Response Schemas
# =============================================================================


class BackupJobCreate(BaseModel):
    """Schema for creating a backup job (no parameters needed for full backup).

    Full system backups export all data without filters. Simply POST
    to the endpoint to create a new backup job.
    """

    model_config = ConfigDict(json_schema_extra={"example": {}})
    # Full backup has no parameters - exports everything


class BackupJobStartResponse(BaseModel):
    """Response when creating a backup job.

    Returns the job ID that can be used to track progress via
    GET /api/backup/{job_id}.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "019478a1-b2c3-7def-8901-234567890abc",
                "status": "pending",
                "message": "Backup job created. Use GET /api/backup/{job_id} to track progress.",
            }
        }
    )

    job_id: str = Field(..., description="Unique job identifier")
    status: BackupJobStatus = Field(BackupJobStatus.PENDING, description="Initial status")
    message: str = Field(..., description="Human-readable message")


class BackupJobProgress(BaseModel):
    """Progress information for a backup job.

    Tracks how many tables have been exported and the overall
    progress percentage.
    """

    total_tables: int = Field(8, description="Total tables to export")
    completed_tables: int = Field(0, description="Tables exported so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")


class BackupJobResponse(BaseModel):
    """Full status response for a backup job.

    Complete status information for a backup job, including progress,
    timing, result, and any error information.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique backup job identifier")
    status: BackupJobStatus = Field(..., description="Current job status")
    progress: BackupJobProgress = Field(default_factory=BackupJobProgress)

    # Timing
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Job start timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")

    # Result (on completion)
    file_path: str | None = Field(None, description="Download path for backup file")
    file_size_bytes: int | None = Field(None, description="Backup file size")
    manifest: BackupManifest | None = Field(None, description="Backup manifest")

    # Error (on failure)
    error_message: str | None = Field(None, description="Error message if failed")


class BackupListItem(BaseModel):
    """Summary item for backup list.

    Lightweight representation of a backup for list views.
    """

    id: str = Field(..., description="Backup ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    file_size_bytes: int = Field(..., description="File size in bytes")
    status: BackupJobStatus = Field(..., description="Job status")
    download_url: str | None = Field(None, description="Download URL if completed")


class BackupListResponse(BaseModel):
    """Response for listing available backups."""

    backups: list[BackupListItem] = Field(default_factory=list)
    total: int = Field(0, description="Total number of backups")


# =============================================================================
# Restore Schemas
# =============================================================================


class RestoreJobStartResponse(BaseModel):
    """Response when starting a restore job.

    Returns the job ID that can be used to track progress via
    GET /api/backup/restore/{job_id}.
    """

    job_id: str = Field(..., description="Unique restore job identifier")
    status: RestoreJobStatus = Field(RestoreJobStatus.PENDING)
    message: str = Field(..., description="Human-readable message")


class RestoreJobProgress(BaseModel):
    """Progress information for a restore job.

    Tracks how many tables have been restored and the overall
    progress percentage.
    """

    total_tables: int = Field(8, description="Total tables to restore")
    completed_tables: int = Field(0, description="Tables restored so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")


class RestoreJobResponse(BaseModel):
    """Full status response for a restore job.

    Complete status information for a restore job, including progress,
    source backup info, timing, result, and any error information.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique restore job identifier")
    status: RestoreJobStatus = Field(..., description="Current job status")
    progress: RestoreJobProgress = Field(default_factory=RestoreJobProgress)

    # Source backup info
    backup_id: str | None = Field(None, description="Source backup ID from manifest")
    backup_created_at: datetime | None = Field(None, description="When source backup was created")

    # Timing
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Job start timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")

    # Result (on completion)
    items_restored: dict[str, int] | None = Field(
        None, description="Count of restored items per table"
    )

    # Error (on failure)
    error_message: str | None = Field(None, description="Error message if failed")
