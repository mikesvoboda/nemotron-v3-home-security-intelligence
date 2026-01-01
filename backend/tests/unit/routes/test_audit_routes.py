"""Unit tests for audit API routes.

Tests cover:
- GET  /api/audit - List audit logs with filtering
- GET  /api/audit/stats - Get audit statistics
- GET  /api/audit/{audit_id} - Get specific audit log
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.audit import router
from backend.core.database import get_db
from backend.models.audit import AuditLog

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


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
def sample_audit_log() -> AuditLog:
    """Create a sample audit log for testing."""
    return AuditLog(
        id=1,
        action="camera_created",
        resource_type="camera",
        resource_id="cam-123",
        actor="admin",
        status="success",
        details={"camera_name": "Front Door"},
        timestamp=datetime(2025, 12, 23, 10, 0, 0),
    )


# =============================================================================
# List Audit Logs Tests
# =============================================================================


class TestListAuditLogs:
    """Tests for GET /api/audit endpoint."""

    def test_list_audit_logs_empty(self, client: TestClient) -> None:
        """Test listing audit logs when none exist."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_logs",
            new_callable=AsyncMock,
        ) as mock_get_logs:
            mock_get_logs.return_value = ([], 0)

            response = client.get("/api/audit")

            assert response.status_code == 200
            data = response.json()
            assert data["logs"] == []
            assert data["count"] == 0
            assert data["limit"] == 100
            assert data["offset"] == 0

    def test_list_audit_logs_with_data(
        self, client: TestClient, sample_audit_log: AuditLog
    ) -> None:
        """Test listing audit logs with existing data."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_logs",
            new_callable=AsyncMock,
        ) as mock_get_logs:
            mock_get_logs.return_value = ([sample_audit_log], 1)

            response = client.get("/api/audit")

            assert response.status_code == 200
            data = response.json()
            assert len(data["logs"]) == 1
            assert data["count"] == 1

    def test_list_audit_logs_filter_by_action(self, client: TestClient) -> None:
        """Test filtering audit logs by action."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_logs",
            new_callable=AsyncMock,
        ) as mock_get_logs:
            mock_get_logs.return_value = ([], 0)

            response = client.get("/api/audit?action=camera_created")

            assert response.status_code == 200
            mock_get_logs.assert_called_once()
            call_args = mock_get_logs.call_args
            assert call_args.kwargs["action"] == "camera_created"

    def test_list_audit_logs_filter_by_resource_type(self, client: TestClient) -> None:
        """Test filtering audit logs by resource type."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_logs",
            new_callable=AsyncMock,
        ) as mock_get_logs:
            mock_get_logs.return_value = ([], 0)

            response = client.get("/api/audit?resource_type=camera")

            assert response.status_code == 200
            call_args = mock_get_logs.call_args
            assert call_args.kwargs["resource_type"] == "camera"

    def test_list_audit_logs_pagination(self, client: TestClient) -> None:
        """Test pagination parameters."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_logs",
            new_callable=AsyncMock,
        ) as mock_get_logs:
            mock_get_logs.return_value = ([], 0)

            response = client.get("/api/audit?limit=10&offset=20")

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 10
            assert data["offset"] == 20


# =============================================================================
# Get Audit Stats Tests
# =============================================================================


class TestGetAuditStats:
    """Tests for GET /api/audit/stats endpoint."""

    def test_get_audit_stats(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting audit statistics."""
        # Mock all the different queries
        mock_total = MagicMock()
        mock_total.scalar.return_value = 100

        mock_today = MagicMock()
        mock_today.scalar.return_value = 10

        mock_action = MagicMock()
        mock_action.__iter__ = lambda _self: iter([])

        mock_resource = MagicMock()
        mock_resource.__iter__ = lambda _self: iter([])

        mock_status = MagicMock()
        mock_status.__iter__ = lambda _self: iter([])

        mock_actors = MagicMock()
        mock_actors.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [
            mock_total,
            mock_today,
            mock_action,
            mock_resource,
            mock_status,
            mock_actors,
        ]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_logs"] == 100
        assert data["logs_today"] == 10
        assert "by_action" in data
        assert "by_resource_type" in data
        assert "by_status" in data
        assert "recent_actors" in data


# =============================================================================
# Get Audit Log Tests
# =============================================================================


class TestGetAuditLog:
    """Tests for GET /api/audit/{audit_id} endpoint."""

    def test_get_audit_log_success(self, client: TestClient, sample_audit_log: AuditLog) -> None:
        """Test getting a specific audit log."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_log_by_id",
            new_callable=AsyncMock,
        ) as mock_get_log:
            mock_get_log.return_value = sample_audit_log

            response = client.get("/api/audit/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["action"] == "camera_created"

    def test_get_audit_log_not_found(self, client: TestClient) -> None:
        """Test getting non-existent audit log returns 404."""
        with patch(
            "backend.api.routes.audit.AuditService.get_audit_log_by_id",
            new_callable=AsyncMock,
        ) as mock_get_log:
            mock_get_log.return_value = None

            response = client.get("/api/audit/999")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()
