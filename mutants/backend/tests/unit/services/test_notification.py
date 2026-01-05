"""Unit tests for notification service.

Tests cover:
- NotificationChannel enum
- NotificationDelivery and DeliveryResult dataclasses
- NotificationService configuration checks
- Email sending (with mocked SMTP)
- Webhook sending (with mocked HTTP client)
- Push notification stub behavior
- Multi-channel delivery
- Notification disabled behavior
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Alert, AlertSeverity, AlertStatus
from backend.services.notification import (
    DeliveryResult,
    NotificationChannel,
    NotificationDelivery,
    NotificationService,
    get_notification_service,
    reset_notification_service,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_user = "user@example.com"
    settings.smtp_password = "test-password-for-testing"  # noqa: S105
    settings.smtp_from_address = "alerts@example.com"
    settings.smtp_use_tls = True
    settings.default_email_recipients = ["recipient@example.com"]
    settings.default_webhook_url = "https://example.com/webhook"
    settings.webhook_timeout_seconds = 30
    return settings


@pytest.fixture
def mock_settings_minimal():
    """Create mock settings with minimal configuration (no email/webhook)."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = None
    settings.smtp_port = 587
    settings.smtp_user = None
    settings.smtp_password = None
    settings.smtp_from_address = None
    settings.smtp_use_tls = True
    settings.default_email_recipients = []
    settings.default_webhook_url = None
    settings.webhook_timeout_seconds = 30
    return settings


@pytest.fixture
def mock_settings_disabled():
    """Create mock settings with notifications disabled."""
    settings = MagicMock()
    settings.notification_enabled = False
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_user = "user@example.com"
    settings.smtp_password = "test-password-for-testing"  # noqa: S105
    settings.smtp_from_address = "alerts@example.com"
    settings.smtp_use_tls = True
    settings.default_email_recipients = ["recipient@example.com"]
    settings.default_webhook_url = "https://example.com/webhook"
    settings.webhook_timeout_seconds = 30
    return settings


@pytest.fixture
def mock_alert():
    """Create a mock Alert for testing."""
    alert = MagicMock(spec=Alert)
    alert.id = "test-alert-id-123"
    alert.event_id = 42
    alert.rule_id = "test-rule-id-456"
    alert.severity = AlertSeverity.HIGH
    alert.status = AlertStatus.PENDING
    alert.dedup_key = "front_door:person:test"
    alert.created_at = datetime.now(UTC)
    alert.channels = ["email", "webhook"]
    alert.alert_metadata = {
        "rule_name": "Test Rule",
        "matched_conditions": ["risk_score >= 70", "object_type = person"],
    }
    return alert


@pytest.fixture
def service(mock_settings):
    """Create a NotificationService with mock settings."""
    return NotificationService(mock_settings)


@pytest.fixture
def service_minimal(mock_settings_minimal):
    """Create a NotificationService with minimal settings."""
    return NotificationService(mock_settings_minimal)


@pytest.fixture
def service_disabled(mock_settings_disabled):
    """Create a NotificationService with notifications disabled."""
    return NotificationService(mock_settings_disabled)


