"""Notification service for delivering alerts through multiple channels.

This module provides the NotificationService for sending alert notifications
via email (SMTP), webhooks (HTTP POST), and push notifications (stubbed).

Usage:
    from backend.services.notification import NotificationService, NotificationChannel

    service = NotificationService(settings)
    result = await service.deliver_alert(alert, [NotificationChannel.EMAIL, NotificationChannel.WEBHOOK])

Delivery Tracking:
    Each delivery attempt is tracked with a NotificationDelivery record containing:
    - channel: Which notification channel was used
    - success: Whether delivery succeeded
    - error: Error message if delivery failed
    - delivered_at: Timestamp of successful delivery
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from backend.core.config import Settings
    from backend.models import Alert

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Notification channel types."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    PUSH = "push"


@dataclass
class NotificationDelivery:
    """Result of a notification delivery attempt."""

    channel: NotificationChannel
    success: bool
    error: str | None = None
    delivered_at: datetime | None = None
    recipient: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "channel": self.channel.value,
            "success": self.success,
            "error": self.error,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "recipient": self.recipient,
        }


@dataclass
class DeliveryResult:
    """Complete result of delivering an alert through multiple channels."""

    alert_id: str
    deliveries: list[NotificationDelivery] = field(default_factory=list)
    all_successful: bool = False

    @property
    def successful_count(self) -> int:
        """Count of successful deliveries."""
        return sum(1 for d in self.deliveries if d.success)

    @property
    def failed_count(self) -> int:
        """Count of failed deliveries."""
        return sum(1 for d in self.deliveries if not d.success)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "deliveries": [d.to_dict() for d in self.deliveries],
            "all_successful": self.all_successful,
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
        }


class NotificationService:
    """Service for delivering alert notifications through multiple channels.

    This service supports:
    - Email (SMTP): Sends HTML emails with alert details
    - Webhook (HTTP POST): Posts JSON payload to configured URL
    - Push (stubbed): Placeholder for push notification integration

    Configuration is loaded from Settings. Each channel can be individually
    configured and is only used if the required settings are present.
    """

    def __init__(self, settings: Settings):
        """Initialize the notification service.

        Args:
            settings: Application settings containing notification configuration
        """
        self.settings = settings
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for webhook requests."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.webhook_timeout_seconds)
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def is_email_configured(self) -> bool:
        """Check if email (SMTP) is configured.

        Note: Recipients can be specified per-alert, so we only require
        SMTP host and from address to be configured.
        """
        return bool(self.settings.smtp_host and self.settings.smtp_from_address)

    def is_webhook_configured(self) -> bool:
        """Check if webhook is configured."""
        return bool(self.settings.default_webhook_url)

    def is_push_configured(self) -> bool:
        """Check if push notifications are configured (stubbed)."""
        # Push is not yet implemented
        return False

    def get_available_channels(self) -> list[NotificationChannel]:
        """Get list of channels that are properly configured."""
        channels = []
        if self.is_email_configured():
            channels.append(NotificationChannel.EMAIL)
        if self.is_webhook_configured():
            channels.append(NotificationChannel.WEBHOOK)
        if self.is_push_configured():
            channels.append(NotificationChannel.PUSH)
        return channels

    async def send_email(
        self,
        alert: Alert,
        recipients: list[str] | None = None,
    ) -> NotificationDelivery:
        """Send an alert notification via email.

        Args:
            alert: The alert to send
            recipients: Optional list of email recipients (defaults to settings)

        Returns:
            NotificationDelivery with success/failure status
        """
        if not self.is_email_configured():
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=False,
                error="Email is not configured (missing SMTP settings)",
            )

        # Use provided recipients or fall back to defaults
        email_recipients = recipients or self.settings.default_email_recipients
        if not email_recipients:
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=False,
                error="No email recipients configured or provided",
            )

        try:
            # Build email content
            subject = self._build_email_subject(alert)
            html_body = self._build_email_body(alert)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.settings.smtp_from_address or ""
            msg["To"] = ", ".join(email_recipients)

            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))

            # Send email (run in thread pool to not block async)
            await asyncio.get_event_loop().run_in_executor(
                None, self._send_email_sync, msg, email_recipients
            )

            logger.info(
                f"Email notification sent for alert {alert.id} to {len(email_recipients)} recipients"
            )
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.utcnow(),
                recipient=", ".join(email_recipients),
            )

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {e}"
            logger.error(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=error_msg,
            )
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Email delivery failed: {e}"
            logger.exception(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=False,
                error=error_msg,
            )

    def _send_email_sync(self, msg: MIMEMultipart, recipients: list[str]) -> None:
        """Synchronous email sending (runs in thread pool).

        Args:
            msg: Email message to send
            recipients: List of recipient email addresses
        """
        if self.settings.smtp_use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.settings.smtp_host or "", self.settings.smtp_port) as server:
                server.starttls(context=context)
                if self.settings.smtp_user and self.settings.smtp_password:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.sendmail(
                    self.settings.smtp_from_address or "",
                    recipients,
                    msg.as_string(),
                )
        else:
            with smtplib.SMTP(self.settings.smtp_host or "", self.settings.smtp_port) as server:
                if self.settings.smtp_user and self.settings.smtp_password:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.sendmail(
                    self.settings.smtp_from_address or "",
                    recipients,
                    msg.as_string(),
                )

    def _build_email_subject(self, alert: Alert) -> str:
        """Build email subject line for an alert.

        Args:
            alert: The alert to build subject for

        Returns:
            Email subject string
        """
        severity = alert.severity.value.upper()
        return f"[{severity}] Security Alert - Home Security Intelligence"

    def _build_email_body(self, alert: Alert) -> str:
        """Build HTML email body for an alert.

        Args:
            alert: The alert to build body for

        Returns:
            HTML string for email body
        """
        metadata = alert.alert_metadata or {}
        rule_name = metadata.get("rule_name", "Unknown Rule")
        matched_conditions = metadata.get("matched_conditions", [])

        conditions_html = ""
        if matched_conditions:
            conditions_html = (
                "<ul>" + "".join(f"<li>{cond}</li>" for cond in matched_conditions) + "</ul>"
            )
        else:
            conditions_html = "<p>No specific conditions recorded.</p>"

        severity_colors = {
            "low": "#28a745",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545",
        }
        severity_color = severity_colors.get(alert.severity.value, "#6c757d")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        .header {{ background-color: {severity_color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ margin-bottom: 15px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>Security Alert: {alert.severity.value.upper()}</h2>
    </div>
    <div class="content">
        <p class="label">Alert ID:</p>
        <p class="value">{alert.id}</p>

        <p class="label">Rule:</p>
        <p class="value">{rule_name}</p>

        <p class="label">Event ID:</p>
        <p class="value">{alert.event_id}</p>

        <p class="label">Status:</p>
        <p class="value">{alert.status.value}</p>

        <p class="label">Created:</p>
        <p class="value">{alert.created_at.isoformat() if alert.created_at else "Unknown"}</p>

        <p class="label">Matched Conditions:</p>
        {conditions_html}

        <div class="footer">
            <p>This is an automated message from Home Security Intelligence.</p>
        </div>
    </div>
</body>
</html>
"""

    async def send_webhook(
        self,
        alert: Alert,
        webhook_url: str | None = None,
    ) -> NotificationDelivery:
        """Send an alert notification via webhook (HTTP POST).

        Args:
            alert: The alert to send
            webhook_url: Optional webhook URL (defaults to settings)

        Returns:
            NotificationDelivery with success/failure status
        """
        url = webhook_url or self.settings.default_webhook_url
        if not url:
            return NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error="No webhook URL configured or provided",
            )

        try:
            # Build webhook payload
            payload = self._build_webhook_payload(alert)

            # Send HTTP POST
            client = await self._get_http_client()
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code >= 200 and response.status_code < 300:
                # Log without user-controlled data to avoid log injection (CodeQL py/log-injection)
                logger.info("Webhook notification sent successfully for alert %s", alert.id)
                return NotificationDelivery(
                    channel=NotificationChannel.WEBHOOK,
                    success=True,
                    delivered_at=datetime.utcnow(),
                    recipient=url,
                )
            else:
                # Log status code only to avoid log injection from response body
                logger.warning("Webhook returned error status %s", response.status_code)
                error_msg = f"Webhook returned status {response.status_code}: {response.text[:200]}"
                return NotificationDelivery(
                    channel=NotificationChannel.WEBHOOK,
                    success=False,
                    error=error_msg,
                    recipient=url,
                )

        except httpx.TimeoutException:
            error_msg = f"Webhook request timed out after {self.settings.webhook_timeout_seconds}s"
            logger.error(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error=error_msg,
                recipient=url,
            )
        except httpx.RequestError as e:
            error_msg = f"Webhook request failed: {e}"
            logger.error(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error=error_msg,
                recipient=url,
            )
        except Exception as e:
            error_msg = f"Webhook delivery failed: {e}"
            logger.exception(error_msg)
            return NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error=error_msg,
                recipient=url,
            )

    def _build_webhook_payload(self, alert: Alert) -> dict:
        """Build JSON payload for webhook notification.

        Args:
            alert: The alert to build payload for

        Returns:
            Dictionary payload for JSON serialization
        """
        metadata = alert.alert_metadata or {}
        return {
            "type": "security_alert",
            "alert": {
                "id": alert.id,
                "event_id": alert.event_id,
                "rule_id": alert.rule_id,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "dedup_key": alert.dedup_key,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
                "channels": alert.channels or [],
            },
            "metadata": {
                "rule_name": metadata.get("rule_name"),
                "matched_conditions": metadata.get("matched_conditions", []),
            },
            "source": "home_security_intelligence",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def send_push(
        self,
        alert: Alert,
        device_tokens: list[str] | None = None,  # noqa: ARG002
    ) -> NotificationDelivery:
        """Send an alert notification via push notification (stubbed).

        This method is a placeholder for future push notification support.
        Currently returns a failure indicating push is not implemented.

        Args:
            alert: The alert to send
            device_tokens: Optional list of device tokens to notify (unused, for future use)

        Returns:
            NotificationDelivery with failure status (not implemented)
        """
        logger.debug(f"Push notification requested for alert {alert.id} (not implemented)")
        return NotificationDelivery(
            channel=NotificationChannel.PUSH,
            success=False,
            error="Push notifications are not yet implemented",
        )

    def _resolve_channels(
        self, alert: Alert, channels: list[NotificationChannel] | None
    ) -> list[NotificationChannel]:
        """Resolve which channels to use for delivery.

        Args:
            alert: The alert being delivered
            channels: Explicitly specified channels, or None for auto-detection

        Returns:
            List of channels to use
        """
        if channels is not None:
            return channels

        # Try to use channels from alert configuration
        alert_channels = alert.channels or []
        if alert_channels:
            resolved = []
            for ch in alert_channels:
                try:
                    resolved.append(NotificationChannel(ch.lower()))
                except ValueError:
                    logger.warning(f"Unknown notification channel: {ch}")
            return resolved

        # Fall back to all available configured channels
        return self.get_available_channels()

    async def _send_to_channel(
        self,
        channel: NotificationChannel,
        alert: Alert,
        email_recipients: list[str] | None,
        webhook_url: str | None,
    ) -> NotificationDelivery:
        """Send to a specific channel.

        Args:
            channel: The channel to send to
            alert: The alert to send
            email_recipients: Email recipients for email channel
            webhook_url: Webhook URL for webhook channel

        Returns:
            NotificationDelivery result
        """
        channel_handlers = {
            NotificationChannel.EMAIL: lambda: self.send_email(alert, email_recipients),
            NotificationChannel.WEBHOOK: lambda: self.send_webhook(alert, webhook_url),
            NotificationChannel.PUSH: lambda: self.send_push(alert),
        }

        handler = channel_handlers.get(channel)
        if handler:
            return await handler()

        return NotificationDelivery(
            channel=channel,
            success=False,
            error=f"Unknown channel: {channel}",
        )

    async def deliver_alert(
        self,
        alert: Alert,
        channels: list[NotificationChannel] | None = None,
        email_recipients: list[str] | None = None,
        webhook_url: str | None = None,
    ) -> DeliveryResult:
        """Deliver an alert through multiple notification channels.

        This is the main entry point for sending notifications. It will
        attempt delivery through all specified channels and collect results.

        Args:
            alert: The alert to deliver
            channels: List of channels to use (defaults to all configured)
            email_recipients: Optional email recipients (for email channel)
            webhook_url: Optional webhook URL (for webhook channel)

        Returns:
            DeliveryResult with all delivery attempts and their outcomes
        """
        if not self.settings.notification_enabled:
            logger.info(f"Notifications disabled, skipping delivery for alert {alert.id}")
            return DeliveryResult(alert_id=alert.id, deliveries=[], all_successful=True)

        resolved_channels = self._resolve_channels(alert, channels)
        if not resolved_channels:
            logger.info(f"No notification channels configured for alert {alert.id}")
            return DeliveryResult(alert_id=alert.id, deliveries=[], all_successful=True)

        logger.info(
            f"Delivering alert {alert.id} via channels: {[c.value for c in resolved_channels]}"
        )

        # Deliver through each channel
        deliveries = [
            await self._send_to_channel(ch, alert, email_recipients, webhook_url)
            for ch in resolved_channels
        ]

        all_successful = all(d.success for d in deliveries)
        result = DeliveryResult(
            alert_id=alert.id, deliveries=deliveries, all_successful=all_successful
        )

        self._log_delivery_result(alert.id, deliveries, all_successful)
        return result

    def _log_delivery_result(
        self, alert_id: str, deliveries: list[NotificationDelivery], all_successful: bool
    ) -> None:
        """Log the delivery result."""
        if all_successful:
            logger.info(f"All {len(deliveries)} notifications delivered for alert {alert_id}")
        else:
            failed_count = sum(1 for d in deliveries if not d.success)
            logger.warning(
                f"{failed_count}/{len(deliveries)} notifications failed for alert {alert_id}"
            )


class _NotificationServiceSingleton:
    """Singleton holder for NotificationService instance."""

    _instance: NotificationService | None = None

    @classmethod
    def get(cls, settings: Settings) -> NotificationService:
        """Get or create a NotificationService instance.

        Args:
            settings: Application settings

        Returns:
            NotificationService instance
        """
        if cls._instance is None:
            cls._instance = NotificationService(settings)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_notification_service(settings: Settings) -> NotificationService:
    """Get or create a NotificationService instance.

    Args:
        settings: Application settings

    Returns:
        NotificationService instance
    """
    return _NotificationServiceSingleton.get(settings)


def reset_notification_service() -> None:
    """Reset the notification service singleton (for testing)."""
    _NotificationServiceSingleton.reset()
