"""Integration tests for Notification API endpoints.

Tests for /api/notification/* endpoints:
- GET /api/notification/config - get notification configuration
- POST /api/notification/test - test notification delivery

These tests use mocked notification services to avoid actual email/webhook delivery.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.notification import NotificationChannel
from backend.services.notification import (
    NotificationDelivery,
    NotificationService,
    reset_notification_service,
)

# Mark all tests in this module for integration
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_notification_singleton():
    """Reset the notification service singleton before and after each test."""
    reset_notification_service()
    yield
    reset_notification_service()


@pytest.fixture
async def notification_client(integration_db, mock_redis):
    """Async HTTP client with notification settings configured.

    This fixture creates an HTTP client with notification settings enabled
    and SMTP/webhook configured for testing.
    """
    from httpx import ASGITransport, AsyncClient

    from backend.core.config import Settings, get_settings
    from backend.main import app

    # Create settings with notifications configured
    notification_settings = Settings(
        notification_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_from_address="alerts@example.com",
        smtp_use_tls=True,
        smtp_user="smtp_user",
        smtp_password="smtp_password",  # noqa: S106 - test password
        default_webhook_url="https://hooks.example.com/webhook",
        webhook_timeout_seconds=30,
        default_email_recipients=["admin@example.com", "security@example.com"],
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.core.config.get_settings", return_value=notification_settings),
        patch("backend.api.routes.notification.get_settings", return_value=notification_settings),
    ):
        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()


@pytest.fixture
async def notification_disabled_client(integration_db, mock_redis):
    """Async HTTP client with notifications disabled."""
    from httpx import ASGITransport, AsyncClient

    from backend.core.config import Settings, get_settings
    from backend.main import app

    # Create settings with notifications disabled
    disabled_settings = Settings(
        notification_enabled=False,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.core.config.get_settings", return_value=disabled_settings),
        patch("backend.api.routes.notification.get_settings", return_value=disabled_settings),
    ):
        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()


@pytest.fixture
async def email_only_client(integration_db, mock_redis):
    """Async HTTP client with only email configured (no webhook)."""
    from httpx import ASGITransport, AsyncClient

    from backend.core.config import Settings, get_settings
    from backend.main import app

    # Create settings with only email configured
    email_only_settings = Settings(
        notification_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_from_address="alerts@example.com",
        smtp_use_tls=True,
        default_email_recipients=["admin@example.com"],
        # No webhook configured
        default_webhook_url=None,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
        patch("backend.core.config.get_settings", return_value=email_only_settings),
        patch("backend.api.routes.notification.get_settings", return_value=email_only_settings),
    ):
        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()


# =============================================================================
# GET /api/notification/config Tests
# =============================================================================


class TestGetNotificationConfig:
    """Tests for GET /api/notification/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_with_all_channels_configured(self, notification_client: AsyncClient):
        """Test getting notification config when all channels are configured."""
        response = await notification_client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()

        assert data["notification_enabled"] is True
        assert data["email_configured"] is True
        assert data["webhook_configured"] is True
        assert data["push_configured"] is False  # Push not yet implemented

        # Check available channels
        assert "email" in data["available_channels"]
        assert "webhook" in data["available_channels"]

        # Check SMTP configuration (sensitive fields should not be exposed)
        assert data["smtp_host"] == "smtp.example.com"
        assert data["smtp_port"] == 587
        assert data["smtp_from_address"] == "alerts@example.com"
        assert data["smtp_use_tls"] is True

        # Check webhook configuration
        assert data["default_webhook_url"] == "https://hooks.example.com/webhook"
        assert data["webhook_timeout_seconds"] == 30

        # Check default recipients
        assert "admin@example.com" in data["default_email_recipients"]
        assert "security@example.com" in data["default_email_recipients"]

    @pytest.mark.asyncio
    async def test_get_config_with_notifications_disabled(
        self, notification_disabled_client: AsyncClient
    ):
        """Test getting notification config when notifications are disabled."""
        response = await notification_disabled_client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()

        assert data["notification_enabled"] is False
        assert data["email_configured"] is False
        assert data["webhook_configured"] is False
        assert data["push_configured"] is False
        assert data["available_channels"] == []

    @pytest.mark.asyncio
    async def test_get_config_with_email_only(self, email_only_client: AsyncClient):
        """Test getting notification config with only email configured."""
        response = await email_only_client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()

        assert data["notification_enabled"] is True
        assert data["email_configured"] is True
        assert data["webhook_configured"] is False
        assert data["push_configured"] is False
        assert data["available_channels"] == ["email"]

        # Webhook-related fields should be None
        assert data["default_webhook_url"] is None
        assert data["webhook_timeout_seconds"] is None

    @pytest.mark.asyncio
    async def test_get_config_response_schema(self, notification_client: AsyncClient):
        """Test that notification config response matches expected schema."""
        response = await notification_client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "notification_enabled",
            "email_configured",
            "webhook_configured",
            "push_configured",
            "available_channels",
            "default_email_recipients",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Optional fields with types
        assert isinstance(data["notification_enabled"], bool)
        assert isinstance(data["email_configured"], bool)
        assert isinstance(data["webhook_configured"], bool)
        assert isinstance(data["push_configured"], bool)
        assert isinstance(data["available_channels"], list)
        assert isinstance(data["default_email_recipients"], list)


