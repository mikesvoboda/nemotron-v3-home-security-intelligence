"""Integration tests for notification delivery pipeline.

This module tests the end-to-end notification delivery pipeline:
Event → Alert Rule → Alert → Notification Delivery

Test Coverage:
- Email delivery (SMTP mocked)
- Webhook delivery (HTTP client mocked)
- Alert rule integration (rule matching → notification sent)
- Error scenarios (SMTP failure, webhook timeout, rate limiting)
- Cooldown period enforcement
- Rule matching criteria

Mock Strategy:
- PostgreSQL: Real database (via integration_db fixture)
- SMTP: Mocked with unittest.mock.patch
- HTTP client (webhook): Mocked with unittest.mock.AsyncMock
- Redis: Mocked via mock_redis fixture

Related Files:
- backend/services/notification.py - Notification service
- backend/services/alert_engine.py - Alert rule engine
- backend/models/alert.py - Alert and AlertRule models
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Camera, Detection, Event
from backend.services.alert_engine import AlertRuleEngine
from backend.services.notification import (
    NotificationChannel,
    NotificationService,
)
from backend.tests.integration.conftest import unique_id

# Mark all tests as integration tests
pytestmark = [pytest.mark.integration]


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime for PostgreSQL compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def notification_test_prefix():
    """Generate a unique prefix for this test run."""
    return unique_id("notif")


@pytest.fixture
def mock_settings():
    """Create mock settings for notification testing."""
    settings = MagicMock()
    settings.notification_enabled = True
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_user = "user@example.com"
    settings.smtp_password = "test-password"  # pragma: allowlist secret
    settings.smtp_from_address = "alerts@example.com"
    settings.smtp_use_tls = True
    settings.default_email_recipients = ["recipient@example.com"]
    settings.default_webhook_url = "https://example.com/webhook"
    settings.webhook_timeout_seconds = 30
    settings.is_development = False  # Production mode for SSRF validation
    return settings


@pytest.fixture
async def test_camera(isolated_db_session, notification_test_prefix):
    """Create a test camera for notification tests."""
    camera_id = f"{notification_test_prefix}_camera"
    camera = Camera(
        id=camera_id,
        name="Test Camera",
        folder_path=f"/export/foscam/{camera_id}",
    )
    isolated_db_session.add(camera)
    await isolated_db_session.flush()
    return camera


@pytest.fixture
async def test_event(isolated_db_session, test_camera):
    """Create a test event for notification tests."""
    event = Event(
        batch_id=unique_id("batch"),
        camera_id=test_camera.id,
        started_at=_utcnow(),
        risk_score=85,
        risk_level="high",
        detection_ids=None,
    )
    isolated_db_session.add(event)
    await isolated_db_session.flush()
    return event


@pytest.fixture
async def test_detection(isolated_db_session, test_camera):
    """Create a test detection for notification tests."""
    detection = Detection(
        camera_id=test_camera.id,
        file_path="/path/to/image.jpg",
        object_type="person",
        confidence=0.95,
        detected_at=_utcnow(),
    )
    isolated_db_session.add(detection)
    await isolated_db_session.flush()
    return detection


@pytest.fixture
async def test_alert_rule(isolated_db_session, test_camera, notification_test_prefix):
    """Create a test alert rule with email and webhook channels."""
    rule = AlertRule(
        name=f"Test Notification Rule {notification_test_prefix}",
        enabled=True,
        severity=AlertSeverity.HIGH,
        risk_threshold=70,
        camera_ids=[test_camera.id],
        channels=["email", "webhook"],
        cooldown_seconds=300,
    )
    isolated_db_session.add(rule)
    await isolated_db_session.flush()
    return rule


@pytest.fixture
async def test_alert(isolated_db_session, test_event, test_alert_rule):
    """Create a test alert for notification tests."""
    alert = Alert(
        event_id=test_event.id,
        rule_id=test_alert_rule.id,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        dedup_key=f"{test_event.camera_id}:{test_alert_rule.id}",
        channels=["email", "webhook"],
        alert_metadata={
            "rule_name": test_alert_rule.name,
            "matched_conditions": ["risk_score >= 70"],
        },
    )
    isolated_db_session.add(alert)
    await isolated_db_session.flush()
    return alert


# =============================================================================
# Email Delivery Tests
# =============================================================================


class TestEmailDelivery:
    """Tests for email notification delivery."""

    @pytest.mark.asyncio
    async def test_email_delivery_success(self, mock_settings, test_alert):
        """Test successful email delivery."""
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            delivery = await service.send_email(test_alert)

            assert delivery.success is True
            assert delivery.channel == NotificationChannel.EMAIL
            assert delivery.error is None
            assert delivery.delivered_at is not None
            assert "recipient@example.com" in delivery.recipient

            # Verify SMTP was called correctly
            mock_smtp.assert_called_once()
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "test-password")
            mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_contains_alert_details(self, mock_settings, test_alert):
        """Test that email contains correct alert details."""
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            await service.send_email(test_alert)

            # Get the email message that was sent
            call_args = mock_server.sendmail.call_args
            email_content = call_args[0][2]  # Third argument is the message

            # Verify email contains alert details
            assert test_alert.id in email_content
            assert str(test_alert.event_id) in email_content
            assert test_alert.severity.value.upper() in email_content

    @pytest.mark.asyncio
    async def test_email_smtp_failure(self, mock_settings, test_alert):
        """Test email delivery failure with SMTP error."""
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.login.side_effect = Exception(
                "SMTP connection failed"
            )

            delivery = await service.send_email(test_alert)

            assert delivery.success is False
            assert delivery.channel == NotificationChannel.EMAIL
            assert "failed" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_email_authentication_failure(self, mock_settings, test_alert):
        """Test email delivery failure with authentication error."""
        import smtplib

        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value.login.side_effect = (
                smtplib.SMTPAuthenticationError(535, b"Authentication failed")
            )

            delivery = await service.send_email(test_alert)

            assert delivery.success is False
            assert "authentication" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_email_not_configured(self, test_alert):
        """Test email delivery when SMTP not configured."""
        settings = MagicMock()
        settings.smtp_host = None
        settings.smtp_from_address = None
        service = NotificationService(settings)

        delivery = await service.send_email(test_alert)

        assert delivery.success is False
        assert "not configured" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_email_no_recipients(self, mock_settings, test_alert):
        """Test email delivery when no recipients configured."""
        mock_settings.default_email_recipients = []
        service = NotificationService(mock_settings)

        delivery = await service.send_email(test_alert)

        assert delivery.success is False
        assert "no email recipients" in delivery.error.lower()


# =============================================================================
# Webhook Delivery Tests
# =============================================================================


class TestWebhookDelivery:
    """Tests for webhook notification delivery."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_success(self, mock_settings, test_alert):
        """Test successful webhook delivery."""
        service = NotificationService(mock_settings)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        service._http_client = mock_client

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is True
        assert delivery.channel == NotificationChannel.WEBHOOK
        assert delivery.error is None
        assert delivery.delivered_at is not None
        assert delivery.recipient == mock_settings.default_webhook_url

        # Verify HTTP POST was called
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_payload_format(self, mock_settings, test_alert):
        """Test webhook payload contains correct format."""
        service = NotificationService(mock_settings)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        service._http_client = mock_client

        await service.send_webhook(test_alert)

        # Get the payload that was sent
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]

        # Verify payload structure
        assert payload["type"] == "security_alert"
        assert payload["alert"]["id"] == test_alert.id
        assert payload["alert"]["event_id"] == test_alert.event_id
        assert payload["alert"]["rule_id"] == test_alert.rule_id
        assert payload["alert"]["severity"] == test_alert.severity.value
        assert payload["alert"]["status"] == test_alert.status.value
        assert payload["source"] == "home_security_intelligence"

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure(self, mock_settings, test_alert):
        """Test webhook handles HTTP error responses."""
        service = NotificationService(mock_settings)

        # Mock HTTP client with error response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response
        service._http_client = mock_client

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is False
        assert "status 500" in delivery.error

    @pytest.mark.asyncio
    async def test_webhook_timeout_handling(self, mock_settings, test_alert):
        """Test webhook timeout handling."""
        service = NotificationService(mock_settings)

        # Mock HTTP client with timeout
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        service._http_client = mock_client

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is False
        assert "timed out" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_webhook_connection_error(self, mock_settings, test_alert):
        """Test webhook connection error handling."""
        service = NotificationService(mock_settings)

        # Mock HTTP client with connection error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        service._http_client = mock_client

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is False
        assert "failed" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_webhook_not_configured(self, test_alert):
        """Test webhook delivery when URL not configured."""
        settings = MagicMock()
        settings.default_webhook_url = None
        service = NotificationService(settings)

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is False
        assert "not configured" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_webhook_ssrf_protection(self, mock_settings, test_alert):
        """Test webhook SSRF validation rejects private IPs."""
        # Test that private IPs are rejected
        service = NotificationService(mock_settings)

        delivery = await service.send_webhook(test_alert, webhook_url="http://127.0.0.1/webhook")

        assert delivery.success is False
        assert "invalid webhook url" in delivery.error.lower()