class TestNotificationChannel:
    """Tests for NotificationChannel enum."""

    def test_channel_values(self):
        """Test that channel values are correct strings."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.PUSH.value == "push"

    def test_channel_is_string_enum(self):
        """Test that channels can be compared to strings."""
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.WEBHOOK == "webhook"
        assert NotificationChannel.PUSH == "push"


class TestNotificationDelivery:
    """Tests for NotificationDelivery dataclass."""

    def test_successful_delivery(self):
        """Test creating a successful delivery record."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="user@example.com",
        )
        assert delivery.success is True
        assert delivery.error is None
        assert delivery.channel == NotificationChannel.EMAIL

    def test_failed_delivery(self):
        """Test creating a failed delivery record."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=False,
            error="Connection refused",
        )
        assert delivery.success is False
        assert delivery.error == "Connection refused"
        assert delivery.delivered_at is None

    def test_to_dict(self):
        """Test converting delivery to dictionary."""
        now = datetime.now(UTC)
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=now,
            recipient="user@example.com",
        )
        result = delivery.to_dict()
        assert result["channel"] == "email"
        assert result["success"] is True
        assert result["delivered_at"] == now.isoformat()
        assert result["recipient"] == "user@example.com"
        assert result["error"] is None


class TestDeliveryResult:
    """Tests for DeliveryResult dataclass."""

    def test_empty_result(self):
        """Test empty delivery result."""
        result = DeliveryResult(alert_id="test-123")
        assert result.successful_count == 0
        assert result.failed_count == 0
        assert result.all_successful is False

    def test_all_successful(self):
        """Test result with all successful deliveries."""
        deliveries = [
            NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
            ),
            NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=True,
            ),
        ]
        result = DeliveryResult(
            alert_id="test-123",
            deliveries=deliveries,
            all_successful=True,
        )
        assert result.successful_count == 2
        assert result.failed_count == 0
        assert result.all_successful is True

    def test_partial_success(self):
        """Test result with mixed success/failure."""
        deliveries = [
            NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
            ),
            NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error="Timeout",
            ),
        ]
        result = DeliveryResult(
            alert_id="test-123",
            deliveries=deliveries,
            all_successful=False,
        )
        assert result.successful_count == 1
        assert result.failed_count == 1

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = DeliveryResult(
            alert_id="test-123",
            deliveries=[
                NotificationDelivery(
                    channel=NotificationChannel.EMAIL,
                    success=True,
                )
            ],
            all_successful=True,
        )
        dict_result = result.to_dict()
        assert dict_result["alert_id"] == "test-123"
        assert dict_result["all_successful"] is True
        assert dict_result["successful_count"] == 1
        assert dict_result["failed_count"] == 0
        assert len(dict_result["deliveries"]) == 1


class TestNotificationServiceConfiguration:
    """Tests for NotificationService configuration checks."""

    def test_is_email_configured(self, service):
        """Test email configuration detection."""
        assert service.is_email_configured() is True

    def test_is_email_not_configured(self, service_minimal):
        """Test email not configured when missing settings."""
        assert service_minimal.is_email_configured() is False

    def test_is_webhook_configured(self, service):
        """Test webhook configuration detection."""
        assert service.is_webhook_configured() is True

    def test_is_webhook_not_configured(self, service_minimal):
        """Test webhook not configured when missing settings."""
        assert service_minimal.is_webhook_configured() is False

    def test_is_push_configured(self, service):
        """Test push is never configured (stubbed)."""
        assert service.is_push_configured() is False

    def test_get_available_channels(self, service):
        """Test getting available channels with full config."""
        channels = service.get_available_channels()
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.WEBHOOK in channels
        assert NotificationChannel.PUSH not in channels

    def test_get_available_channels_minimal(self, service_minimal):
        """Test getting available channels with minimal config."""
        channels = service_minimal.get_available_channels()
        assert len(channels) == 0


class TestNotificationServiceEmail:
    """Tests for email notification sending."""

    @pytest.mark.asyncio
    async def test_send_email_success(self, service, mock_alert):
        """Test successful email sending."""
        with patch.object(service, "_send_email_sync") as mock_send:
            mock_send.return_value = None

            result = await service.send_email(mock_alert)

            assert result.success is True
            assert result.channel == NotificationChannel.EMAIL
            assert result.delivered_at is not None
            assert "recipient@example.com" in result.recipient

    @pytest.mark.asyncio
    async def test_send_email_not_configured(self, service_minimal, mock_alert):
        """Test email failure when not configured."""
        result = await service_minimal.send_email(mock_alert)

        assert result.success is False
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_no_recipients(self, mock_settings, mock_alert):
        """Test email failure when no recipients provided."""
        mock_settings.default_email_recipients = []
        service = NotificationService(mock_settings)

        result = await service.send_email(mock_alert)

        assert result.success is False
        assert "recipients" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_custom_recipients(self, service, mock_alert):
        """Test email with custom recipients."""
        with patch.object(service, "_send_email_sync") as mock_send:
            mock_send.return_value = None

            result = await service.send_email(
                mock_alert, recipients=["custom@example.com", "other@example.com"]
            )

            assert result.success is True
            assert "custom@example.com" in result.recipient
            assert "other@example.com" in result.recipient

    @pytest.mark.asyncio
    async def test_send_email_smtp_error(self, service, mock_alert):
        """Test email failure on SMTP error."""
        import smtplib

        with patch.object(service, "_send_email_sync") as mock_send:
            mock_send.side_effect = smtplib.SMTPException("Connection failed")

            result = await service.send_email(mock_alert)

            assert result.success is False
            assert "SMTP error" in result.error

    def test_build_email_subject(self, service, mock_alert):
        """Test email subject building."""
        subject = service._build_email_subject(mock_alert)
        assert "[HIGH]" in subject
        assert "Security Alert" in subject

    def test_build_email_body(self, service, mock_alert):
        """Test email body building."""
        body = service._build_email_body(mock_alert)
        assert "test-alert-id-123" in body
        assert "Test Rule" in body
        assert "risk_score" in body


class TestNotificationServiceWebhook:
    """Tests for webhook notification sending."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self, service, mock_alert):
        """Test successful webhook sending."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(mock_alert)

            assert result.success is True
            assert result.channel == NotificationChannel.WEBHOOK
            assert result.delivered_at is not None

    @pytest.mark.asyncio
    async def test_send_webhook_not_configured(self, service_minimal, mock_alert):
        """Test webhook failure when not configured."""
        result = await service_minimal.send_webhook(mock_alert)

        assert result.success is False
        assert "not configured" in result.error.lower() or "no webhook" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_webhook_custom_url(self, service, mock_alert):
        """Test webhook with custom URL."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(
                mock_alert, webhook_url="https://custom.example.com/hook"
            )

            assert result.success is True
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://custom.example.com/hook"

    @pytest.mark.asyncio
    async def test_send_webhook_http_error(self, service, mock_alert):
        """Test webhook failure on HTTP error status."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(mock_alert)

            assert result.success is False
            assert "500" in result.error

    @pytest.mark.asyncio
    async def test_send_webhook_timeout(self, service, mock_alert):
        """Test webhook failure on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(mock_alert)

            assert result.success is False
            assert "timed out" in result.error.lower()

    def test_build_webhook_payload(self, service, mock_alert):
        """Test webhook payload building."""
        payload = service._build_webhook_payload(mock_alert)

        assert payload["type"] == "security_alert"
        assert payload["alert"]["id"] == "test-alert-id-123"
        assert payload["alert"]["severity"] == "high"
        assert payload["metadata"]["rule_name"] == "Test Rule"
        assert payload["source"] == "home_security_intelligence"


