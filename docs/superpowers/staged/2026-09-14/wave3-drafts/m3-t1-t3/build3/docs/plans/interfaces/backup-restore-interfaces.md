# Backup/Restore Interface Definitions (NEM-3566)

This document defines the shared interfaces for the Backup/Restore feature implementation.
All agents must follow these interface contracts.

## Linear Issue

- **ID:** NEM-3566
- **Title:** Discovery: Backup/Restore Missing - Full System Backup Export Not Implemented

---

## 1. Backend Schemas (`backend/api/schemas/backup.py`)

```python
"""Pydantic schemas for backup/restore API endpoints."""

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
    """Information about a single backup content type."""
    count: int = Field(..., description="Number of records")
    checksum: str = Field(..., description="SHA256 checksum of the JSON file")

class BackupManifest(BaseModel):
    """Manifest file stored inside backup ZIP."""
    model_config = ConfigDict(from_attributes=True)

    backup_id: str = Field(..., description="Unique backup identifier")
    version: str = Field(..., description="Backup format version (e.g., '1.0')")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    app_version: str | None = Field(None, description="Application version")
    contents: dict[str, BackupContentInfo] = Field(
        default_factory=dict,
        description="Map of content type to info (events, alerts, cameras, etc.)"
    )

# =============================================================================
# API Request/Response Schemas
# =============================================================================

class BackupJobCreate(BaseModel):
    """Schema for creating a backup job (no parameters needed for full backup)."""
    model_config = ConfigDict(
        json_schema_extra={"example": {}}
    )
    # Full backup has no parameters - exports everything

class BackupJobStartResponse(BaseModel):
    """Response when creating a backup job."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "019478a1-b2c3-7def-8901-234567890abc",
                "status": "pending",
                "message": "Backup job created. Use GET /api/backup/{job_id} to track progress."
            }
        }
    )
    job_id: str = Field(..., description="Unique job identifier")
    status: BackupJobStatus = Field(BackupJobStatus.PENDING, description="Initial status")
    message: str = Field(..., description="Human-readable message")

class BackupJobProgress(BaseModel):
    """Progress information for a backup job."""
    total_tables: int = Field(8, description="Total tables to export")
    completed_tables: int = Field(0, description="Tables exported so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")

class BackupJobResponse(BaseModel):
    """Full status response for a backup job."""
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
    """Summary item for backup list."""
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
    """Response when starting a restore job."""
    job_id: str = Field(..., description="Unique restore job identifier")
    status: RestoreJobStatus = Field(RestoreJobStatus.PENDING)
    message: str = Field(..., description="Human-readable message")

class RestoreJobProgress(BaseModel):
    """Progress information for a restore job."""
    total_tables: int = Field(8, description="Total tables to restore")
    completed_tables: int = Field(0, description="Tables restored so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")

class RestoreJobResponse(BaseModel):
    """Full status response for a restore job."""
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
    items_restored: dict[str, int] | None = Field(None, description="Count of restored items per table")

    # Error (on failure)
    error_message: str | None = Field(None, description="Error message if failed")
```

---

## 2. Backend Model (`backend/models/backup_job.py`)

```python
"""BackupJob and RestoreJob models for tracking backup/restore operations."""

from datetime import datetime
from enum import StrEnum, auto
from uuid import uuid7

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now
from .camera import Base


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


class BackupJob(Base):
    """Model for tracking backup job progress."""

    __tablename__ = "backup_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    status: Mapped[BackupJobStatus] = mapped_column(
        Enum(BackupJobStatus, name="backup_job_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BackupJobStatus.PENDING,
    )

    # Progress tracking
    total_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    completed_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manifest_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_backup_jobs_status", "status"),
        Index("idx_backup_jobs_created_at", "created_at"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_backup_progress_range"),
    )


class RestoreJob(Base):
    """Model for tracking restore job progress."""

    __tablename__ = "restore_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    status: Mapped[RestoreJobStatus] = mapped_column(
        Enum(RestoreJobStatus, name="restore_job_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RestoreJobStatus.PENDING,
    )

    # Source backup info
    backup_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backup_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Progress tracking
    total_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    completed_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    items_restored: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_restore_jobs_status", "status"),
        Index("idx_restore_jobs_created_at", "created_at"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_restore_progress_range"),
    )
```

---

## 3. API Routes (`backend/api/routes/backup.py`)