# =============================================================================
# Alert Rule Integration Tests
# =============================================================================


class TestAlertRuleIntegration:
    """Tests for alert rule integration with notification delivery."""

    @pytest.mark.asyncio
    async def test_rule_matches_triggers_notification(
        self,
        isolated_db_session,
        mock_settings,
        test_event,
        test_alert_rule,
        notification_test_prefix,
    ):
        """Test that matching rule triggers notification."""
        # Create alert engine
        engine = AlertRuleEngine(isolated_db_session)

        # Evaluate event (should trigger rule)
        result = await engine.evaluate_event(test_event)

        assert result.has_triggers is True

        # Create alerts
        alerts = await engine.create_alerts_for_event(test_event, result.triggered_rules)
        assert len(alerts) > 0

        # Deliver notification
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            service._http_client = mock_client

            delivery_result = await service.deliver_alert(alerts[0])

            assert delivery_result.all_successful is True
            assert delivery_result.successful_count == 2  # email + webhook

    @pytest.mark.asyncio
    async def test_rule_no_match_no_notification(
        self,
        isolated_db_session,
        test_event,
        test_camera,
        notification_test_prefix,
    ):
        """Test that non-matching rule doesn't trigger notification."""
        # Create rule that won't match (high risk threshold)
        rule = AlertRule(
            name=f"High Threshold Rule {notification_test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=95,  # Event has risk_score=85, won't match
            camera_ids=[test_camera.id],
        )
        isolated_db_session.add(rule)
        await isolated_db_session.flush()

        # Create alert engine
        engine = AlertRuleEngine(isolated_db_session)

        # Evaluate event (should NOT trigger rule)
        result = await engine.evaluate_event(test_event)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_disabled_rule_no_notification(
        self,
        isolated_db_session,
        test_event,
        test_camera,
        notification_test_prefix,
    ):
        """Test that disabled rule doesn't trigger notification."""
        # Create disabled rule
        rule = AlertRule(
            name=f"Disabled Rule {notification_test_prefix}",
            enabled=False,  # Disabled
            severity=AlertSeverity.HIGH,
            risk_threshold=70,
            camera_ids=[test_camera.id],
        )
        isolated_db_session.add(rule)
        await isolated_db_session.flush()

        # Create alert engine
        engine = AlertRuleEngine(isolated_db_session)

        # Evaluate event (should NOT trigger disabled rule)
        result = await engine.evaluate_event(test_event)

        assert result.has_triggers is False

    @pytest.mark.asyncio
    async def test_cooldown_period_respected(
        self,
        isolated_db_session,
        test_event,
        test_alert_rule,
    ):
        """Test that cooldown period prevents duplicate notifications."""
        # Create existing alert within cooldown period
        existing_alert = Alert(
            event_id=test_event.id,
            rule_id=test_alert_rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{test_event.camera_id}:{test_alert_rule.id}",
            created_at=_utcnow_naive() - timedelta(minutes=2),  # 2 minutes ago
        )
        isolated_db_session.add(existing_alert)
        await isolated_db_session.flush()

        # Create alert engine
        engine = AlertRuleEngine(isolated_db_session)

        # Evaluate event (should be in cooldown)
        result = await engine.evaluate_event(test_event)

        # Rule should be skipped due to cooldown
        assert result.has_triggers is False
        assert len(result.skipped_rules) > 0
        assert result.skipped_rules[0][1] == "in_cooldown"

    @pytest.mark.asyncio
    async def test_cooldown_expired_allows_notification(
        self,
        isolated_db_session,
        test_event,
        test_alert_rule,
    ):
        """Test that expired cooldown allows new notification."""
        # Create old alert outside cooldown period
        old_alert = Alert(
            event_id=test_event.id,
            rule_id=test_alert_rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key=f"{test_event.camera_id}:{test_alert_rule.id}",
            created_at=_utcnow_naive() - timedelta(minutes=10),  # 10 minutes ago (cooldown is 5)
        )
        isolated_db_session.add(old_alert)
        await isolated_db_session.flush()

        # Create alert engine
        engine = AlertRuleEngine(isolated_db_session)

        # Evaluate event (cooldown should be expired)
        result = await engine.evaluate_event(test_event)

        assert result.has_triggers is True


