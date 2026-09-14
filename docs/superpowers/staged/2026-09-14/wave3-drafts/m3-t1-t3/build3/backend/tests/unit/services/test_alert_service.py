"""Unit tests for AlertService WebSocket event emissions.

Tests cover:
- create_alert(): Creates alert and emits alert.created event
- update_alert(): Updates alert and emits alert.updated event
- delete_alert(): Deletes alert and emits alert.deleted event
- acknowledge_alert(): Acknowledges alert and emits alert.updated with acknowledged=True
- dismiss_alert(): Dismisses alert and emits alert.updated event
- Payload builders: Verify correct payload structure
- Error handling: Emission failures don't affect CRUD operations
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.models import Alert, AlertSeverity, AlertStatus
from backend.services.alert_service import AlertService, get_alert_service

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
# AlertService Initialization Tests
# =============================================================================


class TestAlertServiceInit:
    """Tests for AlertService initialization."""

    def test_init_with_session_only(self, mock_session: AsyncMock) -> None:
        """Test service can be initialized with session only."""
        service = AlertService(mock_session)
        assert service._session == mock_session
        assert service._emitter is None

    def test_init_with_emitter(self, mock_session: AsyncMock, mock_emitter: AsyncMock) -> None:
        """Test service can be initialized with emitter."""
        service = AlertService(mock_session, mock_emitter)
        assert service._session == mock_session
        assert service._emitter == mock_emitter

    def test_set_emitter_after_init(self, mock_session: AsyncMock, mock_emitter: AsyncMock) -> None:
        """Test emitter can be set after initialization."""
        service = AlertService(mock_session)
        assert service._emitter is None
        service.set_emitter(mock_emitter)
        assert service._emitter == mock_emitter


# =============================================================================
# create_alert Tests
# =============================================================================


class TestCreateAlert:
    """Tests for create_alert method."""

    @pytest.mark.asyncio
    async def test_creates_alert_in_database(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test creates alert record in database."""
        service = AlertService(mock_session, mock_emitter)

        # Mock refresh to set ID and timestamps
        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
            rule_id="rule-uuid",
        )

        assert alert.event_id == 1
        assert alert.severity == AlertSeverity.HIGH
        assert alert.dedup_key == "front_door:rule-123"
        assert alert.rule_id == "rule-uuid"
        assert alert.status == AlertStatus.PENDING
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_alert_created_event(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test emits alert.created WebSocket event."""
        service = AlertService(mock_session, mock_emitter)
        alert_id = str(uuid.uuid4())

        async def mock_refresh(alert: Alert) -> None:
            alert.id = alert_id
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
            correlation_id="test-corr-id",
        )

        mock_emitter.broadcast.assert_called_once()
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_CREATED
        payload = call_args[0][1]
        assert payload["id"] == alert_id
        assert payload["event_id"] == 1
        assert payload["severity"] == "high"
        assert payload["status"] == "pending"
        assert payload["dedup_key"] == "front_door:rule-123"
        assert "created_at" in payload
        assert "updated_at" in payload
        assert call_args[1]["correlation_id"] == "test-corr-id"

    @pytest.mark.asyncio
    async def test_creates_alert_without_emitter(self, mock_session: AsyncMock) -> None:
        """Test creates alert when no emitter is configured."""
        service = AlertService(mock_session, emitter=None)

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        # Should not raise even without emitter
        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
        )

        assert alert is not None
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emission_failure_does_not_affect_create(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test emission failure doesn't affect alert creation."""
        service = AlertService(mock_session, mock_emitter)
        mock_emitter.broadcast.side_effect = Exception("Emission failed")

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        # Should not raise despite emission failure
        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
        )

        assert alert is not None
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_alert_with_optional_fields(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test creates alert with all optional fields."""
        service = AlertService(mock_session, mock_emitter)

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.CRITICAL,
            dedup_key="front_door:rule-123",
            rule_id="rule-uuid",
            status=AlertStatus.DELIVERED,
            channels=["push", "email", "sms"],
            alert_metadata={"custom": "data"},
        )

        assert alert.status == AlertStatus.DELIVERED
        assert alert.channels == ["push", "email", "sms"]
        assert alert.alert_metadata == {"custom": "data"}
        assert alert.rule_id == "rule-uuid"


# =============================================================================
# get_alert Tests
# =============================================================================


class TestGetAlert:
    """Tests for get_alert method."""

    @pytest.mark.asyncio
    async def test_returns_alert_when_found(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test returns alert when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session)
        result = await service.get_alert(sample_alert.id)

        assert result == sample_alert

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        """Test returns None when alert not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session)
        result = await service.get_alert("nonexistent-id")

        assert result is None


