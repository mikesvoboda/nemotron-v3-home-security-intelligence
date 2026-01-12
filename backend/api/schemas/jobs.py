"""Job tracking schemas for API endpoints.

Provides Pydantic models for background job status and progress tracking.

NEM-2390: Added detailed job response schemas with nested Progress, Timing, and RetryInfo.
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


# =============================================================================
# Detailed Job Response Schemas (NEM-2390)
# =============================================================================


class JobProgressDetail(BaseModel):
    """Detailed progress information for a job.

    Provides granular progress tracking beyond a simple percentage.
    """

    percent: int = Field(ge=0, le=100, description="Progress percentage (0-100)")
    current_step: str | None = Field(None, description="Current processing step description")
    items_processed: int | None = Field(None, ge=0, description="Number of items processed so far")
    items_total: int | None = Field(None, ge=0, description="Total number of items to process")

    model_config = {
        "json_schema_extra": {
            "example": {
                "percent": 45,
                "current_step": "Processing events",
                "items_processed": 450,
                "items_total": 1000,
            }
        }
    }


class JobTiming(BaseModel):
    """Timing information for a job.

    Tracks job lifecycle timestamps and duration calculations.
    """

    created_at: datetime = Field(description="When the job was created")
    started_at: datetime | None = Field(None, description="When job execution started")
    completed_at: datetime | None = Field(None, description="When the job completed or failed")
    duration_seconds: float | None = Field(
        None, ge=0, description="Total duration in seconds (if started)"
    )
    estimated_remaining_seconds: float | None = Field(
        None, ge=0, description="Estimated time remaining (if running)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": None,
                "duration_seconds": 45.5,
                "estimated_remaining_seconds": 55.0,
            }
        }
    }


class JobRetryInfo(BaseModel):
    """Retry information for a job.

    Tracks retry attempts and failure history.
    """

    attempt_number: int = Field(ge=1, description="Current attempt number (1-indexed)")
    max_attempts: int = Field(ge=1, description="Maximum number of retry attempts allowed")
    next_retry_at: datetime | None = Field(
        None, description="When the next retry will occur (if applicable)"
    )
    previous_errors: list[str] = Field(
        default_factory=list, description="List of error messages from previous attempts"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "attempt_number": 2,
                "max_attempts": 3,
                "next_retry_at": "2024-01-15T10:35:00Z",
                "previous_errors": ["Connection timeout"],
            }
        }
    }


class JobMetadata(BaseModel):
    """Metadata about job execution.

    Contains input parameters and execution context.
    """

    input_params: dict[str, Any] | None = Field(
        None, description="Input parameters provided when job was created"
    )
    worker_id: str | None = Field(None, description="ID of the worker executing the job")

    model_config = {
        "json_schema_extra": {
            "example": {
                "input_params": {"format": "csv", "camera_id": "cam-1"},
                "worker_id": "worker-abc-123",
            }
        }
    }


class JobDetailResponse(BaseModel):
    """Detailed response model for a single job.

    Provides comprehensive information about a job including progress details,
    timing information, retry status, and execution metadata.

    NEM-2390: GET /api/jobs/{job_id} detail endpoint response.
    """

    id: str = Field(description="Unique job identifier")
    job_type: str = Field(description="Type of job (e.g., 'export', 'ai_analysis')")
    status: JobStatusEnum = Field(description="Current job status")
    queue_name: str | None = Field(None, description="Name of the job queue")
    priority: int = Field(default=0, ge=0, le=10, description="Job priority (0=lowest, 10=highest)")
    progress: JobProgressDetail = Field(description="Detailed progress information")
    timing: JobTiming = Field(description="Job timing and duration information")
    retry_info: JobRetryInfo = Field(description="Retry attempt information")
    result: Any | None = Field(None, description="Job result data (if completed)")
    error: str | None = Field(None, description="Error message (if failed)")
    metadata: JobMetadata = Field(description="Job execution metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "ai_analysis",
                "status": "running",
                "queue_name": "high_priority",
                "priority": 1,
                "progress": {
                    "percent": 45,
                    "current_step": "Analyzing detections",
                    "items_processed": 450,
                    "items_total": 1000,
                },
                "timing": {
                    "created_at": "2024-01-15T10:30:00Z",
                    "started_at": "2024-01-15T10:30:01Z",
                    "completed_at": None,
                    "duration_seconds": 45.5,
                    "estimated_remaining_seconds": 55.0,
                },
                "retry_info": {
                    "attempt_number": 1,
                    "max_attempts": 3,
                    "next_retry_at": None,
                    "previous_errors": [],
                },
                "result": None,
                "error": None,
                "metadata": {
                    "input_params": {"event_ids": ["evt-1", "evt-2"]},
                    "worker_id": "worker-001",
                },
            }
        }
    }


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


class JobAbortResponse(BaseModel):
    """Response model for job abort request."""

    job_id: str = Field(description="Job ID that is being aborted")
    status: JobStatusEnum = Field(description="New job status (aborting/failed)")
    message: str = Field(description="Abort status message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "failed",
                "message": "Job abort requested - worker notified",
            }
        }
    }


class BulkCancelRequest(BaseModel):
    """Request model for bulk job cancellation."""

    job_ids: list[str] = Field(
        min_length=1,
        max_length=100,
        description="List of job IDs to cancel (1-100 jobs)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "550e8400-e29b-41d4-a716-446655440001",
                ]
            }
        }
    }


class BulkCancelError(BaseModel):
    """Error details for a single job in bulk cancellation."""

    job_id: str = Field(description="Job ID that failed to cancel")
    error: str = Field(description="Error message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "error": "Job not found",
            }
        }
    }


class BulkCancelResponse(BaseModel):
    """Response model for bulk job cancellation."""

    cancelled: int = Field(ge=0, description="Number of jobs successfully cancelled")
    failed: int = Field(ge=0, description="Number of jobs that failed to cancel")
    errors: list[BulkCancelError] = Field(
        default_factory=list,
        description="Details of cancellation failures",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "cancelled": 5,
                "failed": 1,
                "errors": [
                    {
                        "job_id": "550e8400-e29b-41d4-a716-446655440005",
                        "error": "Job already completed",
                    }
                ],
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


# =============================================================================
# Job Search Schemas (NEM-2392)
# =============================================================================


class JobSearchAggregations(BaseModel):
    """Aggregation counts for job search results."""

    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Count of matching jobs by status",
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of matching jobs by job type",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "by_status": {
                    "pending": 10,
                    "running": 5,
                    "completed": 100,
                    "failed": 35,
                },
                "by_type": {
                    "ai_analysis": 120,
                    "export": 20,
                    "cleanup": 10,
                },
            }
        }
    }


class JobSearchResponse(BaseModel):
    """Response model for job search with aggregations.

    Extends the standard list response with aggregation data for faceted search.

    NEM-2392: GET /api/jobs/search endpoint response.
    """

    data: list[JobResponse] = Field(description="List of matching jobs")
    meta: PaginationMeta = Field(description="Pagination metadata")
    aggregations: JobSearchAggregations = Field(
        description="Aggregation counts for faceted filtering"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": [
                    {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "job_type": "export",
                        "status": "completed",
                        "progress": 100,
                        "message": "Export completed successfully",
                        "created_at": "2024-01-15T10:30:00Z",
                        "started_at": "2024-01-15T10:30:01Z",
                        "completed_at": "2024-01-15T10:31:30Z",
                        "result": {"file_path": "/exports/data.csv"},
                        "error": None,
                    }
                ],
                "meta": {
                    "total": 150,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": True,
                },
                "aggregations": {
                    "by_status": {
                        "pending": 10,
                        "running": 5,
                        "completed": 100,
                        "failed": 35,
                    },
                    "by_type": {
                        "export": 120,
                        "cleanup": 20,
                        "backup": 10,
                    },
                },
            }
        }
    }


# =============================================================================
# Job History Schemas (NEM-2396)
# =============================================================================


class JobTransitionResponse(BaseModel):
    """A single state transition record in job history."""

    from_status: str | None = Field(
        None, alias="from", description="Previous status (null for initial)"
    )
    to_status: str = Field(alias="to", description="New status after transition")
    at: datetime = Field(description="Timestamp of the transition")
    triggered_by: str = Field(
        description="What triggered the transition (api, worker, system, etc)"
    )
    details: dict[str, Any] | None = Field(None, description="Additional transition details")

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "from": None,
                "to": "queued",
                "at": "2024-01-15T10:30:00Z",
                "triggered_by": "api",
                "details": {"user": "system"},
            }
        },
    }


class JobAttemptResponse(BaseModel):
    """A single job execution attempt record."""

    attempt_number: int = Field(ge=1, description="Sequential attempt number (1-based)")
    started_at: datetime = Field(description="When this attempt started")
    ended_at: datetime | None = Field(None, description="When this attempt ended")
    status: str = Field(
        description="Status of this attempt (started, succeeded, failed, cancelled)"
    )
    error: str | None = Field(None, description="Error message if failed")
    worker_id: str | None = Field(None, description="ID of worker that processed this attempt")
    duration_seconds: float | None = Field(
        None, ge=0, description="Duration in seconds if completed"
    )
    result: dict[str, Any] | None = Field(None, description="Result data if successful")

    model_config = {
        "json_schema_extra": {
            "example": {
                "attempt_number": 1,
                "started_at": "2024-01-15T10:30:01Z",
                "ended_at": "2024-01-15T10:31:30Z",
                "status": "succeeded",
                "error": None,
                "worker_id": "worker-1",
                "duration_seconds": 89.0,
                "result": {"processed": 1000},
            }
        }
    }


class JobHistoryResponse(BaseModel):
    """Complete job history with transitions and attempts.

    NEM-2396: GET /api/jobs/{job_id}/history endpoint response.
    """

    job_id: str = Field(description="Unique job identifier")
    job_type: str = Field(description="Type of job (e.g., 'export', 'cleanup')")
    status: str = Field(description="Current job status")
    created_at: datetime = Field(description="When the job was created")
    started_at: datetime | None = Field(None, description="When job execution started")
    completed_at: datetime | None = Field(None, description="When the job finished")
    transitions: list[JobTransitionResponse] = Field(
        default_factory=list,
        description="State transitions in chronological order",
    )
    attempts: list[JobAttemptResponse] = Field(
        default_factory=list,
        description="Execution attempts in order",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "job_type": "export",
                "status": "completed",
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": "2024-01-15T10:31:30Z",
                "transitions": [
                    {
                        "from": None,
                        "to": "queued",
                        "at": "2024-01-15T10:30:00Z",
                        "triggered_by": "api",
                        "details": None,
                    },
                    {
                        "from": "queued",
                        "to": "running",
                        "at": "2024-01-15T10:30:01Z",
                        "triggered_by": "worker",
                        "details": {"worker_id": "worker-1"},
                    },
                    {
                        "from": "running",
                        "to": "completed",
                        "at": "2024-01-15T10:31:30Z",
                        "triggered_by": "worker",
                        "details": None,
                    },
                ],
                "attempts": [
                    {
                        "attempt_number": 1,
                        "started_at": "2024-01-15T10:30:01Z",
                        "ended_at": "2024-01-15T10:31:30Z",
                        "status": "succeeded",
                        "error": None,
                        "worker_id": "worker-1",
                        "duration_seconds": 89.0,
                        "result": {"events_exported": 1000},
                    }
                ],
            }
        }
    }


class JobLogEntryResponse(BaseModel):
    """A single job log entry."""

    timestamp: datetime = Field(description="When the log entry was created")
    level: str = Field(description="Log level (DEBUG, INFO, WARNING, ERROR)")
    message: str = Field(description="Log message")
    context: dict[str, Any] | None = Field(None, description="Additional context data")
    attempt_number: int = Field(default=1, ge=1, description="Which attempt generated this log")

    model_config = {
        "json_schema_extra": {
            "example": {
                "timestamp": "2024-01-15T10:30:05Z",
                "level": "INFO",
                "message": "Starting export of 1000 events",
                "context": {"event_count": 1000},
                "attempt_number": 1,
            }
        }
    }


class JobLogsResponse(BaseModel):
    """Response for job logs endpoint.

    NEM-2396: GET /api/jobs/{job_id}/logs endpoint response.
    """

    job_id: str = Field(description="Unique job identifier")
    logs: list[JobLogEntryResponse] = Field(
        default_factory=list,
        description="Log entries in chronological order",
    )
    total: int = Field(ge=0, description="Total number of log entries returned")
    has_more: bool = Field(default=False, description="Whether more logs exist beyond the limit")

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "logs": [
                    {
                        "timestamp": "2024-01-15T10:30:01Z",
                        "level": "INFO",
                        "message": "Job started",
                        "context": None,
                        "attempt_number": 1,
                    },
                    {
                        "timestamp": "2024-01-15T10:30:05Z",
                        "level": "INFO",
                        "message": "Processing events: 0/1000",
                        "context": {"progress": 0},
                        "attempt_number": 1,
                    },
                    {
                        "timestamp": "2024-01-15T10:31:30Z",
                        "level": "INFO",
                        "message": "Export completed successfully",
                        "context": {"events_exported": 1000},
                        "attempt_number": 1,
                    },
                ],
                "total": 3,
                "has_more": False,
            }
        }
    }