```python
"""API Endpoint Contract:

POST /api/backup
    - Create a new backup job
    - Returns: BackupJobStartResponse
    - Runs backup in background

GET /api/backup
    - List available backups
    - Returns: BackupListResponse

GET /api/backup/{job_id}
    - Get backup job status
    - Returns: BackupJobResponse

GET /api/backup/{job_id}/download
    - Download backup file
    - Returns: FileResponse (application/zip)

DELETE /api/backup/{job_id}
    - Delete a backup file
    - Returns: {"deleted": true}

POST /api/backup/restore
    - Start restore from uploaded file
    - Accepts: multipart/form-data with file
    - Returns: RestoreJobStartResponse

GET /api/backup/restore/{job_id}
    - Get restore job status
    - Returns: RestoreJobResponse
"""

# Router prefix: /api/backup
# Tags: ["backup"]
```

---

## 4. Service Interfaces

### BackupService (`backend/services/backup_service.py`)

```python
"""BackupService Interface:

class BackupService:
    BACKUP_FORMAT_VERSION = "1.0"
    BACKUP_DIR = Path("/tmp/backups")  # Or from settings

    # Tables to back up (in order)
    BACKUP_TABLES = [
        ("events", Event),
        ("alerts", Alert),
        ("cameras", Camera),
        ("zones", Zone),
        ("prompts", PromptConfig),
        ("baselines", SceneBaseline),
        ("household_members", HouseholdMember),
        ("settings", SystemSetting),
    ]

    async def create_backup(
        self,
        db: AsyncSession,
        job_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> BackupResult:
        '''Create a full system backup.

        Args:
            db: Database session
            job_id: Backup job ID for tracking
            progress_callback: Optional callback(percent, step_name)

        Returns:
            BackupResult with file_path, file_size, manifest
        '''
        ...

    async def _export_table(
        self,
        db: AsyncSession,
        table_name: str,
        model: type,
        output_path: Path,
    ) -> int:
        '''Export a single table to JSON file.

        Returns: Number of records exported
        '''
        ...

    def _calculate_checksum(self, file_path: Path) -> str:
        '''Calculate SHA256 checksum of a file.'''
        ...

    def list_backups(self) -> list[BackupInfo]:
        '''List available backup files.'''
        ...

    def delete_backup(self, backup_id: str) -> bool:
        '''Delete a backup file.'''
        ...
```

### RestoreService (`backend/services/restore_service.py`)

```python
"""RestoreService Interface:

class RestoreService:
    async def restore_from_backup(
        self,
        backup_file: Path,
        db: AsyncSession,
        job_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]] | None = None,
    ) -> RestoreResult:
        '''Restore system from backup file.

        Args:
            backup_file: Path to uploaded backup ZIP
            db: Database session
            job_id: Restore job ID for tracking
            progress_callback: Optional callback(percent, step_name)

        Returns:
            RestoreResult with items_restored counts

        Raises:
            BackupValidationError: If backup is invalid or corrupted
        '''
        ...

    def _validate_manifest(self, manifest: BackupManifest) -> None:
        '''Validate backup manifest version and contents.

        Raises:
            BackupValidationError: If manifest is invalid
        '''
        ...

    def _verify_checksums(self, backup_dir: Path, manifest: BackupManifest) -> None:
        '''Verify all file checksums match manifest.

        Raises:
            BackupCorruptedError: If any checksum doesn't match
        '''
        ...

    async def _restore_table(
        self,
        db: AsyncSession,
        table_name: str,
        file_path: Path,
    ) -> int:
        '''Restore a single table from JSON file.

        Returns: Number of records restored
        '''
        ...
```

---

## 5. Frontend Types (`frontend/src/types/backup.ts`)

