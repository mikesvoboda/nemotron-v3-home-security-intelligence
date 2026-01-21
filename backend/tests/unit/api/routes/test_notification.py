"""Unit tests for notification API endpoints.

This module tests the notification endpoints for:
- GET /api/notification/config - Get notification configuration status
- POST /api/notification/test - Test notification delivery

All tests use mocked dependencies following TDD methodology.
Tests cover success cases, error handling, and validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.routes.notification import (
    _create_error_response,
    _test_email_channel,
    _test_webhook_channel,
)
from backend.api.schemas.notification import (
    NotificationChannel,
    TestNotificationRequest,
    TestNotificationResponse,
)
from backend.core import get_db
from backend.main import app
from backend.services.notification import NotificationDelivery, NotificationService

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.refresh = AsyncMock()
    mock.add = MagicMock()
    return mock


def create_mock_db_dependency(mock_db: AsyncMock):
    """Create a mock dependency that yields mock database."""

    async def _mock_db_dependency():
        yield mock_db

    return _mock_db_dependency


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings with notification configuration."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_from_address = "alerts@example.com"
    settings.smtp_use_tls = True
    settings.smtp_username = "user@example.com"
    settings.smtp_password = "password123"  # pragma: allowlist secret
    settings.default_webhook_url = "https://example.com/webhook"
    settings.webhook_timeout_seconds = 30
    settings.default_email_recipients = ["admin@example.com"]
    return settings


@pytest.fixture
def mock_notification_service() -> MagicMock:
    """Create mock NotificationService."""
    service = MagicMock(spec=NotificationService)
    service.is_email_configured.return_value = True
    service.is_webhook_configured.return_value = True
    service.is_push_configured.return_value = False
    service.get_available_channels.return_value = [
        NotificationChannel.EMAIL,
        NotificationChannel.WEBHOOK,
    ]
    return service


@pytest.fixture
def mock_alert() -> MagicMock:
    """Create mock alert for testing."""
    from backend.models.alert import AlertSeverity, AlertStatus

    alert = MagicMock()
    alert.id = "test-alert-123"
    alert.event_id = 1
    alert.rule_id = "test-rule"
    alert.severity = AlertSeverity.HIGH
    alert.status = AlertStatus.PENDING
    alert.dedup_key = "test-dedup"
    alert.channels = ["email"]
    alert.alert_metadata = {
        "rule_name": "Test Alert",
        "matched_conditions": ["Test condition"],
    }
    alert.created_at = datetime.now(UTC)
    return alert


# =============================================================================
# GET /api/notification/config Tests
# =============================================================================


class TestGetNotificationConfig:
    """Tests for GET /api/notification/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_all_channels_configured(
        self, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test getting configuration when all channels are configured."""
        with (
            patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification/config")

            assert response.status_code == 200
            data = response.json()

            assert data["notification_enabled"] is True
            assert data["email_configured"] is True
            assert data["webhook_configured"] is True
            assert data["push_configured"] is False
            assert "email" in data["available_channels"]
            assert "webhook" in data["available_channels"]
            assert data["smtp_host"] == "smtp.example.com"
            assert data["smtp_port"] == 587
            assert data["smtp_from_address"] == "alerts@example.com"
            assert data["smtp_use_tls"] is True
            assert data["default_webhook_url"] == "https://example.com/webhook"
            assert data["webhook_timeout_seconds"] == 30
            assert data["default_email_recipients"] == ["admin@example.com"]

    @pytest.mark.asyncio
    async def test_get_config_no_email_configured(
        self, mock_notification_service: MagicMock
    ) -> None:
        """Test getting configuration when email is not configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.smtp_host = None
        settings.smtp_port = None
        settings.smtp_from_address = None
        settings.smtp_use_tls = None
        settings.default_webhook_url = "https://example.com/webhook"
        settings.webhook_timeout_seconds = 30
        settings.default_email_recipients = []

        mock_notification_service.is_email_configured.return_value = False
        mock_notification_service.is_webhook_configured.return_value = True
        mock_notification_service.get_available_channels.return_value = [
            NotificationChannel.WEBHOOK
        ]

        with (
            patch("backend.api.routes.notification.get_settings", return_value=settings),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification/config")

            assert response.status_code == 200
            data = response.json()

            assert data["email_configured"] is False
            assert data["webhook_configured"] is True
            assert data["smtp_host"] is None
            assert data["smtp_port"] is None
            assert len(data["available_channels"]) == 1
            assert "webhook" in data["available_channels"]

    @pytest.mark.asyncio
    async def test_get_config_no_webhook_configured(
        self, mock_notification_service: MagicMock
    ) -> None:
        """Test getting configuration when webhook is not configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_from_address = "alerts@example.com"
        settings.smtp_use_tls = True
        settings.default_webhook_url = None
        settings.webhook_timeout_seconds = None
        settings.default_email_recipients = ["admin@example.com"]

        mock_notification_service.is_email_configured.return_value = True
        mock_notification_service.is_webhook_configured.return_value = False
        mock_notification_service.get_available_channels.return_value = [NotificationChannel.EMAIL]

        with (
            patch("backend.api.routes.notification.get_settings", return_value=settings),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification/config")

            assert response.status_code == 200
            data = response.json()

            assert data["email_configured"] is True
            assert data["webhook_configured"] is False
            assert data["default_webhook_url"] is None
            assert data["webhook_timeout_seconds"] is None
            assert len(data["available_channels"]) == 1
            assert "email" in data["available_channels"]

    @pytest.mark.asyncio
    async def test_get_config_notifications_disabled(
        self, mock_notification_service: MagicMock
    ) -> None:
        """Test getting configuration when notifications are disabled."""
        settings = MagicMock()
        settings.notification_enabled = False
        settings.smtp_host = None
        settings.smtp_port = None
        settings.smtp_from_address = None
        settings.smtp_use_tls = None
        settings.default_webhook_url = None
        settings.webhook_timeout_seconds = None
        settings.default_email_recipients = []

        mock_notification_service.is_email_configured.return_value = False
        mock_notification_service.is_webhook_configured.return_value = False
        mock_notification_service.is_push_configured.return_value = False
        mock_notification_service.get_available_channels.return_value = []

        with (
            patch("backend.api.routes.notification.get_settings", return_value=settings),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/notification/config")

            assert response.status_code == 200
            data = response.json()

            assert data["notification_enabled"] is False
            assert data["email_configured"] is False
            assert data["webhook_configured"] is False
            assert data["push_configured"] is False
            assert len(data["available_channels"]) == 0


# =============================================================================
# POST /api/notification/test Tests
# =============================================================================


class TestTestNotification:
    """Tests for POST /api/notification/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_email_success(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test successful email notification test."""
        # Mock successful email delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="test@example.com",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            "email_recipients": ["test@example.com"],
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is True
                assert data["error"] is None
                assert "test@example.com" in data["message"]

                # Verify audit log was created
                mock_db.commit.assert_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_webhook_success(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test successful webhook notification test."""
        # Mock successful webhook delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="https://example.com/webhook",
        )
        mock_notification_service.send_webhook = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "webhook",
                            "webhook_url": "https://example.com/webhook",
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                assert data["channel"] == "webhook"
                assert data["success"] is True
                assert data["error"] is None
                assert "https://example.com/webhook" in data["message"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_email_no_recipients(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test email test fails when no recipients provided or configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.smtp_host = "smtp.example.com"
        settings.smtp_from_address = "alerts@example.com"
        settings.default_email_recipients = []  # No default recipients

        mock_notification_service.is_email_configured.return_value = True

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            # No email_recipients provided
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is False
                assert "email recipients" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_email_not_configured(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test email test fails when SMTP is not configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.smtp_host = None  # SMTP not configured
        settings.smtp_from_address = None
        settings.default_email_recipients = ["test@example.com"]

        mock_notification_service.is_email_configured.return_value = False

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            "email_recipients": ["test@example.com"],
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is False
                assert "smtp settings" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_webhook_no_url(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test webhook test fails when no URL provided or configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.default_webhook_url = None  # No default webhook URL

        mock_notification_service.is_webhook_configured.return_value = False

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "webhook",
                            # No webhook_url provided
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "webhook"
                assert data["success"] is False
                assert "webhook url" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_push_not_implemented(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test push notification test returns not implemented error."""
        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "push",
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "push"
                assert data["success"] is False
                assert "planned for a future release" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_email_delivery_failure(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test email test handles delivery failure."""
        # Mock failed email delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=False,
            error="SMTP connection failed",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            "email_recipients": ["test@example.com"],
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is False
                assert data["error"] == "SMTP connection failed"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_webhook_delivery_failure(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test webhook test handles delivery failure."""
        # Mock failed webhook delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=False,
            error="HTTP 500 Internal Server Error",
        )
        mock_notification_service.send_webhook = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "webhook",
                            "webhook_url": "https://example.com/webhook",
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "webhook"
                assert data["success"] is False
                assert "500" in data["error"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_notification_exception_handling(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test notification test handles unexpected exceptions."""
        # Mock exception during email sending
        mock_notification_service.send_email = AsyncMock(side_effect=Exception("Unexpected error"))

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            "email_recipients": ["test@example.com"],
                        },
                    )

                assert response.status_code == 200  # Returns success=false in body
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is False
                assert data["error"] == "Unexpected error"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_notification_audit_log_failure(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test that audit log failures don't prevent successful notification test."""
        # Mock successful email delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="test@example.com",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)

        # Mock commit failure (audit log)
        mock_db.commit.side_effect = Exception("Audit log failed")

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            "email_recipients": ["test@example.com"],
                        },
                    )

                # Should still succeed despite audit log failure
                assert response.status_code == 200
                data = response.json()

                assert data["channel"] == "email"
                assert data["success"] is True

                # Rollback should be called due to audit log failure
                mock_db.rollback.assert_called()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_notification_uses_default_recipients(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test that default recipients are used when none provided."""
        # Mock successful email delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="admin@example.com",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "email",
                            # No recipients provided, should use defaults
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                # Verify send_email was called with alert
                mock_notification_service.send_email.assert_called_once()
                call_args = mock_notification_service.send_email.call_args
                assert call_args[0][1] == ["admin@example.com"]  # Default recipients
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_notification_uses_default_webhook_url(
        self, mock_db: AsyncMock, mock_settings: MagicMock, mock_notification_service: MagicMock
    ) -> None:
        """Test that default webhook URL is used when none provided."""
        # Mock successful webhook delivery
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="https://example.com/webhook",
        )
        mock_notification_service.send_webhook = AsyncMock(return_value=delivery)

        app.dependency_overrides[get_db] = create_mock_db_dependency(mock_db)
        try:
            with (
                patch("backend.api.routes.notification.get_settings", return_value=mock_settings),
                patch(
                    "backend.api.routes.notification.get_notification_service",
                    return_value=mock_notification_service,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/notification/test",
                        json={
                            "channel": "webhook",
                            # No webhook_url provided, should use default
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                assert data["success"] is True
                # Verify send_webhook was called with default URL
                mock_notification_service.send_webhook.assert_called_once()
                call_args = mock_notification_service.send_webhook.call_args
                assert call_args[0][1] == "https://example.com/webhook"  # Default URL
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions in notification routes."""

    def test_create_error_response(self) -> None:
        """Test _create_error_response helper function."""
        response = _create_error_response(
            NotificationChannel.EMAIL, "SMTP error", "Failed to send email"
        )

        assert isinstance(response, TestNotificationResponse)
        assert response.channel == NotificationChannel.EMAIL
        assert response.success is False
        assert response.error == "SMTP error"
        assert response.message == "Failed to send email"

    @pytest.mark.asyncio
    async def test_test_email_channel_success(
        self, mock_notification_service: MagicMock, mock_settings: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_email_channel helper function success case."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="test@example.com",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)
        mock_notification_service.is_email_configured.return_value = True

        test_request = TestNotificationRequest(
            channel=NotificationChannel.EMAIL, email_recipients=["test@example.com"]
        )

        success, message = await _test_email_channel(
            mock_notification_service, mock_settings, test_request, mock_alert
        )

        assert success is True
        assert "test@example.com" in message

    @pytest.mark.asyncio
    async def test_test_email_channel_no_recipients(
        self, mock_notification_service: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_email_channel fails when no recipients."""
        settings = MagicMock()
        settings.default_email_recipients = []

        test_request = TestNotificationRequest(channel=NotificationChannel.EMAIL)

        success, message = await _test_email_channel(
            mock_notification_service, settings, test_request, mock_alert
        )

        assert success is False
        assert "No email recipients" in message

    @pytest.mark.asyncio
    async def test_test_email_channel_not_configured(
        self, mock_notification_service: MagicMock, mock_settings: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_email_channel fails when email not configured."""
        mock_notification_service.is_email_configured.return_value = False

        test_request = TestNotificationRequest(
            channel=NotificationChannel.EMAIL, email_recipients=["test@example.com"]
        )

        success, message = await _test_email_channel(
            mock_notification_service, mock_settings, test_request, mock_alert
        )

        assert success is False
        assert "Email is not configured" in message

    @pytest.mark.asyncio
    async def test_test_email_channel_delivery_failure(
        self, mock_notification_service: MagicMock, mock_settings: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_email_channel handles delivery failure."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            success=False,
            error="SMTP connection failed",
        )
        mock_notification_service.send_email = AsyncMock(return_value=delivery)
        mock_notification_service.is_email_configured.return_value = True

        test_request = TestNotificationRequest(
            channel=NotificationChannel.EMAIL, email_recipients=["test@example.com"]
        )

        success, message = await _test_email_channel(
            mock_notification_service, mock_settings, test_request, mock_alert
        )

        assert success is False
        assert message == "SMTP connection failed"

    @pytest.mark.asyncio
    async def test_test_webhook_channel_success(
        self, mock_notification_service: MagicMock, mock_settings: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_webhook_channel helper function success case."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=True,
            delivered_at=datetime.now(UTC),
            recipient="https://example.com/webhook",
        )
        mock_notification_service.send_webhook = AsyncMock(return_value=delivery)

        test_request = TestNotificationRequest(
            channel=NotificationChannel.WEBHOOK, webhook_url="https://example.com/webhook"
        )

        success, message = await _test_webhook_channel(
            mock_notification_service, mock_settings, test_request, mock_alert
        )

        assert success is True
        assert "https://example.com/webhook" in message

    @pytest.mark.asyncio
    async def test_test_webhook_channel_no_url(
        self, mock_notification_service: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_webhook_channel fails when no URL provided."""
        settings = MagicMock()
        settings.default_webhook_url = None

        test_request = TestNotificationRequest(channel=NotificationChannel.WEBHOOK)

        success, message = await _test_webhook_channel(
            mock_notification_service, settings, test_request, mock_alert
        )

        assert success is False
        assert "No webhook URL" in message

    @pytest.mark.asyncio
    async def test_test_webhook_channel_delivery_failure(
        self, mock_notification_service: MagicMock, mock_settings: MagicMock, mock_alert: MagicMock
    ) -> None:
        """Test _test_webhook_channel handles delivery failure."""
        delivery = NotificationDelivery(
            channel=NotificationChannel.WEBHOOK,
            success=False,
            error="HTTP 500 Internal Server Error",
        )
        mock_notification_service.send_webhook = AsyncMock(return_value=delivery)

        test_request = TestNotificationRequest(
            channel=NotificationChannel.WEBHOOK, webhook_url="https://example.com/webhook"
        )

        success, message = await _test_webhook_channel(
            mock_notification_service, mock_settings, test_request, mock_alert
        )

        assert success is False
        assert message == "HTTP 500 Internal Server Error"
