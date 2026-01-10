"""Unit tests for alerts API routes.

Tests cover:
- GET    /api/alerts/rules              - List all rules
- POST   /api/alerts/rules              - Create rule
- GET    /api/alerts/rules/{rule_id}    - Get rule
- PUT    /api/alerts/rules/{rule_id}    - Update rule
- DELETE /api/alerts/rules/{rule_id}    - Delete rule
- POST   /api/alerts/rules/{rule_id}/test - Test rule against historical events
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.alerts import _apply_rule_updates, _rule_to_response, router
from backend.api.schemas.alerts import (
    AlertRuleConditions,
    AlertRuleSchedule,
    AlertRuleUpdate,
    AlertSeverity,
)
from backend.core.database import get_db
from backend.models import AlertSeverity as ModelAlertSeverity
from backend.models.alert import AlertRule

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
def sample_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    return AlertRule(
        id=str(uuid.uuid4()),
        name="High Risk Detection",
        description="Alerts when risk score exceeds threshold",
        enabled=True,
        severity=ModelAlertSeverity.HIGH,
        risk_threshold=70,
        object_types=["person"],
        camera_ids=["cam-1"],
        zone_ids=[],
        min_confidence=0.8,
        schedule=None,
        conditions=None,
        dedup_key_template="default:{camera_id}",  # Required field
        cooldown_seconds=300,
        channels=["email"],
        created_at=datetime(2025, 12, 23, 10, 0, 0),
        updated_at=datetime(2025, 12, 23, 10, 0, 0),
    )


# =============================================================================
# List Rules Tests
# =============================================================================


class TestListRules:
    """Tests for GET /api/alerts/rules endpoint."""

    def test_list_rules_empty(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test listing rules when none exist."""
        # Mock count result
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        # Mock empty list result
        mock_list = MagicMock()
        mock_list.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_count, mock_list]

        response = client.get("/api/alerts/rules")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["limit"] == 50
        assert data["pagination"]["offset"] == 0

    def test_list_rules_with_data(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test listing rules with existing data."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 1

        mock_list = MagicMock()
        mock_list.scalars.return_value.all.return_value = [sample_rule]

        mock_db_session.execute.side_effect = [mock_count, mock_list]

        response = client.get("/api/alerts/rules")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["name"] == sample_rule.name

    def test_list_rules_filter_by_enabled(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test filtering rules by enabled status."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 1

        mock_list = MagicMock()
        mock_list.scalars.return_value.all.return_value = [sample_rule]

        mock_db_session.execute.side_effect = [mock_count, mock_list]

        response = client.get("/api/alerts/rules?enabled=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_list_rules_filter_by_severity(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test filtering rules by severity."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 1

        mock_list = MagicMock()
        mock_list.scalars.return_value.all.return_value = [sample_rule]

        mock_db_session.execute.side_effect = [mock_count, mock_list]

        response = client.get("/api/alerts/rules?severity=high")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_list_rules_pagination(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test pagination parameters."""
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0

        mock_list = MagicMock()
        mock_list.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_count, mock_list]

        response = client.get("/api/alerts/rules?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 5


# =============================================================================
# Create Rule Tests
# =============================================================================


class TestCreateRule:
    """Tests for POST /api/alerts/rules endpoint."""

    def test_create_rule_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test successful rule creation."""

        async def mock_refresh(rule):
            rule.id = str(uuid.uuid4())
            rule.created_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.updated_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.dedup_key_template = rule.dedup_key_template or "default"

        mock_db_session.refresh = mock_refresh

        rule_data = {
            "name": "Test Rule",
            "severity": "high",
            "risk_threshold": 70,
            "enabled": True,
        }

        response = client.post("/api/alerts/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Rule"
        assert data["severity"] == "high"
        assert data["risk_threshold"] == 70
        assert data["enabled"] is True

    def test_create_rule_with_schedule(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating rule with schedule."""

        async def mock_refresh(rule):
            rule.id = str(uuid.uuid4())
            rule.created_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.updated_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.dedup_key_template = rule.dedup_key_template or "default"

        mock_db_session.refresh = mock_refresh

        rule_data = {
            "name": "Scheduled Rule",
            "severity": "medium",
            "risk_threshold": 50,
            "schedule": {
                "days_of_week": [1, 2, 3, 4, 5],
                "start_hour": 9,
                "end_hour": 17,
            },
        }

        response = client.post("/api/alerts/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["schedule"] is not None

    def test_create_rule_with_conditions(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating rule with conditions."""

        async def mock_refresh(rule):
            rule.id = str(uuid.uuid4())
            rule.created_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.updated_at = datetime(2025, 12, 23, 10, 0, 0)
            rule.dedup_key_template = rule.dedup_key_template or "default"

        mock_db_session.refresh = mock_refresh

        rule_data = {
            "name": "Conditional Rule",
            "severity": "critical",
            "risk_threshold": 90,
            "conditions": {
                "logic": "and",
                "conditions": [
                    {"field": "risk_score", "operator": ">=", "value": 80},
                ],
            },
        }

        response = client.post("/api/alerts/rules", json=rule_data)

        assert response.status_code == 201

    def test_create_rule_missing_name(self, client: TestClient) -> None:
        """Test creating rule without name fails."""
        rule_data = {
            "severity": "high",
            "risk_threshold": 70,
        }

        response = client.post("/api/alerts/rules", json=rule_data)

        assert response.status_code == 422

    def test_create_rule_invalid_severity(self, client: TestClient) -> None:
        """Test creating rule with invalid severity fails."""
        rule_data = {
            "name": "Test Rule",
            "severity": "invalid",
            "risk_threshold": 70,
        }

        response = client.post("/api/alerts/rules", json=rule_data)

        assert response.status_code == 422


# =============================================================================
# Get Rule Tests
# =============================================================================


class TestGetRule:
    """Tests for GET /api/alerts/rules/{rule_id} endpoint."""

    def test_get_rule_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test getting a rule by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/alerts/rules/{sample_rule.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_rule.id
        assert data["name"] == sample_rule.name

    def test_get_rule_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting non-existent rule returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/alerts/rules/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


# =============================================================================
# Update Rule Tests
# =============================================================================


class TestUpdateRule:
    """Tests for PUT /api/alerts/rules/{rule_id} endpoint."""

    def test_update_rule_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test updating a rule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            f"/api/alerts/rules/{sample_rule.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_rule_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test updating non-existent rule returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/alerts/rules/{fake_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 404

    def test_update_rule_severity(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test updating rule severity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            f"/api/alerts/rules/{sample_rule.id}",
            json={"severity": "critical"},
        )

        assert response.status_code == 200

    def test_update_rule_schedule(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test updating rule schedule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            f"/api/alerts/rules/{sample_rule.id}",
            json={
                "schedule": {
                    "days_of_week": [0, 6],
                    "start_hour": 18,
                    "end_hour": 6,
                }
            },
        )

        assert response.status_code == 200


# =============================================================================
# Delete Rule Tests
# =============================================================================


class TestDeleteRule:
    """Tests for DELETE /api/alerts/rules/{rule_id} endpoint."""

    def test_delete_rule_success(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test deleting a rule."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_db_session.execute.return_value = mock_result

        response = client.delete(f"/api/alerts/rules/{sample_rule.id}")

        assert response.status_code == 204
        mock_db_session.delete.assert_called_once_with(sample_rule)

    def test_delete_rule_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test deleting non-existent rule returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/alerts/rules/{fake_id}")

        assert response.status_code == 404


# =============================================================================
# Test Rule Tests
# =============================================================================


class TestTestRule:
    """Tests for POST /api/alerts/rules/{rule_id}/test endpoint."""

    def test_test_rule_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test testing non-existent rule returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/api/alerts/rules/{fake_id}/test",
            json={"limit": 10},
        )

        assert response.status_code == 404

    def test_test_rule_no_events(
        self, client: TestClient, mock_db_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        """Test testing rule with no events."""
        # First call returns the rule
        mock_rule_result = MagicMock()
        mock_rule_result.scalar_one_or_none.return_value = sample_rule

        # Second call returns empty events
        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_rule_result, mock_events_result]

        response = client.post(
            f"/api/alerts/rules/{sample_rule.id}/test",
            json={"limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["events_tested"] == 0
        assert data["events_matched"] == 0
        assert data["match_rate"] == 0.0


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestRuleToResponse:
    """Tests for _rule_to_response helper function."""

    def test_rule_to_response_with_enum_severity(self, sample_rule: AlertRule) -> None:
        """Test conversion with enum severity."""
        result = _rule_to_response(sample_rule)

        assert result["id"] == sample_rule.id
        assert result["name"] == sample_rule.name
        assert result["severity"] == "high"

    def test_rule_to_response_with_string_severity(self) -> None:
        """Test conversion with string severity."""
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Test Rule",
            severity="low",  # String instead of enum
            enabled=True,
            dedup_key_template="default",
            created_at=datetime(2025, 12, 23, 10, 0, 0),
            updated_at=datetime(2025, 12, 23, 10, 0, 0),
        )

        result = _rule_to_response(rule)

        assert result["severity"] == "low"

    def test_rule_to_response_includes_all_fields(self, sample_rule: AlertRule) -> None:
        """Test that all required fields are included."""
        result = _rule_to_response(sample_rule)

        required_fields = [
            "id",
            "name",
            "description",
            "enabled",
            "severity",
            "risk_threshold",
            "object_types",
            "camera_ids",
            "zone_ids",
            "min_confidence",
            "schedule",
            "conditions",
            "dedup_key_template",
            "cooldown_seconds",
            "channels",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in result


class TestApplyRuleUpdates:
    """Tests for _apply_rule_updates helper function."""

    def test_apply_simple_fields(self, sample_rule: AlertRule) -> None:
        """Test updating simple fields."""
        update_data = AlertRuleUpdate(name="New Name", enabled=False)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.name == "New Name"
        assert sample_rule.enabled is False

    def test_apply_severity_update(self, sample_rule: AlertRule) -> None:
        """Test updating severity field."""
        update_data = AlertRuleUpdate(severity=AlertSeverity.CRITICAL)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.severity == ModelAlertSeverity.CRITICAL

    def test_apply_schedule_update(self, sample_rule: AlertRule) -> None:
        """Test updating schedule field."""
        schedule = AlertRuleSchedule(days_of_week=[1, 2, 3], start_hour=9, end_hour=17)
        update_data = AlertRuleUpdate(schedule=schedule)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.schedule is not None

    def test_apply_null_schedule_update(self, sample_rule: AlertRule) -> None:
        """Test clearing schedule field."""
        sample_rule.schedule = {"days_of_week": [0, 6]}
        update_data = AlertRuleUpdate(schedule=None)
        update_dict = {"schedule": None}

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.schedule is None

    def test_apply_conditions_update(self, sample_rule: AlertRule) -> None:
        """Test updating conditions field."""
        conditions = AlertRuleConditions(
            logic="and",
            conditions=[{"field": "risk_score", "operator": ">=", "value": 80}],
        )
        update_data = AlertRuleUpdate(conditions=conditions)
        update_dict = update_data.model_dump(exclude_unset=True)

        _apply_rule_updates(sample_rule, update_data, update_dict)

        assert sample_rule.conditions is not None
