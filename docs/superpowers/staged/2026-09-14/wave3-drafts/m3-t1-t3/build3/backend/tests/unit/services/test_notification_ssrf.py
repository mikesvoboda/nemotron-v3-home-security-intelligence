"""Unit tests for SSRF protection in notification service send_webhook method.

Tests cover:
- SSRF protection at the service layer before HTTP requests are made
- Private IP blocking (10.x, 172.16-31.x, 192.168.x, 127.x)
- Cloud metadata endpoint blocking (169.254.169.254)
- Scheme validation (HTTPS required except localhost in dev)
- DNS resolution validation
- Integration with existing url_validation module

NEM-1615: Add SSRF protection for webhook URLs in notification service
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.url_validation import SSRFValidationError
from backend.services.notification import (
    NotificationChannel,
    NotificationService,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_user = "user@example.com"
    settings.smtp_password = "test-password-for-testing"  # pragma: allowlist secret
    settings.smtp_from_address = "alerts@example.com"
    settings.smtp_use_tls = True
    settings.default_email_recipients = ["recipient@example.com"]
    settings.default_webhook_url = "https://example.com/webhook"
    settings.webhook_timeout_seconds = 30
    settings.is_development = False
    return settings


@pytest.fixture
def mock_settings_dev():
    """Create mock settings for development mode testing."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = None
    settings.smtp_port = 587
    settings.smtp_user = None
    settings.smtp_password = None
    settings.smtp_from_address = None
    settings.smtp_use_tls = True
    settings.default_email_recipients = []
    settings.default_webhook_url = "http://localhost:8000/webhook"
    settings.webhook_timeout_seconds = 30
    settings.is_development = True
    return settings


@pytest.fixture
def mock_alert():
    """Create a mock Alert for testing."""
    from backend.models import Alert, AlertSeverity, AlertStatus

    alert = MagicMock(spec=Alert)
    alert.id = "test-alert-id-123"
    alert.event_id = 42
    alert.rule_id = "test-rule-id-456"
    alert.severity = AlertSeverity.HIGH
    alert.status = AlertStatus.PENDING
    alert.dedup_key = "front_door:person:test"
    alert.created_at = datetime.now(UTC)
    alert.channels = ["webhook"]
    alert.alert_metadata = {
        "rule_name": "Test Rule",
        "matched_conditions": ["risk_score >= 70"],
    }
    return alert


@pytest.fixture
def service(mock_settings):
    """Create a NotificationService with mock settings."""
    return NotificationService(mock_settings)


@pytest.fixture
def service_dev(mock_settings_dev):
    """Create a NotificationService with development settings."""
    return NotificationService(mock_settings_dev)