# =============================================================================
# update_alert Tests
# =============================================================================


class TestUpdateAlert:
    """Tests for update_alert method."""

    @pytest.mark.asyncio
    async def test_updates_alert_status(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test updates alert status."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.update_alert(
            sample_alert.id,
            status=AlertStatus.DELIVERED,
        )

        assert result is not None
        assert result.status == AlertStatus.DELIVERED
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_alert_updated_event(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test emits alert.updated WebSocket event."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.update_alert(
            sample_alert.id,
            status=AlertStatus.DELIVERED,
            correlation_id="test-corr-id",
        )

        mock_emitter.broadcast.assert_called_once()
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_UPDATED
        payload = call_args[0][1]
        assert payload["id"] == sample_alert.id
        assert payload["updated_fields"] == ["status"]
        assert payload["status"] == "delivered"
        assert call_args[1]["correlation_id"] == "test-corr-id"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test returns None when alert not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.update_alert(
            "nonexistent-id",
            status=AlertStatus.DELIVERED,
        )

        assert result is None
        mock_emitter.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_emission_when_no_changes(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test no emission when no fields changed."""
        sample_alert.status = AlertStatus.PENDING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        # Update with same status
        await service.update_alert(
            sample_alert.id,
            status=AlertStatus.PENDING,
        )

        mock_emitter.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_multiple_fields(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test updates multiple fields at once."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.update_alert(
            sample_alert.id,
            status=AlertStatus.DELIVERED,
            severity=AlertSeverity.CRITICAL,
            channels=["push"],
        )

        call_args = mock_emitter.broadcast.call_args
        payload = call_args[0][1]
        assert "status" in payload["updated_fields"]
        assert "severity" in payload["updated_fields"]
        assert "channels" in payload["updated_fields"]


# =============================================================================
# delete_alert Tests
# =============================================================================


class TestDeleteAlert:
    """Tests for delete_alert method."""

    @pytest.mark.asyncio
    async def test_deletes_alert_from_database(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test deletes alert from database."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.delete_alert(sample_alert.id)

        assert result is True
        mock_session.delete.assert_called_once_with(sample_alert)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_alert_deleted_event(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test emits alert.deleted WebSocket event."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.delete_alert(
            sample_alert.id,
            reason="User request",
            correlation_id="test-corr-id",
        )

        mock_emitter.broadcast.assert_called_once()
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_DELETED
        payload = call_args[0][1]
        assert payload["id"] == sample_alert.id
        assert payload["reason"] == "User request"
        assert call_args[1]["correlation_id"] == "test-corr-id"

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test returns False when alert not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.delete_alert("nonexistent-id")

        assert result is False
        mock_session.delete.assert_not_called()
        mock_emitter.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_emission_failure_does_not_affect_delete(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test emission failure doesn't affect alert deletion."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result
        mock_emitter.broadcast.side_effect = Exception("Emission failed")

        service = AlertService(mock_session, mock_emitter)
        result = await service.delete_alert(sample_alert.id)

        assert result is True
        mock_session.delete.assert_called_once()


# =============================================================================
# acknowledge_alert Tests
# =============================================================================


class TestAcknowledgeAlert:
    """Tests for acknowledge_alert method."""

    @pytest.mark.asyncio
    async def test_acknowledges_alert(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test acknowledges alert and sets status."""
        sample_alert.status = AlertStatus.PENDING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.acknowledge_alert(sample_alert.id)

        assert result is not None
        assert result.status == AlertStatus.ACKNOWLEDGED
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_alert_updated_with_acknowledged_flag(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test emits alert.updated event with acknowledged=True."""
        sample_alert.status = AlertStatus.PENDING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.acknowledge_alert(
            sample_alert.id,
            correlation_id="test-corr-id",
        )

        mock_emitter.broadcast.assert_called_once()
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_UPDATED
        payload = call_args[0][1]
        assert payload["id"] == sample_alert.id
        assert payload["acknowledged"] is True
        assert payload["updated_fields"] == ["status"]
        assert call_args[1]["correlation_id"] == "test-corr-id"

    @pytest.mark.asyncio
    async def test_adds_acknowledged_at_to_metadata(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test adds acknowledged_at timestamp to metadata."""
        sample_alert.status = AlertStatus.PENDING
        sample_alert.alert_metadata = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.acknowledge_alert(sample_alert.id)

        assert result is not None
        assert result.alert_metadata is not None
        assert "acknowledged_at" in result.alert_metadata

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test returns None when alert not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.acknowledge_alert("nonexistent-id")

        assert result is None
        mock_emitter.broadcast.assert_not_called()


# =============================================================================
# dismiss_alert Tests
# =============================================================================


class TestDismissAlert:
    """Tests for dismiss_alert method."""

    @pytest.mark.asyncio
    async def test_dismisses_alert(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test dismisses alert and sets status."""
        sample_alert.status = AlertStatus.PENDING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.dismiss_alert(sample_alert.id)

        assert result is not None
        assert result.status == AlertStatus.DISMISSED
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_alert_updated_event(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test emits alert.updated event on dismiss."""
        sample_alert.status = AlertStatus.PENDING
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.dismiss_alert(
            sample_alert.id,
            reason="False positive",
            correlation_id="test-corr-id",
        )

        mock_emitter.broadcast.assert_called_once()
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_UPDATED
        payload = call_args[0][1]
        assert payload["id"] == sample_alert.id
        assert payload["updated_fields"] == ["status"]
        assert call_args[1]["correlation_id"] == "test-corr-id"

    @pytest.mark.asyncio
    async def test_adds_dismissed_metadata(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test adds dismissed_at and reason to metadata."""
        sample_alert.status = AlertStatus.PENDING
        sample_alert.alert_metadata = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.dismiss_alert(sample_alert.id, reason="False positive")

        assert result is not None
        assert result.alert_metadata is not None
        assert "dismissed_at" in result.alert_metadata
        assert result.alert_metadata["dismissed_reason"] == "False positive"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test returns None when alert not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.dismiss_alert("nonexistent-id")

        assert result is None
        mock_emitter.broadcast.assert_not_called()


# =============================================================================
# Payload Builder Tests
# =============================================================================


class TestPayloadBuilders:
    """Tests for payload builder methods."""

    def test_build_alert_created_payload(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test builds correct payload for alert.created."""
        service = AlertService(mock_session)
        payload = service._build_alert_created_payload(sample_alert)

        assert payload["id"] == sample_alert.id
        assert payload["event_id"] == sample_alert.event_id
        assert payload["rule_id"] == sample_alert.rule_id
        assert payload["severity"] == "high"
        assert payload["status"] == "pending"
        assert payload["dedup_key"] == sample_alert.dedup_key
        assert "created_at" in payload
        assert "updated_at" in payload

    def test_build_alert_updated_payload(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test builds correct payload for alert.updated."""
        service = AlertService(mock_session)
        payload = service._build_alert_updated_payload(
            sample_alert,
            updated_fields=["status", "severity"],
            acknowledged=False,
        )

        assert payload["id"] == sample_alert.id
        assert payload["event_id"] == sample_alert.event_id
        assert payload["rule_id"] == sample_alert.rule_id
        assert payload["updated_fields"] == ["status", "severity"]
        assert "updated_at" in payload
        assert "status" in payload
        assert "severity" in payload

    def test_build_alert_updated_payload_with_acknowledged(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test builds payload with acknowledged flag."""
        service = AlertService(mock_session)
        payload = service._build_alert_updated_payload(
            sample_alert,
            updated_fields=["status"],
            acknowledged=True,
        )

        assert payload["acknowledged"] is True

    def test_build_alert_updated_payload_without_acknowledged(
        self, mock_session: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test builds payload without acknowledged flag when False."""
        service = AlertService(mock_session)
        payload = service._build_alert_updated_payload(
            sample_alert,
            updated_fields=["status"],
            acknowledged=False,
        )

        assert "acknowledged" not in payload


# =============================================================================
# get_alert_service Factory Tests
# =============================================================================


class TestGetAlertService:
    """Tests for get_alert_service factory function."""

    @pytest.mark.asyncio
    async def test_returns_alert_service(self, mock_session: AsyncMock) -> None:
        """Test returns AlertService instance."""
        service = await get_alert_service(mock_session)
        assert isinstance(service, AlertService)
        assert service._session == mock_session
        assert service._emitter is None

    @pytest.mark.asyncio
    async def test_passes_emitter(self, mock_session: AsyncMock, mock_emitter: AsyncMock) -> None:
        """Test passes emitter to service."""
        service = await get_alert_service(mock_session, mock_emitter)
        assert service._emitter == mock_emitter


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for AlertService."""

    @pytest.mark.asyncio
    async def test_create_alert_with_empty_channels(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test creates alert with empty channels list."""
        service = AlertService(mock_session, mock_emitter)

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
            channels=[],
        )

        assert alert.channels == []

    @pytest.mark.asyncio
    async def test_update_with_none_values_does_not_update(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test None values don't trigger updates."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        await service.update_alert(
            sample_alert.id,
            status=None,
            severity=None,
        )

        # No emission since no fields changed
        mock_emitter.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_acknowledge_preserves_existing_metadata(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test acknowledge preserves existing metadata."""
        sample_alert.alert_metadata = {"existing": "data"}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.acknowledge_alert(sample_alert.id)

        assert result is not None
        assert result.alert_metadata["existing"] == "data"
        assert "acknowledged_at" in result.alert_metadata

    @pytest.mark.asyncio
    async def test_dismiss_without_reason(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock, sample_alert: Alert
    ) -> None:
        """Test dismiss without providing a reason."""
        sample_alert.alert_metadata = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_session.execute.return_value = mock_result

        service = AlertService(mock_session, mock_emitter)
        result = await service.dismiss_alert(sample_alert.id)

        assert result is not None
        assert result.alert_metadata is not None
        assert "dismissed_at" in result.alert_metadata
        assert "dismissed_reason" not in result.alert_metadata

    @pytest.mark.asyncio
    async def test_create_alert_default_status(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test default status is PENDING."""
        service = AlertService(mock_session, mock_emitter)

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
        )

        assert alert.status == AlertStatus.PENDING


# =============================================================================
# Concurrent Operations Tests
# =============================================================================


class TestConcurrentOperations:
    """Tests for concurrent operation scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_creates_have_unique_ids(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test multiple creates generate unique alert IDs."""
        service = AlertService(mock_session, mock_emitter)
        alert_ids = []

        async def mock_refresh(alert: Alert) -> None:
            alert.id = str(uuid.uuid4())
            alert_ids.append(alert.id)
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh

        for i in range(3):
            await service.create_alert(
                event_id=i,
                severity=AlertSeverity.HIGH,
                dedup_key=f"key-{i}",
            )

        assert len(set(alert_ids)) == 3  # All IDs should be unique


# =============================================================================
# Integration-Like Tests (Mocked but Full Flow)
# =============================================================================


class TestFullFlows:
    """Tests that exercise full operation flows."""

    @pytest.mark.asyncio
    async def test_create_acknowledge_dismiss_flow(
        self, mock_session: AsyncMock, mock_emitter: AsyncMock
    ) -> None:
        """Test full lifecycle: create -> acknowledge -> dismiss."""
        service = AlertService(mock_session, mock_emitter)
        alert_id = str(uuid.uuid4())

        # Create alert
        async def mock_refresh_create(alert: Alert) -> None:
            alert.id = alert_id
            alert.created_at = datetime.now(UTC)
            alert.updated_at = datetime.now(UTC)

        mock_session.refresh.side_effect = mock_refresh_create
        alert = await service.create_alert(
            event_id=1,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:rule-123",
        )

        # Verify created emission
        assert mock_emitter.broadcast.call_count == 1
        assert mock_emitter.broadcast.call_args[0][0] == WebSocketEventType.ALERT_CREATED

        # Acknowledge alert
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        mock_session.execute.return_value = mock_result
        mock_session.refresh.side_effect = AsyncMock()

        await service.acknowledge_alert(alert_id)

        # Verify acknowledged emission
        assert mock_emitter.broadcast.call_count == 2
        call_args = mock_emitter.broadcast.call_args
        assert call_args[0][0] == WebSocketEventType.ALERT_UPDATED
        assert call_args[0][1]["acknowledged"] is True

        # Dismiss alert
        await service.dismiss_alert(alert_id, reason="Resolved")

        # Verify dismissed emission
        assert mock_emitter.broadcast.call_count == 3
        assert mock_emitter.broadcast.call_args[0][0] == WebSocketEventType.ALERT_UPDATED
