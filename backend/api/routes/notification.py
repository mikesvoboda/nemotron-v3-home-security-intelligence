"""Notification configuration API endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.notification import (
    NotificationChannel,
    NotificationConfigResponse,
    NotificationHistoryEntry,
    NotificationHistoryResponse,
    TestNotificationRequest,
    TestNotificationResponse,
)
from backend.core import get_db, get_settings
from backend.models.audit import AuditAction
from backend.services.audit import AuditService
from backend.services.notification import (
    NotificationService,
    get_notification_service,
)

if TYPE_CHECKING:
    from backend.core.config import Settings
    from backend.models import Alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notification", tags=["notification"])


@router.get("/config", response_model=NotificationConfigResponse)
async def get_notification_config() -> NotificationConfigResponse:
    """Get notification configuration status.

    Returns the current notification configuration including:
    - Whether notifications are enabled
    - Which channels are configured (email, webhook, push)
    - SMTP host and port (if configured)
    - Default webhook URL (if configured)
    - Default email recipients

    Note: Sensitive fields like SMTP password are NOT returned.

    Returns:
        NotificationConfigResponse with current notification settings
    """
    settings = get_settings()
    notification_service = get_notification_service(settings)

    # Get available channels from the service
    available_channels = notification_service.get_available_channels()

    return NotificationConfigResponse(
        notification_enabled=settings.notification_enabled,
        email_configured=notification_service.is_email_configured(),
        webhook_configured=notification_service.is_webhook_configured(),
        push_configured=notification_service.is_push_configured(),
        available_channels=[NotificationChannel(ch.value) for ch in available_channels],
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port if settings.smtp_host else None,
        smtp_from_address=settings.smtp_from_address,
        smtp_use_tls=settings.smtp_use_tls if settings.smtp_host else None,
        default_webhook_url=settings.default_webhook_url,
        webhook_timeout_seconds=(
            settings.webhook_timeout_seconds if settings.default_webhook_url else None
        ),
        default_email_recipients=settings.default_email_recipients,
    )


def _create_error_response(
    channel: NotificationChannel, error: str, message: str
) -> TestNotificationResponse:
    """Create a standardized error response for notification tests."""
    return TestNotificationResponse(
        channel=channel,
        success=False,
        error=error,
        message=message,
    )


async def _test_email_channel(
    notification_service: NotificationService,
    settings: Settings,
    test_request: TestNotificationRequest,
    mock_alert: Alert,
) -> tuple[bool, str | None]:
    """Test email notification channel.

    Returns:
        Tuple of (success, error_or_result_message)
    """
    # Use provided recipients or fall back to defaults
    recipients = test_request.email_recipients or settings.default_email_recipients
    if not recipients:
        return (False, "No email recipients provided or configured")

    if not notification_service.is_email_configured():
        return (False, "Email is not configured (missing SMTP settings)")

    delivery = await notification_service.send_email(mock_alert, recipients)
    if delivery.success:
        return (True, f"Test email sent successfully to {', '.join(recipients)}")
    return (False, delivery.error)


async def _test_webhook_channel(
    notification_service: NotificationService,
    settings: Settings,
    test_request: TestNotificationRequest,
    mock_alert: Alert,
) -> tuple[bool, str | None]:
    """Test webhook notification channel.

    Returns:
        Tuple of (success, error_or_result_message)
    """
    # Use provided URL or fall back to default
    webhook_url = test_request.webhook_url or settings.default_webhook_url
    if not webhook_url:
        return (False, "No webhook URL provided or configured")

    delivery = await notification_service.send_webhook(mock_alert, webhook_url)
    if delivery.success:
        return (True, f"Test webhook sent successfully to {webhook_url}")
    return (False, delivery.error)


@router.post("/test", response_model=TestNotificationResponse)
async def test_notification(
    request: Request,
    test_request: TestNotificationRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> TestNotificationResponse:
    """Test notification delivery for a specific channel.

    Sends a test notification to verify the configuration is working.
    For email, sends a test email to the specified recipients or default recipients.
    For webhook, sends a test payload to the specified URL or default URL.

    Args:
        test_request: Test notification request with channel and optional overrides

    Returns:
        TestNotificationResponse with test result
    """
    settings = get_settings()
    notification_service = get_notification_service(settings)

    channel = test_request.channel

    # Create a mock alert for testing
    from backend.models import Alert
    from backend.models.alert import AlertSeverity, AlertStatus

    mock_alert = Alert(
        id="test-notification-" + datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
        event_id=0,
        rule_id="test-rule",
        severity=AlertSeverity.LOW,
        status=AlertStatus.PENDING,
        dedup_key="test-notification",
        channels=[channel.value],
        alert_metadata={
            "rule_name": "Test Notification",
            "matched_conditions": ["This is a test notification to verify configuration"],
        },
        created_at=datetime.now(UTC),
    )

    try:
        # Route to appropriate channel handler
        if channel == NotificationChannel.EMAIL:
            success, result = await _test_email_channel(
                notification_service, settings, test_request, mock_alert
            )
        elif channel == NotificationChannel.WEBHOOK:
            success, result = await _test_webhook_channel(
                notification_service, settings, test_request, mock_alert
            )
        elif channel == NotificationChannel.PUSH:
            success, result = False, "Push notifications are not yet implemented"
        else:
            success, result = False, f"Unknown channel: {channel}"

        # Handle failure cases
        if not success:
            error_messages = {
                "No email recipients provided or configured": "Please provide email recipients or configure default recipients",
                "Email is not configured (missing SMTP settings)": "Please configure SMTP settings (host, from address) to enable email notifications",
                "No webhook URL provided or configured": "Please provide a webhook URL or configure default webhook URL",
                "Push notifications are not yet implemented": "Push notification support is planned for a future release",
            }
            message = error_messages.get(
                result or "",
                f"Failed to send test {channel.value}: {result}" if result else "Unknown error",
            )
            if result and result.startswith("Unknown channel:"):
                message = "Invalid notification channel specified"
            return _create_error_response(channel, result or "Unknown error", message)

        # Log the audit entry for successful test
        try:
            await AuditService.log_action(
                db=db,
                action=AuditAction.NOTIFICATION_TEST,
                resource_type="notification",
                resource_id=channel.value,
                actor="anonymous",
                details={"channel": channel.value, "success": True},
                request=request,
            )
            await db.commit()
        except Exception:
            logger.error(
                "Failed to commit audit log",
                exc_info=True,
                extra={"action": "notification_test", "channel": channel.value},
            )
            await db.rollback()
            # Don't fail the main operation - audit is non-critical

        return TestNotificationResponse(
            channel=channel,
            success=True,
            error=None,
            message=result or "",
        )

    except Exception as e:
        # Log without user-controlled data to avoid log injection (CodeQL py/log-injection)
        logger.exception("Error testing notification")
        return _create_error_response(
            channel,
            str(e),
            f"An error occurred while testing {channel.value} notification",
        )


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    alert_id: str | None = Query(None, description="Filter by alert ID"),
    channel: NotificationChannel | None = Query(None, description="Filter by channel"),
    success: bool | None = Query(None, description="Filter by success status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> NotificationHistoryResponse:
    """Get notification delivery history with optional filters.

    Returns paginated notification delivery records with optional filtering
    by alert ID, channel type, and success status.

    Note: This endpoint returns the structure for notification history.
    A future enhancement will persist delivery records to the database
    and return actual history data.

    Args:
        alert_id: Optional alert ID to filter by
        channel: Optional notification channel to filter by
        success: Optional success status to filter by
        limit: Maximum number of results to return (1-100, default 50)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        NotificationHistoryResponse with delivery history entries
    """
    # Note: Currently returns empty list since notification deliveries
    # are not yet persisted to the database. This provides the API structure
    # for frontend integration. A future task (NotificationDelivery model)
    # will enable actual history tracking.
    #
    # When implemented, this will query the notification_deliveries table
    # with the provided filters and return paginated results.

    logger.debug(
        "Notification history requested",
        extra={
            "alert_id": alert_id,
            "channel": channel.value if channel else None,
            "success": success,
            "limit": limit,
            "offset": offset,
        },
    )

    # Return empty response with correct structure
    # This allows frontend to integrate now while backend persistence is added later
    entries: list[NotificationHistoryEntry] = []

    return NotificationHistoryResponse(
        entries=entries,
        count=0,
        limit=limit,
        offset=offset,
    )
