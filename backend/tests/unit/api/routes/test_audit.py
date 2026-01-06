"""Unit tests for audit API routes.

Tests cover:
- GET  /api/audit/stats - Get audit statistics with optimized single aggregation query

TDD Tests for NEM-1533: Optimize audit stats endpoint with single aggregation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.audit import router
from backend.core.database import get_db

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


# =============================================================================
# Audit Stats Endpoint Tests
# =============================================================================


class TestGetAuditStatsOptimized:
    """Tests for GET /api/audit/stats endpoint with optimized single aggregation query.

    The optimized endpoint should:
    1. Execute minimal database queries (1 aggregation + 1 for actors = 2 total)
    2. Use PostgreSQL aggregate functions (jsonb_object_agg)
    3. Return the same response structure as before
    4. Be backwards compatible with existing API consumers
    """

    def test_audit_stats_returns_expected_structure(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that audit stats returns all expected fields."""
        # Mock the aggregated result from the single query
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 100
        mock_row.logs_today = 10
        mock_row.by_action = '{"camera_created": 30, "event_reviewed": 25, "settings_changed": 20}'
        mock_row.by_resource_type = '{"camera": 40, "event": 35, "settings": 25}'
        mock_row.by_status = '{"success": 85, "failure": 15}'
        mock_agg_result.one_or_none.return_value = mock_row

        # Mock the recent actors query
        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter(
            [
                MagicMock(actor="admin"),
                MagicMock(actor="system"),
            ]
        )

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        assert "total_logs" in data
        assert "logs_today" in data
        assert "by_action" in data
        assert "by_resource_type" in data
        assert "by_status" in data
        assert "recent_actors" in data

        # Verify data types
        assert isinstance(data["total_logs"], int)
        assert isinstance(data["logs_today"], int)
        assert isinstance(data["by_action"], dict)
        assert isinstance(data["by_resource_type"], dict)
        assert isinstance(data["by_status"], dict)
        assert isinstance(data["recent_actors"], list)

    def test_audit_stats_two_query_execution(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that the endpoint uses only 2 database queries.

        Previously this endpoint made 6 separate queries:
        1. Total count
        2. Today count
        3. By action
        4. By resource type
        5. By status
        6. Recent actors

        After optimization, it should make only 2 queries:
        1. Single aggregation query for all counts and breakdowns
        2. Recent actors query (needs separate ordering)
        """
        # Mock the aggregated result
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 50
        mock_row.logs_today = 5
        mock_row.by_action = '{"camera_created": 25}'
        mock_row.by_resource_type = '{"camera": 50}'
        mock_row.by_status = '{"success": 45, "failure": 5}'
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        # Verify only 2 queries were executed (aggregation + actors)
        assert mock_db_session.execute.call_count == 2

    def test_audit_stats_empty_database(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test audit stats with no audit logs in database."""
        # Mock empty result
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 0
        mock_row.logs_today = 0
        mock_row.by_action = "{}"
        mock_row.by_resource_type = "{}"
        mock_row.by_status = "{}"
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_logs"] == 0
        assert data["logs_today"] == 0
        assert data["by_action"] == {}
        assert data["by_resource_type"] == {}
        assert data["by_status"] == {}
        assert data["recent_actors"] == []

    def test_audit_stats_values_correctly_aggregated(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that aggregated values are correctly parsed and returned."""
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 150
        mock_row.logs_today = 25
        mock_row.by_action = '{"camera_created": 50, "event_reviewed": 40, "settings_changed": 30, "rule_updated": 30}'
        mock_row.by_resource_type = '{"camera": 60, "event": 50, "settings": 25, "rule": 15}'
        mock_row.by_status = '{"success": 140, "failure": 10}'
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter(
            [
                MagicMock(actor="admin"),
                MagicMock(actor="system"),
                MagicMock(actor="api_user"),
            ]
        )

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify counts
        assert data["total_logs"] == 150
        assert data["logs_today"] == 25

        # Verify by_action breakdown
        assert data["by_action"]["camera_created"] == 50
        assert data["by_action"]["event_reviewed"] == 40
        assert data["by_action"]["settings_changed"] == 30
        assert data["by_action"]["rule_updated"] == 30

        # Verify by_resource_type breakdown
        assert data["by_resource_type"]["camera"] == 60
        assert data["by_resource_type"]["event"] == 50
        assert data["by_resource_type"]["settings"] == 25
        assert data["by_resource_type"]["rule"] == 15

        # Verify by_status breakdown
        assert data["by_status"]["success"] == 140
        assert data["by_status"]["failure"] == 10

        # Verify recent actors
        assert data["recent_actors"] == ["admin", "system", "api_user"]

    def test_audit_stats_handles_null_aggregation_result(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that endpoint handles NULL aggregation results gracefully."""
        # Simulate case where aggregation returns NULL (e.g., empty table)
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = None
        mock_row.logs_today = None
        mock_row.by_action = None
        mock_row.by_resource_type = None
        mock_row.by_status = None
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        # Should return 0/empty for null values
        assert data["total_logs"] == 0
        assert data["logs_today"] == 0
        assert data["by_action"] == {}
        assert data["by_resource_type"] == {}
        assert data["by_status"] == {}

    def test_audit_stats_handles_no_row_returned(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that endpoint handles case where no row is returned."""
        # Simulate case where query returns no row
        mock_agg_result = MagicMock()
        mock_agg_result.one_or_none.return_value = None

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        # Should return 0/empty for all values
        assert data["total_logs"] == 0
        assert data["logs_today"] == 0
        assert data["by_action"] == {}
        assert data["by_resource_type"] == {}
        assert data["by_status"] == {}
        assert data["recent_actors"] == []

    def test_audit_stats_backwards_compatible_response(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that response matches AuditLogStats schema for backwards compatibility."""
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 100
        mock_row.logs_today = 10
        mock_row.by_action = '{"camera_created": 30}'
        mock_row.by_resource_type = '{"camera": 40}'
        mock_row.by_status = '{"success": 85, "failure": 15}'
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([MagicMock(actor="admin")])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate against expected schema structure
        from backend.api.schemas.audit import AuditLogStats

        # This should not raise ValidationError if schema is compatible
        validated = AuditLogStats(**data)
        assert validated.total_logs == 100
        assert validated.logs_today == 10
        assert validated.by_action == {"camera_created": 30}
        assert validated.by_resource_type == {"camera": 40}
        assert validated.by_status == {"success": 85, "failure": 15}
        assert validated.recent_actors == ["admin"]

    def test_audit_stats_handles_empty_string_json(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that endpoint handles empty JSON string results."""
        mock_agg_result = MagicMock()
        mock_row = MagicMock()
        mock_row.total_logs = 0
        mock_row.logs_today = 0
        mock_row.by_action = ""
        mock_row.by_resource_type = ""
        mock_row.by_status = ""
        mock_agg_result.one_or_none.return_value = mock_row

        mock_actors_result = MagicMock()
        mock_actors_result.__iter__ = lambda _self: iter([])

        mock_db_session.execute.side_effect = [mock_agg_result, mock_actors_result]

        response = client.get("/api/audit/stats")

        assert response.status_code == 200
        data = response.json()
        # Should return empty dicts for empty strings
        assert data["by_action"] == {}
        assert data["by_resource_type"] == {}
        assert data["by_status"] == {}
