"""Pydantic schemas for export API endpoints.

This module defines request/response schemas for the export progress tracking
API. Supports background export jobs with real-time progress updates.

Export Types:
    - events: Security event data export
    - alerts: Alert history export
    - full_backup: Complete system backup

Export Formats:
    - csv: Comma-separated values
    - json: JSON format
    - zip: Compressed archive
    - excel: XLSX spreadsheet
"""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta


class ExportJobStatusEnum(StrEnum):
    """Export job status values."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class ExportTypeEnum(StrEnum):
    """Types of exports available."""

    EVENTS = "events"
    ALERTS = "alerts"
    FULL_BACKUP = "full_backup"


class ExportFormatEnum(StrEnum):
    """Export file formats."""

    CSV = "csv"
    JSON = "json"
    ZIP = "zip"
    EXCEL = "excel"


# =============================================================================
# Export Job Request Schemas
# =============================================================================


class ExportJobCreate(BaseModel):
    """Schema for creating an export job.

    Create a new background export job with optional filtering parameters.
    The job will be processed asynchronously and can be monitored via
    the job status endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "export_type": "events",
                "export_format": "csv",
                "camera_id": "front_door",
                "risk_level": "high",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-12T23:59:59Z",
                "reviewed": None,
            }
        }
    )

    export_type: ExportTypeEnum = Field(
        ExportTypeEnum.EVENTS,
        description="Type of data to export (events, alerts, full_backup)",
    )
    export_format: ExportFormatEnum = Field(
        ExportFormatEnum.CSV,
        description="Output file format (csv, json, zip, excel)",
    )

    # Filter parameters (for events export)
    camera_id: str | None = Field(None, description="Filter by camera ID")
    risk_level: str | None = Field(
        None,
        description="Filter by risk level (low, medium, high, critical)",
    )
    start_date: datetime | None = Field(
        None,
        description="Filter events starting from this date (ISO format)",
    )
    end_date: datetime | None = Field(
        None,
        description="Filter events ending before this date (ISO format)",
    )
    reviewed: bool | None = Field(
        None,
        description="Filter by reviewed status (true=reviewed, false=unreviewed, null=all)",
    )


class ExportJobStartResponse(BaseModel):
    """Response when creating an export job.

    Returns the job ID that can be used to track progress via
    GET /api/exports/{job_id}.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Export job created. Use GET /api/exports/{job_id} to track progress.",
            }
        }
    )

    job_id: str = Field(..., description="Unique job identifier for tracking progress")
    status: ExportJobStatusEnum = Field(
        ExportJobStatusEnum.PENDING,
        description="Initial job status (always pending)",
    )
    message: str = Field(..., description="Human-readable status message")


# =============================================================================
# Export Job Progress Schemas
# =============================================================================


class ExportJobProgress(BaseModel):
    """Schema for export job progress information.

    Detailed progress information for an export job, including
    timing, item counts, and current step.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_items": 1230,
                "processed_items": 245,
                "progress_percent": 20,
                "current_step": "Processing events...",
                "estimated_completion": "2025-01-12T14:35:00Z",
            }
        }
    )

    total_items: int | None = Field(None, description="Total items to process (null if unknown)")
    processed_items: int = Field(0, ge=0, description="Number of items processed so far")
    progress_percent: int = Field(0, ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str | None = Field(None, description="Current processing step description")
    estimated_completion: datetime | None = Field(
        None,
        description="Estimated completion time (ISO format)",
    )


class ExportJobResult(BaseModel):
    """Schema for completed export job result.

    Information about the completed export, including download path
    and file statistics.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "output_path": "/api/exports/download/events_export_20250112_143000.csv",
                "output_size_bytes": 125432,
                "event_count": 1230,
                "format": "csv",
            }
        }
    )

    output_path: str | None = Field(None, description="Download path for the exported file")
    output_size_bytes: int | None = Field(None, ge=0, description="File size in bytes")
    event_count: int = Field(0, ge=0, description="Number of records exported")
    format: str = Field(..., description="Export format used")


# =============================================================================
# Export Job Response Schemas
# =============================================================================


class ExportJobResponse(BaseModel):
    """Schema for export job status response.

    Complete status information for an export job, including
    progress, timing, result, and any error information.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "export_type": "events",
                "export_format": "csv",
                "progress": {
                    "total_items": 1230,
                    "processed_items": 245,
                    "progress_percent": 20,
                    "current_step": "Processing events...",
                    "estimated_completion": "2025-01-12T14:35:00Z",
                },
                "created_at": "2025-01-12T14:30:00Z",
                "started_at": "2025-01-12T14:30:01Z",
                "completed_at": None,
                "result": None,
                "error_message": None,
            }
        },
    )

    id: str = Field(..., description="Unique export job identifier")
    status: ExportJobStatusEnum = Field(..., description="Current job status")
    export_type: str = Field(..., description="Type of export")
    export_format: str = Field(..., description="Export file format")

    # Progress information
    progress: ExportJobProgress = Field(
        default_factory=ExportJobProgress,
        description="Progress information",
    )

    # Timing information
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Job start timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")

    # Result information (populated on completion)
    result: ExportJobResult | None = Field(
        None,
        description="Export result (populated when completed)",
    )

    # Error information (populated on failure)
    error_message: str | None = Field(
        None,
        description="Error message (populated when failed)",
    )


