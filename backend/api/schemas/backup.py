"""Pydantic schemas for backup/restore API endpoints."""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field


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


class BackupContentInfo(BaseModel):
    """Information about a single backup content type."""

    count: int = Field(..., description="Number of records")
    checksum: str = Field(..., description="SHA256 checksum of the JSON file")


class BackupManifest(BaseModel):
    """Manifest file stored inside backup ZIP."""

    model_config = ConfigDict(from_attributes=True)

    backup_id: str = Field(..., description="Unique backup identifier")
    version: str = Field(..., description="Backup format version (e.g., '1.1')")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    app_version: str | None = Field(None, description="Application version")
    installation_id: str | None = Field(
        None, description="Identifier of the installation that created the backup"
    )
    label: str | None = Field(
        None, description="Optional label (e.g. 'before restore of <backup> at <time>')"
    )
    contents: dict[str, BackupContentInfo] = Field(
        default_factory=dict,
        description="Map of content type to info",
    )


class BackupJobCreate(BaseModel):
    """Schema for creating a backup job (no parameters needed for full backup)."""

    model_config = ConfigDict(json_schema_extra={"example": {}})


class BackupJobStartResponse(BaseModel):
    """Response when creating a backup job."""

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
    """Progress information for a backup job."""

    total_tables: int = Field(12, description="Total tables to export")
    completed_tables: int = Field(0, description="Tables exported so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")


class BackupJobResponse(BaseModel):
    """Full status response for a backup job."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique backup job identifier")
    status: BackupJobStatus = Field(..., description="Current job status")
    progress: BackupJobProgress = Field(default_factory=BackupJobProgress)

    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Job start timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")

    file_path: str | None = Field(None, description="Download path for backup file")
    file_size_bytes: int | None = Field(None, description="Backup file size")
    manifest: BackupManifest | None = Field(None, description="Backup manifest")

    error_message: str | None = Field(None, description="Error message if failed")


class BackupListItem(BaseModel):
    """Summary item for backup list."""

    id: str = Field(..., description="Backup ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    file_size_bytes: int = Field(..., description="File size in bytes")
    status: BackupJobStatus = Field(..., description="Job status")
    download_url: str | None = Field(None, description="Download URL if completed")
    label: str | None = Field(None, description="Optional label (e.g. safety backup note)")


class BackupListResponse(BaseModel):
    """Response for listing available backups."""

    backups: list[BackupListItem] = Field(default_factory=list)
    total: int = Field(0, description="Total number of backups")


class RestoreJobStartResponse(BaseModel):
    """Response when starting a restore job."""

    job_id: str = Field(..., description="Unique restore job identifier")
    status: RestoreJobStatus = Field(RestoreJobStatus.PENDING)
    message: str = Field(..., description="Human-readable message")


class RestoreJobProgress(BaseModel):
    """Progress information for a restore job."""

    total_tables: int = Field(12, description="Total tables to restore")
    completed_tables: int = Field(0, description="Tables restored so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")


class TableRestoreSummary(BaseModel):
    """Per-table restore statistics."""

    updated: int = Field(0, description="Rows updated in place")
    inserted: int = Field(0, description="Rows added")
    replaced: int = Field(0, description="Rows replaced (e.g. baselines)")
    kept: int = Field(0, description="Existing rows not in the backup and kept")


class RestoreJobResponse(BaseModel):
    """Full status response for a restore job."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique restore job identifier")
    status: RestoreJobStatus = Field(..., description="Current job status")
    progress: RestoreJobProgress = Field(default_factory=RestoreJobProgress)

    backup_id: str | None = Field(None, description="Source backup ID from manifest")
    backup_created_at: datetime | None = Field(None, description="When source backup was created")

    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Job start timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")

    items_restored: dict[str, int] | None = Field(
        None, description="Count of restored items per table"
    )
    safety_backup_id: str | None = Field(
        None, description="Automatic safety backup job ID created before restore"
    )
    tables: dict[str, TableRestoreSummary] | None = Field(
        None, description="Per-table restore breakdown (updated, inserted, replaced, kept)"
    )
    added_rows: dict[str, list[str]] | None = Field(
        None, description="Added rows by name per table"
    )
    cleared_known_person_links: list[str] | None = Field(
        None, description="Household member names whose known-person links were cleared"
    )
    skipped_tables: list[str] | None = Field(
        None, description="Tables skipped by version adapter (e.g. events, alerts on 1.0 archives)"
    )
    same_installation: bool | None = Field(
        None, description="Whether the restored archive came from this installation"
    )

    error_message: str | None = Field(None, description="Error message if failed")