class TestWebhookSSRFProtection:
    """Tests for SSRF protection in send_webhook method."""

    @pytest.mark.asyncio
    async def test_private_ip_10_blocked(self, service, mock_alert):
        """Test that 10.x.x.x private IPs are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://10.0.0.1/webhook")

        assert result.success is False
        assert result.channel == NotificationChannel.WEBHOOK
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_private_ip_172_blocked(self, service, mock_alert):
        """Test that 172.16-31.x.x private IPs are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://172.16.0.1/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_private_ip_192_blocked(self, service, mock_alert):
        """Test that 192.168.x.x private IPs are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://192.168.1.1/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_loopback_blocked_in_production(self, service, mock_alert):
        """Test that 127.x.x.x loopback is blocked in production."""
        result = await service.send_webhook(mock_alert, webhook_url="https://127.0.0.1/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_aws_metadata_ip_blocked(self, service, mock_alert):
        """Test that AWS metadata IP 169.254.169.254 is blocked."""
        result = await service.send_webhook(
            mock_alert, webhook_url="https://169.254.169.254/latest/meta-data/"
        )

        assert result.success is False
        assert (
            "blocked" in result.error.lower()
            or "metadata" in result.error.lower()
            or "private" in result.error.lower()
        )

    @pytest.mark.asyncio
    async def test_aws_ecs_metadata_blocked(self, service, mock_alert):
        """Test that AWS ECS metadata IP 169.254.170.2 is blocked."""
        result = await service.send_webhook(
            mock_alert, webhook_url="https://169.254.170.2/v3/metadata"
        )

        assert result.success is False
        # Link-local range (169.254.x.x) should be blocked
        assert (
            "blocked" in result.error.lower()
            or "private" in result.error.lower()
            or "link-local" in result.error.lower()
        )

    @pytest.mark.asyncio
    async def test_metadata_hostname_blocked(self, service, mock_alert):
        """Test that metadata hostnames are blocked."""
        result = await service.send_webhook(
            mock_alert, webhook_url="https://metadata.google.internal/v1/"
        )

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_http_blocked_for_external_in_production(self, service, mock_alert):
        """Test that HTTP is blocked for external URLs in production."""
        result = await service.send_webhook(mock_alert, webhook_url="http://example.com/webhook")

        assert result.success is False
        assert "https" in result.error.lower() or "scheme" in result.error.lower()

    @pytest.mark.asyncio
    async def test_embedded_credentials_blocked(self, service, mock_alert):
        """Test that URLs with embedded credentials are blocked."""
        result = await service.send_webhook(
            mock_alert,
            webhook_url="https://user:pass@example.com/webhook",  # pragma: allowlist secret
        )

        assert result.success is False
        assert "credentials" in result.error.lower()

    @pytest.mark.asyncio
    async def test_valid_https_url_allowed(self, service, mock_alert):
        """Test that valid HTTPS external URLs are allowed."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(service, "_get_http_client", return_value=mock_client),
            patch(
                "backend.services.notification.validate_webhook_url_for_request"
            ) as mock_validate,
        ):
            mock_validate.return_value = "https://hooks.slack.com/services/T123/B456"

            result = await service.send_webhook(
                mock_alert, webhook_url="https://hooks.slack.com/services/T123/B456"
            )

            assert result.success is True
            assert result.channel == NotificationChannel.WEBHOOK


