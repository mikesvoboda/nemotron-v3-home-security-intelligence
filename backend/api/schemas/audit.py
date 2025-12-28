"""Pydantic schemas for audit log API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.audit import AuditAction, AuditStatus


class AuditLogResponse(BaseModel):
    """Schema for a single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Audit log entry ID")
    timestamp: datetime = Field(..., description="When the action occurred")
    action: str = Field(..., description="The action performed")
    resource_type: str = Field(
        ..., description="Type of resource (event, alert, rule, camera, settings)"
    )
    resource_id: str | None = Field(None, description="ID of the specific resource")
    actor: str = Field(..., description="User or system that performed the action")
    ip_address: str | None = Field(None, description="IP address of the client")
    user_agent: str | None = Field(None, description="User agent string of the client")
    details: dict[str, Any] | None = Field(None, description="Action-specific details")
    status: str = Field(..., description="Status of the action (success/failure)")


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log response."""

    logs: list[AuditLogResponse] = Field(..., description="List of audit log entries")
    count: int = Field(..., description="Total count matching filters")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class AuditLogStats(BaseModel):
    """Schema for audit log statistics."""

    total_logs: int = Field(..., description="Total number of audit logs")
    logs_today: int = Field(..., description="Number of logs today")
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
