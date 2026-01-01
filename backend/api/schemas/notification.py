"""Pydantic schemas for notification API endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.url_validation import SSRFValidationError, validate_webhook_url


class NotificationChannel(str, Enum):
    """Notification channel types."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    PUSH = "push"


# =============================================================================
# Notification Delivery Schemas
# =============================================================================


class NotificationDeliveryResponse(BaseModel):
    """Schema for a single notification delivery result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "email",
                "success": True,
                "error": None,
                "delivered_at": "2025-12-28T12:00:30Z",
                "recipient": "user@example.com",
            }
        }
    )

    channel: NotificationChannel = Field(..., description="Notification channel used")
    success: bool = Field(..., description="Whether delivery was successful")
    error: str | None = Field(None, description="Error message if delivery failed")
    delivered_at: datetime | None = Field(None, description="Timestamp of successful delivery")
    recipient: str | None = Field(None, description="Recipient identifier (email, URL, etc.)")


class DeliveryResultResponse(BaseModel):
    """Schema for complete delivery result across multiple channels."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_id": "550e8400-e29b-41d4-a716-446655440001",
                "deliveries": [
                    {
                        "channel": "email",
                        "success": True,
                        "error": None,
                        "delivered_at": "2025-12-28T12:00:30Z",
                        "recipient": "user@example.com",
                    },
                    {
                        "channel": "webhook",
                        "success": True,
                        "error": None,
                        "delivered_at": "2025-12-28T12:00:31Z",
                        "recipient": "https://example.com/webhook",
                    },
                ],
                "all_successful": True,
                "successful_count": 2,
                "failed_count": 0,
            }
        }
    )

    alert_id: str = Field(..., description="Alert ID that was delivered")
    deliveries: list[NotificationDeliveryResponse] = Field(
        ..., description="List of delivery attempts"
    )
    all_successful: bool = Field(..., description="Whether all deliveries succeeded")
    successful_count: int = Field(..., description="Number of successful deliveries")
    failed_count: int = Field(..., description="Number of failed deliveries")


# =============================================================================
# Notification Send Schemas
# =============================================================================


class SendNotificationRequest(BaseModel):
    """Schema for requesting notification delivery for an alert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_id": "550e8400-e29b-41d4-a716-446655440001",
                "channels": ["email", "webhook"],
                "email_recipients": ["user@example.com", "admin@example.com"],
                "webhook_url": "https://example.com/webhook",
            }
        }
    )

    alert_id: str = Field(..., description="Alert ID to send notifications for")
    channels: list[NotificationChannel] | None = Field(
        None,
        description="Channels to use (defaults to alert's configured channels or all available)",
    )
    email_recipients: list[str] | None = Field(
        None, description="Email recipients (overrides default recipients)"
    )
    webhook_url: str | None = Field(
        None,
        description="Webhook URL (overrides default webhook URL). Must be HTTPS and not point to private IPs.",
    )

    @field_validator("webhook_url", mode="before")
    @classmethod
    def validate_webhook_url_ssrf(cls, v: Any) -> str | None:
        """Validate webhook URL for SSRF protection.

        Args:
            v: The URL value to validate (can be None)

        Returns:
            The validated URL as a string, or None if not provided

        Raises:
            ValueError: If the URL fails SSRF validation
        """
        if v is None or v == "":
            return None

        url_str = str(v)

        try:
            # Use SSRF-safe validation (allow localhost HTTP in dev for testing)
            # In production, resolve_dns=False for schema validation,
            # full DNS validation happens at request time
            return validate_webhook_url(url_str, allow_dev_http=True, resolve_dns=False)
        except SSRFValidationError as e:
            # Convert to ValueError for Pydantic
            raise ValueError(str(e)) from None


class WebhookTestNotificationRequest(BaseModel):
    """Schema for testing notification configuration."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "email",
                "email_recipients": ["test@example.com"],
                "webhook_url": None,
            }
        }
    )

    channel: NotificationChannel = Field(..., description="Channel to test")
    email_recipients: list[str] | None = Field(None, description="Email recipients for email test")
    webhook_url: str | None = Field(
        None,
        description="Webhook URL for webhook test. Must be HTTPS and not point to private IPs.",
    )

    @field_validator("webhook_url", mode="before")
    @classmethod
    def validate_webhook_url_ssrf(cls, v: Any) -> str | None:
        """Validate webhook URL for SSRF protection.

        Args:
            v: The URL value to validate (can be None)

        Returns:
            The validated URL as a string, or None if not provided

        Raises:
            ValueError: If the URL fails SSRF validation
        """
        if v is None or v == "":
            return None

        url_str = str(v)

        try:
            # Use SSRF-safe validation (allow localhost HTTP in dev for testing)
            return validate_webhook_url(url_str, allow_dev_http=True, resolve_dns=False)
        except SSRFValidationError as e:
            # Convert to ValueError for Pydantic
            raise ValueError(str(e)) from None