class ExportJobListResponse(BaseModel):
    """Schema for export job list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "completed",
                        "export_type": "events",
                        "export_format": "csv",
                        "progress": {
                            "total_items": 1230,
                            "processed_items": 1230,
                            "progress_percent": 100,
                            "current_step": "Complete",
                        },
                        "created_at": "2025-01-12T14:30:00Z",
                        "started_at": "2025-01-12T14:30:01Z",
                        "completed_at": "2025-01-12T14:35:00Z",
                        "result": {
                            "output_path": "/api/exports/download/events_export_20250112_143000.csv",
                            "output_size_bytes": 125432,
                            "event_count": 1230,
                            "format": "csv",
                        },
                        "error_message": None,
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[ExportJobResponse] = Field(..., description="List of export jobs")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


# =============================================================================
# Export Job Update Schemas
# =============================================================================


class ExportJobUpdate(BaseModel):
    """Schema for updating an export job.

    Internal schema used by the export service to update job progress.
    Not exposed via API (jobs are managed internally).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "running",
                "processed_items": 500,
                "progress_percent": 40,
                "current_step": "Processing events...",
            }
        }
    )

    status: ExportJobStatusEnum | None = Field(None, description="New job status")
    total_items: int | None = Field(None, ge=0, description="Total items to process")
    processed_items: int | None = Field(None, ge=0, description="Items processed")
    progress_percent: int | None = Field(None, ge=0, le=100, description="Progress percentage")
    current_step: str | None = Field(None, description="Current step description")
    started_at: datetime | None = Field(None, description="Job start time")
    completed_at: datetime | None = Field(None, description="Job completion time")
    estimated_completion: datetime | None = Field(None, description="Estimated completion time")
    output_path: str | None = Field(None, description="Output file path")
    output_size_bytes: int | None = Field(None, ge=0, description="Output file size")
    error_message: str | None = Field(None, description="Error message if failed")


# =============================================================================
# Export Download Schemas
# =============================================================================


class ExportDownloadResponse(BaseModel):
    """Schema for export file download metadata.

    Returned when checking if a file is ready for download.
    The actual file is served via a separate streaming endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ready": True,
                "filename": "events_export_20250112_143000.csv",
                "content_type": "text/csv",
                "size_bytes": 125432,
                "download_url": "/api/exports/550e8400-e29b-41d4-a716-446655440000/download",
            }
        }
    )

    ready: bool = Field(..., description="Whether the file is ready for download")
    filename: str | None = Field(None, description="Exported filename")
    content_type: str | None = Field(None, description="MIME type of the file")
    size_bytes: int | None = Field(None, ge=0, description="File size in bytes")
    download_url: str | None = Field(None, description="URL to download the file")


# =============================================================================
# Export Cancel Schema
# =============================================================================


class ExportJobCancelResponse(BaseModel):
    """Schema for export job cancellation response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "failed",
                "message": "Export job cancelled by user",
                "cancelled": True,
            }
        }
    )

    job_id: str = Field(..., description="Job ID that was cancelled")
    status: ExportJobStatusEnum = Field(..., description="New job status after cancellation")
    message: str = Field(..., description="Cancellation status message")
    cancelled: bool = Field(..., description="Whether cancellation was successful")
