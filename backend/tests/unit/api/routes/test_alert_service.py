"""Unit tests for Alert Service CRUD API routes.

Tests the API endpoints for Alert Service CRUD operations (NEM-4931).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Alert, AlertSeverity, AlertStatus


class TestListAlerts:
    """Tests for GET /api/alert-service/alerts endpoint."""

    @pytest.mark.asyncio
    async def test_list_alerts_success(self) -> None:
        """Test listing alerts returns all alerts with pagination."""
        from backend.api.routes.alert_service import list_alerts

        mock_db = AsyncMock()

        # Mock alerts query
        mock_alert1 = MagicMock(spec=Alert)
        mock_alert1.id = "alert-id-1"
        mock_alert1.event_id = 1
        mock_alert1.rule_id = None
        mock_alert1.severity = AlertSeverity.HIGH
        mock_alert1.status = AlertStatus.PENDING
        mock_alert1.dedup_key = "key1"
        mock_alert1.channels = ["pushover"]
        mock_alert1.alert_metadata = None
        mock_alert1.created_at = datetime(2025, 1, 31, tzinfo=UTC)
        mock_alert1.updated_at = datetime(2025, 1, 31, tzinfo=UTC)
        mock_alert1.delivered_at = None

        mock_alert2 = MagicMock(spec=Alert)
        mock_alert2.id = "alert-id-2"
        mock_alert2.event_id = 2
        mock_alert2.rule_id = "rule-123"
        mock_alert2.severity = AlertSeverity.MEDIUM
        mock_alert2.status = AlertStatus.ACKNOWLEDGED
        mock_alert2.dedup_key = "key2"
        mock_alert2.channels = []
        mock_alert2.alert_metadata = {"note": "test"}
        mock_alert2.created_at = datetime(2025, 1, 30, tzinfo=UTC)
        mock_alert2.updated_at = datetime(2025, 1, 30, tzinfo=UTC)
        mock_alert2.delivered_at = None

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock alerts query result
        mock_alerts_result = MagicMock()
        mock_alerts_result.scalars.return_value.all.return_value = [
            mock_alert1,
            mock_alert2,
        ]

        mock_db.execute.side_effect = [mock_count_result, mock_alerts_result]

        result = await list_alerts(
            status_filter=None,
            severity_filter=None,
            event_id=None,
            rule_id=None,
            limit=50,
            offset=0,
            db=mock_db,
        )

        assert len(result.items) == 2
        assert result.pagination.total == 2
        assert result.items[0].id == "alert-id-1"
        assert result.items[1].id == "alert-id-2"

    @pytest.mark.asyncio
    async def test_list_alerts_empty(self) -> None:
        """Test listing alerts returns empty list."""
        from backend.api.routes.alert_service import list_alerts

        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_alerts_result = MagicMock()
        mock_alerts_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_count_result, mock_alerts_result]

        result = await list_alerts(
            status_filter=None,
            severity_filter=None,
            event_id=None,
            rule_id=None,
            limit=50,
            offset=0,
            db=mock_db,
        )

        assert result.items == []
        assert result.pagination.total == 0

    @pytest.mark.asyncio
    async def test_list_alerts_with_filters(self) -> None:
        """Test listing alerts with status and severity filters."""
        from backend.api.routes.alert_service import list_alerts
        from backend.api.schemas.alerts import AlertSeverity as SchemaSeverity
        from backend.api.schemas.alerts import AlertStatus as SchemaStatus

        mock_db = AsyncMock()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "filtered-alert"
        mock_alert.event_id = 1
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.CRITICAL
        mock_alert.status = AlertStatus.PENDING
        mock_alert.dedup_key = "key"
        mock_alert.channels = []
        mock_alert.alert_metadata = None
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        mock_alerts_result = MagicMock()
        mock_alerts_result.scalars.return_value.all.return_value = [mock_alert]

        mock_db.execute.side_effect = [mock_count_result, mock_alerts_result]

        result = await list_alerts(
            status_filter=SchemaStatus.PENDING,
            severity_filter=SchemaSeverity.CRITICAL,
            event_id=None,
            rule_id=None,
            limit=50,
            offset=0,
            db=mock_db,
        )

        assert len(result.items) == 1
        assert result.items[0].id == "filtered-alert"


class TestGetAlert:
    """Tests for GET /api/alert-service/alerts/{alert_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_alert_success(self) -> None:
        """Test getting an alert by ID."""
        from backend.api.routes.alert_service import get_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "test-alert-id"
        mock_alert.event_id = 123
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.HIGH
        mock_alert.status = AlertStatus.PENDING
        mock_alert.dedup_key = "test:key"
        mock_alert.channels = []
        mock_alert.alert_metadata = None
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        with patch.object(AlertService, "get_alert", return_value=mock_alert):
            result = await get_alert(alert_id="test-alert-id", db=mock_db)

        assert result.id == "test-alert-id"
        assert result.event_id == 123

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self) -> None:
        """Test getting a non-existent alert returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.alert_service import get_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "get_alert", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_alert(alert_id="nonexistent", db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestCreateAlert:
    """Tests for POST /api/alert-service/alerts endpoint."""

    @pytest.mark.asyncio
    async def test_create_alert_success(self) -> None:
        """Test successfully creating an alert."""
        from backend.api.routes.alert_service import create_alert
        from backend.api.schemas.alert_service import AlertServiceCreateRequest
        from backend.api.schemas.alerts import AlertSeverity as SchemaSeverity
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "new-alert-id"
        mock_alert.event_id = 456
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.HIGH
        mock_alert.status = AlertStatus.PENDING
        mock_alert.dedup_key = "test:create"
        mock_alert.channels = ["webhook"]
        mock_alert.alert_metadata = {"source": "test"}
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        request = AlertServiceCreateRequest(
            event_id=456,
            severity=SchemaSeverity.HIGH,
            dedup_key="test:create",
            channels=["webhook"],
            metadata={"source": "test"},
        )

        with patch.object(AlertService, "create_alert", return_value=mock_alert):
            result = await create_alert(alert_data=request, db=mock_db)

        assert result.id == "new-alert-id"
        assert result.event_id == 456
        mock_db.commit.assert_called_once()


class TestUpdateAlert:
    """Tests for PUT /api/alert-service/alerts/{alert_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_alert_success(self) -> None:
        """Test successfully updating an alert."""
        from backend.api.routes.alert_service import update_alert
        from backend.api.schemas.alert_service import AlertServiceUpdateRequest
        from backend.api.schemas.alerts import AlertStatus as SchemaStatus
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "update-alert-id"
        mock_alert.event_id = 789
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.MEDIUM
        mock_alert.status = AlertStatus.ACKNOWLEDGED
        mock_alert.dedup_key = "test:update"
        mock_alert.channels = []
        mock_alert.alert_metadata = None
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        request = AlertServiceUpdateRequest(status=SchemaStatus.ACKNOWLEDGED)

        with patch.object(AlertService, "update_alert", return_value=mock_alert):
            result = await update_alert(alert_id="update-alert-id", alert_data=request, db=mock_db)

        assert result.id == "update-alert-id"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_alert_not_found(self) -> None:
        """Test updating a non-existent alert returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.alert_service import update_alert
        from backend.api.schemas.alert_service import AlertServiceUpdateRequest
        from backend.api.schemas.alerts import AlertStatus as SchemaStatus
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()
        request = AlertServiceUpdateRequest(status=SchemaStatus.ACKNOWLEDGED)

        with patch.object(AlertService, "update_alert", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await update_alert(alert_id="nonexistent", alert_data=request, db=mock_db)

        assert exc_info.value.status_code == 404


class TestDeleteAlert:
    """Tests for DELETE /api/alert-service/alerts/{alert_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_alert_success(self) -> None:
        """Test successfully deleting an alert."""
        from backend.api.routes.alert_service import delete_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "delete_alert", return_value=True):
            result = await delete_alert(alert_id="delete-alert-id", db=mock_db)

        assert result.success is True
        assert result.deleted_id == "delete-alert-id"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_alert_not_found(self) -> None:
        """Test deleting a non-existent alert returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.alert_service import delete_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "delete_alert", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await delete_alert(alert_id="nonexistent", db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_alert_with_reason(self) -> None:
        """Test deleting an alert with reason."""
        from backend.api.routes.alert_service import delete_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "delete_alert", return_value=True) as mock_delete:
            result = await delete_alert(alert_id="test-id", reason="Test deletion", db=mock_db)

        assert result.success is True
        mock_delete.assert_called_once()
        # Verify reason was passed
        call_kwargs = mock_delete.call_args.kwargs
        assert call_kwargs.get("reason") == "Test deletion"


class TestAcknowledgeAlert:
    """Tests for POST /api/alert-service/alerts/{alert_id}/acknowledge endpoint."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert_success(self) -> None:
        """Test successfully acknowledging an alert."""
        from backend.api.routes.alert_service import acknowledge_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "ack-alert-id"
        mock_alert.event_id = 100
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.HIGH
        mock_alert.status = AlertStatus.ACKNOWLEDGED
        mock_alert.dedup_key = "test:ack"
        mock_alert.channels = []
        mock_alert.alert_metadata = {"acknowledged_at": "2025-01-31T12:00:00Z"}
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        with patch.object(AlertService, "acknowledge_alert", return_value=mock_alert):
            result = await acknowledge_alert(alert_id="ack-alert-id", db=mock_db)

        assert result.id == "ack-alert-id"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self) -> None:
        """Test acknowledging a non-existent alert returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.alert_service import acknowledge_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "acknowledge_alert", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await acknowledge_alert(alert_id="nonexistent", db=mock_db)

        assert exc_info.value.status_code == 404


class TestDismissAlert:
    """Tests for POST /api/alert-service/alerts/{alert_id}/dismiss endpoint."""

    @pytest.mark.asyncio
    async def test_dismiss_alert_success(self) -> None:
        """Test successfully dismissing an alert."""
        from backend.api.routes.alert_service import dismiss_alert
        from backend.api.schemas.alert_service import DismissRequest
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "dismiss-alert-id"
        mock_alert.event_id = 200
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.MEDIUM
        mock_alert.status = AlertStatus.DISMISSED
        mock_alert.dedup_key = "test:dismiss"
        mock_alert.channels = []
        mock_alert.alert_metadata = {"dismissed_reason": "False positive"}
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        request = DismissRequest(reason="False positive")

        with patch.object(AlertService, "dismiss_alert", return_value=mock_alert):
            result = await dismiss_alert(alert_id="dismiss-alert-id", request=request, db=mock_db)

        assert result.id == "dismiss-alert-id"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_dismiss_alert_without_reason(self) -> None:
        """Test dismissing an alert without reason."""
        from backend.api.routes.alert_service import dismiss_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = "dismiss-id"
        mock_alert.event_id = 300
        mock_alert.rule_id = None
        mock_alert.severity = AlertSeverity.LOW
        mock_alert.status = AlertStatus.DISMISSED
        mock_alert.dedup_key = "key"
        mock_alert.channels = []
        mock_alert.alert_metadata = None
        mock_alert.created_at = datetime.now(UTC)
        mock_alert.updated_at = datetime.now(UTC)
        mock_alert.delivered_at = None

        with patch.object(AlertService, "dismiss_alert", return_value=mock_alert):
            result = await dismiss_alert(alert_id="dismiss-id", db=mock_db)

        assert result.id == "dismiss-id"

    @pytest.mark.asyncio
    async def test_dismiss_alert_not_found(self) -> None:
        """Test dismissing a non-existent alert returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.alert_service import dismiss_alert
        from backend.services.alert_service import AlertService

        mock_db = AsyncMock()

        with patch.object(AlertService, "dismiss_alert", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await dismiss_alert(alert_id="nonexistent", db=mock_db)

        assert exc_info.value.status_code == 404