class TestNotificationServicePush:
    """Tests for push notification (stubbed)."""

    @pytest.mark.asyncio
    async def test_send_push_not_implemented(self, service, mock_alert):
        """Test push returns not implemented error."""
        result = await service.send_push(mock_alert)

        assert result.success is False
        assert result.channel == NotificationChannel.PUSH
        assert "not yet implemented" in result.error.lower()


class TestNotificationServiceDeliverAlert:
    """Tests for multi-channel alert delivery."""

    @pytest.mark.asyncio
    async def test_deliver_alert_disabled(self, service_disabled, mock_alert):
        """Test delivery skipped when notifications disabled."""
        result = await service_disabled.deliver_alert(mock_alert)

        assert result.all_successful is True
        assert len(result.deliveries) == 0

    @pytest.mark.asyncio
    async def test_deliver_alert_all_channels(self, service, mock_alert):
        """Test delivery through all configured channels."""
        with (
            patch.object(service, "send_email") as mock_email,
            patch.object(service, "send_webhook") as mock_webhook,
        ):
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.now(UTC),
            )
            mock_webhook.return_value = NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=True,
                delivered_at=datetime.now(UTC),
            )

            result = await service.deliver_alert(mock_alert)

            assert result.all_successful is True
            assert len(result.deliveries) == 2
            mock_email.assert_called_once()
            mock_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_alert_specific_channels(self, service, mock_alert):
        """Test delivery to specific channels only."""
        with patch.object(service, "send_email") as mock_email:
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.now(UTC),
            )

            result = await service.deliver_alert(mock_alert, channels=[NotificationChannel.EMAIL])

            assert len(result.deliveries) == 1
            assert result.deliveries[0].channel == NotificationChannel.EMAIL
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_alert_from_alert_channels(self, service, mock_alert):
        """Test delivery uses alert's configured channels."""
        mock_alert.channels = ["email"]  # Only email configured on alert

        with patch.object(service, "send_email") as mock_email:
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.now(UTC),
            )

            result = await service.deliver_alert(mock_alert)

            assert len(result.deliveries) == 1
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_alert_partial_failure(self, service, mock_alert):
        """Test delivery with one channel failing."""
        with (
            patch.object(service, "send_email") as mock_email,
            patch.object(service, "send_webhook") as mock_webhook,
        ):
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.now(UTC),
            )
            mock_webhook.return_value = NotificationDelivery(
                channel=NotificationChannel.WEBHOOK,
                success=False,
                error="Connection refused",
            )

            result = await service.deliver_alert(mock_alert)

            assert result.all_successful is False
            assert result.successful_count == 1
            assert result.failed_count == 1

    @pytest.mark.asyncio
    async def test_deliver_alert_no_channels(self, service_minimal, mock_alert):
        """Test delivery when no channels are available."""
        mock_alert.channels = []

        result = await service_minimal.deliver_alert(mock_alert)

        assert result.all_successful is True
        assert len(result.deliveries) == 0