# =============================================================================
# Error Scenario Tests
# =============================================================================


class TestErrorScenarios:
    """Tests for error handling in notification delivery."""

    @pytest.mark.asyncio
    async def test_email_service_unavailable(self, mock_settings, test_alert):
        """Test handling of email service being unavailable."""
        import smtplib

        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = smtplib.SMTPException("Service unavailable")

            delivery = await service.send_email(test_alert)

            assert delivery.success is False
            assert "smtp error" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_webhook_endpoint_unreachable(self, mock_settings, test_alert):
        """Test handling of unreachable webhook endpoint."""
        service = NotificationService(mock_settings)

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        service._http_client = mock_client

        delivery = await service.send_webhook(test_alert)

        assert delivery.success is False
        assert "request failed" in delivery.error.lower()

    @pytest.mark.asyncio
    async def test_partial_delivery_failure(self, mock_settings, test_alert):
        """Test partial failure (email succeeds, webhook fails)."""
        service = NotificationService(mock_settings)

        # Mock successful email
        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Mock failed webhook
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Error"
            mock_client.post.return_value = mock_response
            service._http_client = mock_client

            delivery_result = await service.deliver_alert(
                test_alert, channels=[NotificationChannel.EMAIL, NotificationChannel.WEBHOOK]
            )

            assert delivery_result.all_successful is False
            assert delivery_result.successful_count == 1  # Only email
            assert delivery_result.failed_count == 1  # Webhook failed

    @pytest.mark.asyncio
    async def test_notifications_disabled(self, test_alert):
        """Test that notifications are skipped when disabled."""
        settings = MagicMock()
        settings.notification_enabled = False
        service = NotificationService(settings)

        delivery_result = await service.deliver_alert(test_alert)

        assert delivery_result.all_successful is True  # No-op is success
        assert len(delivery_result.deliveries) == 0


