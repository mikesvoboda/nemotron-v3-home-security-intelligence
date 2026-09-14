"""Unit tests for notification API routes.

Tests cover:
- GET  /api/notification/config - Get notification configuration
- POST /api/notification/test   - Test notification delivery
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.notification import (
    _create_error_response,
    _test_email_channel,
    _test_webhook_channel,
    router,
)
from backend.api.schemas.notification import (
    NotificationChannel,
    TestNotificationRequest,
)
from backend.core.database import get_db
from backend.models import Alert
from backend.models.alert import AlertSeverity, AlertStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_settings():
    """Create mock settings for notification config."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_from_address = "noreply@example.com"
    settings.smtp_use_tls = True
    settings.default_webhook_url = "https://webhook.example.com/notify"
    settings.webhook_timeout_seconds = 30
    settings.default_email_recipients = ["admin@example.com"]
    return settings


@pytest.fixture
def mock_notification_service():
    """Create mock notification service."""
    service = MagicMock()
    service.is_email_configured.return_value = True
    service.is_webhook_configured.return_value = True
    service.is_push_configured.return_value = False
    service.get_available_channels.return_value = [
        MagicMock(value="email"),
        MagicMock(value="webhook"),
    ]
    return service


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_alert() -> Alert:
    """Create a mock alert for testing."""
    return Alert(
        id="test-alert-123",
        event_id=0,
        rule_id="test-rule",
        severity=AlertSeverity.LOW,
        status=AlertStatus.PENDING,
        dedup_key="test-notification",
        channels=["email"],
        alert_metadata={},
        created_at=datetime.now(UTC),
    )


# =============================================================================
# Get Config Tests
# =============================================================================