```typescript
// Backup job status
export type BackupJobStatus = 'pending' | 'running' | 'completed' | 'failed';
export type RestoreJobStatus = 'pending' | 'validating' | 'restoring' | 'completed' | 'failed';

// Backup manifest (from backend)
export interface BackupContentInfo {
  count: number;
  checksum: string;
}

export interface BackupManifest {
  backup_id: string;
  version: string;
  created_at: string; // ISO datetime
  app_version: string | null;
  contents: Record<string, BackupContentInfo>;
}

// Backup job
export interface BackupJobProgress {
  total_tables: number;
  completed_tables: number;
  progress_percent: number;
  current_step: string | null;
}

export interface BackupJob {
  id: string;
  status: BackupJobStatus;
  progress: BackupJobProgress;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  file_path: string | null;
  file_size_bytes: number | null;
  manifest: BackupManifest | null;
  error_message: string | null;
}

export interface BackupListItem {
  id: string;
  created_at: string;
  file_size_bytes: number;
  status: BackupJobStatus;
  download_url: string | null;
}

export interface BackupListResponse {
  backups: BackupListItem[];
  total: number;
}

// Restore job
export interface RestoreJobProgress {
  total_tables: number;
  completed_tables: number;
  progress_percent: number;
  current_step: string | null;
}

export interface RestoreJob {
  id: string;
  status: RestoreJobStatus;
  progress: RestoreJobProgress;
  backup_id: string | null;
  backup_created_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  items_restored: Record<string, number> | null;
  error_message: string | null;
}

// API responses
export interface BackupJobStartResponse {
  job_id: string;
  status: BackupJobStatus;
  message: string;
}

export interface RestoreJobStartResponse {
  job_id: string;
  status: RestoreJobStatus;
  message: string;
}
```

---

## 6. Frontend API (`frontend/src/services/backupApi.ts`)

```typescript
/**
 * API client functions for backup/restore endpoints.
 *
 * Endpoints:
 *   POST   /api/backup              - Create backup job
 *   GET    /api/backup              - List backups
 *   GET    /api/backup/:id          - Get backup status
 *   GET    /api/backup/:id/download - Download backup file
 *   DELETE /api/backup/:id          - Delete backup
 *   POST   /api/backup/restore      - Start restore (multipart file upload)
 *   GET    /api/backup/restore/:id  - Get restore status
 */

import type {
  BackupJob,
  BackupJobStartResponse,
  BackupListResponse,
  RestoreJob,
  RestoreJobStartResponse,
} from '../types/backup';

const API_BASE = '/api/backup';

export async function createBackup(): Promise<BackupJobStartResponse>;
export async function listBackups(): Promise<BackupListResponse>;
export async function getBackupJob(jobId: string): Promise<BackupJob>;
export function getBackupDownloadUrl(jobId: string): string;
export async function deleteBackup(jobId: string): Promise<void>;
export async function startRestore(file: File): Promise<RestoreJobStartResponse>;
export async function getRestoreJob(jobId: string): Promise<RestoreJob>;
```

---

## 7. Frontend Hook (`frontend/src/hooks/useBackup.ts`)

```typescript
/**
 * TanStack Query hooks for backup/restore operations.
 *
 * Query Keys:
 *   ['backup'] - base key
 *   ['backup', 'list'] - backup list
 *   ['backup', 'job', jobId] - specific backup job
 *   ['backup', 'restore', jobId] - specific restore job
 *
 * Hooks:
 *   useBackupList() - Fetch list of backups
 *   useBackupJob(jobId, options) - Fetch backup job status with polling
 *   useRestoreJob(jobId, options) - Fetch restore job status with polling
 *   useCreateBackup() - Mutation to create backup
 *   useDeleteBackup() - Mutation to delete backup
 *   useStartRestore() - Mutation to start restore from file
 */

export const BACKUP_QUERY_KEYS = {
  all: ['backup'] as const,
  list: ['backup', 'list'] as const,
  job: (id: string) => ['backup', 'job', id] as const,
  restore: (id: string) => ['backup', 'restore', id] as const,
};

// Hook interfaces follow useGpuConfig.ts patterns
```

---

## 8. Agent Assignments

| Agent | Scope                                    | Files                                                                                                               |
| ----- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **1** | Backend schemas & models                 | `backend/api/schemas/backup.py`, `backend/models/backup_job.py`                                                     |
| **2** | BackupService                            | `backend/services/backup_service.py`                                                                                |
| **3** | RestoreService + API routes              | `backend/services/restore_service.py`, `backend/api/routes/backup.py`                                               |
| **4** | Frontend (types, API, hooks, components) | `frontend/src/types/backup.ts`, `frontend/src/services/backupApi.ts`, `frontend/src/hooks/useBackup.ts`, components |

---

## 9. Testing Requirements

- **Unit tests** for services in `backend/tests/unit/services/`
- **Integration tests** for API in `backend/tests/integration/test_backup_api.py`
- **Frontend tests** in `frontend/src/hooks/useBackup.test.ts`
