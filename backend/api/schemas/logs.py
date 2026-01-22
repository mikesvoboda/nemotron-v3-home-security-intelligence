"""Pydantic schemas for frontend log ingestion endpoints.

This module defines schemas for the frontend logging endpoints that receive
log entries from the browser. These logs are captured by the frontend logger.ts
service and sent to the backend for structured logging via Loki.

The endpoints support both single log entries and batched submissions to
reduce API calls and improve performance.

Frontend log levels:
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Potential issues that should be monitored
- ERROR: Error conditions that need attention
- CRITICAL: Severe errors that may cause failures

Usage:
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

    POST /api/logs/frontend/batch
    {
        "entries": [
            {"level": "INFO", "message": "Page loaded", "component": "App"},
            {"level": "ERROR", "message": "API call failed", "component": "API"}
        ]
    }
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