class TestNotificationServiceModule:
    """Tests for module-level functions."""

    def test_get_notification_service(self, mock_settings):
        """Test getting notification service singleton."""
        reset_notification_service()

        service1 = get_notification_service(mock_settings)
        service2 = get_notification_service(mock_settings)

        assert service1 is service2
        reset_notification_service()

    def test_reset_notification_service(self, mock_settings):
        """Test resetting notification service singleton."""
        reset_notification_service()

        service1 = get_notification_service(mock_settings)
        reset_notification_service()
        service2 = get_notification_service(mock_settings)

        assert service1 is not service2
        reset_notification_service()


class TestNotificationServiceCleanup:
    """Tests for service cleanup."""

    @pytest.mark.asyncio
    async def test_close_with_no_client(self, service):
        """Test close when no HTTP client was created."""
        # Should not raise
        await service.close()

    @pytest.mark.asyncio
    async def test_close_with_client(self, service, mock_alert):
        """Test close after HTTP client was used."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Use the service to create HTTP client
            await service.send_webhook(mock_alert)

            # Now close should work
            await service.close()


class TestNotificationServiceEmailErrors:
    """Tests for email sending error paths (coverage for lines 222-245, 254-269)."""

    @pytest.mark.asyncio
    async def test_send_email_smtp_authentication_error(self, service, mock_alert):
        """Test email failure on SMTP authentication error (lines 222-229)."""
        import smtplib

        with patch.object(service, "_send_email_sync") as mock_send:
            mock_send.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

            result = await service.send_email(mock_alert)

            assert result.success is False
            assert result.channel == NotificationChannel.EMAIL
            assert "SMTP authentication failed" in result.error

    @pytest.mark.asyncio
    async def test_send_email_generic_exception(self, service, mock_alert):
        """Test email failure on generic exception (lines 238-245)."""
        with patch.object(service, "_send_email_sync") as mock_send:
            mock_send.side_effect = RuntimeError("Unexpected error occurred")

            result = await service.send_email(mock_alert)

            assert result.success is False
            assert result.channel == NotificationChannel.EMAIL
            assert "Email delivery failed" in result.error
            assert "Unexpected error occurred" in result.error

    def test_send_email_sync_with_tls(self, mock_settings, mock_alert):
        """Test synchronous email sending with TLS enabled (lines 254-264)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        mock_settings.smtp_use_tls = True
        service = NotificationService(mock_settings)

        # Create a test message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Test"
        msg["From"] = mock_settings.smtp_from_address
        msg["To"] = "test@example.com"
        msg.attach(MIMEText("<p>Test</p>", "html"))

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            service._send_email_sync(msg, ["test@example.com"])

            mock_smtp_class.assert_called_once_with(
                mock_settings.smtp_host, mock_settings.smtp_port
            )
            mock_smtp_instance.starttls.assert_called_once()
            mock_smtp_instance.login.assert_called_once_with(
                mock_settings.smtp_user, mock_settings.smtp_password
            )
            mock_smtp_instance.sendmail.assert_called_once()

    def test_send_email_sync_without_tls(self, mock_settings, mock_alert):
        """Test synchronous email sending without TLS (lines 265-273)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        mock_settings.smtp_use_tls = False
        service = NotificationService(mock_settings)

        # Create a test message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Test"
        msg["From"] = mock_settings.smtp_from_address
        msg["To"] = "test@example.com"
        msg.attach(MIMEText("<p>Test</p>", "html"))

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            service._send_email_sync(msg, ["test@example.com"])

            mock_smtp_class.assert_called_once_with(
                mock_settings.smtp_host, mock_settings.smtp_port
            )
            # TLS should NOT be called
            mock_smtp_instance.starttls.assert_not_called()
            mock_smtp_instance.login.assert_called_once()
            mock_smtp_instance.sendmail.assert_called_once()

    def test_send_email_sync_without_auth(self, mock_settings, mock_alert):
        """Test synchronous email sending without authentication credentials."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        mock_settings.smtp_use_tls = False
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        service = NotificationService(mock_settings)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Test"
        msg["From"] = mock_settings.smtp_from_address
        msg["To"] = "test@example.com"
        msg.attach(MIMEText("<p>Test</p>", "html"))

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_instance = MagicMock()
            mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
            mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

            service._send_email_sync(msg, ["test@example.com"])

            # Login should NOT be called when no credentials
            mock_smtp_instance.login.assert_not_called()
            mock_smtp_instance.sendmail.assert_called_once()


