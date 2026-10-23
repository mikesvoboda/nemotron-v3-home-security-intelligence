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


class PushSubscriptionKeys(BaseModel):
    """Browser-supplied Web Push encryption keys (PushSubscriptionJSON.keys)."""

    p256dh: str = Field(..., min_length=1, description="Client public key (P-256, urlsafe base64)")
    auth: str = Field(..., min_length=1, description="Authentication secret (urlsafe base64)")


class PushSubscriptionRegister(BaseModel):
    """Body for registering/rotating This-browser's Web Push subscription.

    Mirrors the browser's ``PushSubscriptionJSON``: endpoint plus keys, with an
    optional device id so multiple browsers can each hold their own channel row.
    """

    endpoint: str = Field(..., min_length=1, description="Push service endpoint URL")
    keys: PushSubscriptionKeys = Field(..., description="p256dh + auth encryption keys")
    device_id: str | None = Field(
        default=None, description="Stable browser identifier; used to match the channel row"
    )


class PushSubscriptionState(BaseModel):
    """This-browser subscription state for the settings page (masked).

    The privacy row (4n-alerting.md "Privacy"): the API never returns secrets
    or push keys in full — key material is masked to a fingerprint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "registered": True,
                "enabled": True,
                "endpoint": "https://fcm.googleapis.com/fcm/send/…",
                "push_subscription": {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/…",
                    "keys": {"p256dh": "p256dh:bf31…", "auth": "auth:9d20…"},
                },
                "last_error": None,
            }
        }
    )

    registered: bool = Field(..., description="Whether a subscription exists for this browser")
    enabled: bool = Field(default=False, description="Whether the channel row is enabled")
    endpoint: str | None = Field(default=None, description="Push service endpoint (host truncated)")
    push_subscription: dict | None = Field(
        default=None, description="Masked subscription: endpoint + fingerprinted keys"
    )
    last_error: str | None = Field(
        default=None, description="Last delivery error, e.g. subscription_expired"
    )


class PushSubscriptionRegisterResponse(BaseModel):
    """Answer to a successful registration/rotation."""

    status: str = Field(..., description="registered")
    push_subscription: dict = Field(..., description="Masked subscription echo")
    enabled: bool = Field(default=True, description="Channel state after registration")