# =============================================================================
# POST /api/notification/test Tests - Email Channel
# =============================================================================


class TestNotificationTestEmail:
    """Tests for POST /api/notification/test endpoint - Email channel."""

    @pytest.mark.asyncio
    async def test_test_email_notification_success(self, notification_client: AsyncClient):
        """Test successful email notification test."""
        # Mock the email sending
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            recipient="admin@example.com, security@example.com",
        )

        with patch.object(NotificationService, "send_email", AsyncMock(return_value=mock_delivery)):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "email"
        assert data["success"] is True
        assert data["error"] is None
        assert "sent successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_test_email_with_custom_recipients(self, notification_client: AsyncClient):
        """Test email notification with custom recipients."""
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            recipient="test@example.com",
        )

        with patch.object(NotificationService, "send_email", AsyncMock(return_value=mock_delivery)):
            response = await notification_client.post(
                "/api/notification/test",
                json={
                    "channel": "email",
                    "email_recipients": ["test@example.com"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_test_email_not_configured(self, notification_disabled_client: AsyncClient):
        """Test email notification when SMTP is not configured."""
        response = await notification_disabled_client.post(
            "/api/notification/test",
            json={"channel": "email"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "email"
        assert data["success"] is False
        assert data["error"] is not None
        # Should indicate SMTP is not configured or no recipients
        assert "configured" in data["message"].lower() or "recipients" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_test_email_no_recipients(self, email_only_client: AsyncClient):
        """Test email notification without recipients configured."""
        # Create settings with email configured but no recipients
        from backend.core.config import Settings, get_settings

        no_recipients_settings = Settings(
            notification_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_from_address="alerts@example.com",
            smtp_use_tls=True,
            default_email_recipients=[],  # No default recipients
            database_url=os.environ.get("DATABASE_URL", ""),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
        )

        with patch(
            "backend.api.routes.notification.get_settings",
            return_value=no_recipients_settings,
        ):
            get_settings.cache_clear()
            reset_notification_service()

            response = await email_only_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "recipients" in data["error"].lower() or "recipients" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_test_email_delivery_failure(self, notification_client: AsyncClient):
        """Test email notification when delivery fails."""
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=False,
            error="SMTP connection refused",
        )

        with patch.object(NotificationService, "send_email", AsyncMock(return_value=mock_delivery)):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "email"
        assert data["success"] is False
        assert data["error"] is not None
        assert "SMTP connection refused" in data["error"]


# =============================================================================
# POST /api/notification/test Tests - Webhook Channel
# =============================================================================


class TestNotificationTestWebhook:
    """Tests for POST /api/notification/test endpoint - Webhook channel."""

    @pytest.mark.asyncio
    async def test_test_webhook_notification_success(self, notification_client: AsyncClient):
        """Test successful webhook notification test."""
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=True,
            recipient="https://hooks.example.com/webhook",
        )

        with patch.object(
            NotificationService, "send_webhook", AsyncMock(return_value=mock_delivery)
        ):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "webhook"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "webhook"
        assert data["success"] is True
        assert data["error"] is None
        assert "sent successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_test_webhook_with_custom_url(self, notification_client: AsyncClient):
        """Test webhook notification with custom URL."""
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=True,
            recipient="https://custom.example.com/hook",
        )

        with patch.object(
            NotificationService, "send_webhook", AsyncMock(return_value=mock_delivery)
        ):
            response = await notification_client.post(
                "/api/notification/test",
                json={
                    "channel": "webhook",
                    "webhook_url": "https://custom.example.com/hook",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_test_webhook_not_configured(self, email_only_client: AsyncClient):
        """Test webhook notification when no webhook URL is configured."""
        response = await email_only_client.post(
            "/api/notification/test",
            json={"channel": "webhook"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "webhook"
        assert data["success"] is False
        assert data["error"] is not None
        assert "webhook" in data["message"].lower() or "url" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_test_webhook_delivery_failure(self, notification_client: AsyncClient):
        """Test webhook notification when delivery fails."""
        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=False,
            error="Connection timeout",
        )

        with patch.object(
            NotificationService, "send_webhook", AsyncMock(return_value=mock_delivery)
        ):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "webhook"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "webhook"
        assert data["success"] is False
        assert data["error"] is not None
        assert "timeout" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_test_webhook_invalid_url_validation(self, notification_client: AsyncClient):
        """Test webhook URL validation rejects invalid URLs."""
        # Test with private IP (SSRF protection)
        response = await notification_client.post(
            "/api/notification/test",
            json={
                "channel": "webhook",
                "webhook_url": "http://192.168.1.1/hook",
            },
        )

        # Should get validation error (422) for private IP
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_webhook_http_url_rejected(self, notification_client: AsyncClient):
        """Test webhook URL validation rejects non-HTTPS URLs (in production mode)."""
        # Non-localhost HTTP URLs should be rejected for SSRF protection
        # Note: localhost HTTP may be allowed in dev mode
        response = await notification_client.post(
            "/api/notification/test",
            json={
                "channel": "webhook",
                "webhook_url": "http://external-server.com/hook",
            },
        )

        # Should get validation error (422) for non-HTTPS
        assert response.status_code == 422


# =============================================================================
# POST /api/notification/test Tests - Push Channel
# =============================================================================


class TestNotificationTestPush:
    """Tests for POST /api/notification/test endpoint - Push channel."""

    @pytest.mark.asyncio
    async def test_test_push_not_implemented(self, notification_client: AsyncClient):
        """Test push notification returns not implemented error."""
        response = await notification_client.post(
            "/api/notification/test",
            json={"channel": "push"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["channel"] == "push"
        assert data["success"] is False
        assert "not yet implemented" in data["error"].lower()


# =============================================================================
# POST /api/notification/test Tests - Error Handling
# =============================================================================


class TestNotificationTestErrors:
    """Tests for error handling in POST /api/notification/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_invalid_channel(self, notification_client: AsyncClient):
        """Test with invalid notification channel."""
        response = await notification_client.post(
            "/api/notification/test",
            json={"channel": "invalid_channel"},
        )

        # Should get validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_missing_channel(self, notification_client: AsyncClient):
        """Test with missing channel parameter."""
        response = await notification_client.post(
            "/api/notification/test",
            json={},
        )

        # Should get validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_invalid_email_recipients_format(self, notification_client: AsyncClient):
        """Test with invalid email recipients format."""
        response = await notification_client.post(
            "/api/notification/test",
            json={
                "channel": "email",
                "email_recipients": "not-a-list",  # Should be a list
            },
        )

        # Should get validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_exception_handling(self, notification_client: AsyncClient):
        """Test that exceptions during notification test are handled gracefully."""
        with patch.object(
            NotificationService,
            "send_email",
            AsyncMock(side_effect=Exception("Unexpected error")),
        ):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["error"] is not None
        assert "Unexpected error" in data["error"]


# =============================================================================
# Audit Logging Tests
# =============================================================================


class TestNotificationAuditLogging:
    """Tests for audit logging of notification test actions."""

    @pytest.mark.asyncio
    async def test_successful_test_creates_audit_log(
        self, notification_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that successful notification test creates an audit log entry."""
        from sqlalchemy import select

        from backend.models.audit import AuditLog

        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            recipient="admin@example.com",
        )

        with patch.object(NotificationService, "send_email", AsyncMock(return_value=mock_delivery)):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Check for audit log entry
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "notification_test")
        )
        logs = result.scalars().all()

        # Should have at least one audit log for this test
        matching_logs = [
            log
            for log in logs
            if log.resource_type == "notification" and log.resource_id == "email"
        ]
        assert len(matching_logs) >= 1

        # Verify audit log details
        log = matching_logs[0]
        assert log.details is not None
        assert log.details.get("channel") == "email"
        assert log.details.get("success") is True

    @pytest.mark.asyncio
    async def test_failed_test_does_not_create_audit_log(
        self, notification_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that failed notification test does not create an audit log entry."""
        from sqlalchemy import select

        from backend.models.audit import AuditLog

        # Count audit logs before the test
        result_before = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "notification_test")
        )
        count_before = len(result_before.scalars().all())

        mock_delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=False,
            error="SMTP error",
        )

        with patch.object(NotificationService, "send_email", AsyncMock(return_value=mock_delivery)):
            response = await notification_client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is False

        # Count audit logs after the test - should be same as before
        # Refresh session to see committed changes
        await db_session.commit()
        result_after = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "notification_test")
        )
        count_after = len(result_after.scalars().all())

        # Failed tests should not create audit logs
        assert count_after == count_before


# =============================================================================
# Integration with Default Client
# =============================================================================


class TestNotificationWithDefaultClient:
    """Tests using the default client fixture (minimal configuration)."""

    @pytest.mark.asyncio
    async def test_get_config_with_default_settings(self, client: AsyncClient):
        """Test notification config with default settings."""
        response = await client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()

        # Default settings should have notifications disabled or minimal config
        assert "notification_enabled" in data
        assert isinstance(data["notification_enabled"], bool)