# Keep original name for backward compatibility
TestNotificationRequest = WebhookTestNotificationRequest


class TestNotificationResponse(BaseModel):
    """Schema for test notification result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "email",
                "success": True,
                "error": None,
                "message": "Test email sent successfully to test@example.com",
            }
        }
    )

    channel: NotificationChannel = Field(..., description="Channel that was tested")
    success: bool = Field(..., description="Whether the test was successful")
    error: str | None = Field(None, description="Error message if test failed")
    message: str = Field(..., description="Human-readable result message")


# =============================================================================
# Notification Configuration Schemas
# =============================================================================


class NotificationConfigResponse(BaseModel):
    """Schema for notification configuration status."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notification_enabled": True,
                "email_configured": True,
                "webhook_configured": True,
                "push_configured": False,
                "available_channels": ["email", "webhook"],
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_from_address": "alerts@example.com",
                "smtp_use_tls": True,
                "default_webhook_url": "https://example.com/webhook",
                "webhook_timeout_seconds": 30,
                "default_email_recipients": ["user@example.com"],
            }
        }
    )

    notification_enabled: bool = Field(..., description="Whether notifications are enabled")
    email_configured: bool = Field(..., description="Whether email (SMTP) is configured")
    webhook_configured: bool = Field(..., description="Whether webhook is configured")
    push_configured: bool = Field(..., description="Whether push notifications are configured")
    available_channels: list[NotificationChannel] = Field(
        ..., description="List of channels that are properly configured"
    )
    smtp_host: str | None = Field(None, description="Configured SMTP host (if any)")
    smtp_port: int | None = Field(None, description="Configured SMTP port")
    smtp_from_address: str | None = Field(None, description="Configured sender email")
    smtp_use_tls: bool | None = Field(None, description="Whether TLS is enabled for SMTP")
    default_webhook_url: str | None = Field(None, description="Default webhook URL")
    webhook_timeout_seconds: int | None = Field(None, description="Webhook request timeout")
    default_email_recipients: list[str] = Field(
        default_factory=list, description="Default email recipients"
    )


# =============================================================================
# Notification History Schemas
# =============================================================================


class NotificationHistoryEntry(BaseModel):
    """Schema for a notification history entry."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "alert_id": "550e8400-e29b-41d4-a716-446655440001",
                "channel": "email",
                "recipient": "user@example.com",
                "success": True,
                "error": None,
                "delivered_at": "2025-12-28T12:00:30Z",
                "created_at": "2025-12-28T12:00:29Z",
            }
        }
    )

    id: str = Field(..., description="Notification delivery ID")
    alert_id: str = Field(..., description="Associated alert ID")
    channel: NotificationChannel = Field(..., description="Notification channel")
    recipient: str | None = Field(None, description="Recipient identifier")
    success: bool = Field(..., description="Whether delivery was successful")
    error: str | None = Field(None, description="Error message if failed")
    delivered_at: datetime | None = Field(None, description="Delivery timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")


class NotificationHistoryResponse(BaseModel):
    """Schema for notification history list response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entries": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440002",
                        "alert_id": "550e8400-e29b-41d4-a716-446655440001",
                        "channel": "email",
                        "recipient": "user@example.com",
                        "success": True,
                        "error": None,
                        "delivered_at": "2025-12-28T12:00:30Z",
                        "created_at": "2025-12-28T12:00:29Z",
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    entries: list[NotificationHistoryEntry] = Field(..., description="Notification history entries")
    count: int = Field(..., description="Total number of entries matching filters")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")
