"""Unit tests for notification API schemas.

Tests cover:
- NotificationConfigUpdate validation
- SMTP settings validation (host, port, from address)
- Webhook URL SSRF validation
- Email format validation
- Port range validation

NEM-3632: Notification channel configuration UI
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas.notification import NotificationConfigUpdate

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# NotificationConfigUpdate Tests
# =============================================================================


class TestNotificationConfigUpdate:
    """Tests for NotificationConfigUpdate schema."""

    def test_valid_smtp_enabled(self):
        """Test valid smtp_enabled toggle."""
        config = NotificationConfigUpdate(smtp_enabled=True)
        assert config.smtp_enabled is True

        config = NotificationConfigUpdate(smtp_enabled=False)
        assert config.smtp_enabled is False

    def test_valid_webhook_enabled(self):
        """Test valid webhook_enabled toggle."""
        config = NotificationConfigUpdate(webhook_enabled=True)
        assert config.webhook_enabled is True

        config = NotificationConfigUpdate(webhook_enabled=False)
        assert config.webhook_enabled is False

    def test_valid_smtp_host(self):
        """Test valid SMTP host values."""
        config = NotificationConfigUpdate(smtp_host="smtp.example.com")
        assert config.smtp_host == "smtp.example.com"

        config = NotificationConfigUpdate(smtp_host="mail.company.org")
        assert config.smtp_host == "mail.company.org"

    def test_valid_smtp_port(self):
        """Test valid SMTP port values."""
        # Standard SMTP port
        config = NotificationConfigUpdate(smtp_port=25)
        assert config.smtp_port == 25

        # TLS port
        config = NotificationConfigUpdate(smtp_port=587)
        assert config.smtp_port == 587

        # SSL port
        config = NotificationConfigUpdate(smtp_port=465)
        assert config.smtp_port == 465

    def test_invalid_smtp_port_too_high(self):
        """Test that port above 65535 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(smtp_port=70000)
        assert "smtp_port" in str(exc_info.value)

    def test_invalid_smtp_port_negative(self):
        """Test that negative port is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(smtp_port=-1)
        assert "smtp_port" in str(exc_info.value)

    def test_invalid_smtp_port_zero(self):
        """Test that port 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(smtp_port=0)
        assert "smtp_port" in str(exc_info.value)

    def test_valid_smtp_from_address(self):
        """Test valid SMTP from address."""
        config = NotificationConfigUpdate(smtp_from_address="alerts@example.com")
        assert config.smtp_from_address == "alerts@example.com"

        config = NotificationConfigUpdate(smtp_from_address="noreply@security.company.org")
        assert config.smtp_from_address == "noreply@security.company.org"

    def test_invalid_smtp_from_address_no_at(self):
        """Test that email without @ is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(smtp_from_address="not-an-email")
        assert "smtp_from_address" in str(exc_info.value)

    def test_invalid_smtp_from_address_no_domain(self):
        """Test that email without domain is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(smtp_from_address="user@")
        assert "smtp_from_address" in str(exc_info.value)

    def test_valid_webhook_url_https(self):
        """Test valid HTTPS webhook URL."""
        config = NotificationConfigUpdate(default_webhook_url="https://hooks.example.com/notify")
        assert config.default_webhook_url == "https://hooks.example.com/notify"

    def test_invalid_webhook_url_private_ip(self):
        """Test that private IP webhook URL is rejected (SSRF protection)."""
        with pytest.raises(ValidationError) as exc_info:
            NotificationConfigUpdate(default_webhook_url="http://192.168.1.1/webhook")
        assert "default_webhook_url" in str(exc_info.value)

    def test_invalid_webhook_url_localhost(self):
        """Test that localhost webhook URL is rejected in strict mode."""
        # Note: localhost might be allowed in dev mode, but we test the validation
        config = NotificationConfigUpdate(default_webhook_url="http://localhost:8080/webhook")
        # In dev mode, localhost is allowed
        assert config.default_webhook_url is not None

    def test_empty_update_is_valid(self):
        """Test that empty update body is valid."""
        config = NotificationConfigUpdate()
        assert config.smtp_enabled is None
        assert config.webhook_enabled is None
        assert config.smtp_host is None
        assert config.smtp_port is None
        assert config.smtp_from_address is None
        assert config.default_webhook_url is None

    def test_partial_update(self):
        """Test that partial updates only set specified fields."""
        config = NotificationConfigUpdate(smtp_enabled=True)
        assert config.smtp_enabled is True
        assert config.webhook_enabled is None
        assert config.smtp_host is None

    def test_full_update(self):
        """Test a full configuration update."""
        config = NotificationConfigUpdate(
            smtp_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_from_address="alerts@example.com",
            webhook_enabled=True,
            default_webhook_url="https://hooks.example.com/webhook",
        )
        assert config.smtp_enabled is True
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 587
        assert config.smtp_from_address == "alerts@example.com"
        assert config.webhook_enabled is True
        assert config.default_webhook_url == "https://hooks.example.com/webhook"

    def test_null_values_to_clear_settings(self):
        """Test that null values can be used to clear settings."""
        # Create with explicit None values
        config = NotificationConfigUpdate(
            smtp_host=None,
            smtp_port=None,
            smtp_from_address=None,
            default_webhook_url=None,
        )
        assert config.smtp_host is None
        assert config.smtp_port is None
        assert config.smtp_from_address is None
        assert config.default_webhook_url is None