# =============================================================================
# Multi-Channel Delivery Tests
# =============================================================================


class TestMultiChannelDelivery:
    """Tests for multi-channel notification delivery."""

    @pytest.mark.asyncio
    async def test_deliver_to_all_channels(self, mock_settings, test_alert):
        """Test delivering to all configured channels."""
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            service._http_client = mock_client

            delivery_result = await service.deliver_alert(test_alert)

            assert delivery_result.all_successful is True
            assert delivery_result.successful_count == 2  # email + webhook
            assert len(delivery_result.deliveries) == 2

    @pytest.mark.asyncio
    async def test_deliver_to_specific_channels(self, mock_settings, test_alert):
        """Test delivering to specific channels only."""
        service = NotificationService(mock_settings)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        service._http_client = mock_client

        delivery_result = await service.deliver_alert(
            test_alert, channels=[NotificationChannel.WEBHOOK]
        )

        assert len(delivery_result.deliveries) == 1
        assert delivery_result.deliveries[0].channel == NotificationChannel.WEBHOOK

    @pytest.mark.asyncio
    async def test_push_notification_not_implemented(self, mock_settings, test_alert):
        """Test that push notifications return not implemented."""
        service = NotificationService(mock_settings)

        delivery = await service.send_push(test_alert)

        assert delivery.success is False
        assert "not yet implemented" in delivery.error.lower()


# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================


class TestNotificationPipeline:
    """End-to-end tests for the complete notification pipeline."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_event_to_notification(
        self,
        isolated_db_session,
        mock_settings,
        test_camera,
        notification_test_prefix,
    ):
        """Test complete pipeline: Event → Rule Match → Alert → Notification."""
        # 1. Create alert rule
        rule = AlertRule(
            name=f"Pipeline Test Rule {notification_test_prefix}",
            enabled=True,
            severity=AlertSeverity.CRITICAL,
            risk_threshold=80,
            camera_ids=[test_camera.id],
            channels=["email", "webhook"],
        )
        isolated_db_session.add(rule)
        await isolated_db_session.flush()

        # 2. Create event
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=90,  # Exceeds threshold
            risk_level="critical",
        )
        isolated_db_session.add(event)
        await isolated_db_session.flush()

        # 3. Evaluate rules
        engine = AlertRuleEngine(isolated_db_session)
        result = await engine.evaluate_event(event)

        assert result.has_triggers is True

        # 4. Create alerts
        alerts = await engine.create_alerts_for_event(event, result.triggered_rules)
        assert len(alerts) > 0

        # Verify alert in database
        db_alert = await isolated_db_session.execute(select(Alert).where(Alert.id == alerts[0].id))
        alert = db_alert.scalar_one()

        assert alert.event_id == event.id
        assert alert.rule_id == rule.id
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.PENDING

        # 5. Deliver notification
        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            service._http_client = mock_client

            delivery_result = await service.deliver_alert(alert)

            assert delivery_result.all_successful is True
            assert delivery_result.successful_count == 2

    @pytest.mark.asyncio
    async def test_pipeline_with_detection_filtering(
        self,
        isolated_db_session,
        mock_settings,
        test_camera,
        notification_test_prefix,
    ):
        """Test pipeline with object type filtering."""
        # 1. Create rule that filters for "person" detections
        rule = AlertRule(
            name=f"Person Detection Rule {notification_test_prefix}",
            enabled=True,
            severity=AlertSeverity.HIGH,
            object_types=["person"],
            camera_ids=[test_camera.id],
            channels=["email"],
        )
        isolated_db_session.add(rule)
        await isolated_db_session.flush()

        # 2. Create detection
        detection = Detection(
            camera_id=test_camera.id,
            file_path="/path/to/image.jpg",
            object_type="person",
            confidence=0.95,
            detected_at=_utcnow(),
        )
        isolated_db_session.add(detection)
        await isolated_db_session.flush()

        # 3. Create event
        event = Event(
            batch_id=unique_id("batch"),
            camera_id=test_camera.id,
            started_at=_utcnow(),
            risk_score=70,
            risk_level="high",
            detection_ids=json.dumps([detection.id]),
        )
        isolated_db_session.add(event)
        await isolated_db_session.flush()

        # Link detection to event via junction table
        from backend.models.event_detection import EventDetection

        junction = EventDetection(event_id=event.id, detection_id=detection.id)
        isolated_db_session.add(junction)
        await isolated_db_session.flush()

        # 4. Evaluate rules (should match due to "person" detection)
        engine = AlertRuleEngine(isolated_db_session)
        result = await engine.evaluate_event(event)

        assert result.has_triggers is True

        # 5. Create and deliver notification
        alerts = await engine.create_alerts_for_event(event, result.triggered_rules)

        service = NotificationService(mock_settings)

        with patch("backend.services.notification.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            delivery_result = await service.deliver_alert(alerts[0])

            assert delivery_result.all_successful is True
