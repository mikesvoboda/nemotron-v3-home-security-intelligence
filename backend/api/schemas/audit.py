"""Pydantic schemas for audit log API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.audit import AuditAction, AuditStatus


class AuditLogResponse(BaseModel):
    """Schema for a single audit log entry."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "timestamp": "2026-01-03T10:30:00Z",
                "action": "acknowledge",
                "resource_type": "event",
                "resource_id": "123",
                "actor": "admin@example.com",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "details": {"previous_status": "unacknowledged", "new_status": "acknowledged"},
                "status": "success",
            }
        },
    )

    id: int = Field(..., ge=1, description="Audit log entry ID")
    timestamp: datetime = Field(..., description="When the action occurred (UTC)")
    action: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The action performed (e.g., 'create', 'update', 'delete', 'acknowledge')",
    )
    resource_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of resource (event, alert, rule, camera, settings)",
    )
    resource_id: str | None = Field(None, max_length=128, description="ID of the specific resource")
    actor: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="User or system that performed the action",
    )
    ip_address: str | None = Field(
        None,
        max_length=45,
        description="IP address of the client (IPv4 or IPv6)",
    )
    user_agent: str | None = Field(
        None, max_length=500, description="User agent string of the client"
    )
    details: dict[str, Any] | None = Field(
        None, description="Action-specific details (JSON-serializable)"
    )
    status: str = Field(
        ...,
        pattern=r"^(success|failure)$",
        description="Status of the action (success/failure)",
    )


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log response.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Cursor-based pagination offers better performance for large datasets.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logs": [
                    {
                        "id": 1,
                        "timestamp": "2026-01-03T10:30:00Z",
                        "action": "acknowledge",
                        "resource_type": "event",
                        "resource_id": "123",
                        "actor": "admin@example.com",
                        "ip_address": "192.168.1.100",
                        "user_agent": None,
                        "details": None,
                        "status": "success",
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
                "next_cursor": "eyJpZCI6IDEsICJjcmVhdGVkX2F0IjogIjIwMjYtMDEtMDNUMTA6MzA6MDBaIn0=",  # pragma: allowlist secret
                "has_more": False,
            }
        }
    )

    logs: list[AuditLogResponse] = Field(..., description="List of audit log entries")
    count: int = Field(..., ge=0, description="Total count matching filters")
    limit: int = Field(..., ge=1, le=1000, description="Page size (1-1000)")
    offset: int = Field(..., ge=0, description="Page offset (0-based, deprecated)")
    next_cursor: str | None = Field(
        None, description="Cursor for next page (use this instead of offset)"
    )
    has_more: bool = Field(False, description="Whether more results are available")
    deprecation_warning: str | None = Field(
        None, description="Warning when using deprecated offset pagination"
    )


class AuditLogStats(BaseModel):
    """Schema for audit log statistics."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_logs": 5000,
                "logs_today": 150,
                "by_action": {"acknowledge": 50, "create": 30, "update": 45, "delete": 25},
                "by_resource_type": {"event": 80, "alert": 40, "camera": 20, "settings": 10},
                "by_status": {"success": 145, "failure": 5},
                "recent_actors": ["admin@example.com", "system", "scheduler"],
            }
        }
    )

    total_logs: int = Field(..., ge=0, description="Total number of audit logs")
    logs_today: int = Field(..., ge=0, description="Number of logs today")
    by_action: dict[str, int] = Field(..., description="Counts by action type")
    by_resource_type: dict[str, int] = Field(..., description="Counts by resource type")
    by_status: dict[str, int] = Field(..., description="Counts by status")
    recent_actors: list[str] = Field(..., description="Recently active actors")


# Re-export enums for convenience in routes
__all__ = [
    "AuditAction",
    "AuditLogListResponse",
    "AuditLogResponse",
    "AuditLogStats",
    "AuditStatus",
]
