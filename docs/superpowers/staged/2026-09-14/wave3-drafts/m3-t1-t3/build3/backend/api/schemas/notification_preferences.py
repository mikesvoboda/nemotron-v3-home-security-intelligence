"""Pydantic schemas for notification preferences API endpoints."""

from datetime import time

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta
from backend.models.notification_preferences import DayOfWeek, NotificationSound, RiskLevel

__all__ = [
    "CameraNotificationSettingResponse",
    "CameraNotificationSettingUpdate",
    "CameraNotificationSettingsListResponse",
    "DayOfWeek",
    "NotificationPreferencesResponse",
    "NotificationPreferencesUpdate",
    "NotificationSound",
    "QuietHoursPeriodCreate",
    "QuietHoursPeriodResponse",
    "QuietHoursPeriodsListResponse",
    "RiskLevel",
]


class NotificationPreferencesResponse(BaseModel):
    """Schema for notification preferences response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "enabled": True,
                "sound": "default",
                "risk_filters": ["critical", "high", "medium"],
            }
        },
    )

    id: int = Field(1, description="Preferences ID (always 1, singleton)")
    enabled: bool = Field(..., description="Whether notifications are globally enabled")
    sound: str = Field(..., description="Notification sound (none, default, alert, chime, urgent)")
    risk_filters: list[str] = Field(
        ...,
        description="Risk levels that trigger notifications (critical, high, medium, low)",
    )


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "sound": "alert",
                "risk_filters": ["critical", "high"],
            }
        }
    )

    enabled: bool | None = Field(None, description="Whether notifications are globally enabled")
    sound: str | None = Field(
        None, description="Notification sound (none, default, alert, chime, urgent)"
    )
    risk_filters: list[str] | None = Field(
        None,
        description="Risk levels that trigger notifications (critical, high, medium, low)",
    )


class CameraNotificationSettingResponse(BaseModel):
    """Schema for camera notification setting response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "camera_id": "front_door",
                "enabled": True,
                "risk_threshold": 50,
            }
        },
    )

    id: str = Field(..., description="Setting UUID")
    camera_id: str = Field(..., description="Camera ID")
    enabled: bool = Field(..., description="Whether notifications are enabled for this camera")
    risk_threshold: int = Field(
        ...,
        ge=0,
        le=100,
        description="Minimum risk score to trigger notifications (0-100)",
    )


class CameraNotificationSettingUpdate(BaseModel):
    """Schema for updating camera notification setting."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": False,
                "risk_threshold": 70,
            }
        }
    )

    enabled: bool | None = Field(
        None, description="Whether notifications are enabled for this camera"
    )
    risk_threshold: int | None = Field(
        None,
        ge=0,
        le=100,
        description="Minimum risk score to trigger notifications (0-100)",
    )


class CameraNotificationSettingsListResponse(BaseModel):
    """Schema for camera notification settings list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "camera_id": "front_door",
                        "enabled": True,
                        "risk_threshold": 50,
                    },
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "camera_id": "back_yard",
                        "enabled": False,
                        "risk_threshold": 70,
                    },
                ],
                "pagination": {
                    "total": 2,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[CameraNotificationSettingResponse] = Field(
        ..., description="List of camera notification settings"
    )
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class QuietHoursPeriodCreate(BaseModel):
    """Schema for creating a quiet hours period."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "Night Time",
                "start_time": "22:00:00",
                "end_time": "06:00:00",
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            }
        }
    )

    label: str = Field(..., min_length=1, max_length=255, description="Period label")
    start_time: time = Field(..., description="Start time (HH:MM:SS)")
    end_time: time = Field(..., description="End time (HH:MM:SS)")
    days: list[str] = Field(
        default_factory=lambda: [day.value for day in DayOfWeek],
        description="Days of week when period is active",
    )


class QuietHoursPeriodResponse(BaseModel):
    """Schema for quiet hours period response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "label": "Night Time",
                "start_time": "22:00:00",
                "end_time": "06:00:00",
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            }
        },
    )

    id: str = Field(..., description="Period UUID")
    label: str = Field(..., description="Period label")
    start_time: time = Field(..., description="Start time")
    end_time: time = Field(..., description="End time")
    days: list[str] = Field(..., description="Days of week when period is active")


class QuietHoursPeriodsListResponse(BaseModel):
    """Schema for quiet hours periods list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "label": "Night Time",
                        "start_time": "22:00:00",
                        "end_time": "06:00:00",
                        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[QuietHoursPeriodResponse] = Field(..., description="List of quiet hours periods")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
