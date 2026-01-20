"""Unit tests for webhooks API routes.

Tests the webhook receiver endpoints:
- POST /api/webhooks/alerts - Receive Alertmanager webhook notifications

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from backend.api.routes.webhooks import receive_alertmanager_webhook
from backend.api.schemas.webhooks import (
    AlertmanagerStatus,
    AlertmanagerWebhookPayload,
    WebhookAlert,
)


class TestReceiveAlertmanagerWebhook:
    """Tests for POST /api/webhooks/alerts endpoint."""

    def _create_alert(
        self,
        alertname: str = "TestAlert",
        severity: str = "warning",
        status: AlertmanagerStatus = AlertmanagerStatus.FIRING,
        component: str = "test",
    ) -> WebhookAlert:
        """Helper to create an WebhookAlert for testing."""
        return WebhookAlert(
            status=status,
            labels={
                "alertname": alertname,
                "severity": severity,
                "component": component,
            },
            annotations={
                "summary": f"{alertname} summary",
                "description": f"{alertname} description",
            },
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            endsAt=None,
            generatorURL="http://prometheus:9090/graph",
            fingerprint=f"fp-{alertname.lower()}",
        )

    def _create_payload(
        self,
        alerts: list[WebhookAlert] | None = None,
        status: AlertmanagerStatus = AlertmanagerStatus.FIRING,
        receiver: str = "test-receiver",
    ) -> AlertmanagerWebhookPayload:
        """Helper to create an AlertmanagerWebhookPayload for testing."""
        if alerts is None:
            alerts = [self._create_alert()]

        return AlertmanagerWebhookPayload(
            version="4",
            groupKey='{}:{alertname="TestAlert"}',
            truncatedAlerts=0,
            status=status,
            receiver=receiver,
            groupLabels={"alertname": "TestAlert"},
            commonLabels={"alertname": "TestAlert", "severity": "warning"},
            commonAnnotations={"summary": "Test summary"},
            externalURL="http://alertmanager:9093",
            alerts=alerts,
        )

    @pytest.mark.asyncio
    async def test_receive_single_firing_alert(self) -> None:
        """Test receiving a single firing alert."""
        payload = self._create_payload()
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 1
        assert result.processed == 1
        assert "1 alert(s)" in result.message

    @pytest.mark.asyncio
    async def test_receive_multiple_alerts(self) -> None:
        """Test receiving multiple alerts in one webhook."""
        alerts = [
            self._create_alert(alertname="Alert1", severity="warning"),
            self._create_alert(alertname="Alert2", severity="critical"),
            self._create_alert(alertname="Alert3", severity="info"),
        ]
        payload = self._create_payload(alerts=alerts)
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 3
        assert result.processed == 3
        assert "3 alert(s)" in result.message

    @pytest.mark.asyncio
    async def test_receive_resolved_alert(self) -> None:
        """Test receiving a resolved alert."""
        alert = WebhookAlert(
            status=AlertmanagerStatus.RESOLVED,
            labels={"alertname": "TestAlert", "severity": "warning", "component": "test"},
            annotations={"summary": "Test resolved"},
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            endsAt=datetime(2026, 1, 17, 12, 30, 0, tzinfo=UTC),
            fingerprint="fp-resolved",
        )
        payload = self._create_payload(alerts=[alert], status=AlertmanagerStatus.RESOLVED)
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 1
        assert result.processed == 1

    @pytest.mark.asyncio
    async def test_receive_critical_alert_logs_error(self) -> None:
        """Test that critical firing alerts are logged at error level."""
        alert = self._create_alert(alertname="CriticalAlert", severity="critical")
        payload = self._create_payload(alerts=[alert])
        background_tasks = BackgroundTasks()

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger") as mock_logger,
        ):
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        # Verify error logging for critical alerts
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        assert "CriticalAlert" in call_args
        assert "critical" in call_args

    @pytest.mark.asyncio
    async def test_receive_warning_alert_logs_warning(self) -> None:
        """Test that warning firing alerts are logged at warning level."""
        alert = self._create_alert(alertname="WarningAlert", severity="warning")
        payload = self._create_payload(alerts=[alert])
        background_tasks = BackgroundTasks()

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger") as mock_logger,
        ):
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_receive_info_alert_logs_info(self) -> None:
        """Test that info firing alerts are logged at info level."""
        alert = self._create_alert(alertname="InfoAlert", severity="info")
        payload = self._create_payload(alerts=[alert])
        background_tasks = BackgroundTasks()

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger") as mock_logger,
        ):
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_broadcaster_not_initialized_does_not_fail(self) -> None:
        """Test that webhook succeeds even if WebSocket broadcaster is not ready."""
        payload = self._create_payload()
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster_cls.get_instance.side_effect = RuntimeError(
                "Broadcaster not initialized"
            )

            result = await receive_alertmanager_webhook(payload, background_tasks)

        # Should still succeed - broadcast failure is non-fatal
        assert result.status == "ok"
        assert result.received == 1
        assert result.processed == 1

    @pytest.mark.asyncio
    async def test_response_includes_receiver_name(self) -> None:
        """Test that response message includes the receiver name."""
        payload = self._create_payload(receiver="critical-receiver")
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert "critical-receiver" in result.message

    @pytest.mark.asyncio
    async def test_empty_alerts_list(self) -> None:
        """Test handling of webhook with empty alerts list."""
        payload = self._create_payload(alerts=[])
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 0
        assert result.processed == 0

    @pytest.mark.asyncio
    async def test_alert_with_missing_optional_labels(self) -> None:
        """Test handling of alert with missing optional labels."""
        alert = WebhookAlert(
            status=AlertmanagerStatus.FIRING,
            labels={"alertname": "MinimalAlert"},  # Missing severity and component
            annotations={},  # Missing summary and description
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            fingerprint="fp-minimal",
        )
        payload = self._create_payload(alerts=[alert])
        background_tasks = BackgroundTasks()

        with patch("backend.api.routes.webhooks.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 1
        assert result.processed == 1


class TestAlertmanagerSchemas:
    """Tests for Alertmanager webhook Pydantic schemas."""

    def test_alert_status_enum_values(self) -> None:
        """Test AlertmanagerStatus enum values."""
        assert AlertmanagerStatus.FIRING == "firing"
        assert AlertmanagerStatus.RESOLVED == "resolved"

    def test_alertmanager_alert_required_fields(self) -> None:
        """Test WebhookAlert with required fields only."""
        alert = WebhookAlert(
            status=AlertmanagerStatus.FIRING,
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            fingerprint="test-fp",
        )
        assert alert.status == AlertmanagerStatus.FIRING
        assert alert.fingerprint == "test-fp"
        assert alert.labels == {}
        assert alert.annotations == {}

    def test_alertmanager_alert_all_fields(self) -> None:
        """Test WebhookAlert with all fields."""
        alert = WebhookAlert(
            status=AlertmanagerStatus.RESOLVED,
            labels={"alertname": "Test", "severity": "critical"},
            annotations={"summary": "Test summary", "description": "Test desc"},
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            endsAt=datetime(2026, 1, 17, 13, 0, 0, tzinfo=UTC),
            generatorURL="http://prometheus:9090/graph",
            fingerprint="full-fp",
        )
        assert alert.status == AlertmanagerStatus.RESOLVED
        assert alert.labels["alertname"] == "Test"
        assert alert.labels["severity"] == "critical"
        assert alert.annotations["summary"] == "Test summary"
        assert alert.endsAt is not None
        assert alert.generatorURL == "http://prometheus:9090/graph"

    def test_alertmanager_webhook_payload(self) -> None:
        """Test AlertmanagerWebhookPayload with all fields."""
        alert = WebhookAlert(
            status=AlertmanagerStatus.FIRING,
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            fingerprint="test-fp",
        )
        payload = AlertmanagerWebhookPayload(
            version="4",
            groupKey="test-group",
            status=AlertmanagerStatus.FIRING,
            receiver="test-receiver",
            alerts=[alert],
        )
        assert payload.version == "4"
        assert payload.groupKey == "test-group"
        assert payload.receiver == "test-receiver"
        assert len(payload.alerts) == 1
        assert payload.truncatedAlerts == 0