class TestGetNotificationConfig:
    """Tests for GET /api/notification/config endpoint."""

    def test_get_config_returns_full_config(
        self, client: TestClient, mock_settings, mock_notification_service
    ) -> None:
        """Test getting notification configuration."""
        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            response = client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()
        assert data["notification_enabled"] is True
        assert data["email_configured"] is True
        assert data["webhook_configured"] is True
        assert data["push_configured"] is False
        assert data["smtp_host"] == "smtp.example.com"
        assert data["smtp_port"] == 587

    def test_get_config_no_smtp_hides_port(
        self, client: TestClient, mock_notification_service
    ) -> None:
        """Test that SMTP port is hidden when SMTP host is not configured."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.smtp_host = None
        settings.smtp_port = 587
        settings.smtp_from_address = None
        settings.smtp_use_tls = True
        settings.default_webhook_url = None
        settings.webhook_timeout_seconds = 30
        settings.default_email_recipients = []

        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            response = client.get("/api/notification/config")

        assert response.status_code == 200
        data = response.json()
        assert data["smtp_host"] is None
        assert data["smtp_port"] is None


# =============================================================================
# Test Notification Tests
# =============================================================================


class TestTestNotification:
    """Tests for POST /api/notification/test endpoint."""

    def test_test_email_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_settings,
        mock_notification_service,
    ) -> None:
        """Test successful email notification test."""
        # Mock successful delivery
        mock_delivery = MagicMock()
        mock_delivery.success = True
        mock_notification_service.send_email = AsyncMock(return_value=mock_delivery)

        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
            patch(
                "backend.api.routes.notification.AuditService.log_action", new_callable=AsyncMock
            ),
        ):
            response = client.post(
                "/api/notification/test",
                json={
                    "channel": "email",
                    "email_recipients": ["test@example.com"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "email"

    def test_test_email_no_recipients(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_notification_service,
    ) -> None:
        """Test email notification test fails without recipients."""
        settings = MagicMock()
        settings.notification_enabled = True
        settings.default_email_recipients = []

        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            response = client.post(
                "/api/notification/test",
                json={"channel": "email"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "recipients" in data["message"].lower()

    def test_test_webhook_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_settings,
        mock_notification_service,
    ) -> None:
        """Test successful webhook notification test."""
        mock_delivery = MagicMock()
        mock_delivery.success = True
        mock_notification_service.send_webhook = AsyncMock(return_value=mock_delivery)

        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
            patch(
                "backend.api.routes.notification.AuditService.log_action", new_callable=AsyncMock
            ),
        ):
            response = client.post(
                "/api/notification/test",
                json={
                    "channel": "webhook",
                    "webhook_url": "https://test.example.com/webhook",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "webhook"

    def test_test_push_not_implemented(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_settings,
        mock_notification_service,
    ) -> None:
        """Test push notification returns not implemented."""
        with (
            patch(
                "backend.api.routes.notification.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.api.routes.notification.get_notification_service",
                return_value=mock_notification_service,
            ),
        ):
            response = client.post(
                "/api/notification/test",
                json={"channel": "push"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not yet implemented" in data["error"].lower()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestCreateErrorResponse:
    """Tests for _create_error_response helper function."""

    def test_create_error_response(self) -> None:
        """Test creating error response."""
        response = _create_error_response(
            NotificationChannel.EMAIL,
            "Connection refused",
            "Failed to connect to SMTP server",
        )

        assert response.channel == NotificationChannel.EMAIL
        assert response.success is False
        assert response.error == "Connection refused"
        assert "SMTP" in response.message


class TestTestEmailChannel:
    """Tests for _test_email_channel helper function."""

    @pytest.mark.asyncio
    async def test_email_channel_no_recipients(self, mock_alert) -> None:
        """Test email channel fails without recipients."""
        service = MagicMock()
        settings = MagicMock()
        settings.default_email_recipients = []
        request = TestNotificationRequest(channel=NotificationChannel.EMAIL)

        success, result = await _test_email_channel(service, settings, request, mock_alert)

        assert success is False
        assert "recipients" in result.lower()

    @pytest.mark.asyncio
    async def test_email_channel_not_configured(self, mock_alert) -> None:
        """Test email channel fails when not configured."""
        service = MagicMock()
        service.is_email_configured.return_value = False
        settings = MagicMock()
        settings.default_email_recipients = ["test@example.com"]
        request = TestNotificationRequest(channel=NotificationChannel.EMAIL)

        success, result = await _test_email_channel(service, settings, request, mock_alert)

        assert success is False
        assert "not configured" in result.lower()

    @pytest.mark.asyncio
    async def test_email_channel_success(self, mock_alert) -> None:
        """Test email channel success."""
        service = MagicMock()
        service.is_email_configured.return_value = True
        mock_delivery = MagicMock()
        mock_delivery.success = True
        service.send_email = AsyncMock(return_value=mock_delivery)

        settings = MagicMock()
        settings.default_email_recipients = ["test@example.com"]
        request = TestNotificationRequest(channel=NotificationChannel.EMAIL)

        success, result = await _test_email_channel(service, settings, request, mock_alert)

        assert success is True
        assert "successfully" in result.lower()


class TestTestWebhookChannel:
    """Tests for _test_webhook_channel helper function."""

    @pytest.mark.asyncio
    async def test_webhook_channel_no_url(self, mock_alert) -> None:
        """Test webhook channel fails without URL."""
        service = MagicMock()
        settings = MagicMock()
        settings.default_webhook_url = None
        request = TestNotificationRequest(channel=NotificationChannel.WEBHOOK)

        success, result = await _test_webhook_channel(service, settings, request, mock_alert)

        assert success is False
        assert "url" in result.lower()

    @pytest.mark.asyncio
    async def test_webhook_channel_success(self, mock_alert) -> None:
        """Test webhook channel success."""
        service = MagicMock()
        mock_delivery = MagicMock()
        mock_delivery.success = True
        service.send_webhook = AsyncMock(return_value=mock_delivery)

        settings = MagicMock()
        settings.default_webhook_url = "https://webhook.example.com"
        request = TestNotificationRequest(channel=NotificationChannel.WEBHOOK)

        success, result = await _test_webhook_channel(service, settings, request, mock_alert)

        assert success is True
        assert "successfully" in result.lower()
