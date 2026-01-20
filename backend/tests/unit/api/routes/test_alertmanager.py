"""Unit tests for Alertmanager webhook API routes.

Tests the Alertmanager webhook receiver endpoint:
- POST /api/v1/alertmanager/webhook - Receive alerts from Alertmanager

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.

NEM-3122: Phase 3.1 - Alertmanager webhook receiver for Prometheus alerts.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.alertmanager import (
    _broadcast_prometheus_alert,
    receive_alertmanager_webhook,
)
from backend.api.schemas.alertmanager import (
    AlertmanagerAlert,
    AlertmanagerWebhook,
    PrometheusAlertStatus,
)
from backend.models.prometheus_alert import (
    PrometheusAlert,
)
from backend.models.prometheus_alert import (
    PrometheusAlertStatus as ModelPrometheusAlertStatus,
)


class TestReceiveAlertmanagerWebhook:
    """Tests for POST /api/v1/alertmanager/webhook endpoint."""

    def _create_alert(
        self,
        alertname: str = "TestAlert",
        severity: str = "warning",
        status: PrometheusAlertStatus = PrometheusAlertStatus.FIRING,
        fingerprint: str | None = None,
    ) -> AlertmanagerAlert:
        """Helper to create an AlertmanagerAlert for testing."""
        return AlertmanagerAlert(
            fingerprint=fingerprint or f"fp-{alertname.lower()}",
            status=status,
            labels={
                "alertname": alertname,
                "severity": severity,
                "instance": "localhost:9090",
            },
            annotations={
                "summary": f"{alertname} summary",
                "description": f"{alertname} description",
            },
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            endsAt=None,
            generatorURL="http://prometheus:9090/graph",
        )

    def _create_payload(
        self,
        alerts: list[AlertmanagerAlert] | None = None,
        status: PrometheusAlertStatus = PrometheusAlertStatus.FIRING,
        receiver: str = "test-receiver",
    ) -> AlertmanagerWebhook:
        """Helper to create an AlertmanagerWebhook for testing."""
        if alerts is None:
            alerts = [self._create_alert()]

        return AlertmanagerWebhook(
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

    @pytest.fixture
    def mock_db_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_receive_single_firing_alert(self, mock_db_session: AsyncMock) -> None:
        """Test receiving a single firing alert."""
        payload = self._create_payload()

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 1
        assert result.stored == 1
        assert "1 alert(s)" in result.message
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_multiple_alerts(self, mock_db_session: AsyncMock) -> None:
        """Test receiving multiple alerts in one webhook."""
        alerts = [
            self._create_alert(alertname="Alert1", severity="warning"),
            self._create_alert(alertname="Alert2", severity="critical"),
            self._create_alert(alertname="Alert3", severity="info"),
        ]
        payload = self._create_payload(alerts=alerts)

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 3
        assert result.stored == 3
        assert "3 alert(s)" in result.message
        assert mock_db_session.add.call_count == 3

    @pytest.mark.asyncio
    async def test_receive_resolved_alert(self, mock_db_session: AsyncMock) -> None:
        """Test receiving a resolved alert."""
        alert = AlertmanagerAlert(
            fingerprint="fp-resolved",
            status=PrometheusAlertStatus.RESOLVED,
            labels={"alertname": "TestAlert", "severity": "warning"},
            annotations={"summary": "Test resolved"},
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            endsAt=datetime(2026, 1, 20, 12, 30, 0, tzinfo=UTC),
        )
        payload = self._create_payload(alerts=[alert], status=PrometheusAlertStatus.RESOLVED)

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 1
        assert result.stored == 1

    @pytest.mark.asyncio
    async def test_receive_critical_alert_logs_error(self, mock_db_session: AsyncMock) -> None:
        """Test that critical firing alerts are logged at error level."""
        alert = self._create_alert(alertname="CriticalAlert", severity="critical")
        payload = self._create_payload(alerts=[alert])

        with (
            patch(
                "backend.api.routes.alertmanager._broadcast_prometheus_alert",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("backend.api.routes.alertmanager.logger") as mock_logger,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        # Verify error logging for critical alerts
        mock_logger.error.assert_called()
        call_args = str(mock_logger.error.call_args)
        assert "CriticalAlert" in call_args
        assert "critical" in call_args

    @pytest.mark.asyncio
    async def test_receive_warning_alert_logs_warning(self, mock_db_session: AsyncMock) -> None:
        """Test that warning firing alerts are logged at warning level."""
        alert = self._create_alert(alertname="WarningAlert", severity="warning")
        payload = self._create_payload(alerts=[alert])

        with (
            patch(
                "backend.api.routes.alertmanager._broadcast_prometheus_alert",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("backend.api.routes.alertmanager.logger") as mock_logger,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_receive_info_alert_logs_info(self, mock_db_session: AsyncMock) -> None:
        """Test that info firing alerts are logged at info level."""
        alert = self._create_alert(alertname="InfoAlert", severity="info")
        payload = self._create_payload(alerts=[alert])

        with (
            patch(
                "backend.api.routes.alertmanager._broadcast_prometheus_alert",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("backend.api.routes.alertmanager.logger") as mock_logger,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_empty_alerts_list(self, mock_db_session: AsyncMock) -> None:
        """Test handling of webhook with empty alerts list."""
        payload = self._create_payload(alerts=[])

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 0
        assert result.stored == 0
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_response_includes_receiver_name(self, mock_db_session: AsyncMock) -> None:
        """Test that response message includes the receiver name."""
        payload = self._create_payload(receiver="critical-receiver")

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert "critical-receiver" in result.message

    @pytest.mark.asyncio
    async def test_alert_with_missing_optional_labels(self, mock_db_session: AsyncMock) -> None:
        """Test handling of alert with missing optional labels."""
        alert = AlertmanagerAlert(
            fingerprint="fp-minimal",
            status=PrometheusAlertStatus.FIRING,
            labels={"alertname": "MinimalAlert"},  # Missing severity and instance
            annotations={},  # Missing summary and description
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
        )
        payload = self._create_payload(alerts=[alert])

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 1
        assert result.stored == 1

    @pytest.mark.asyncio
    async def test_broadcast_failure_does_not_affect_storage(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that broadcast failure doesn't prevent storage."""
        payload = self._create_payload()

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=False,  # Broadcast fails
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert result.received == 1
        assert result.stored == 1
        assert result.broadcast == 0  # Broadcast failed
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_commit_failure(self, mock_db_session: AsyncMock) -> None:
        """Test handling of database commit failure."""
        payload = self._create_payload()
        mock_db_session.commit.side_effect = Exception("Database error")

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "partial"
        assert result.stored == 0
        assert "commit failed" in result.message
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_with_year_0001_ends_at(self, mock_db_session: AsyncMock) -> None:
        """Test that endsAt with year 0001 is treated as null (alert still firing)."""
        alert = AlertmanagerAlert(
            fingerprint="fp-still-firing",
            status=PrometheusAlertStatus.FIRING,
            labels={"alertname": "StillFiring", "severity": "warning"},
            annotations={"summary": "Still firing"},
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            endsAt=datetime(1, 1, 1, 0, 0, 0, tzinfo=UTC),  # Year 0001 = still firing
        )
        payload = self._create_payload(alerts=[alert])

        added_alert: PrometheusAlert | None = None

        def capture_add(obj: PrometheusAlert) -> None:
            nonlocal added_alert
            added_alert = obj

        mock_db_session.add.side_effect = capture_add

        with patch(
            "backend.api.routes.alertmanager._broadcast_prometheus_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await receive_alertmanager_webhook(payload, mock_db_session, redis_client=None)

        assert result.status == "ok"
        assert added_alert is not None
        assert added_alert.ends_at is None  # Year 0001 should be treated as null


class TestBroadcastPrometheusAlert:
    """Tests for _broadcast_prometheus_alert helper function."""

    @pytest.mark.asyncio
    async def test_broadcast_with_no_redis_returns_false(self) -> None:
        """Test that broadcast returns False when Redis is not available."""
        alert = PrometheusAlert(
            id=1,
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "Test", "severity": "warning"},
            annotations={"summary": "Test alert"},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )

        result = await _broadcast_prometheus_alert(alert, redis_client=None)

        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_with_broadcaster_not_initialized(self) -> None:
        """Test that broadcast returns False when broadcaster is not initialized."""
        alert = PrometheusAlert(
            id=1,
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "Test", "severity": "warning"},
            annotations={"summary": "Test alert"},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )
        mock_redis = MagicMock()

        with patch("backend.api.routes.alertmanager.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster_cls.get_instance = MagicMock(
                side_effect=RuntimeError("Broadcaster not initialized")
            )

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_success(self) -> None:
        """Test successful broadcast."""
        alert = PrometheusAlert(
            id=1,
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "Test", "severity": "warning"},
            annotations={"summary": "Test alert"},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )
        mock_redis = MagicMock()

        with patch("backend.api.routes.alertmanager.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock()
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is True
        mock_broadcaster._redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_failure_returns_false(self) -> None:
        """Test that broadcast returns False when publish fails."""
        alert = PrometheusAlert(
            id=1,
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "Test", "severity": "warning"},
            annotations={"summary": "Test alert"},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )
        mock_redis = MagicMock()

        with patch("backend.api.routes.alertmanager.EventBroadcaster") as mock_broadcaster_cls:
            mock_broadcaster = MagicMock()
            mock_broadcaster._redis = MagicMock()
            mock_broadcaster._redis.publish = AsyncMock(side_effect=Exception("Publish failed"))
            mock_broadcaster.channel_name = "events"
            mock_broadcaster_cls.get_instance = MagicMock(return_value=mock_broadcaster)

            result = await _broadcast_prometheus_alert(alert, redis_client=mock_redis)

        assert result is False


