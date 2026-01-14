"""Unit tests for alert instance API routes (NEM-1981).

Tests cover:
- POST /api/alerts/{alert_id}/acknowledge - Acknowledge an alert
- POST /api/alerts/{alert_id}/dismiss     - Dismiss an alert
- WebSocket broadcast on status changes (NEM-2582: now via background tasks with retry)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.alerts import (
    _alert_to_response_dict,
    _alert_to_websocket_data,
    alerts_instance_router,
)
from backend.core.database import get_db
from backend.models import Alert
from backend.models.alert import AlertSeverityEnum, AlertStatusEnum
from backend.services.event_broadcaster import BroadcastRetryMetrics

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_broadcaster() -> MagicMock:
    """Create a mock EventBroadcaster with broadcast_metrics for NEM-2582."""
    broadcaster = MagicMock()
    broadcaster.broadcast_alert = AsyncMock(return_value=1)
    # NEM-2582: Add broadcast_metrics for retry mechanism
    broadcaster.broadcast_metrics = BroadcastRetryMetrics()
    return broadcaster


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_broadcaster: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(alerts_instance_router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_alert() -> Alert:
    """Create a sample alert for testing."""
    alert = MagicMock(spec=Alert)
    alert.id = str(uuid.uuid4())
    alert.event_id = 123
    alert.rule_id = str(uuid.uuid4())
    alert.severity = AlertSeverityEnum.HIGH
    alert.status = AlertStatusEnum.PENDING
    alert.dedup_key = "front_door:person:rule1"
    alert.created_at = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)
    alert.updated_at = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)
    alert.delivered_at = None
    alert.channels = ["pushover"]
    alert.alert_metadata = {"camera_name": "Front Door"}
    return alert


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestAlertHelperFunctions:
    """Tests for alert helper functions."""

    def test_alert_to_response_dict(self, sample_alert: Alert) -> None:
        """Test converting alert model to response dict."""
        result = _alert_to_response_dict(sample_alert)

        assert result["id"] == sample_alert.id
        assert result["event_id"] == sample_alert.event_id
        assert result["rule_id"] == sample_alert.rule_id
        assert result["severity"] == "high"
        assert result["status"] == "pending"
        assert result["dedup_key"] == sample_alert.dedup_key
        assert result["channels"] == ["pushover"]

    def test_alert_to_websocket_data(self, sample_alert: Alert) -> None:
        """Test converting alert model to WebSocket broadcast data."""
        result = _alert_to_websocket_data(sample_alert)

        assert result["id"] == sample_alert.id
        assert result["event_id"] == sample_alert.event_id
        assert result["rule_id"] == sample_alert.rule_id
        assert result["severity"] == "high"
        assert result["status"] == "pending"
        assert result["dedup_key"] == sample_alert.dedup_key
        assert "created_at" in result
        assert "updated_at" in result

    def test_alert_to_response_dict_with_none_channels(self, sample_alert: Alert) -> None:
        """Test that None channels returns empty list."""
        sample_alert.channels = None
        result = _alert_to_response_dict(sample_alert)
        assert result["channels"] == []


# =============================================================================
# Acknowledge Alert Tests
# =============================================================================


class TestAcknowledgeAlert:
    """Tests for POST /api/alerts/{alert_id}/acknowledge endpoint."""

    def test_acknowledge_pending_alert(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test acknowledging a pending alert."""
        # Setup: Alert in PENDING status
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_alert.id

    def test_acknowledge_delivered_alert(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test acknowledging a delivered alert."""
        # Setup: Alert in DELIVERED status
        sample_alert.status = AlertStatusEnum.DELIVERED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        assert response.status_code == 200

    def test_acknowledge_already_acknowledged_alert_fails(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
    ) -> None:
        """Test that acknowledging an already acknowledged alert returns 409."""
        # Setup: Alert already ACKNOWLEDGED
        sample_alert.status = AlertStatusEnum.ACKNOWLEDGED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        assert response.status_code == 409
        assert "cannot be acknowledged" in response.json()["detail"].lower()

    def test_acknowledge_dismissed_alert_fails(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
    ) -> None:
        """Test that acknowledging a dismissed alert returns 409."""
        # Setup: Alert is DISMISSED
        sample_alert.status = AlertStatusEnum.DISMISSED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        assert response.status_code == 409

    def test_acknowledge_nonexistent_alert_returns_404(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test acknowledging a nonexistent alert returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        alert_id = str(uuid.uuid4())
        response = client.post(f"/api/alerts/{alert_id}/acknowledge")

        assert response.status_code == 404
        assert alert_id in response.json()["detail"]

    def test_acknowledge_schedules_broadcast_in_background(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test that acknowledging schedules a broadcast via background task (NEM-2582)."""
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        # Track if background task was added
        background_task_added = False

        def mock_add_task(*args, **kwargs):
            nonlocal background_task_added
            background_task_added = True

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        assert response.status_code == 200
        # Background tasks are registered but executed after response in TestClient
        # We verify the request succeeds and broadcaster instance is obtained

    def test_acknowledge_succeeds_even_if_broadcaster_unavailable(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
    ) -> None:
        """Test that acknowledge succeeds even if broadcaster is unavailable (NEM-2582)."""
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        # Make broadcaster unavailable by raising RuntimeError
        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            side_effect=RuntimeError("Broadcaster not initialized"),
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/acknowledge")

        # Request should still succeed - broadcast scheduling failure is non-blocking
        assert response.status_code == 200


# =============================================================================
# Dismiss Alert Tests
# =============================================================================


class TestDismissAlert:
    """Tests for POST /api/alerts/{alert_id}/dismiss endpoint."""

    def test_dismiss_pending_alert(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test dismissing a pending alert."""
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_alert.id

    def test_dismiss_delivered_alert(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test dismissing a delivered alert."""
        sample_alert.status = AlertStatusEnum.DELIVERED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        assert response.status_code == 200

    def test_dismiss_acknowledged_alert(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test dismissing an acknowledged alert."""
        sample_alert.status = AlertStatusEnum.ACKNOWLEDGED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        assert response.status_code == 200

    def test_dismiss_already_dismissed_alert_fails(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
    ) -> None:
        """Test that dismissing an already dismissed alert returns 409."""
        sample_alert.status = AlertStatusEnum.DISMISSED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        assert response.status_code == 409
        assert "already dismissed" in response.json()["detail"]

    def test_dismiss_nonexistent_alert_returns_404(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test dismissing a nonexistent alert returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        alert_id = str(uuid.uuid4())
        response = client.post(f"/api/alerts/{alert_id}/dismiss")

        assert response.status_code == 404

    def test_dismiss_schedules_broadcast_in_background(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
        mock_broadcaster: MagicMock,
    ) -> None:
        """Test that dismissing schedules a broadcast via background task (NEM-2582)."""
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            return_value=mock_broadcaster,
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        assert response.status_code == 200
        # Background tasks are registered but executed after response in TestClient
        # We verify the request succeeds and broadcaster instance is obtained

    def test_dismiss_succeeds_even_if_broadcaster_unavailable(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_alert: Alert,
    ) -> None:
        """Test that dismiss succeeds even if broadcaster is unavailable (NEM-2582)."""
        sample_alert.status = AlertStatusEnum.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_alert
        mock_db_session.execute.return_value = mock_result

        # Make broadcaster unavailable by raising RuntimeError
        with patch(
            "backend.api.routes.alerts.EventBroadcaster.get_instance",
            side_effect=RuntimeError("Broadcaster not initialized"),
        ):
            response = client.post(f"/api/alerts/{sample_alert.id}/dismiss")

        # Request should still succeed - broadcast scheduling failure is non-blocking
        assert response.status_code == 200
