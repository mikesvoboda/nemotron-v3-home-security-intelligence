"""Pydantic schemas for logs API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """Schema for a single log entry."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "timestamp": "2026-01-03T10:30:00Z",
                "level": "INFO",
                "component": "backend.services.detector",
                "message": "Detection completed for front_door camera",
                "camera_id": "front_door",
                "event_id": 123,
                "request_id": "req-550e8400-e29b-41d4",
                "detection_id": 456,
                "duration_ms": 150,
                "extra": {"detections_count": 3, "confidence_avg": 0.87},
                "source": "backend",
            }
        },
    )

    id: int = Field(..., ge=1, description="Log entry ID")
    timestamp: datetime = Field(..., description="Log timestamp (UTC)")
    level: str = Field(
        ...,
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    component: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Component/module name (e.g., 'backend.services.detector')",
    )
    message: str = Field(..., min_length=1, max_length=5000, description="Log message content")
    camera_id: str | None = Field(
        None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Associated camera ID (alphanumeric, underscore, hyphen only)",
    )
    event_id: int | None = Field(None, ge=1, description="Associated event ID")
    request_id: str | None = Field(
        None,
        max_length=128,
        description="Request correlation ID for tracing",
    )
    detection_id: int | None = Field(None, ge=1, description="Associated detection ID")
    duration_ms: int | None = Field(None, ge=0, description="Operation duration in milliseconds")
    extra: dict[str, Any] | None = Field(
        None, description="Additional structured data (JSON-serializable)"
    )
    source: str = Field(
        "backend",
        pattern=r"^(backend|frontend)$",
        description="Log source (backend, frontend)",
    )


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses (NEM-2075)."""

    total: int = Field(..., ge=0, description="Total count matching filters")
    limit: int = Field(..., ge=1, le=1000, description="Page size (1-1000)")
    offset: int | None = Field(
        None, ge=0, description="Page offset (0-based, for offset pagination)"
    )
    cursor: str | None = Field(None, description="Current cursor position")
    next_cursor: str | None = Field(None, description="Cursor for next page")
    has_more: bool = Field(False, description="Whether more results are available")


class LogsResponse(BaseModel):
    """Schema for paginated logs response (NEM-2075 pagination envelope).

    Uses standardized pagination envelope with 'items' and 'pagination' fields.
    Supports both cursor-based pagination (recommended) and offset pagination.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "timestamp": "2026-01-03T10:30:00Z",
                        "level": "INFO",
                        "component": "backend.services.detector",
                        "message": "Detection completed",
                        "camera_id": "front_door",
                        "event_id": 123,
                        "request_id": None,
                        "detection_id": 456,
                        "duration_ms": 150,
                        "extra": None,
                        "source": "backend",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": None,
                    "cursor": None,
                    "next_cursor": "eyJpZCI6IDEsICJjcmVhdGVkX2F0IjogIjIwMjYtMDEtMDNUMTA6MzA6MDBaIn0=",  # pragma: allowlist secret
                    "has_more": False,
                },
            }
        }
    )

    items: list[LogEntry] = Field(..., description="List of log entries")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class LogStats(BaseModel):
    """Schema for log statistics (dashboard)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_today": 1500,
                "errors_today": 12,
                "warnings_today": 45,
                "by_component": {
                    "backend.services.detector": 800,
                    "backend.services.analyzer": 400,
                    "backend.api.routes": 300,
                },
                "by_level": {
                    "DEBUG": 500,
                    "INFO": 900,
                    "WARNING": 45,
                    "ERROR": 12,
                    "CRITICAL": 0,
                },
                "top_component": "backend.services.detector",
            }
        }
    )

    total_today: int = Field(..., ge=0, description="Total logs today")
    errors_today: int = Field(..., ge=0, description="Error count today")
    warnings_today: int = Field(..., ge=0, description="Warning count today")
    by_component: dict[str, int] = Field(..., description="Counts by component")
    by_level: dict[str, int] = Field(..., description="Counts by level")
    top_component: str | None = Field(None, description="Most active component")


class FrontendLogCreate(BaseModel):
    """Schema for frontend log submission."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "level": "ERROR",
                "component": "RiskGauge",
                "message": "WebSocket connection lost",
                "extra": {"reconnect_attempts": 3, "last_error": "Connection refused"},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "url": "https://localhost:5173/dashboard",
            }
        }
    )

    level: str = Field(
        ...,
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    component: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Frontend component name (e.g., 'RiskGauge', 'CameraGrid')",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Log message content",
    )
    extra: dict[str, Any] | None = Field(None, description="Additional context (JSON-serializable)")
    user_agent: str | None = Field(None, max_length=500, description="Browser user agent string")
    url: str | None = Field(None, max_length=2000, description="Page URL where log occurred")
