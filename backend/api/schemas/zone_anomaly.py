"""Pydantic schemas for zone anomaly API endpoints.

This module provides request/response schemas for the zone anomaly API,
enabling detection of unusual activity patterns in camera zones.

Related: NEM-3199 (Frontend Anomaly Alert Integration)
Related: NEM-3198 (Backend Anomaly Detection Service)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta


class AnomalyType(str, Enum):
    """Types of zone anomalies that can be detected."""

    UNUSUAL_TIME = "unusual_time"
    UNUSUAL_FREQUENCY = "unusual_frequency"
    UNUSUAL_DWELL = "unusual_dwell"
    UNUSUAL_ENTITY = "unusual_entity"


class AnomalySeverity(str, Enum):
    """Severity levels for detected anomalies."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ZoneAnomalyResponse(BaseModel):
    """Response schema for a single zone anomaly."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "zone_id": "456e7890-e89b-12d3-a456-426614174001",
                "camera_id": "front_door",
                "anomaly_type": "unusual_time",
                "severity": "warning",
                "title": "Unusual activity at 03:15",
                "description": "Activity detected in Front Door at 03:15 when typical activity is 0.1.",
                "expected_value": 0.1,
                "actual_value": 1.0,
                "deviation": 3.5,
                "detection_id": 12345,
                "thumbnail_url": "/api/detections/12345/image",
                "acknowledged": False,
                "acknowledged_at": None,
                "acknowledged_by": None,
                "timestamp": "2025-01-24T03:15:00Z",
                "created_at": "2025-01-24T03:15:00Z",
                "updated_at": "2025-01-24T03:15:00Z",
            }
        },
    )

    id: str = Field(..., description="Unique identifier for the anomaly")
    zone_id: str = Field(..., description="Zone ID where anomaly was detected")
    camera_id: str = Field(..., description="Camera ID associated with the zone")
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    severity: str = Field(..., description="Severity level of the anomaly")
    title: str = Field(..., description="Human-readable title")
    description: str | None = Field(None, description="Detailed description of the anomaly")
    expected_value: float | None = Field(None, description="Expected value from baseline")
    actual_value: float | None = Field(None, description="Actual observed value")
    deviation: float | None = Field(None, description="Statistical deviation from baseline")
    detection_id: int | None = Field(None, description="Related detection ID if applicable")
    thumbnail_url: str | None = Field(None, description="URL to thumbnail image for visual context")
    acknowledged: bool = Field(..., description="Whether the anomaly has been acknowledged")
    acknowledged_at: datetime | None = Field(None, description="When the anomaly was acknowledged")
    acknowledged_by: str | None = Field(None, description="Who acknowledged the anomaly")
    timestamp: datetime = Field(..., description="When the anomaly occurred")
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime = Field(..., description="When the record was last updated")


class ZoneAnomalyListResponse(BaseModel):
    """Response schema for zone anomaly list endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "zone_id": "456e7890-e89b-12d3-a456-426614174001",
                        "camera_id": "front_door",
                        "anomaly_type": "unusual_time",
                        "severity": "warning",
                        "title": "Unusual activity at 03:15",
                        "description": "Activity detected in Front Door at 03:15.",
                        "expected_value": 0.1,
                        "actual_value": 1.0,
                        "deviation": 3.5,
                        "detection_id": 12345,
                        "thumbnail_url": "/api/detections/12345/image",
                        "acknowledged": False,
                        "acknowledged_at": None,
                        "acknowledged_by": None,
                        "timestamp": "2025-01-24T03:15:00Z",
                        "created_at": "2025-01-24T03:15:00Z",
                        "updated_at": "2025-01-24T03:15:00Z",
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

    items: list[ZoneAnomalyResponse] = Field(..., description="List of anomalies")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class ZoneAnomalyAcknowledgeResponse(BaseModel):
    """Response schema for acknowledging an anomaly."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "acknowledged": True,
                "acknowledged_at": "2025-01-24T04:00:00Z",
                "acknowledged_by": None,
            }
        }
    )

    id: str = Field(..., description="Anomaly ID")
    acknowledged: bool = Field(..., description="Whether the anomaly is now acknowledged")
    acknowledged_at: datetime = Field(..., description="When the anomaly was acknowledged")
    acknowledged_by: str | None = Field(None, description="Who acknowledged the anomaly")
