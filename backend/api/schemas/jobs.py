"""Job tracking schemas for API endpoints.

Provides Pydantic models for background job status and progress tracking.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.api.schemas.pagination import PaginationMeta


class JobStatusEnum(StrEnum):
    """Status of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResponse(BaseModel):
    """Response model for job status."""

    job_id: str = Field(description="Unique job identifier")
    job_type: str = Field(description="Type of job (e.g., 'export')")
    status: JobStatusEnum = Field(description="Current job status")
    progress: int = Field(ge=0, le=100, description="Progress percentage (0-100)")
    message: str | None = Field(None, description="Human-readable status message")
    created_at: str = Field(description="ISO 8601 timestamp when job was created")
    started_at: str | None = Field(None, description="ISO 8601 timestamp when job started")
    completed_at: str | None = Field(None, description="ISO 8601 timestamp when job finished")
    result: Any | None = Field(None, description="Job result data (if completed)")
    error: str | None = Field(None, description="Error message (if failed)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "status": "running",
                "progress": 45,
                "message": "Exporting events: 450/1000",
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": None,
                "result": None,
                "error": None,
            }
        }
    }


class ExportJobResult(BaseModel):
    """Result data for completed export jobs."""

    file_path: str = Field(description="Path or URL to the exported file")
    file_size: int = Field(ge=0, description="File size in bytes")
    event_count: int = Field(ge=0, description="Number of events exported")
    format: str = Field(description="Export format (csv, json, zip)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/api/exports/events_export_20240115_103000.csv",
                "file_size": 125432,
                "event_count": 1000,
                "format": "csv",
            }
        }
    }


class ExportJobStartResponse(BaseModel):
    """Response when starting an export job."""

    job_id: str = Field(description="Job ID for tracking progress")
    status: JobStatusEnum = Field(default=JobStatusEnum.PENDING, description="Initial job status")
    message: str = Field(description="Status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Export job created. Use GET /api/jobs/{job_id} to track progress.",
            }
        }
    }


class ExportFormat(StrEnum):
    """Supported export formats."""

    CSV = "csv"
    JSON = "json"
    ZIP = "zip"


class ExportJobRequest(BaseModel):
    """Request to start an export job."""

    format: ExportFormat = Field(default=ExportFormat.CSV, description="Export format")
    camera_id: str | None = Field(None, description="Filter by camera ID")
    risk_level: str | None = Field(
        None, description="Filter by risk level (low, medium, high, critical)"
    )
    start_date: datetime | None = Field(None, description="Filter by start date (ISO format)")
    end_date: datetime | None = Field(None, description="Filter by end date (ISO format)")
    reviewed: bool | None = Field(None, description="Filter by reviewed status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "format": "csv",
                "camera_id": None,
                "risk_level": "high",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-15T23:59:59Z",
                "reviewed": None,
            }
        }
    }


class JobListResponse(BaseModel):
    """Response model for listing jobs with pagination.

    Uses the standardized pagination envelope format (NEM-2178).
    """

    items: list[JobResponse] = Field(description="List of jobs")
    pagination: PaginationMeta = Field(description="Pagination metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "job_type": "export",
                        "status": "running",
                        "progress": 45,
                        "message": "Exporting events: 450/1000",
                        "created_at": "2024-01-15T10:30:00Z",
                        "started_at": "2024-01-15T10:30:01Z",
                        "completed_at": None,
                        "result": None,
                        "error": None,
                    }
                ],
                "pagination": {
                    "total": 100,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": True,
                },
            }
        }
    }


class JobTypeInfo(BaseModel):
    """Information about a job type."""

    name: str = Field(description="Job type name (e.g., 'export', 'cleanup')")
    description: str = Field(description="Human-readable description of the job type")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "export",
                "description": "Export events to CSV, JSON, or ZIP format",
            }
        }
    }


class JobTypesResponse(BaseModel):
    """Response model for listing job types."""

    job_types: list[JobTypeInfo] = Field(description="List of available job types")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_types": [
                    {
                        "name": "export",
                        "description": "Export events to CSV, JSON, or ZIP format",
                    },
                    {
                        "name": "cleanup",
                        "description": "Clean up old data and temporary files",
                    },
                ]
            }
        }
    }


class JobCancelResponse(BaseModel):
    """Response model for job cancellation request."""

    job_id: str = Field(description="Job ID that was cancelled")
    status: JobStatusEnum = Field(description="New job status after cancellation")
    message: str = Field(description="Cancellation status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "failed",
                "message": "Job cancellation requested",
            }
        }
    }


class JobStatusCount(BaseModel):
    """Count of jobs by status."""

    status: JobStatusEnum = Field(description="Job status")
    count: int = Field(ge=0, description="Number of jobs with this status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "completed",
                "count": 42,
            }
        }
    }


class JobTypeCount(BaseModel):
    """Count of jobs by type."""

    job_type: str = Field(description="Job type name")
    count: int = Field(ge=0, description="Number of jobs of this type")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_type": "export",
                "count": 25,
            }
        }
    }


class JobStatsResponse(BaseModel):
    """Response model for job statistics.

    Provides aggregate statistics about jobs including counts by status,
    counts by type, and timing information.
    """

    total_jobs: int = Field(ge=0, description="Total number of jobs tracked")
    by_status: list[JobStatusCount] = Field(description="Job counts by status")
    by_type: list[JobTypeCount] = Field(description="Job counts by type")
    average_duration_seconds: float | None = Field(
        None, description="Average job duration in seconds (for completed jobs)"
    )
    oldest_pending_job_age_seconds: float | None = Field(
        None, description="Age of the oldest pending job in seconds"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_jobs": 100,
                "by_status": [
                    {"status": "completed", "count": 75},
                    {"status": "running", "count": 5},
                    {"status": "pending", "count": 10},
                    {"status": "failed", "count": 10},
                ],
                "by_type": [
                    {"job_type": "export", "count": 60},
                    {"job_type": "cleanup", "count": 30},
                    {"job_type": "backup", "count": 10},
                ],
                "average_duration_seconds": 45.5,
                "oldest_pending_job_age_seconds": 120.0,
            }
        }
    }