class TestNotificationServiceWebhookErrors:
    """Tests for webhook sending error paths (coverage for lines 423-440)."""

    @pytest.mark.asyncio
    async def test_send_webhook_request_error(self, service, mock_alert):
        """Test webhook failure on httpx.RequestError (lines 423-431)."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(mock_alert)

            assert result.success is False
            assert result.channel == NotificationChannel.WEBHOOK
            assert "Webhook request failed" in result.error
            assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_send_webhook_generic_exception(self, service, mock_alert):
        """Test webhook failure on generic exception (lines 432-440)."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = RuntimeError("Unexpected network error")

        with patch.object(service, "_get_http_client", return_value=mock_client):
            result = await service.send_webhook(mock_alert)

            assert result.success is False
            assert result.channel == NotificationChannel.WEBHOOK
            assert "Webhook delivery failed" in result.error
            assert "Unexpected network error" in result.error


class TestNotificationServiceEdgeCases:
    """Tests for edge cases and configuration scenarios."""

    def test_build_email_body_no_matched_conditions(self, service, mock_alert):
        """Test email body with no matched conditions (line 306)."""
        mock_alert.alert_metadata = {"rule_name": "Test Rule", "matched_conditions": []}

        body = service._build_email_body(mock_alert)

        assert "No specific conditions recorded." in body

    def test_build_email_body_none_metadata(self, service, mock_alert):
        """Test email body with None metadata."""
        mock_alert.alert_metadata = None

        body = service._build_email_body(mock_alert)

        assert "No specific conditions recorded." in body
        assert "Unknown Rule" in body

    @pytest.mark.asyncio
    async def test_resolve_channels_with_unknown_channel(self, service, mock_alert):
        """Test channel resolution with unknown channel name (lines 518-519)."""
        mock_alert.channels = ["email", "unknown_channel", "webhook"]

        # Use the _resolve_channels method directly
        resolved = service._resolve_channels(mock_alert, None)

        # Only valid channels should be resolved
        assert NotificationChannel.EMAIL in resolved
        assert NotificationChannel.WEBHOOK in resolved
        assert len(resolved) == 2  # unknown_channel should be filtered out

    @pytest.mark.asyncio
    async def test_send_to_unknown_channel(self, service, mock_alert):
        """Test sending to unknown channel (line 553)."""
        # Create a mock channel that's not in the handlers
        # We need to test the fallback case in _send_to_channel
        # This is tricky because NotificationChannel is an enum
        # We can test by passing a value that won't match any handler

        # Create a custom channel value by subclassing
        class FakeChannel(str):
            value = "fake"

        fake_channel = FakeChannel("fake")

        result = await service._send_to_channel(
            fake_channel,  # type: ignore
            mock_alert,
            None,
            None,
        )

        assert result.success is False
        assert "Unknown channel" in result.error

    def test_get_available_channels_with_push_configured(self, mock_settings):
        """Test available channels when push would be configured (line 160)."""
        service = NotificationService(mock_settings)

        # Mock is_push_configured to return True to cover line 160
        with patch.object(service, "is_push_configured", return_value=True):
            channels = service.get_available_channels()

            assert NotificationChannel.PUSH in channels
            assert NotificationChannel.EMAIL in channels
            assert NotificationChannel.WEBHOOK in channels

    @pytest.mark.asyncio
    async def test_deliver_alert_with_invalid_alert_channels(self, service, mock_alert):
        """Test delivery when alert has invalid channel names."""
        mock_alert.channels = ["invalid1", "invalid2"]

        result = await service.deliver_alert(mock_alert)

        # With no valid channels, should succeed with empty deliveries
        assert result.all_successful is True
        assert len(result.deliveries) == 0

    @pytest.mark.asyncio
    async def test_deliver_alert_with_mixed_valid_invalid_channels(self, service, mock_alert):
        """Test delivery with mix of valid and invalid channel names."""
        mock_alert.channels = ["email", "invalid_channel"]

        with patch.object(service, "send_email") as mock_email:
            mock_email.return_value = NotificationDelivery(
                channel=NotificationChannel.EMAIL,
                success=True,
                delivered_at=datetime.now(UTC),
            )

            result = await service.deliver_alert(mock_alert)

            # Only email should be delivered (invalid_channel filtered out)
            assert len(result.deliveries) == 1
            assert result.deliveries[0].channel == NotificationChannel.EMAIL
            mock_email.assert_called_once()
