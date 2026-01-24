"""Pydantic schemas for log management endpoints.

This module defines schemas for:
1. Frontend log ingestion endpoints (POST /api/logs/frontend, POST /api/logs/frontend/batch)
2. Log viewing endpoints (GET /api/logs, GET /api/logs/stats)

The endpoints support both single log entries and batched submissions to
reduce API calls and improve performance.

Log levels:
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Potential issues that should be monitored
- ERROR: Error conditions that need attention
- CRITICAL: Severe errors that may cause failures

Usage:
    # Ingest a frontend log
    POST /api/logs/frontend
    {
        "level": "ERROR",
        "message": "Failed to load dashboard data",
        "component": "Dashboard",
        "timestamp": "2024-01-15T10:30:00Z",
        "context": {
            "error_code": "API_TIMEOUT",
            "retry_count": 3
        },
        "url": "https://example.com/dashboard"
    }

    # Query logs
    GET /api/logs?level=ERROR&component=backend&limit=50

    # Get log statistics
    GET /api/logs/stats
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta


class FrontendLogLevel(str, Enum):
    """Supported frontend log levels.

    These correspond to the log levels used by the frontend logger.ts service.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class FrontendLogEntry(BaseModel):
    """A single log entry from the frontend.

    This schema matches the structure sent by the frontend logger.ts service.
    All fields except level and message are optional to allow flexibility in
    what context the frontend can provide.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: The log message content
        timestamp: When the log was created (ISO 8601 format)
        component: Frontend component name (e.g., "Dashboard", "AlertForm")
        context: Additional structured context data (renamed from 'extra' in frontend)
        url: Browser URL where the log was generated
        user_agent: Browser user agent string
    """

    level: FrontendLogLevel = Field(..., description="Log level")
    message: str = Field(..., min_length=1, max_length=10000, description="Log message content")
    timestamp: datetime | None = Field(
        None, description="When the log was created (ISO 8601 format)"
    )
    component: str | None = Field(None, max_length=100, description="Frontend component name")
    context: dict[str, Any] | None = Field(
        None, alias="extra", description="Additional structured context data"
    )
    url: str | None = Field(
        None, max_length=2000, description="Browser URL where log was generated"
    )
    user_agent: str | None = Field(None, max_length=500, description="Browser user agent string")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'context' and 'extra' field names
        json_schema_extra={
            "example": {
                "level": "ERROR",
                "message": "Failed to load dashboard data",
                "timestamp": "2024-01-15T10:30:00Z",
                "component": "Dashboard",
                "extra": {
                    "error_code": "API_TIMEOUT",
                    "retry_count": 3,
                    "url": "https://example.com/dashboard",
                },
                "url": "https://example.com/dashboard",
            }
        },
    )


class FrontendLogBatchRequest(BaseModel):
    """Batch request for multiple frontend log entries.

    The frontend batches log entries to reduce API calls. Each batch may
    contain logs from different components or at different levels.

    Attributes:
        entries: List of log entries to ingest (1-100 entries)
    """

    entries: list[FrontendLogEntry] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of log entries to ingest (1-100 entries)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entries": [
                    {
                        "level": "INFO",
                        "message": "Page loaded successfully",
                        "component": "App",
                        "timestamp": "2024-01-15T10:30:00Z",
                    },
                    {
                        "level": "ERROR",
                        "message": "API call failed",
                        "component": "API",
                        "timestamp": "2024-01-15T10:30:01Z",
                        "extra": {"endpoint": "/api/events", "status": 500},
                    },
                ]
            }
        },
    )


class FrontendLogResponse(BaseModel):
    """Response from the frontend log ingestion endpoints.

    Attributes:
        success: Whether the ingestion was successful
        count: Number of log entries successfully ingested
        message: Human-readable status message
    """

    success: bool = Field(..., description="Whether ingestion was successful")
    count: int = Field(..., ge=0, description="Number of entries successfully ingested")
    message: str | None = Field(None, description="Human-readable status message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "count": 5,
                "message": "Successfully ingested 5 log entry(ies)",
            }
        },
    )


# =============================================================================
# Log Query Schemas (GET /api/logs, GET /api/logs/stats)
# =============================================================================


