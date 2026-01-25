"""Unit tests for webhook integration in event handlers (NEM-3624).

Tests verify that webhooks are triggered correctly when:
- Alerts are created (ALERT_FIRED)
- Alerts are acknowledged (ALERT_ACKNOWLEDGED)
- Alerts are dismissed (ALERT_DISMISSED)
- Events are created (EVENT_CREATED)
- Entities are discovered (ENTITY_DISCOVERED)

These tests focus on verifying the integration points call the webhook
service correctly, without testing the webhook delivery itself.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.models import Alert, AlertSeverity, AlertStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_emitter() -> AsyncMock:
    """Create a mock WebSocket emitter."""
    emitter = AsyncMock()
    emitter.broadcast = AsyncMock(return_value=True)
    return emitter


@pytest.fixture
def mock_webhook_service() -> MagicMock:
    """Create a mock webhook service."""
    service = MagicMock()
    service.trigger_webhooks_for_event = AsyncMock()
    return service


@pytest.fixture
def sample_alert() -> Alert:
    """Create a sample alert for testing."""
    alert = Alert(
        id=str(uuid.uuid4()),
        event_id=1,
        rule_id=str(uuid.uuid4()),
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        dedup_key="front_door:rule-123",
        channels=["push", "email"],
        alert_metadata={"test": "data"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return alert


# =============================================================================
# AlertService Webhook Integration Tests
# =============================================================================


class TestAlertServiceWebhookIntegration:
    """Tests for webhook integration in AlertService."""

    @pytest.mark.asyncio
    async def test_create_alert_triggers_webhook(
        self,
        mock_session: AsyncMock,
        mock_emitter: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that create_alert triggers ALERT_FIRED webhook."""
        from backend.services.alert_service import AlertService

        with patch(
            "backend.services.alert_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = AlertService(mock_session, mock_emitter)

            await service.create_alert(
                event_id=1,
                severity=AlertSeverity.HIGH,
                dedup_key="camera1:rule1",
            )

            # Verify webhook was triggered
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            assert call_args[0][1] == WebhookEventType.ALERT_FIRED

    @pytest.mark.asyncio
    async def test_acknowledge_alert_triggers_webhook(
        self,
        mock_session: AsyncMock,
        mock_emitter: AsyncMock,
        mock_webhook_service: MagicMock,
        sample_alert: Alert,
    ) -> None:
        """Test that acknowledge_alert triggers ALERT_ACKNOWLEDGED webhook."""
        from backend.services.alert_service import AlertService

        # Mock get_alert to return sample alert
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.alert_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = AlertService(mock_session, mock_emitter)

            await service.acknowledge_alert(alert_id=sample_alert.id)

            # Verify webhook was triggered
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            assert call_args[0][1] == WebhookEventType.ALERT_ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_dismiss_alert_triggers_webhook(
        self,
        mock_session: AsyncMock,
        mock_emitter: AsyncMock,
        mock_webhook_service: MagicMock,
        sample_alert: Alert,
    ) -> None:
        """Test that dismiss_alert triggers ALERT_DISMISSED webhook."""
        from backend.services.alert_service import AlertService

        # Mock get_alert to return sample alert
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        with patch(
            "backend.services.alert_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = AlertService(mock_session, mock_emitter)

            await service.dismiss_alert(alert_id=sample_alert.id, reason="Test reason")

            # Verify webhook was triggered
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            assert call_args[0][1] == WebhookEventType.ALERT_DISMISSED
            # Verify reason is included in data
            webhook_data = call_args[0][2]
            assert webhook_data.get("dismissed_reason") == "Test reason"

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_fail_alert_creation(
        self,
        mock_session: AsyncMock,
        mock_emitter: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that webhook failure doesn't prevent alert creation."""
        from backend.services.alert_service import AlertService

        # Make webhook trigger raise an exception
        mock_webhook_service.trigger_webhooks_for_event.side_effect = RuntimeError("Webhook failed")

        with patch(
            "backend.services.alert_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = AlertService(mock_session, mock_emitter)

            # Should not raise even though webhook failed
            alert = await service.create_alert(
                event_id=1,
                severity=AlertSeverity.HIGH,
                dedup_key="camera1:rule1",
            )

            assert alert is not None
            mock_session.add.assert_called_once()


# =============================================================================
# AlertEngine Webhook Integration Tests
# =============================================================================


class TestAlertEngineWebhookIntegration:
    """Tests for webhook integration in AlertRuleEngine."""

    @pytest.mark.asyncio
    async def test_create_alerts_triggers_webhooks(
        self,
        mock_session: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that create_alerts_for_event triggers ALERT_FIRED webhooks."""
        from backend.models import AlertRule, Event
        from backend.services.alert_engine import AlertRuleEngine, TriggeredRule

        with patch(
            "backend.services.alert_engine.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            engine = AlertRuleEngine(mock_session)

            # Create mock event
            event = MagicMock(spec=Event)
            event.id = 1
            event.camera_id = "front_door"
            event.risk_score = 75

            # Create mock rule
            rule = MagicMock(spec=AlertRule)
            rule.id = str(uuid.uuid4())
            rule.name = "High Risk Alert"
            rule.channels = ["push"]

            triggered = TriggeredRule(
                rule=rule,
                severity=AlertSeverity.HIGH,
                matched_conditions=["risk_threshold"],
                dedup_key="front_door:rule1",
            )

            await engine.create_alerts_for_event(event, [triggered])

            # Verify webhook was triggered
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            assert call_args[0][1] == WebhookEventType.ALERT_FIRED


# =============================================================================
# EntityClusteringService Webhook Integration Tests
# =============================================================================


class TestEntityClusteringWebhookIntegration:
    """Tests for webhook integration in EntityClusteringService.

    Note: These tests use higher-level mocking to avoid SQLAlchemy's
    flag_modified() which requires actual ORM instances. We test the
    webhook trigger helper method directly to verify integration.
    """

    @pytest.mark.asyncio
    async def test_trigger_entity_discovered_webhook(
        self,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test the _trigger_entity_discovered_webhook method directly."""
        from backend.models import Entity
        from backend.services.entity_clustering_service import EntityClusteringService

        # Create mock repository
        mock_repo = MagicMock()
        mock_repo.session = AsyncMock()

        # Create a real Entity instance for the test
        entity = Entity(
            entity_type="person",
            trust_status="unknown",
            first_seen_at=datetime.now(UTC),
            detection_count=1,
        )

        with patch(
            "backend.services.entity_clustering_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = EntityClusteringService(entity_repository=mock_repo)

            # Call the webhook trigger method directly
            await service._trigger_entity_discovered_webhook(
                entity=entity,
                camera_id="front_door",
            )

            # Verify webhook was triggered
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
            call_args = mock_webhook_service.trigger_webhooks_for_event.call_args
            assert call_args[0][1] == WebhookEventType.ENTITY_DISCOVERED

            # Verify webhook data contains expected fields
            webhook_data = call_args[0][2]
            assert "entity_id" in webhook_data
            assert webhook_data["entity_type"] == "person"
            assert webhook_data["camera_id"] == "front_door"
            assert webhook_data["trust_status"] == "unknown"

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_fail_entity_creation(
        self,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that webhook failure doesn't prevent entity webhook trigger."""
        from backend.models import Entity
        from backend.services.entity_clustering_service import EntityClusteringService

        # Make webhook trigger raise an exception
        mock_webhook_service.trigger_webhooks_for_event.side_effect = RuntimeError("Webhook failed")

        # Create mock repository
        mock_repo = MagicMock()
        mock_repo.session = AsyncMock()

        # Create a real Entity instance for the test
        entity = Entity(
            entity_type="person",
            trust_status="unknown",
            first_seen_at=datetime.now(UTC),
            detection_count=1,
        )

        with patch(
            "backend.services.entity_clustering_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            service = EntityClusteringService(entity_repository=mock_repo)

            # Should not raise even though webhook failed
            await service._trigger_entity_discovered_webhook(
                entity=entity,
                camera_id="front_door",
            )

            # Verify the service was called (even though it failed)
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()


# =============================================================================
# trigger_webhook_background Function Tests
# =============================================================================


class TestTriggerWebhookBackground:
    """Tests for the trigger_webhook_background helper function."""

    @pytest.mark.asyncio
    async def test_trigger_webhook_background_calls_service(
        self,
        mock_session: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that trigger_webhook_background calls webhook service correctly."""
        from backend.services.webhook_service import trigger_webhook_background

        with patch(
            "backend.services.webhook_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            await trigger_webhook_background(
                db=mock_session,
                event_type=WebhookEventType.ALERT_FIRED,
                event_data={"alert_id": "test-123"},
                event_id="test-123",
            )

            mock_webhook_service.trigger_webhooks_for_event.assert_called_once_with(
                mock_session,
                WebhookEventType.ALERT_FIRED,
                {"alert_id": "test-123"},
                event_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_trigger_webhook_background_handles_errors(
        self,
        mock_session: AsyncMock,
        mock_webhook_service: MagicMock,
    ) -> None:
        """Test that trigger_webhook_background handles errors gracefully."""
        from backend.services.webhook_service import trigger_webhook_background

        mock_webhook_service.trigger_webhooks_for_event.side_effect = RuntimeError("Test error")

        with patch(
            "backend.services.webhook_service.get_webhook_service",
            return_value=mock_webhook_service,
        ):
            # Should not raise even though service failed
            await trigger_webhook_background(
                db=mock_session,
                event_type=WebhookEventType.ALERT_FIRED,
                event_data={"alert_id": "test-123"},
                event_id="test-123",
            )

            # Verify the service was called
            mock_webhook_service.trigger_webhooks_for_event.assert_called_once()
