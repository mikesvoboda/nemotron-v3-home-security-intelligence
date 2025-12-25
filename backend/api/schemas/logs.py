"""Pydantic schemas for logs API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """Schema for a single log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Log entry ID")
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    component: str = Field(..., description="Component/module name")
    message: str = Field(..., description="Log message")
    camera_id: str | None = Field(None, description="Associated camera ID")
    event_id: int | None = Field(None, description="Associated event ID")
    request_id: str | None = Field(None, description="Request correlation ID")
    detection_id: int | None = Field(None, description="Associated detection ID")
    duration_ms: int | None = Field(None, description="Operation duration in milliseconds")
    extra: dict[str, Any] | None = Field(None, description="Additional structured data")
    source: str = Field("backend", description="Log source (backend, frontend)")


class LogsResponse(BaseModel):
    """Schema for paginated logs response."""

    logs: list[LogEntry] = Field(..., description="List of log entries")
    count: int = Field(..., description="Total count matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class LogStats(BaseModel):
    """Schema for log statistics (dashboard)."""

    total_today: int = Field(..., description="Total logs today")
    errors_today: int = Field(..., description="Error count today")
    warnings_today: int = Field(..., description="Warning count today")
    by_component: dict[str, int] = Field(..., description="Counts by component")
    by_level: dict[str, int] = Field(..., description="Counts by level")
    top_component: str | None = Field(None, description="Most active component")


class FrontendLogCreate(BaseModel):
    """Schema for frontend log submission."""

    level: str = Field(
        ..., description="Log level", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    component: str = Field(..., description="Frontend component name", max_length=50)
    message: str = Field(..., description="Log message", max_length=2000)
    extra: dict[str, Any] | None = Field(None, description="Additional context")
    user_agent: str | None = Field(None, description="Browser user agent")
    url: str | None = Field(None, description="Page URL where log occurred")