class TestAlertmanagerSchemas:
    """Tests for Alertmanager webhook Pydantic schemas."""

    def test_prometheus_alert_status_enum_values(self) -> None:
        """Test PrometheusAlertStatus enum values."""
        assert PrometheusAlertStatus.FIRING == "firing"
        assert PrometheusAlertStatus.RESOLVED == "resolved"

    def test_alertmanager_alert_required_fields(self) -> None:
        """Test AlertmanagerAlert with required fields only."""
        alert = AlertmanagerAlert(
            fingerprint="test-fp",
            status=PrometheusAlertStatus.FIRING,
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
        )
        assert alert.status == PrometheusAlertStatus.FIRING
        assert alert.fingerprint == "test-fp"
        assert alert.labels == {}
        assert alert.annotations == {}

    def test_alertmanager_alert_all_fields(self) -> None:
        """Test AlertmanagerAlert with all fields."""
        alert = AlertmanagerAlert(
            fingerprint="full-fp",
            status=PrometheusAlertStatus.RESOLVED,
            labels={"alertname": "Test", "severity": "critical"},
            annotations={"summary": "Test summary", "description": "Test desc"},
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            endsAt=datetime(2026, 1, 20, 13, 0, 0, tzinfo=UTC),
            generatorURL="http://prometheus:9090/graph",
        )
        assert alert.status == PrometheusAlertStatus.RESOLVED
        assert alert.labels["alertname"] == "Test"
        assert alert.labels["severity"] == "critical"
        assert alert.annotations["summary"] == "Test summary"
        assert alert.endsAt is not None
        assert alert.generatorURL == "http://prometheus:9090/graph"

    def test_alertmanager_webhook_payload(self) -> None:
        """Test AlertmanagerWebhook with all fields."""
        alert = AlertmanagerAlert(
            fingerprint="test-fp",
            status=PrometheusAlertStatus.FIRING,
            startsAt=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
        )
        payload = AlertmanagerWebhook(
            version="4",
            groupKey="test-group",
            status=PrometheusAlertStatus.FIRING,
            receiver="test-receiver",
            alerts=[alert],
        )
        assert payload.version == "4"
        assert payload.groupKey == "test-group"
        assert payload.receiver == "test-receiver"
        assert len(payload.alerts) == 1
        assert payload.truncatedAlerts == 0


