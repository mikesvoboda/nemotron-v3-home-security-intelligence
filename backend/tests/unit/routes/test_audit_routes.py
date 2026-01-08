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
    """Tests for GET /api/audit endpoint.

    The endpoint now uses direct database queries with cursor-based pagination
    instead of the AuditService.get_audit_logs() method.
    """

    def test_list_audit_logs_empty(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test listing audit logs when none exist."""
        # Mock execute for count query - scalar() is sync
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # Mock execute for logs query - scalars().all() are sync
        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []

        # Both queries return their respective results
        mock_db_session.execute = AsyncMock(side_effect=[count_result, logs_result])

        response = client.get("/api/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert data["count"] == 0
        assert data["limit"] == 100
        assert data["offset"] == 0

    def test_list_audit_logs_with_data(
        self, client: TestClient, sample_audit_log: AuditLog, mock_db_session: AsyncMock
    ) -> None:
        """Test listing audit logs with existing data."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        # Mock logs query
        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = [sample_audit_log]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, logs_result])

        response = client.get("/api/audit")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["count"] == 1

    def test_list_audit_logs_filter_by_action(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering audit logs by action."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, logs_result])

        response = client.get("/api/audit?action=camera_created")

        assert response.status_code == 200
        # Verify execute was called (filter is applied in the query)
        assert mock_db_session.execute.call_count == 2

    def test_list_audit_logs_filter_by_resource_type(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering audit logs by resource type."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, logs_result])

        response = client.get("/api/audit?resource_type=camera")

        assert response.status_code == 200
        # Verify execute was called (filter is applied in the query)
        assert mock_db_session.execute.call_count == 2

    def test_list_audit_logs_pagination(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test pagination parameters."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, logs_result])

        response = client.get("/api/audit?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


# =============================================================================
# Get Audit Stats Tests
# =============================================================================


class TestGetAuditStats:
    """Tests for GET /api/audit/stats endpoint.

    The endpoint uses an optimized query strategy:
    - One UNION ALL query for total, today, by_action, by_resource_type, by_status
    - One separate query for recent_actors (requires different filtering)
    """

    def test_get_audit_stats(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting audit statistics with optimized 2-query implementation."""
        # Mock the combined UNION ALL query result
        # Returns rows with (category, key, count) structure - uses tuples for index access
        mock_combined_result = MagicMock()
        mock_combined_result.fetchall.return_value = [
            ("total", "all", 100),
            ("today", "all", 10),
            ("action", "camera_created", 25),
            ("resource_type", "camera", 30),
            ("status", "success", 95),
        ]

        # Mock the recent actors query result
        mock_actor_row = MagicMock()
        mock_actor_row.actor = "admin"
        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([mock_actor_row])

        # Set up the mock to return different results for the 2 queries
        mock_db_session.execute.side_effect = [
            mock_combined_result,
            mock_actors_result,
        ]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_logs"] == 100
        assert data["logs_today"] == 10
        assert data["by_action"] == {"camera_created": 25}
        assert data["by_resource_type"] == {"camera": 30}
        assert data["by_status"] == {"success": 95}
        assert data["recent_actors"] == ["admin"]

        # Verify only 2 database queries were made (optimized from 6)
        assert mock_db_session.execute.call_count == 2

    def test_get_audit_stats_empty_data(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test getting audit statistics when no data exists."""
        # Mock empty UNION ALL query result - uses tuples for index access
        mock_combined_result = MagicMock()
        mock_combined_result.fetchall.return_value = [
            ("total", "all", 0),
            ("today", "all", 0),
        ]

        # Mock empty recent actors
        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [
            mock_combined_result,
            mock_actors_result,
        ]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_logs"] == 0
        assert data["logs_today"] == 0
        assert data["by_action"] == {}
        assert data["by_resource_type"] == {}
        assert data["by_status"] == {}
        assert data["recent_actors"] == []

    def test_get_audit_stats_multiple_actions_and_statuses(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test stats with multiple action types and statuses."""
        # Build combined result with multiple actions and statuses - uses tuples for index access
        rows = [
            ("total", "all", 500),
            ("today", "all", 50),
            # Multiple actions
            ("action", "camera_created", 100),
            ("action", "event_reviewed", 200),
            ("action", "settings_changed", 50),
            # Multiple resource types
            ("resource_type", "camera", 150),
            ("resource_type", "event", 200),
            ("resource_type", "settings", 50),
            # Multiple statuses
            ("status", "success", 450),
            ("status", "failure", 50),
        ]

        mock_combined_result = MagicMock()
        mock_combined_result.fetchall.return_value = rows

        # Mock multiple recent actors
        actors = []
        for actor_name in ["admin", "system", "user1"]:
            actor_row = MagicMock()
            actor_row.actor = actor_name
            actors.append(actor_row)

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self, _actors=actors: iter(_actors)

        mock_db_session.execute.side_effect = [
            mock_combined_result,
            mock_actors_result,
        ]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_logs"] == 500
        assert data["logs_today"] == 50
        assert data["by_action"] == {
            "camera_created": 100,
            "event_reviewed": 200,
            "settings_changed": 50,
        }
        assert data["by_resource_type"] == {"camera": 150, "event": 200, "settings": 50}
        assert data["by_status"] == {"success": 450, "failure": 50}
        assert data["recent_actors"] == ["admin", "system", "user1"]


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
