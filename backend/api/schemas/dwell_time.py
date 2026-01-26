"""Pydantic schemas for dwell time tracking and loitering detection.

This module defines schemas for:
- DwellTimeRecordResponse: API response for dwell time records
- LoiteringAlert: Alert generated when loitering threshold exceeded
- ActiveDwellerResponse: Response for objects currently in a zone
- DwellHistoryResponse: Historical dwell time records
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DwellTimeRecordBase(BaseModel):
    """Base schema for dwell time record data."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "entry_time": "2026-01-26T12:00:00Z",
                "exit_time": "2026-01-26T12:05:30Z",
                "total_seconds": 330.0,
                "triggered_alert": True,
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    track_id: int = Field(..., description="Tracking ID of the detected object")
    camera_id: str = Field(..., description="ID of the camera where detection occurred")
    object_class: str = Field(..., description="Classification of the object (e.g., person)")


class DwellTimeRecordResponse(DwellTimeRecordBase):
    """Response schema for a dwell time record.

    Includes computed fields and database identifiers.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "zone_id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "entry_time": "2026-01-26T12:00:00Z",
                "exit_time": "2026-01-26T12:05:30Z",
                "total_seconds": 330.0,
                "triggered_alert": True,
                "is_active": False,
            }
        },
    )

    id: int = Field(..., description="Unique dwell time record identifier")
    entry_time: datetime = Field(..., description="Timestamp when object entered the zone")
    exit_time: datetime | None = Field(
        None,
        description="Timestamp when object exited the zone (null if still present)",
    )
    total_seconds: float = Field(
        ...,
        ge=0,
        description="Total dwell time in seconds",
    )
    triggered_alert: bool = Field(
        ...,
        description="Whether this dwell time triggered a loitering alert",
    )
    is_active: bool = Field(
        default=False,
        description="Whether the object is still in the zone (no exit time)",
    )


class LoiteringAlert(BaseModel):
    """Alert generated when an object exceeds the loitering threshold.

    This schema represents a loitering event where an object has been
    detected in a zone for longer than the configured threshold.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "entry_time": "2026-01-26T12:00:00Z",
                "dwell_seconds": 350.5,
                "threshold_seconds": 300.0,
                "record_id": 123,
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone where loitering detected")
    track_id: int = Field(..., description="Tracking ID of the loitering object")
    camera_id: str = Field(..., description="ID of the camera where detection occurred")
    object_class: str = Field(..., description="Classification of the loitering object")
    entry_time: datetime = Field(..., description="When the object entered the zone")
    dwell_seconds: float = Field(..., ge=0, description="Current dwell time in seconds")
    threshold_seconds: float = Field(..., ge=0, description="Loitering threshold that was exceeded")
    record_id: int = Field(..., description="ID of the associated dwell time record")


class ActiveDwellerResponse(BaseModel):
    """Response for an object currently dwelling in a zone.

    Includes real-time dwell time calculation.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "record_id": 1,
                "track_id": 42,
                "camera_id": "front_door",
                "object_class": "person",
                "entry_time": "2026-01-26T12:00:00Z",
                "current_dwell_seconds": 150.3,
            }
        },
    )

    record_id: int = Field(..., description="ID of the dwell time record")
    track_id: int = Field(..., description="Tracking ID of the object")
    camera_id: str = Field(..., description="ID of the camera")
    object_class: str = Field(..., description="Classification of the object")
    entry_time: datetime = Field(..., description="When the object entered the zone")
    current_dwell_seconds: float = Field(
        ...,
        ge=0,
        description="Current dwell time in seconds (calculated at request time)",
    )


class ActiveDwellersListResponse(BaseModel):
    """List of objects currently dwelling in a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "dwellers": [
                    {
                        "record_id": 1,
                        "track_id": 42,
                        "camera_id": "front_door",
                        "object_class": "person",
                        "entry_time": "2026-01-26T12:00:00Z",
                        "current_dwell_seconds": 150.3,
                    }
                ],
                "total": 1,
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    dwellers: list[ActiveDwellerResponse] = Field(
        ...,
        description="List of objects currently in the zone",
    )
    total: int = Field(..., ge=0, description="Total number of active dwellers")


class DwellHistoryResponse(BaseModel):
    """Historical dwell time records for a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "records": [
                    {
                        "id": 1,
                        "zone_id": 1,
                        "track_id": 42,
                        "camera_id": "front_door",
                        "object_class": "person",
                        "entry_time": "2026-01-26T12:00:00Z",
                        "exit_time": "2026-01-26T12:05:30Z",
                        "total_seconds": 330.0,
                        "triggered_alert": True,
                        "is_active": False,
                    }
                ],
                "total": 1,
                "start_time": "2026-01-26T11:00:00Z",
                "end_time": "2026-01-26T13:00:00Z",
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    records: list[DwellTimeRecordResponse] = Field(
        ...,
        description="Dwell time records in the time window",
    )
    total: int = Field(..., ge=0, description="Total number of records")
    start_time: datetime = Field(..., description="Start of the query time window")
    end_time: datetime = Field(..., description="End of the query time window")


class LoiteringCheckRequest(BaseModel):
    """Request to check for loitering in a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "threshold_seconds": 300.0,
            }
        }
    )

    threshold_seconds: float = Field(
        ...,
        gt=0,
        description="Dwell time threshold in seconds to trigger loitering alert",
    )


class LoiteringCheckResponse(BaseModel):
    """Response containing loitering alerts for a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "threshold_seconds": 300.0,
                "alerts": [
                    {
                        "zone_id": 1,
                        "track_id": 42,
                        "camera_id": "front_door",
                        "object_class": "person",
                        "entry_time": "2026-01-26T12:00:00Z",
                        "dwell_seconds": 350.5,
                        "threshold_seconds": 300.0,
                        "record_id": 123,
                    }
                ],
                "total_alerts": 1,
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone checked")
    threshold_seconds: float = Field(..., description="Threshold used for checking")
    alerts: list[LoiteringAlert] = Field(..., description="Loitering alerts detected")
    total_alerts: int = Field(..., ge=0, description="Total number of alerts")


class DwellStatisticsResponse(BaseModel):
    """Statistics for dwell time in a zone."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_id": 1,
                "total_records": 50,
                "avg_dwell_seconds": 120.5,
                "max_dwell_seconds": 600.0,
                "min_dwell_seconds": 5.0,
                "alerts_triggered": 3,
                "start_time": "2026-01-26T00:00:00Z",
                "end_time": "2026-01-26T23:59:59Z",
            }
        }
    )

    zone_id: int = Field(..., description="ID of the polygon zone")
    total_records: int = Field(..., ge=0, description="Total number of completed dwell records")
    avg_dwell_seconds: float = Field(..., ge=0, description="Average dwell time in seconds")
    max_dwell_seconds: float = Field(..., ge=0, description="Maximum dwell time in seconds")
    min_dwell_seconds: float = Field(..., ge=0, description="Minimum dwell time in seconds")
    alerts_triggered: int = Field(..., ge=0, description="Number of loitering alerts triggered")
    start_time: datetime = Field(..., description="Start of the statistics time window")
    end_time: datetime = Field(..., description="End of the statistics time window")


# Export all schemas
__all__ = [
    "ActiveDwellerResponse",
    "ActiveDwellersListResponse",
    "DwellHistoryResponse",
    "DwellStatisticsResponse",
    "DwellTimeRecordBase",
    "DwellTimeRecordResponse",
    "LoiteringAlert",
    "LoiteringCheckRequest",
    "LoiteringCheckResponse",
]