class TestPrometheusAlertModel:
    """Tests for PrometheusAlert database model."""

    def test_model_creation(self) -> None:
        """Test creating a PrometheusAlert model instance."""
        alert = PrometheusAlert(
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "TestAlert", "severity": "warning"},
            annotations={"summary": "Test summary", "description": "Test description"},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )

        assert alert.fingerprint == "test-fp"
        assert alert.status == ModelPrometheusAlertStatus.FIRING
        assert alert.alertname == "TestAlert"
        assert alert.severity == "warning"
        assert alert.summary == "Test summary"
        assert alert.description == "Test description"

    def test_model_properties_with_missing_values(self) -> None:
        """Test model properties with missing label/annotation values."""
        alert = PrometheusAlert(
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={},  # No alertname or severity
            annotations={},  # No summary or description
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )

        assert alert.alertname == "unknown"
        assert alert.severity == "info"
        assert alert.summary == ""
        assert alert.description == ""

    def test_model_repr(self) -> None:
        """Test model string representation."""
        alert = PrometheusAlert(
            id=1,
            fingerprint="test-fp",
            status=ModelPrometheusAlertStatus.FIRING,
            labels={"alertname": "TestAlert"},
            annotations={},
            starts_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 1, 20, 12, 0, 5, tzinfo=UTC),
        )

        repr_str = repr(alert)
        assert "PrometheusAlert" in repr_str
        assert "test-fp" in repr_str
        assert "TestAlert" in repr_str
        assert "firing" in repr_str.lower()
