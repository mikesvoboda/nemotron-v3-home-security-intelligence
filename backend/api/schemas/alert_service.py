"""Pydantic schemas for Alert Service CRUD API endpoints.

Implements NEM-4931: Expose Alert Service CRUD Endpoints.

These schemas provide request/response models for the AlertService CRUD operations,
enabling programmatic management of alerts (create, read, update, delete).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.alerts import AlertSeverity, AlertStatus, DedupKeyStr
from backend.api.schemas.pagination import PaginationMeta


class AlertServiceCreateRequest(BaseModel):
    """Schema for creating an alert via the Alert Service.

    This bypasses alert rules and creates an alert directly. Useful for
    programmatic alert creation from external systems or internal services.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "severity": "high",
                "dedup_key": "front_door:manual_alert",
                "rule_id": None,
                "status": "pending",
                "channels": ["pushover", "webhook"],
                "metadata": {"source": "external_system", "note": "Manual alert"},
            }
        }
    )

    event_id: int = Field(..., description="Event ID that this alert relates to")
    severity: AlertSeverity = Field(
        AlertSeverity.MEDIUM, description="Alert severity level"
    )
    dedup_key: DedupKeyStr = Field(
        ...,
        max_length=255,
        description="Deduplication key for alert grouping. "
        "Only alphanumeric, underscore, hyphen, and colon characters allowed.",
    )
    rule_id: str | None = Field(
        None, description="Optional alert rule UUID that triggered this alert"
    )
    status: AlertStatus = Field(
        AlertStatus.PENDING, description="Initial alert status"
    )
    channels: list[str] = Field(
        default_factory=list, description="Notification channels for delivery"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Additional context metadata for the alert"
    )


class AlertServiceUpdateRequest(BaseModel):
    """Schema for updating an alert via the Alert Service.

    All fields are optional. Only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "acknowledged",
                "severity": "high",
                "metadata": {"acknowledged_by": "admin"},
            }
        }
    )

    status: AlertStatus | None = Field(None, description="New alert status")
    severity: AlertSeverity | None = Field(None, description="New severity level")
    channels: list[str] | None = Field(None, description="Updated notification channels")
    metadata: dict[str, Any] | None = Field(
        None, description="Updated metadata (replaces existing)"
    )


class AlertServiceResponse(BaseModel):
    """Schema for alert response from Alert Service operations."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "019477e6-8c5e-7abc-def0-123456789abc",
                "event_id": 123,
                "rule_id": None,
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:manual_alert",
                "channels": ["pushover"],
                "metadata": {"source": "external_system"},
                "created_at": "2025-01-31T12:00:00Z",
                "updated_at": "2025-01-31T12:00:00Z",
                "delivered_at": None,
            }
        },
    )

    id: str = Field(..., description="Alert UUID")
    event_id: int = Field(..., description="Associated event ID")
    rule_id: str | None = Field(None, description="Alert rule UUID that triggered this")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(..., description="Alert status")
    dedup_key: str = Field(..., description="Deduplication key")
    channels: list[str] = Field(default_factory=list, description="Notification channels")
    metadata: dict[str, Any] | None = Field(
        None,
        description="Additional context metadata",
        validation_alias="alert_metadata",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    delivered_at: datetime | None = Field(None, description="Delivery timestamp")


class AlertServiceListResponse(BaseModel):
    """Schema for alert list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "019477e6-8c5e-7abc-def0-123456789abc",
                        "event_id": 123,
                        "rule_id": None,
                        "severity": "high",
                        "status": "pending",
                        "dedup_key": "front_door:manual_alert",
                        "channels": ["pushover"],
                        "metadata": {},
                        "created_at": "2025-01-31T12:00:00Z",
                        "updated_at": "2025-01-31T12:00:00Z",
                        "delivered_at": None,
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "has_more": False,
                },
            }
        }
    )

    items: list[AlertServiceResponse] = Field(..., description="List of alerts")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class AlertServiceDeleteResponse(BaseModel):
    """Schema for alert deletion response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "deleted_id": "019477e6-8c5e-7abc-def0-123456789abc",
                "message": "Alert deleted successfully",
            }
        }
    )

    success: bool = Field(..., description="Whether the deletion was successful")
    deleted_id: str = Field(..., description="ID of the deleted alert")
    message: str = Field("Alert deleted successfully", description="Status message")


class AcknowledgeRequest(BaseModel):
    """Schema for acknowledging an alert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "correlation_id": "req-12345",
            }
        }
    )

    correlation_id: str | None = Field(
        None, description="Optional correlation ID for request tracing"
    )


class DismissRequest(BaseModel):
    """Schema for dismissing an alert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "False positive - neighbor's cat",
                "correlation_id": "req-12345",
            }
        }
    )

    reason: str | None = Field(None, description="Reason for dismissing the alert")
    correlation_id: str | None = Field(
        None, description="Optional correlation ID for request tracing"
    )