class LogLevel(str, Enum):
    """Log levels for filtering logs."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(str, Enum):
    """Log sources for filtering logs."""

    BACKEND = "backend"
    FRONTEND = "frontend"


class LogEntryResponse(BaseModel):
    """Schema for a single log entry in query responses.

    This schema is used for GET /api/logs responses and represents
    a log record from the database.

    Attributes:
        id: Unique log entry identifier
        timestamp: When the log was created (UTC)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        component: Component that generated the log (e.g., "backend.api.routes.events")
        message: The log message content
        camera_id: Optional camera ID associated with this log
        event_id: Optional event ID associated with this log
        request_id: Optional request ID for correlation
        detection_id: Optional detection ID associated with this log
        duration_ms: Optional duration in milliseconds (for timing logs)
        extra: Additional structured context data (JSON)
        source: Log source (backend or frontend)
    """

    id: int = Field(..., ge=1, description="Unique log entry ID")
    timestamp: datetime = Field(..., description="When the log was created (UTC)")
    level: str = Field(
        ...,
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    component: str = Field(
        ...,
        max_length=100,
        description="Component that generated the log",
    )
    message: str = Field(..., description="Log message content")
    camera_id: str | None = Field(None, description="Associated camera ID")
    event_id: int | None = Field(None, description="Associated event ID")
    request_id: str | None = Field(None, description="Request ID for correlation")
    detection_id: int | None = Field(None, description="Associated detection ID")
    duration_ms: int | None = Field(None, description="Duration in milliseconds")
    extra: dict[str, Any] | None = Field(None, description="Additional structured context")
    source: str = Field(
        default="backend",
        description="Log source (backend or frontend)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12345,
                "timestamp": "2026-01-15T10:30:00Z",
                "level": "ERROR",
                "component": "backend.services.detector",
                "message": "Detection failed: timeout after 30s",
                "camera_id": "front_door",
                "event_id": 456,
                "request_id": "req-abc123",
                "detection_id": 789,
                "duration_ms": 30000,
                "extra": {"retry_count": 3, "error_code": "TIMEOUT"},
                "source": "backend",
            }
        },
    )


class LogsListResponse(BaseModel):
    """Schema for paginated log query response.

    Supports both cursor-based pagination (recommended) and offset pagination.
    Cursor-based pagination offers better performance for large datasets.
    """

    items: list[LogEntryResponse] = Field(..., description="List of log entries")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    deprecation_warning: str | None = Field(
        None, description="Warning when using deprecated offset pagination"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 12345,
                        "timestamp": "2026-01-15T10:30:00Z",
                        "level": "ERROR",
                        "component": "backend.services.detector",
                        "message": "Detection failed",
                        "camera_id": "front_door",
                        "event_id": None,
                        "request_id": "req-abc123",
                        "detection_id": None,
                        "duration_ms": None,
                        "extra": None,
                        "source": "backend",
                    }
                ],
                "pagination": {
                    "total": 1500,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": "eyJpZCI6IDEyMzQ1fQ==",  # pragma: allowlist secret
                    "has_more": True,
                },
            }
        }
    )


class LogStats(BaseModel):
    """Schema for log statistics dashboard.

    Provides aggregated statistics about logs for the dashboard,
    including counts by level and component.

    Attributes:
        errors_today: Number of ERROR logs today
        warnings_today: Number of WARNING logs today
        total_today: Total number of logs today
        top_component: The component with the most logs today (if any)
        by_component: Breakdown of log counts by component
    """

    errors_today: int = Field(..., ge=0, description="Number of errors today")
    warnings_today: int = Field(..., ge=0, description="Number of warnings today")
    total_today: int = Field(..., ge=0, description="Total logs today")
    top_component: str | None = Field(None, description="Component with most logs today")
    by_component: dict[str, int] = Field(
        default_factory=dict,
        description="Log counts by component",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors_today": 15,
                "warnings_today": 42,
                "total_today": 1500,
                "top_component": "backend.services.detector",
                "by_component": {
                    "backend.services.detector": 350,
                    "backend.api.routes.events": 280,
                    "frontend": 200,
                    "backend.services.analyzer": 150,
                },
            }
        }
    )


# Re-export for convenience
__all__ = [
    "FrontendLogBatchRequest",
    "FrontendLogEntry",
    "FrontendLogLevel",
    "FrontendLogResponse",
    "LogEntryResponse",
    "LogLevel",
    "LogSource",
    "LogStats",
    "LogsListResponse",
]
