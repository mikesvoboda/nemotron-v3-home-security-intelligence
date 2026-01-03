"""Unit tests for webhook SSRF protection in notification schemas.

Tests cover:
- SendNotificationRequest webhook URL validation
- WebhookTestNotificationRequest webhook URL validation
- Schema-level SSRF blocking
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.notification import (
    NotificationChannel,
    SendNotificationRequest,
    WebhookTestNotificationRequest,
)


class TestSendNotificationRequestWebhookSSRF:
    """Tests for SSRF protection in SendNotificationRequest."""

    def test_valid_https_webhook_url(self):
        """Test that valid HTTPS webhook URLs are accepted."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="https://example.com/webhook",
        )
        assert request.webhook_url == "https://example.com/webhook"

    def test_valid_https_webhook_with_path(self):
        """Test that HTTPS URLs with paths are accepted."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="https://api.slack.com/hooks/T123/B456",
        )
        assert request.webhook_url == "https://api.slack.com/hooks/T123/B456"

    def test_null_webhook_url_allowed(self):
        """Test that null webhook URL is allowed."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url=None,
        )
        assert request.webhook_url is None

    def test_empty_webhook_url_becomes_none(self):
        """Test that empty string webhook URL becomes None."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="",
        )
        assert request.webhook_url is None

    def test_localhost_http_allowed_in_dev(self):
        """Test that localhost HTTP is allowed (dev mode)."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="http://localhost:8000/webhook",
        )
        assert request.webhook_url == "http://localhost:8000/webhook"

    def test_localhost_127_http_allowed(self):
        """Test that 127.0.0.1 HTTP is allowed (dev mode)."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="http://127.0.0.1:8000/webhook",
        )
        assert request.webhook_url == "http://127.0.0.1:8000/webhook"

    def test_external_http_blocked(self):
        """Test that external HTTP URLs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="http://example.com/webhook",
            )
        assert "localhost" in str(exc_info.value).lower()

    def test_private_ip_10_blocked(self):
        """Test that 10.x.x.x IPs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://10.0.0.1/webhook",
            )
        assert "private" in str(exc_info.value).lower() or "reserved" in str(exc_info.value).lower()

    def test_private_ip_172_blocked(self):
        """Test that 172.16-31.x.x IPs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://172.16.0.1/webhook",
            )
        assert "private" in str(exc_info.value).lower() or "reserved" in str(exc_info.value).lower()

    def test_private_ip_192_blocked(self):
        """Test that 192.168.x.x IPs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://192.168.1.1/webhook",
            )
        assert "private" in str(exc_info.value).lower() or "reserved" in str(exc_info.value).lower()

    def test_aws_metadata_ip_blocked(self):
        """Test that AWS metadata IP is blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://169.254.169.254/latest/meta-data/",
            )
        assert (
            "blocked" in str(exc_info.value).lower()
            or "metadata" in str(exc_info.value).lower()
            or "private" in str(exc_info.value).lower()
        )

    def test_metadata_hostname_blocked(self):
        """Test that metadata hostnames are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://metadata.google.internal/v1/",
            )
        assert "blocked" in str(exc_info.value).lower()

    def test_embedded_credentials_blocked(self):
        """Test that URLs with credentials are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://user:pass@example.com/webhook",
            )
        assert "credentials" in str(exc_info.value).lower()

    def test_ftp_scheme_blocked(self):
        """Test that non-HTTP schemes are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="ftp://example.com/file",
            )
        assert "scheme" in str(exc_info.value).lower()


class TestWebhookTestNotificationRequestSSRF:
    """Tests for SSRF protection in WebhookTestNotificationRequest."""

    def test_valid_https_webhook_url(self):
        """Test that valid HTTPS webhook URLs are accepted."""
        request = WebhookTestNotificationRequest(
            channel=NotificationChannel.WEBHOOK,
            webhook_url="https://example.com/test",
        )
        assert request.webhook_url == "https://example.com/test"

    def test_null_webhook_url_allowed(self):
        """Test that null webhook URL is allowed."""
        request = WebhookTestNotificationRequest(
            channel=NotificationChannel.EMAIL,
            webhook_url=None,
        )
        assert request.webhook_url is None

    def test_private_ip_blocked(self):
        """Test that private IPs are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookTestNotificationRequest(
                channel=NotificationChannel.WEBHOOK,
                webhook_url="https://10.0.0.1/test",
            )
        assert "private" in str(exc_info.value).lower() or "reserved" in str(exc_info.value).lower()

    def test_aws_metadata_blocked(self):
        """Test that AWS metadata is blocked."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookTestNotificationRequest(
                channel=NotificationChannel.WEBHOOK,
                webhook_url="https://169.254.169.254/",
            )
        assert (
            "blocked" in str(exc_info.value).lower()
            or "metadata" in str(exc_info.value).lower()
            or "private" in str(exc_info.value).lower()
        )

    def test_localhost_http_allowed(self):
        """Test that localhost HTTP is allowed for testing."""
        request = WebhookTestNotificationRequest(
            channel=NotificationChannel.WEBHOOK,
            webhook_url="http://localhost:8000/test",
        )
        assert request.webhook_url == "http://localhost:8000/test"


class TestNotificationSchemaEdgeCases:
    """Tests for edge cases in notification schema validation."""

    def test_ipv6_localhost_http_allowed(self):
        """Test that IPv6 localhost HTTP is allowed in dev mode."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="http://[::1]:8000/webhook",
        )
        assert request.webhook_url == "http://[::1]:8000/webhook"

    def test_link_local_blocked(self):
        """Test that link-local addresses are blocked."""
        with pytest.raises(ValidationError):
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://169.254.0.1/webhook",
            )

    def test_carrier_grade_nat_blocked(self):
        """Test that carrier-grade NAT addresses are blocked."""
        with pytest.raises(ValidationError):
            SendNotificationRequest(
                alert_id="test-alert-123",
                webhook_url="https://100.64.0.1/webhook",
            )

    def test_url_with_port_allowed(self):
        """Test that URLs with non-standard ports are allowed."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="https://example.com:8443/webhook",
        )
        assert ":8443" in request.webhook_url

    def test_url_with_query_params_allowed(self):
        """Test that URLs with query parameters are allowed."""
        request = SendNotificationRequest(
            alert_id="test-alert-123",
            webhook_url="https://example.com/webhook?token=abc&channel=test",
        )
        assert "token=abc" in request.webhook_url