class TestWebhookSSRFDevelopmentMode:
    """Tests for SSRF protection with development mode settings."""

    @pytest.mark.asyncio
    async def test_localhost_http_allowed_in_dev(self, service_dev, mock_alert):
        """Test that localhost HTTP is allowed in development mode."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(service_dev, "_get_http_client", return_value=mock_client),
            patch(
                "backend.services.notification.validate_webhook_url_for_request"
            ) as mock_validate,
        ):
            mock_validate.return_value = "http://localhost:8000/webhook"

            result = await service_dev.send_webhook(
                mock_alert, webhook_url="http://localhost:8000/webhook"
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_127_http_allowed_in_dev(self, service_dev, mock_alert):
        """Test that 127.0.0.1 HTTP is allowed in development mode."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with (
            patch.object(service_dev, "_get_http_client", return_value=mock_client),
            patch(
                "backend.services.notification.validate_webhook_url_for_request"
            ) as mock_validate,
        ):
            mock_validate.return_value = "http://127.0.0.1:8000/webhook"

            result = await service_dev.send_webhook(
                mock_alert, webhook_url="http://127.0.0.1:8000/webhook"
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_private_ip_still_blocked_in_dev(self, service_dev, mock_alert):
        """Test that private IPs (non-localhost) are still blocked in dev."""
        result = await service_dev.send_webhook(
            mock_alert, webhook_url="http://192.168.1.1/webhook"
        )

        assert result.success is False
        # Private IP or HTTP for non-localhost should be blocked
        assert (
            "private" in result.error.lower()
            or "localhost" in result.error.lower()
            or "https" in result.error.lower()
        )


class TestWebhookSSRFDNSRebinding:
    """Tests for DNS rebinding protection."""

    @pytest.mark.asyncio
    async def test_dns_resolving_to_private_ip_blocked(self, service, mock_alert):
        """Test that hostnames resolving to private IPs are blocked."""
        # This tests the DNS rebinding attack scenario
        with patch(
            "backend.services.notification.validate_webhook_url_for_request"
        ) as mock_validate:
            mock_validate.side_effect = SSRFValidationError(
                "Hostname 'evil.com' resolves to private IP: 10.0.0.1"
            )

            result = await service.send_webhook(mock_alert, webhook_url="https://evil.com/webhook")

            assert result.success is False
            assert "private" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dns_resolving_to_metadata_ip_blocked(self, service, mock_alert):
        """Test that hostnames resolving to metadata IPs are blocked."""
        with patch(
            "backend.services.notification.validate_webhook_url_for_request"
        ) as mock_validate:
            mock_validate.side_effect = SSRFValidationError(
                "Hostname 'evil.com' resolves to blocked IP: 169.254.169.254"
            )

            result = await service.send_webhook(mock_alert, webhook_url="https://evil.com/webhook")

            assert result.success is False


class TestWebhookSSRFEdgeCases:
    """Tests for SSRF protection edge cases."""

    @pytest.mark.asyncio
    async def test_empty_webhook_url_returns_not_configured(self, mock_settings, mock_alert):
        """Test that empty webhook URL returns not configured error."""
        mock_settings.default_webhook_url = None
        service = NotificationService(mock_settings)

        result = await service.send_webhook(mock_alert, webhook_url=None)

        assert result.success is False
        assert "not configured" in result.error.lower() or "no webhook" in result.error.lower()

    @pytest.mark.asyncio
    async def test_carrier_grade_nat_blocked(self, service, mock_alert):
        """Test that carrier-grade NAT addresses (100.64.x.x) are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://100.64.0.1/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ipv6_loopback_blocked(self, service, mock_alert):
        """Test that IPv6 loopback is blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://[::1]/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ipv6_link_local_blocked(self, service, mock_alert):
        """Test that IPv6 link-local addresses are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="https://[fe80::1]/webhook")

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ftp_scheme_blocked(self, service, mock_alert):
        """Test that non-HTTP schemes are blocked."""
        result = await service.send_webhook(mock_alert, webhook_url="ftp://example.com/file")

        assert result.success is False
        assert "scheme" in result.error.lower()


class TestWebhookSSRFValidationIntegration:
    """Integration tests for SSRF validation with the full URL validation module."""

    @pytest.mark.asyncio
    async def test_validation_called_before_http_request(self, service, mock_alert):
        """Test that URL validation is called before making HTTP request."""
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=200, text="OK")

        with (
            patch.object(service, "_get_http_client", return_value=mock_client),
            patch(
                "backend.services.notification.validate_webhook_url_for_request"
            ) as mock_validate,
        ):
            mock_validate.return_value = "https://example.com/webhook"

            await service.send_webhook(mock_alert, webhook_url="https://example.com/webhook")

            # Validate should be called before HTTP client
            mock_validate.assert_called_once()
            # HTTP client should be called after validation
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_failure_prevents_http_request(self, service, mock_alert):
        """Test that validation failure prevents HTTP request from being made."""
        mock_client = AsyncMock()

        with patch.object(service, "_get_http_client", return_value=mock_client):
            # Use a private IP URL that should be blocked
            result = await service.send_webhook(mock_alert, webhook_url="https://10.0.0.1/webhook")

            assert result.success is False
            # HTTP client should NOT be called when validation fails
            mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_webhook_url_validated(self, service, mock_alert):
        """Test that the default webhook URL from settings is also validated."""
        # Modify service settings to have a private IP default
        service.settings.default_webhook_url = "https://10.0.0.1/webhook"

        result = await service.send_webhook(mock_alert, webhook_url=None)

        assert result.success is False
        assert "private" in result.error.lower() or "reserved" in result.error.lower()
